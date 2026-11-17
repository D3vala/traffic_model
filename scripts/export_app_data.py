"""
export_app_data.py — build the web app's data bundle from the notebook's outputs.

Reads (all produced by MMDA_Traffic_Simulation.ipynb, see brief §5.1):
  results/tables/simulation_results.csv           headline means/percentiles (trend == "frozen")
  results/processed/model_params.json             hourShare, alpha, window, rate_per, window_rate
  results/processed/approximate_spatial_zones.csv zone centroids
  results/tables/event_zone_hour_summary.csv      Step 8 joint zone x hour profile
  results/tables/event_scenario_summary.csv       Step 8 scenario means + rates (all assumptions)
  results/tables/event_vs_count_comparison.csv    Step 6 vs Step 8 agreement
  results/processed/exposure_focal.csv            2025 AADT per corridor
  results/processed/incident_monthly_panel.csv    window crash totals per corridor
  results/logs/validation_log.txt                 "N of M checks passed"
  results/logs/simulation_log.txt                 run date and run count

Writes:
  app/data/app-data.js    window.APP_DATA = {...};   (loaded by <script>, works on file://)
  app/data/app-data.json  same content, for reference

Consistency rules enforced (brief §5.4): hourShare rows sum to 1, zoneGivenHour rows sum to 1,
24 annual entries, p05 < mean < p95 everywhere, AADT matches the notebook's stated 2025 values.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT_DIR = ROOT / "app" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CORRIDORS = ["EDSA", "C5"]
ELASTICITIES = [0.8, 1.0, 1.2]
DEFAULT_ELASTICITY = 1.0
SCENARIOS = [  # (key, label, volume_change) — keys are the CSV's scenario column
    ("baseline", "Today", 0.0),
    ("plus_10", "+10%", 0.10),
    ("plus_20", "+20%", 0.20),
    ("plus_30", "+30%", 0.30),
]
DAYS_2025 = 365  # 2025 is not a leap year; cfg.DAYS_PER_YEAR = 365 in Step 1

# Sanity targets stated in the notebook / brief Appendix C.
STATED_AADT_2025 = {"EDSA": 421728, "C5": 225885}
STATED_WINDOW_CRASHES = {"EDSA": 5429, "C5": 1680}

# Prior Step 6 reference (sanity only; CSVs are authoritative). Tolerance ±1.
# Tuple second values record the original Step 8 run, not the regenerated run.
APPENDIX_B = {
    ("EDSA", "baseline"): (3376, 3418),
    ("EDSA", "plus_10"): (3778, 3763),
    ("EDSA", "plus_20"): (4061, 4081),
    ("EDSA", "plus_30"): (4411, 4402),
    ("C5", "baseline"): (1334, 1338),
    ("C5", "plus_10"): (1470, 1471),
    ("C5", "plus_20"): (1633, 1660),
    ("C5", "plus_30"): (1766, 1768),
}


def log(msg=""):
    print(msg)


def load_notebook_settings():
    nb = json.loads((ROOT / "MMDA_Traffic_Simulation.ipynb").read_text(encoding="utf-8"))
    code = "\n".join("".join(cell["source"]) for cell in nb["cells"]
                     if cell["cell_type"] == "code")
    settings = {}
    for name in ("ZONES_PER_ROAD", "EVENT_RUNS"):
        match = re.search(rf"^{name}\s*=\s*(\d+)\s*$", code, re.MULTILINE)
        assert match, f"could not read {name} from the notebook"
        settings[name] = int(match.group(1))
        assert settings[name] > 0, f"{name} must be positive"
    return settings


# ---------------------------------------------------------------------------
# Headline annual results (Step 6, frozen trend only)
# ---------------------------------------------------------------------------

def load_annual():
    sim = pd.read_csv(RESULTS / "tables" / "simulation_results.csv")
    sim = sim[sim["trend"] == "frozen"].copy()
    expected_rows = len(CORRIDORS) * len(SCENARIOS) * len(ELASTICITIES)
    assert len(sim) == expected_rows, (
        f"frozen-trend rows: expected {expected_rows}, found {len(sim)}. "
        'Missing trend == "frozen" filter, or the CSV is incomplete.'
    )

    annual = {c: {} for c in CORRIDORS}
    for c in CORRIDORS:
        for e in ELASTICITIES:
            entry = {}
            for key, _, change in SCENARIOS:
                rows = sim[(sim["corridor"] == c)
                           & np.isclose(sim["elasticity"], e)
                           & (sim["scenario"] == key)]
                assert len(rows) == 1, f"expected 1 row for {c}/{e}/{key}, found {len(rows)}"
                r = rows.iloc[0]
                assert abs(float(r["volume_change"]) - change) < 1e-9, (
                    f"volume_change mismatch for {c}/{key}: {r['volume_change']} vs {change}"
                )
                entry[key] = {
                    "mean": float(r["mean"]),
                    "median": float(r["median"]),
                    "p05": float(r["p05"]),
                    "p95": float(r["p95"]),
                    "sd": float(r["sd"]),
                }
                assert entry[key]["p05"] < entry[key]["mean"] < entry[key]["p95"], (
                    f"percentile order violated for {c}/{e}/{key}"
                )
            annual[c][str(e)] = entry
    n_entries = sum(len(entry) for by_e in annual.values() for entry in by_e.values())
    assert n_entries == 2 * 3 * 4, f"annual must hold 2 x 3 x 4 entries, found {n_entries}"
    log(f"  annual              {n_entries} entries (2 corridors x 3 assumptions x 4 scenarios)")
    return annual


# ---------------------------------------------------------------------------
# Model parameters: hour share, alpha, window
# ---------------------------------------------------------------------------

def load_model_params():
    params = json.loads((RESULTS / "processed" / "model_params.json").read_text())
    hour_share = {}
    for c in CORRIDORS:
        s = [float(x) for x in params["hourly_share"][c]]
        assert len(s) == 24, f"{c} hourShare must have 24 values, found {len(s)}"
        assert abs(sum(s) - 1.0) <= 1e-6, f"{c} hourShare sums to {sum(s)}, expected 1"
        hour_share[c] = s

    # Peak statements used by the notebook (sanity, matches its printed log).
    for c, want_peak, want_top4 in (("EDSA", 7, 28.6), ("C5", 15, 35.1)):
        s = np.array(hour_share[c])
        peak = int(s.argmax())
        top4 = round(float(np.sort(s)[-4:].sum()) * 100, 1)
        assert peak == want_peak, f"{c} peak hour {peak}, notebook says {want_peak}"
        assert abs(top4 - want_top4) < 0.05, f"{c} top-4 share {top4}%, notebook says {want_top4}%"
        log(f"  hourShare {c:<5}     peak {peak:02d}:00, busiest 4 hours {top4}% (matches notebook)")

    assert params["estimation_window"] == ["2018-09", "2020-02"]
    assert params["n_months"] == 18
    assert params["rate_per"] == 100_000
    return params, hour_share


# ---------------------------------------------------------------------------
# Zones and the Step 8 zone-given-hour profile
# ---------------------------------------------------------------------------

def load_zones(settings):
    z = pd.read_csv(RESULTS / "processed" / "approximate_spatial_zones.csv")
    count = settings["ZONES_PER_ROAD"]
    assert len(z) == len(CORRIDORS) * count, f"expected {len(CORRIDORS) * count} zones, found {len(z)}"
    zones = {}
    for c in CORRIDORS:
        rows = z[z["road"] == c].sort_values("zone").reset_index(drop=True)
        assert len(rows) == count, f"{c}: expected {count} zones, found {len(rows)}"
        expected_ids = [f"{c}_ZONE_{i:02d}" for i in range(1, count + 1)]
        assert rows["zone"].tolist() == expected_ids, f"{c}: zone IDs do not match the notebook"
        zones[c] = [
            {
                "n": i + 1,
                "id": str(r["zone"]),
                "lat": float(r["latitude"]),
                "lon": float(r["longitude"]),
                "historicalReports": int(r["historical_reports"]),
            }
            for i, r in rows.iterrows()
        ]
    # Equal-count construction: historical zone counts differ by at most one.
    for c in CORRIDORS:
        counts = {z_["historicalReports"] for z_ in zones[c]}
        assert max(counts) - min(counts) <= 1, (
            f"{c} zones are not equal-count splits: {sorted(counts)}"
        )
    log(f"  zones               {count} per corridor, equal-count splits verified")
    return zones


def load_zone_given_hour(zones):
    """P(zone | hour) from the Step 8 joint profile, baseline / elasticity 1.0,
    normalised within each hour. Hours with no rows get equal zone shares."""
    ev = pd.read_csv(RESULTS / "tables" / "event_zone_hour_summary.csv")
    ev = ev[(ev["scenario"] == "baseline") & np.isclose(ev["elasticity"], DEFAULT_ELASTICITY)]
    ev = ev[ev["hour"].astype(str).str.fullmatch(r"\d{2}")].copy()
    ev["hour_i"] = ev["hour"].astype(int)

    out = {}
    for c in CORRIDORS:
        rows_c = ev[ev["corridor"] == c]
        zone_ids = [zone["id"] for zone in zones[c]]
        count = len(zone_ids)
        assert set(rows_c["zone"]) == set(zone_ids), f"{c}: event profile zones do not match centroids"
        table = np.full((24, count), np.nan)
        for h in range(24):
            rh = rows_c[rows_c["hour_i"] == h]
            if rh.empty:
                continue
            vals = []
            for zid in zone_ids:
                m = rh[rh["zone"] == zid]
                vals.append(float(m["mean_annual_events"].sum()) if len(m) else 0.0)
            total = sum(vals)
            table[h] = [v / total for v in vals] if total > 0 else [1.0 / count] * count
        # Fill any hour with no rows at all.
        for h in range(24):
            if np.isnan(table[h]).all():
                table[h] = [1.0 / count] * count
        assert not np.isnan(table).any(), f"{c}: zoneGivenHour has missing hours"
        row_sums = table.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-6), f"{c}: zoneGivenHour rows do not sum to 1"
        out[c] = [[float(x) for x in row] for row in table]
    log("  zoneGivenHour       24 hours x exported zones, every row sums to 1")
    return out


# ---------------------------------------------------------------------------
# Exposure, window totals, rates
# ---------------------------------------------------------------------------

def load_exposure():
    ex = pd.read_csv(RESULTS / "processed" / "exposure_focal.csv")
    aadt = {}
    for c in CORRIDORS:
        rows = ex[(ex["Year"] == 2025) & (ex["road_label"] == c)]
        assert len(rows) == 1, f"expected one 2025 row for {c}, found {len(rows)}"
        val = int(rows.iloc[0]["aadt"])
        assert val == STATED_AADT_2025[c], (
            f"{c} 2025 AADT {val:,} does not match exposure_focal / stated {STATED_AADT_2025[c]:,}"
        )
        aadt[c] = val
    log(f"  aadt2025            EDSA {aadt['EDSA']:,} · C5 {aadt['C5']:,} (matches exposure_focal)")
    return aadt


def load_window_crashes():
    panel = pd.read_csv(RESULTS / "processed" / "incident_monthly_panel.csv")
    inw = panel["in_window"].astype(str).str.lower().eq("true")
    totals = (panel[inw & panel["corridor"].isin(CORRIDORS)]
              .groupby("corridor")["crashes"].sum().to_dict())
    for c in CORRIDORS:
        assert int(totals[c]) == STATED_WINDOW_CRASHES[c], (
            f"{c} window crashes {totals[c]}, notebook states {STATED_WINDOW_CRASHES[c]}"
        )
    log(f"  windowCrashes       EDSA {totals['EDSA']:,} · C5 {totals['C5']:,} (matches validation log)")
    return {c: int(totals[c]) for c in CORRIDORS}


def load_rates(settings):
    """Rates for all assumptions come from the regenerated Step 8 event table."""
    ev = pd.read_csv(RESULTS / "tables" / "event_scenario_summary.csv")
    assert len(ev) == len(CORRIDORS) * len(SCENARIOS) * len(ELASTICITIES), "event_scenario_summary rows unexpected"
    assert (ev["runs"] == settings["EVENT_RUNS"]).all(), "event run counts do not match the notebook"

    out = {}
    for c in CORRIDORS:
        out[c] = {}
        for e in ELASTICITIES:
            entry = {}
            for key, _, _ in SCENARIOS:
                rows = ev[(ev["corridor"] == c) & (ev["scenario"] == key)
                          & np.isclose(ev["elasticity"], e)]
                assert len(rows) == 1, f"expected one event rate for {c}/{e}/{key}"
                entry[key] = float(rows.iloc[0]["mean_rate_per_100k"])
                assert 0.5 < entry[key] < 5.0, f"implausible rate for {c}/{e}/{key}"
            out[c][str(e)] = entry
    log("  ratePer100k         all three assumptions from event_scenario_summary")
    return out


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

def load_meta(settings):
    val_log = (RESULTS / "logs" / "validation_log.txt").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(\d+)\s+of\s+(\d+)\s+checks passed", val_log)
    assert m, "could not parse validation pass count"
    passed, total = int(m.group(1)), int(m.group(2))

    sim_log = (RESULTS / "logs" / "simulation_log.txt").read_text(encoding="utf-8", errors="replace")
    run_date = re.search(r"run\s+(\d{4}-\d{2}-\d{2})", sim_log).group(1)
    runs = int(re.search(r"Monte Carlo runs per scenario:\s*([\d,]+)",
                         sim_log).group(1).replace(",", ""))
    assert runs == 1000, f"expected 1,000 runs per scenario, log says {runs}"

    nb_src = (ROOT / "MMDA_Traffic_Simulation.ipynb").read_text(encoding="utf-8")
    seed = int(re.search(r"RANDOM_SEED\s*=\s*(\d+)", nb_src).group(1))
    baseline_year = int(re.search(r"BASELINE_YEAR\s*=\s*(\d+)", nb_src).group(1))

    cmp_df = pd.read_csv(RESULTS / "tables" / "event_vs_count_comparison.csv")
    raw_max_diff = float(cmp_df["difference_pct"].abs().max())
    # Match the notebook's Step 8.8b gate, rather than the previous run's result.
    assert raw_max_diff < 5.0, f"event vs count disagreement {raw_max_diff}% exceeds the notebook's 5% gate"
    max_diff = round(raw_max_diff, 1)

    params = json.loads((RESULTS / "processed" / "model_params.json").read_text())
    return {
        "source": "MMDA_Traffic_Simulation.ipynb",
        "runDate": run_date,
        "runsPerScenario": runs,
        "eventRunsPerScenario": settings["EVENT_RUNS"],
        "zonesPerRoad": settings["ZONES_PER_ROAD"],
        "seed": seed,
        "baselineYear": baseline_year,
        "estimationWindow": params["estimation_window"],
        "nMonths": int(params["n_months"]),
        "modelFamily": "Negative Binomial",
        "alpha": float(params["alpha"]),
        "ratePer": int(params["rate_per"]),
        "windowRate": {c: float(params["window_rate"][c]) for c in CORRIDORS},
        "validation": {"passed": passed, "total": total},
        "eventVsCountMaxDiffPct": max_diff,
    }


# ---------------------------------------------------------------------------
# Reconciliation vs Appendix B (sanity only; CSV is authoritative)
# ---------------------------------------------------------------------------

def reconcile(annual):
    events = pd.read_csv(RESULTS / "tables" / "event_scenario_summary.csv")
    events = events[np.isclose(events["elasticity"], DEFAULT_ELASTICITY)]
    log("")
    log("  Reconciliation vs Step 6 reference, with regenerated Step 8 counts:")
    log(f"    {'corridor':<9}{'scenario':<11}{'exported':>10}{'Appx B S6':>11}{'current S8':>11}   ok")
    log("    " + "-" * 57)
    ok_all = True
    for (c, key), (b6, _) in APPENDIX_B.items():
        b8 = round(float(events[(events["corridor"] == c) & (events["scenario"] == key)]["mean"].iloc[0]))
        got = round(annual[c]["1.0"][key]["mean"])
        ok = abs(got - b6) <= 1
        ok_all &= ok
        log(f"    {c:<9}{key:<11}{got:>10,}{b6:>11,}{b8:>11,}   {'match' if ok else 'MISMATCH'}")
    assert ok_all, "reconciliation against Appendix B failed (check trend == frozen filter)"
    log("    All reconciled.")


def main():
    log("export_app_data.py — building app data bundle")
    log("")
    settings = load_notebook_settings()
    annual = load_annual()
    params, hour_share = load_model_params()
    zones = load_zones(settings)
    zone_given_hour = load_zone_given_hour(zones)
    aadt = load_exposure()
    window_crashes = load_window_crashes()
    rates = load_rates(settings)
    meta = load_meta(settings)

    bundle = {
        "meta": meta,
        "corridors": {
            c: {"label": c, "aadt2025": aadt[c], "windowCrashes": window_crashes[c],
                "zones": zones[c]}
            for c in CORRIDORS
        },
        "scenarios": [{"key": k, "label": lab, "change": ch} for k, lab, ch in SCENARIOS],
        "elasticities": ELASTICITIES,
        "annual": annual,
        "ratePer100k": rates,
        "hourShare": hour_share,
        "zoneGivenHour": zone_given_hour,
        "annualQuantiles": None,  # stretch S1: not exported by the notebook
    }

    reconcile(annual)

    js = "window.APP_DATA = " + json.dumps(bundle, indent=2, ensure_ascii=False) + ";\n"
    (OUT_DIR / "app-data.js").write_text(js, encoding="utf-8")
    (OUT_DIR / "app-data.json").write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    log("")
    log(f"  validation          {meta['validation']['passed']} of {meta['validation']['total']} checks passed")
    log(f"  run                 {meta['runDate']} · {meta['runsPerScenario']:,} runs/scenario "
        f"· seed {meta['seed']}")
    log(f"  event vs count      max {meta['eventVsCountMaxDiffPct']}%")
    log("")
    log(f"Wrote {OUT_DIR / 'app-data.js'}")
    log(f"Wrote {OUT_DIR / 'app-data.json'}")
    log("All assertions passed.")


if __name__ == "__main__":
    main()



