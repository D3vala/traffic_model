// Consistency checks for the app bundle (brief §5.4 / Phase 5 gate).
// Usage: node scripts/check_app_data.js
global.window = {};
const fs = require("fs");
eval(fs.readFileSync(__dirname + "/../app/data/app-data.js", "utf8"));
const D = window.APP_DATA;

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
  && hs.every(x => Math.abs(x - 1) < 1e-6);
console.log(pass ? "ALL CONSISTENCY CHECKS PASS" : "CHECKS FAILED");
process.exit(pass ? 0 : 1);
