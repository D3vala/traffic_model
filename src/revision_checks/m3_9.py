"""Task 9: holdout benchmarks for Member 1's main model. Refs #T9.

Checks first whether the member3_* predictions were fitted on the first 14
months only and whether they contain interval columns. No training-fit
covariance was saved, so 90% predictive interval coverage is reported as
unavailable. Poisson and Negative Binomial deviances are both reported.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PRED = ROOT / "results" / "tables" / "member3_model_variant_holdout_predictions.csv"
SUMM = ROOT / "results" / "tables" / "member3_model_variant_holdout_summary.csv"
PANEL = ROOT / "results" / "processed" / "incident_monthly_panel.csv"
EXPOSURE = ROOT / "results" / "processed" / "exposure_alignment.csv"
PARAMS = ROOT / "results" / "processed" / "model_params.json"
OUT_MONTH = ROOT / "results" / "tables" / "holdout_month_level.csv"
OUT_CMP = ROOT / "results" / "tables" / "holdout_model_comparison.csv"

MAIN = "main_2harmonic_actual_exposure"
CORRIDORS = ("EDSA", "C5")
N_TRAIN = 14

COVERAGE_NA = "N/A: no training-fit covariance saved"
POISSON_DEV_FORMULA = "Poisson deviance: D = 2 * sum[ y*ln(y/mu) - (y - mu) ], 0*ln(0)=0"
NB_DEV_FORMULA = (
    "NB2 deviance: D = 2 * sum[ y*ln(y/mu) - (y + 1/alpha)*ln((y + 1/alpha)/(mu + 1/alpha)) ], "
    "0*ln(0)=0; alpha from model_params.json"
)


def load_inputs():
    pred = pd.read_csv(PRED)
    summ = pd.read_csv(SUMM)
    panel = pd.read_csv(PANEL)
    exposure = pd.read_csv(EXPOSURE)
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    return pred, summ, panel, exposure, params


def check_fit_window_and_intervals(pred, panel):
    interval_cols = [
        c for c in pred.columns
        if any(k in c.lower() for k in ("interval", "lower", "upper", "ci", "quantile"))
    ]
    inwin = panel[
        panel["in_window"].astype(str).str.lower().isin(["true", "1", "yes"])
        & panel["corridor"].isin(CORRIDORS)
    ]
    months = sorted(inwin["ym"].unique())
    test_months = sorted(pred["ym"].unique())
    fitted_first_14 = (
        len(months) == 18
        and test_months == months[N_TRAIN:]
        and months[N_TRAIN - 1] == "2019-10"
    )
    return interval_cols, months, fitted_first_14


def build_benchmarks(panel, exposure, test):
    rows = []
    for corridor in CORRIDORS:
        ph = panel[
            panel["corridor"].eq(corridor)
            & panel["in_window"].astype(str).str.lower().isin(["true", "1", "yes"])
        ].sort_values("ym")
        train = ph.iloc[:N_TRAIN]
        eh = exposure[exposure["corridor"].eq(corridor)].sort_values("ym")
        train_exp = eh.merge(train[["ym"]], on="ym", how="inner")
        train_rate = train["crashes"].sum() / train_exp["vehicle_passages"].sum()
        hist_mean = train["crashes"].mean()
        past = ph.set_index("ym")["crashes"].to_dict()

        for _, t in test[test["corridor"].eq(corridor)].iterrows():
            ym = t["ym"]
            year, month = int(t["year"]), int(t["month"])
            naive = past.get(f"{year - 1:04d}-{month:02d}", np.nan)
            if np.isnan(naive):
                raise ValueError(f"Missing seasonal-naive value for {corridor} {ym}")
            rows.append(
                {
                    "ym": ym,
                    "corridor": corridor,
                    "historical_mean": hist_mean,
                    "seasonal_naive": float(naive),
                    "exposure_only": train_rate * float(t["exposure"]),
                }
            )
    return pd.DataFrame(rows)


def metrics(frame, pred_col, alpha):
    y = frame["crashes"].to_numpy(float)
    p = frame[pred_col].to_numpy(float)
    err = p - y
    nonzero = y > 0
    y_safe = np.where(nonzero, y, 1.0)

    poisson_dev = 2.0 * np.sum(
        np.where(nonzero, y_safe * np.log(y_safe / p) - (y - p), p)
    )
    r = 1.0 / alpha
    nb_dev = 2.0 * np.sum(
        np.where(
            nonzero,
            y_safe * np.log(y_safe / p) - (y + r) * np.log((y + r) / (p + r)),
            r * np.log((p + r) / r),
        )
    )
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mape_pct": float(np.mean(np.abs(err[nonzero]) / y[nonzero] * 100.0)),
        "poisson_deviance": float(poisson_dev),
        "nb_deviance": float(nb_dev),
        "mean_signed_bias": float(np.mean(err)),
    }


def main():
    pred, summ, panel, exposure, params = load_inputs()
    alpha = float(params["alpha"])
    interval_cols, months, fitted_first_14 = check_fit_window_and_intervals(pred, panel)
    test = pred[pred["variant"].eq(MAIN)].copy().sort_values(["corridor", "ym"])

    print("T9 holdout benchmarks")
    print(f"member3_* fitted on first {N_TRAIN} months only: {fitted_first_14} "
          f"(train {months[0]}..{months[N_TRAIN - 1]}, test {months[N_TRAIN]}..{months[-1]})")
    print(f"member3_* interval columns present: {bool(interval_cols)} {interval_cols}")
    print(f"Test months: {sorted(test['ym'].unique())} (n={test['ym'].nunique()} per corridor)")
    print(f"90% interval coverage: {COVERAGE_NA}")

    # recompute main-model MAE/MAPE and compare with Member 1's summary
    for corridor in CORRIDORS:
        g = test[test["corridor"].eq(corridor)]
        m = metrics(g, "predicted", alpha)
        srow = summ[
            summ["variant"].eq(MAIN) & summ["corridor"].eq(corridor)
        ].iloc[0]
        match = (
            np.isclose(m["mae"], float(srow["mae"]))
            and np.isclose(m["mape_pct"], float(srow["mape_pct"]))
        )
        print(
            f"{corridor} main recomputed MAE={m['mae']:.6f} MAPE={m['mape_pct']:.6f}% "
            f"vs summary {float(srow['mae']):.6f} / {float(srow['mape_pct']):.6f}% -> "
            f"{'MATCH' if match else 'MISMATCH'}"
        )
        if not match:
            raise AssertionError(f"Main-model metrics mismatch for {corridor}")

    bench = build_benchmarks(panel, exposure, test)
    test = test.merge(
        bench[["ym", "corridor", "historical_mean", "seasonal_naive", "exposure_only"]],
        on=["ym", "corridor"],
        how="left",
        validate="1:1",
    )

    methods = ["main", "historical_mean", "seasonal_naive", "exposure_only"]
    pred_col = {
        "main": "predicted",
        "historical_mean": "historical_mean",
        "seasonal_naive": "seasonal_naive",
        "exposure_only": "exposure_only",
    }
    month_rows = []
    summary_rows = []
    for corridor in CORRIDORS:
        for method in methods:
            g = test[test["corridor"].eq(corridor)].copy()
            m = metrics(g, pred_col[method], alpha)
            interval_note = (
                "No training-fit covariance saved; 90% predictive interval not computed."
                if method == "main" else
                "Benchmark method has no predictive interval; coverage not applicable."
            )
            summary_rows.append(
                {
                    "corridor": corridor,
                    "method": method,
                    "n_test_months": int(len(g)),
                    **m,
                    "interval_coverage_90_pct": COVERAGE_NA,
                    "interval_note": interval_note,
                    "poisson_deviance_formula": POISSON_DEV_FORMULA,
                    "nb_deviance_formula": NB_DEV_FORMULA,
                    "bias_sign": "predicted - observed (negative = underprediction)",
                }
            )
            for _, r in g.iterrows():
                month_rows.append(
                    {
                        "corridor": corridor,
                        "ym": r["ym"],
                        "method": method,
                        "observed": int(r["crashes"]),
                        "predicted": float(r[pred_col[method]]),
                        "signed_error": float(r[pred_col[method]]) - float(r["crashes"]),
                        "interval_coverage_90_pct": COVERAGE_NA,
                        "interval_note": interval_note,
                    }
                )

    OUT_MONTH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(month_rows).to_csv(OUT_MONTH, index=False, encoding="utf-8")
    pd.DataFrame(summary_rows).to_csv(OUT_CMP, index=False, encoding="utf-8")
    print(f"Poisson deviance: {POISSON_DEV_FORMULA}")
    print(f"NB deviance: {NB_DEV_FORMULA}")
    print(f"NB alpha={alpha}")
    for s in summary_rows:
        print(
            f"  {s['corridor']:4s} {s['method']:15s} MAE={s['mae']:.3f} "
            f"MAPE={s['mape_pct']:.2f}% pois_dev={s['poisson_deviance']:.2f} "
            f"nb_dev={s['nb_deviance']:.2f} bias={s['mean_signed_bias']:+.3f} "
            f"cov90={s['interval_coverage_90_pct']}"
        )
    print(f"Saved {OUT_MONTH.relative_to(ROOT)} ({len(month_rows)} rows)")
    print(f"Saved {OUT_CMP.relative_to(ROOT)} ({len(summary_rows)} rows)")


if __name__ == "__main__":
    main()
