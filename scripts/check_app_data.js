// Consistency checks for the app bundle (brief §5.4 / Phase 5 gate).
// Usage: node scripts/check_app_data.js
global.window = {};
const fs = require("fs");
eval(fs.readFileSync(__dirname + "/../app/data/app-data.js", "utf8"));
const D = window.APP_DATA;

// Check dimensions and IDs against generated centroids, so omitting a zone
// cannot silently pass just because the remaining probabilities sum to one.
const centroidRows = fs.readFileSync(__dirname + "/../results/processed/approximate_spatial_zones.csv", "utf8")
  .trim().split(/\r?\n/).slice(1).map(line => line.split(","));
let zonesOk = Number.isInteger(D.meta.zonesPerRoad) && D.meta.zonesPerRoad > 0;
for (const c of ["EDSA", "C5"]) {
  const zones = D.corridors[c].zones;
  const expectedIds = centroidRows.filter(row => row[0] === c).map(row => row[1]).sort();
  zonesOk = zonesOk && zones.length === D.meta.zonesPerRoad
    && JSON.stringify(zones.map(z => z.id).sort()) === JSON.stringify(expectedIds)
    && D.zoneGivenHour[c].length === 24
    && D.zoneGivenHour[c].every(row => row.length === zones.length
      && row.every(p => Number.isFinite(p) && p >= 0 && p <= 1));
}
console.log("zone dimensions and generated IDs match:", zonesOk);

const eventLines = fs.readFileSync(__dirname + "/../results/tables/event_scenario_summary.csv", "utf8")
  .trim().split(/\r?\n/);
const eventHeaders = eventLines[0].split(",");
const eventRows = eventLines.slice(1).map(line => {
  const values = line.split(",");
  return Object.fromEntries(eventHeaders.map((key, i) => [key, values[i]]));
});
const eventRatesOk = eventRows.length === 24 && eventRows.every(row => {
  const elasticity = Number(row.elasticity).toFixed(1);
  const rate = D.ratePer100k[row.corridor]?.[elasticity]?.[row.scenario];
  return Number(row.runs) === D.meta.eventRunsPerScenario
    && Number.isFinite(rate) && Math.abs(rate - Number(row.mean_rate_per_100k)) < 1e-10;
});
console.log("event runs and all assumption rates match generated results:", eventRatesOk);

let maxHourDiff = 0, maxZoneDiff = 0;
for (const c of ["EDSA", "C5"]) {
  for (const e of D.elasticities) {
    for (const s of D.scenarios) {
      const m = D.annual[c][e.toFixed(1)][s.key].mean;
      const hours = D.hourShare[c].map(x => m * x);
      const sum = hours.reduce((a, b) => a + b, 0);
      maxHourDiff = Math.max(maxHourDiff, Math.abs(sum - m));
      for (let h = 0; h < 24; h++) {
        const zs = D.zoneGivenHour[c][h].map(p => hours[h] * p);
        const zsum = zs.reduce((a, b) => a + b, 0);
        maxZoneDiff = Math.max(maxZoneDiff, Math.abs(zsum - hours[h]));
      }
    }
  }
}
console.log("max |hours sum - mean| =", maxHourDiff, "(limit 1)");
console.log("max |zones sum - hour| =", maxZoneDiff, "(limit 0.01)");

// Reconciliation targets: Appendix B (Step 6) at elasticity 1.0
const targets = {
  EDSA_baseline: [3376, 2559, 4427],
  EDSA_plus_10: [3778, 2805, 4965],
  EDSA_plus_30: [4411, 3262, 5761],
  C5_baseline: [1334, 836, 2018],
  C5_plus_30: [1766, 1091, 2699],
};
let ok = true;
for (const [k, v] of Object.entries(targets)) {
  const idx = k.indexOf("_");
  const c = k.slice(0, idx), s = k.slice(idx + 1);
  const a = D.annual[c]["1.0"][s];
  const match = [a.mean, a.p05, a.p95].map(Math.round)
    .every((x, i) => Math.abs(x - v[i]) <= 1);
  ok = ok && match;
  console.log(k, [a.mean, a.p05, a.p95].map(Math.round).join(" / "),
              match ? "MATCH" : "MISMATCH");
}

const hs = ["EDSA", "C5"].map(c => D.hourShare[c].reduce((a, b) => a + b, 0));
console.log("hourShare sums:", hs.map(x => x.toFixed(9)).join(", "));
const zg = ["EDSA", "C5"].every(c =>
  D.zoneGivenHour[c].every(r => Math.abs(r.reduce((a, b) => a + b, 0) - 1) < 1e-6));
console.log("zoneGivenHour rows sum to 1:", zg);
const n = Object.values(D.annual).reduce(
  (t, x) => t + Object.values(x).reduce((m, y) => m + Object.keys(y).length, 0), 0);
console.log("annual entries:", n, "(expect 24)");

const pass = maxHourDiff <= 1 && maxZoneDiff <= 0.01 && ok && zg && n === 24
  && zonesOk && eventRatesOk && hs.every(x => Math.abs(x - 1) < 1e-6);
console.log(pass ? "ALL CONSISTENCY CHECKS PASS" : "CHECKS FAILED");
process.exit(pass ? 0 : 1);
