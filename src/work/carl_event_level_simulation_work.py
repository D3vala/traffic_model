"""
carl_event_level_simulation_work.py — Member 3 Event-Level Spatiotemporal Allocation & Validation

Implements (working copy only — the main notebook and main model are NOT changed):
1. Approximate spatial zones derived via SVD/PCA along the corridor coordinate cloud
   (notebook Step 8.3, unchanged). Six zones per corridor, projected_min/projected_max
   in km, road renamed to corridor.
2. Month-aware zone x hour allocation by shrinkage toward the corridor-wide profile:
       p(z,h | c,m) = ( n[c,m,z,h] + kappa * p0[c,z,h] ) / ( N[c,m] + kappa )
   The corridor-wide p0 is the existing Step 8.4 event_joint_profile.csv.
   Kappa is chosen by leave-one-month-out log-likelihood over
   {10, 25, 50, 100, 250, 500, 1000, 2500, 10000} plus a kappa = infinity
   reference (corridor-wide profile only). The held-out month is removed BEFORE
   p0 is recomputed, so no held-out data leaks into the baseline.
   The exported profile uses the best FINITE kappa. The log states whether that
   kappa sits at the grid edge and whether kappa = infinity beats or ties it.
   If infinity beats/ties, it states plainly that 18 months do not support
   month-specific allocation. Neither method is promoted to the main model.
3. Step 8.5 counts are reproduced exactly, including the fitted coefficient
   covariance draw when model_params.json supplies it, with rng =
   default_rng(RANDOM_SEED + 800). Only the Step 8.6 allocation changes.
4. Validation checks: probability sums, valid dates/hours/corridors, exact
   conservation, Step 8 vs Step 6 gate, sample events restricted to runs 1-2 at
   elasticity 1.0, and month-aware monthly counts equal to the original Step 8.5
   counts in results/tables/event_scenario_summary.csv.

All text output is written with encoding="utf-8".
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration and paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
PROCESSED = RESULTS / "processed"
TABLES = RESULTS / "tables"
LOGS = RESULTS / "logs"

for directory in (PROCESSED, TABLES, LOGS):
    directory.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 20260919
EVENT_RUNS = 1000
SAMPLE_RUNS = 2
ZONES_PER_ROAD = 6
EVENT_ELASTICITIES = [0.8, 1.0, 1.2]
SCENARIOS = {
    "baseline": 0.00,
    "plus_10": 0.10,
    "plus_20": 0.20,
    "plus_30": 0.30,
}
BASELINE_YEAR = 2025
RATE_PER = 100_000

# Extended kappa grid plus the corridor-wide (no month effect) reference.
KAPPA_CANDIDATES = [10, 25, 50, 100, 250, 500, 1000, 2500, 10000]
KAPPA_INF = "inf"
# A cell observed only in the held-out month would make the recomputed p0 zero
# there. Add-one smoothing on the recomputed baseline keeps the LOO likelihood
# finite; it is applied identically to every candidate, including infinity.
P0_LOO_PSEUDOCOUNT = 1.0


def log(msg="", log_buffer=None):
    print(msg)
    if log_buffer is not None:
        log_buffer.append(str(msg))


def as_boolean(series):
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


# ---------------------------------------------------------------------------
# Step 8.3 — Approximate spatial zones and boundaries
# ---------------------------------------------------------------------------
def compute_zone_boundaries(incidents, log_buffer):
    log("=" * 74, log_buffer)
    log("STEP 8.3 — APPROXIMATE SPATIAL ZONES & BOUNDARIES", log_buffer)
    log("=" * 74, log_buffer)

    historical = incidents[
        as_boolean(incidents["in_window"])
        & incidents["incident_class"].eq("CRASH")
        & incidents["corridor"].isin(["EDSA", "C5"])
    ].copy()

    for col in ("hour", "Latitude", "Longitude"):
        historical[col] = pd.to_numeric(historical[col], errors="coerce")

    historical["zone"] = "UNKNOWN_LOCATION"
    historical["hour_label"] = historical["hour"].apply(
        lambda h: f"{int(h):02d}" if pd.notna(h) and 0 <= h <= 23 else "UNKNOWN_TIME"
    )
    historical["projected_km"] = np.nan

    zone_info = []
    for road in ("EDSA", "C5"):
        valid = (
            historical["corridor"].eq(road)
            & as_boolean(historical["geo_valid"])
            & historical["Latitude"].notna()
            & historical["Longitude"].notna()
        )
        road_points = historical.loc[valid, ["Latitude", "Longitude"]].to_numpy(dtype=float)

        if len(road_points) < ZONES_PER_ROAD * 10:
            raise ValueError(f"Not enough valid GPS records for {road}.")

        scaled = road_points * np.array([111.0, 108.0])
        centered = scaled - scaled.mean(axis=0)
        _, _, axes = np.linalg.svd(centered, full_matrices=False)
        projected = centered @ axes[0]
        if axes[0][0] < 0:
            projected *= -1

        historical.loc[valid, "projected_km"] = projected
        ranks = pd.Series(projected, index=historical.index[valid]).rank(method="first")
        zone_numbers = pd.qcut(ranks, q=ZONES_PER_ROAD, labels=False)
        historical.loc[valid, "zone"] = [
            f"{road}_ZONE_{int(n) + 1:02d}" for n in zone_numbers
        ]

        for zone, grp in historical.loc[valid].groupby("zone"):
            zone_info.append({
                "corridor": road,
                "zone": zone,
                "historical_reports": len(grp),
                "latitude": grp["Latitude"].mean(),
                "longitude": grp["Longitude"].mean(),
                "projected_min": grp["projected_km"].min(),
                "projected_max": grp["projected_km"].max(),
            })

    zone_boundaries = pd.DataFrame(zone_info)
    out_path = PROCESSED / "zone_boundaries.csv"
    zone_boundaries.to_csv(out_path, index=False)
    log(f"Saved: {out_path} ({len(zone_boundaries)} zones)", log_buffer)
    log(zone_boundaries.to_string(index=False), log_buffer)
    log("", log_buffer)
    return historical, zone_boundaries


# ---------------------------------------------------------------------------
# Step 8.4 — Monthly profile with leakage-free LOO kappa selection
# ---------------------------------------------------------------------------
def fit_monthly_profile(historical, p0_df, log_buffer):
    log("=" * 74, log_buffer)
    log("STEP 8.4 — MONTH-AWARE SHRINKAGE PROFILE & LOO KAPPA GRID", log_buffer)
    log("=" * 74, log_buffer)

    historical = historical.copy()
    historical["period"] = pd.to_datetime(historical["date"]).dt.to_period("M").astype(str)
    historical["month"] = pd.to_datetime(historical["date"]).dt.month
    periods = sorted(historical["period"].unique())

    log(f"Estimation window: {len(periods)} months ({periods[0]} to {periods[-1]})", log_buffer)
    log("Sparsity: Sep-Feb appear twice in the 18-month window; Mar-Aug only once (2019).", log_buffer)
    log("Month-of-year is therefore confounded with year and trend.", log_buffer)
    log("", log_buffer)
    log("Leave-one-month-out log-likelihood (p0 recomputed WITHOUT the held-out month;", log_buffer)
    log(f"add-one pseudocount {P0_LOO_PSEUDOCOUNT:g} on the recomputed baseline):", log_buffer)

    support = {}
    for c in ("EDSA", "C5"):
        support[c] = pd.MultiIndex.from_frame(
            p0_df[p0_df["corridor"].eq(c)][["zone", "hour_label"]].drop_duplicates()
        )

    candidates = KAPPA_CANDIDATES + [KAPPA_INF]

    def loo_loglik(kappa):
        ll = {"EDSA": 0.0, "C5": 0.0}
        for period in periods:
            train = historical[historical["period"] != period]
            test = historical[historical["period"] == period]
            test_month = int(test["month"].iloc[0])
            for c in ("EDSA", "C5"):
                idx = support[c]
                train_c = train[train["corridor"].eq(c)]
                test_c = test[test["corridor"].eq(c)]

                # Recompute p0 from training months only — no held-out leakage.
                n_all = (
                    train_c.groupby(["zone", "hour_label"]).size()
                    .reindex(idx, fill_value=0).astype(float)
                )
                p0_train = (
                    (n_all + P0_LOO_PSEUDOCOUNT)
                    / (n_all.sum() + P0_LOO_PSEUDOCOUNT * len(idx))
                )

                y_test = (
                    test_c.groupby(["zone", "hour_label"]).size()
                    .reindex(idx, fill_value=0).astype(float)
                )

                if kappa == KAPPA_INF:
                    prob = p0_train
                else:
                    n_cm = (
                        train_c[train_c["month"].eq(test_month)]
                        .groupby(["zone", "hour_label"]).size()
                        .reindex(idx, fill_value=0).astype(float)
                    )
                    prob = (n_cm + kappa * p0_train) / (n_cm.sum() + kappa)

                ll[c] += float((y_test * np.log(prob)).sum())
        return ll

    grid_records = []
    log(f"  {'kappa':<8}{'EDSA LL':>14}{'C5 LL':>14}{'Combined LL':>14}", log_buffer)
    log("  " + "-" * 52, log_buffer)
    for kappa in candidates:
        ll = loo_loglik(kappa)
        combined = ll["EDSA"] + ll["C5"]
        grid_records.append({
            "kappa": kappa,
            "edsa_ll": ll["EDSA"],
            "c5_ll": ll["C5"],
            "combined_ll": combined,
        })
        label = "inf" if kappa == KAPPA_INF else str(kappa)
        log(f"  {label:<8}{ll['EDSA']:>14.3f}{ll['C5']:>14.3f}{combined:>14.3f}", log_buffer)

    grid_df = pd.DataFrame(grid_records)
    finite = grid_df[grid_df["kappa"] != KAPPA_INF]
    best_row = finite.loc[finite["combined_ll"].idxmax()]
    best_kappa = int(best_row["kappa"])
    best_ll = float(best_row["combined_ll"])
    inf_ll = float(grid_df.loc[grid_df["kappa"].eq(KAPPA_INF), "combined_ll"].iloc[0])
    at_edge = best_kappa == max(KAPPA_CANDIDATES)
    inf_beats = inf_ll > best_ll + 1e-9
    inf_ties = abs(inf_ll - best_ll) <= 1e-9

    log("", log_buffer)
    log(f"Best FINITE kappa: {best_kappa} (Combined LL = {best_ll:.3f})", log_buffer)
    log(f"Kappa = infinity reference: Combined LL = {inf_ll:.3f}", log_buffer)
    log(f"Best finite kappa at grid edge ({max(KAPPA_CANDIDATES)}): {'YES' if at_edge else 'NO'}", log_buffer)
    log(f"Kappa = infinity beats best finite: {'YES' if inf_beats else 'NO'}"
        f" (ties: {'YES' if inf_ties else 'NO'})", log_buffer)
    if inf_beats or inf_ties:
        log("", log_buffer)
        log("PLAIN STATEMENT: 18 months of historical data do NOT support month-specific", log_buffer)
        log("allocation. The corridor-wide (kappa = infinity) profile fits the held-out", log_buffer)
        log("months at least as well as any finite kappa. The exported month-aware profile", log_buffer)
        log("is supplied for review only; neither method is promoted to the main model.", log_buffer)
        log("", log_buffer)
        log("SCOPE OF THE KAPPA COMPARISON: the held-out Mar-Aug months have no other-year", log_buffer)
        log("data in the 18-month window (they occur once, in 2019), so no other-year month", log_buffer)
        log("is available to validate against. The kappa comparison therefore rests on", log_buffer)
        log("Sep-Feb only, which each appear in two years. This is NO EVIDENCE FOR A MONTH", log_buffer)
        log("EFFECT, not evidence that one is absent; it does not justify month-specific", log_buffer)
        log("allocation with the data currently available.", log_buffer)
    log("", log_buffer)

    # Export the full smoothed monthly profile at the best FINITE kappa.
    monthly_rows = []
    for c in ("EDSA", "C5"):
        hist_c = historical[historical["corridor"].eq(c)]
        supp = p0_df[p0_df["corridor"].eq(c)].set_index(["zone", "hour_label"])
        p0 = supp["probability"]
        for m in range(1, 13):
            hist_cm = hist_c[hist_c["month"].eq(m)]
            n_cm = (
                hist_cm.groupby(["zone", "hour_label"]).size()
                .reindex(supp.index, fill_value=0)
            )
            n_total = int(n_cm.sum())
            smoothed = (n_cm + best_kappa * p0) / (n_total + best_kappa)
            assert np.isclose(smoothed.sum(), 1.0, atol=1e-12), (
                f"Probabilities do not sum to 1.0 for {c} month {m}"
            )
            for (zone, hour_label), prob_val in smoothed.items():
                monthly_rows.append({
                    "corridor": c,
                    "month": m,
                    "zone": zone,
                    "hour_label": hour_label,
                    "historical_reports": int(n_cm.loc[(zone, hour_label)]),
                    "p0_probability": float(p0.loc[(zone, hour_label)]),
                    "probability": float(prob_val),
                    "kappa": best_kappa,
                    "month_data_weight": n_total / (n_total + best_kappa),
                })

    monthly_profile = pd.DataFrame(monthly_rows)
    out_path = PROCESSED / "monthly_zone_hour_profile.csv"
    monthly_profile.to_csv(out_path, index=False)
    log(f"Saved: {out_path} ({len(monthly_profile)} rows) at best FINITE kappa={best_kappa}", log_buffer)
    log("", log_buffer)

    return monthly_profile, best_kappa, grid_df


# ---------------------------------------------------------------------------
# Step 8.5 — Reproduce monthly counts exactly (covariance draw included)
# ---------------------------------------------------------------------------
def build_step85_covariance(params, coef_names):
    if "covariance_matrix" not in params or "covariance_order" not in params:
        return None
    saved_order = list(params["covariance_order"])
    saved_cov = np.asarray(params["covariance_matrix"], dtype=float)
    if saved_cov.shape != (len(saved_order), len(saved_order)):
        return None
    order_index = [saved_order.index(name) for name in coef_names]
    cov = saved_cov[np.ix_(order_index, order_index)]
    cov = (cov + cov.T) / 2
    eigval, eigvec = np.linalg.eigh(cov)
    cov = (eigvec * np.clip(eigval, 0.0, None)) @ eigvec.T
    return cov


def run_monthly_simulation(params, baseline, design, log_buffer):
    log("=" * 74, log_buffer)
    log("STEP 8.5 — REPRODUCE MONTHLY COUNTS (RNG SEED AND DRAW ORDER PRESERVED)", log_buffer)
    log("=" * 74, log_buffer)

    rng = np.random.default_rng(RANDOM_SEED + 800)
    coef_names = list(params["coefficients"])
    coefs = np.array([params["coefficients"][k] for k in coef_names], dtype=float)
    std_errors = np.array([params["std_errors"][k] for k in coef_names], dtype=float)
    alpha = max(float(params["alpha"]), 0.0)
    covariance = build_step85_covariance(params, coef_names)
    log(f"Coefficient draw: {'full covariance matrix' if covariance is not None else 'independent std errors (fallback)'}", log_buffer)

    monthly_simulations = {}
    summary_rows = []
    for road in ("EDSA", "C5"):
        road_design = design[design["corridor"].eq(road)].sort_values("month").reset_index(drop=True)
        X = road_design[coef_names].to_numpy(dtype=float)
        days = road_design["days"].to_numpy(dtype=float)
        aadt = float(baseline.loc[road, "aadt"])

        for elasticity in EVENT_ELASTICITIES:
            # One parameter draw per (corridor, elasticity), reused across scenarios,
            # exactly as in notebook cell 43 (Step 8.5).
            if covariance is not None:
                coefficient_draws = rng.multivariate_normal(coefs, covariance, size=EVENT_RUNS)
            else:
                coefficient_draws = rng.normal(
                    loc=coefs, scale=std_errors, size=(EVENT_RUNS, len(coefs))
                )
            linear_predictor = coefficient_draws @ X.T
            exposure_offset = np.log(aadt * days / params["rate_per"])
            base_expected = np.exp(np.clip(linear_predictor + exposure_offset, -20, 20))

            for scenario, traffic_change in SCENARIOS.items():
                expected_counts = base_expected * (1 + traffic_change) ** elasticity
                if alpha > 0:
                    latent_rates = rng.gamma(shape=1 / alpha, scale=expected_counts * alpha)
                    monthly_counts = rng.poisson(latent_rates)
                else:
                    monthly_counts = rng.poisson(expected_counts)

                key = (road, scenario, elasticity)
                monthly_simulations[key] = monthly_counts
                annual_totals = monthly_counts.sum(axis=1)
                annual_exposure = aadt * (1 + traffic_change) * days.sum()
                summary_rows.append({
                    "corridor": road,
                    "scenario": scenario,
                    "traffic_change": traffic_change,
                    "elasticity": elasticity,
                    "runs": EVENT_RUNS,
                    "mean": float(annual_totals.mean()),
                    "std": float(annual_totals.std(ddof=1)),
                    "p05": float(np.quantile(annual_totals, 0.05)),
                    "median": float(np.median(annual_totals)),
                    "p95": float(np.quantile(annual_totals, 0.95)),
                    "mean_rate_per_100k": float(
                        annual_totals.mean() / annual_exposure * RATE_PER
                    ),
                })

    event_summary = pd.DataFrame(summary_rows)
    log(f"Generated monthly simulations for {len(monthly_simulations)} keys.", log_buffer)
    log("", log_buffer)
    return monthly_simulations, event_summary, rng


# ---------------------------------------------------------------------------
# Step 8.6 — Month-aware event allocation
# ---------------------------------------------------------------------------
def run_event_allocation(monthly_simulations, monthly_profile, design, rng, log_buffer):
    log("=" * 74, log_buffer)
    log("STEP 8.6 — MONTH-AWARE SPATIOTEMPORAL EVENT ALLOCATION", log_buffer)
    log("=" * 74, log_buffer)

    sample_event_rows = []
    allocation_rows = []
    profile_lookup = {}
    categories_lookup = {}
    for (corridor, month), grp in monthly_profile.groupby(["corridor", "month"]):
        grp_sorted = grp.reset_index(drop=True)
        profile_lookup[(corridor, month)] = grp_sorted["probability"].to_numpy(dtype=float)
        categories_lookup[(corridor, month)] = grp_sorted[["zone", "hour_label"]].to_dict("records")

    total_allocated = 0
    total_simulated = 0
    for key, monthly_counts in monthly_simulations.items():
        road, scenario, elasticity = key
        road_design = design[design["corridor"].eq(road)].sort_values("month").reset_index(drop=True)
        corridor_cats = categories_lookup[(road, 1)]
        allocated_totals = np.zeros(len(corridor_cats), dtype=np.int64)

        for run in range(EVENT_RUNS):
            for month_index, count in enumerate(monthly_counts[run]):
                count = int(count)
                if count == 0:
                    continue
                month = int(road_design.loc[month_index, "month"])
                days_in_month = int(road_design.loc[month_index, "days"])
                probs = profile_lookup[(road, month)]
                cats = categories_lookup[(road, month)]

                allocation = rng.multinomial(count, probs)
                allocated_totals += allocation

                # Notebook condition: detailed records only for runs 1-2 at elasticity 1.0.
                if run >= SAMPLE_RUNS or elasticity != 1.0:
                    continue
                for cat_idx, number in enumerate(allocation):
                    if number == 0:
                        continue
                    cat = cats[cat_idx]
                    random_days = rng.integers(1, days_in_month + 1, size=int(number))
                    random_minutes = rng.integers(0, 60, size=int(number))
                    for day, minute in zip(random_days, random_minutes):
                        sample_event_rows.append({
                            "run": run + 1,
                            "scenario": scenario,
                            "elasticity": elasticity,
                            "corridor": road,
                            "year": BASELINE_YEAR,
                            "month": month,
                            "day": int(day),
                            "hour": cat["hour_label"],
                            "minute": int(minute),
                            "zone": cat["zone"],
                            "event_type": "SIMULATED_REPORTED_CRASH",
                        })

        assert allocated_totals.sum() == monthly_counts.sum(), (
            f"Conservation error for {key}: {allocated_totals.sum()} != {monthly_counts.sum()}"
        )
        total_allocated += int(allocated_totals.sum())
        total_simulated += int(monthly_counts.sum())

        for idx, cat in enumerate(corridor_cats):
            allocation_rows.append({
                "corridor": road,
                "scenario": scenario,
                "elasticity": elasticity,
                "zone": cat["zone"],
                "hour": cat["hour_label"],
                "mean_annual_events": float(allocated_totals[idx] / EVENT_RUNS),
            })

    sample_events = pd.DataFrame(sample_event_rows)
    event_allocation = pd.DataFrame(allocation_rows)
    log(f"Total simulated events across all runs: {total_simulated:,}", log_buffer)
    log(f"Total allocated events across all runs: {total_allocated:,}", log_buffer)
    log("Conservation: EXACT (0 events lost)", log_buffer)
    log(f"Sample event records kept: {len(sample_events):,}", log_buffer)
    log("", log_buffer)
    return sample_events, event_allocation


# ---------------------------------------------------------------------------
# Step 8.8 — Validation
# ---------------------------------------------------------------------------
def verify_and_validate(monthly_profile, event_summary, event_allocation,
                        sample_events, log_buffer):
    log("=" * 74, log_buffer)
    log("STEP 8.8 — VALIDATION CHECKS & STEP 6 CROSS-CHECK", log_buffer)
    log("=" * 74, log_buffer)

    checks = {}
    sums_ok = True
    for (corridor, month), grp in monthly_profile.groupby(["corridor", "month"]):
        if not np.isclose(grp["probability"].sum(), 1.0, atol=1e-12):
            sums_ok = False
    checks["Monthly probabilities sum to 1.0 per corridor/month"] = bool(sums_ok)
    checks["Nonnegative simulated incident counts"] = bool((event_summary["mean"] >= 0).all())
    checks["Simulation intervals ordered (p05 <= median <= p95)"] = bool(
        ((event_summary["p05"] <= event_summary["median"])
         & (event_summary["median"] <= event_summary["p95"])).all()
    )
    checks["Valid corridors (EDSA, C5)"] = bool(sample_events["corridor"].isin(["EDSA", "C5"]).all())
    valid_hours = [f"{h:02d}" for h in range(24)] + ["UNKNOWN_TIME"]
    checks["Valid hours (00-23, UNKNOWN_TIME)"] = bool(sample_events["hour"].isin(valid_hours).all())
    checks["Valid calendar dates in sample events"] = bool(
        pd.to_datetime(sample_events[["year", "month", "day"]], errors="coerce").notna().all()
    )
    checks["Valid days for the month"] = bool(
        (
            sample_events["day"]
            <= pd.to_datetime(
                sample_events[["year", "month"]].assign(day=1)
            ).dt.days_in_month
        ).all()
    )

    all_allocated = True
    for _, row in event_summary.iterrows():
        sel = event_allocation[
            event_allocation["corridor"].eq(row["corridor"])
            & event_allocation["scenario"].eq(row["scenario"])
            & event_allocation["elasticity"].eq(row["elasticity"])
        ]
        if not np.isclose(sel["mean_annual_events"].sum(), row["mean"], atol=1e-8):
            all_allocated = False
    checks["Exact count conservation (no events lost)"] = bool(all_allocated)

    # Required check: sample events only from runs 1-2 at elasticity 1.0.
    sample_ok = (
        len(sample_events) > 0
        and bool(sample_events["run"].isin([1, 2]).all())
        and bool(sample_events["elasticity"].eq(1.0).all())
    )
    checks["Sample events only runs 1-2 at elasticity 1.0"] = bool(sample_ok)

    # Required check: month-aware monthly counts equal the original Step 8.5 counts.
    cols = ["mean", "std", "p05", "median", "p95", "mean_rate_per_100k"]
    keys = ["corridor", "scenario", "elasticity"]
    reference = pd.read_csv(TABLES / "event_scenario_summary.csv")
    comparison = event_summary[keys + cols].merge(
        reference[keys + cols], on=keys, how="outer", suffixes=("_ours", "_step85"), indicator=True
    )
    matched = bool(comparison["_merge"].eq("both").all())
    max_diff = 0.0
    for col in cols:
        if matched:
            max_diff = max(
                max_diff,
                float((comparison[f"{col}_ours"] - comparison[f"{col}_step85"]).abs().max()),
            )
        else:
            max_diff = np.inf
    step85_ok = matched and max_diff <= 1e-8
    checks["Month-aware monthly counts equal original Step 8.5 counts"] = bool(step85_ok)

    # Step 6 gate (unchanged).
    step6 = pd.read_csv(TABLES / "simulation_results.csv")
    s6 = step6[(step6["trend"] == "frozen") & (step6["elasticity"] == 1.0)][
        ["corridor", "scenario", "mean"]
    ].rename(columns={"mean": "step6_mean"})
    s8 = event_summary[event_summary["elasticity"] == 1.0][
        ["corridor", "scenario", "mean"]
    ].rename(columns={"mean": "step8_mean"})
    comp = s6.merge(s8, on=["corridor", "scenario"], how="inner")
    comp["diff_pct"] = (comp["step8_mean"] / comp["step6_mean"] - 1) * 100
    worst_diff = float(comp["diff_pct"].abs().max())
    checks["Step 6 vs Step 8 agreement (< 5.0% discrepancy gate)"] = bool(worst_diff < 5.0)

    log("Validation Summary Table:", log_buffer)
    for name, passed in checks.items():
        log(f"  [{'PASS' if passed else 'FAIL'}] {name}", log_buffer)
    log("", log_buffer)
    log("Step 8.5 agreement: maximum absolute difference across all 24 keys and", log_buffer)
    log(f"  six summary statistics = {max_diff:.10g} (tolerance 1e-8)", log_buffer)
    log("", log_buffer)
    log("Step 6 vs Step 8 Comparison Table (elasticity = 1.0, frozen trend):", log_buffer)
    log(f"  {'corridor':<9}{'scenario':<12}{'Step 6':>10}{'Step 8':>10}{'diff %':>10}", log_buffer)
    log("  " + "-" * 51, log_buffer)
    for _, r in comp.iterrows():
        log(
            f"  {r['corridor']:<9}{r['scenario']:<12}{r['step6_mean']:>10.1f}"
            f"{r['step8_mean']:>10.1f}{r['diff_pct']:>9.2f}%",
            log_buffer,
        )
    log("", log_buffer)
    log(f"Largest disagreement vs Step 6: {worst_diff:.2f}% (Threshold: < 5.00%)", log_buffer)
    log("", log_buffer)

    assert all(checks.values()), "One or more validation checks failed!"
    return checks, comp


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log_buffer = []
    log("=" * 74, log_buffer)
    log("EVENT-LEVEL SPATIOTEMPORAL ALLOCATION WORK (MEMBER 3)", log_buffer)
    log("=" * 74, log_buffer)
    log("", log_buffer)

    incidents = pd.read_csv(PROCESSED / "incidents_clean.csv")
    params = json.loads((PROCESSED / "model_params.json").read_text(encoding="utf-8"))
    exposure = pd.read_csv(PROCESSED / "exposure_focal.csv")
    baseline = exposure[exposure["Year"] == BASELINE_YEAR].set_index("road_label")
    p0_df = pd.read_csv(PROCESSED / "event_joint_profile.csv")

    t_end = params["n_months"] - 1
    design_rows = []
    for road in ("EDSA", "C5"):
        is_c5 = 1.0 if road == "C5" else 0.0
        for m in range(1, 13):
            angle = 2 * np.pi * m / 12
            design_rows.append({
                "corridor": road,
                "month": m,
                "days": pd.Period(f"{BASELINE_YEAR}-{m:02d}").days_in_month,
                "const": 1.0,
                "is_c5": is_c5,
                "t": float(t_end),
                "t_x_c5": float(t_end) * is_c5,
                "sin1": np.sin(angle),
                "cos1": np.cos(angle),
                "sin2": np.sin(2 * angle),
                "cos2": np.cos(2 * angle),
                "log_feed": 0.0,
            })
    design = pd.DataFrame(design_rows)

    historical, _ = compute_zone_boundaries(incidents, log_buffer)
    monthly_profile, best_kappa, grid_df = fit_monthly_profile(historical, p0_df, log_buffer)
    monthly_simulations, event_summary, rng = run_monthly_simulation(
        params, baseline, design, log_buffer
    )
    sample_events, event_allocation = run_event_allocation(
        monthly_simulations, monthly_profile, design, rng, log_buffer
    )
    verify_and_validate(monthly_profile, event_summary, event_allocation, sample_events, log_buffer)

    val_log_path = LOGS / "event_allocation_validation.txt"
    val_log_path.write_text("\n".join(log_buffer) + "\n", encoding="utf-8")
    log(f"Wrote validation report to: {val_log_path}", log_buffer)
    log("=" * 74, log_buffer)
    log("ALL TASKS COMPLETED SUCCESSFULLY", log_buffer)
    log("=" * 74, log_buffer)


if __name__ == "__main__":
    main()
