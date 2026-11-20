"""Task 10: C5 holdout diagnostics. Refs #T10.

Uses only the two member3_* tables for variant diagnostics, and reads T9's
holdout_model_comparison.csv for the main-model versus baseline comparison.
No refit. No causes are asserted. n=4 test months per corridor.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PRED = ROOT / "results" / "tables" / "member3_model_variant_holdout_predictions.csv"
SUMM = ROOT / "results" / "tables" / "member3_model_variant_holdout_summary.csv"
T9 = ROOT / "results" / "tables" / "holdout_model_comparison.csv"
OUT = ROOT / "results" / "tables" / "c5_holdout_diagnostics.csv"

MAIN = "main_2harmonic_actual_exposure"
CORRIDORS = ("EDSA", "C5")


def main():
    pred = pd.read_csv(PRED)
    summ = pd.read_csv(SUMM)
    t9 = pd.read_csv(T9)

    rows = []

    def add(section, corridor, item, metric, value, detail, source):
        rows.append(
            {
                "section": section,
                "corridor": corridor,
                "variant_or_method": item,
                "metric": metric,
                "value": value,
                "detail": detail,
                "source": source,
                "n_test_months": 4,
                "note": "n=4 test months per corridor. Descriptive only; no causes asserted.",
            }
        )

    # per-variant underprediction and mean signed error, from the member3 summary
    for _, r in summ.iterrows():
        add(
            "variant_error", r["corridor"], r["variant"], "underpredicted_months",
            int(r["underpredicted_months"]),
            f"out of {int(r['test_months'])} held-out months",
            "member3_model_variant_holdout_summary.csv",
        )
        add(
            "variant_error", r["corridor"], r["variant"], "mean_signed_error",
            float(r["mean_signed_bias"]),
            "predicted - observed; negative = underprediction",
            "member3_model_variant_holdout_summary.csv",
        )

    # largest-error month per corridor x variant, from the member3 predictions
    for (corridor, variant), g in pred.groupby(["corridor", "variant"]):
        top = g.loc[g["absolute_error"].idxmax()]
        add(
            "largest_error_month", corridor, variant, "max_absolute_error",
            float(top["absolute_error"]),
            f"ym={top['ym']} observed={int(top['crashes'])} "
            f"predicted={top['predicted']:.3f} signed_error={top['signed_error']:+.3f}",
            "member3_model_variant_holdout_predictions.csv",
        )

    # sensitivity comparisons within the main-model family
    for corridor in CORRIDORS:
        s = summ[summ["corridor"].eq(corridor)]
        main_mae = float(s.loc[s["variant"].eq(MAIN), "mae"].iloc[0])
        aadt = float(
            s.loc[s["variant"].eq("main_2harmonic_2019_aadt_for_2020"), "mae"].iloc[0]
        )
        reduced = float(
            s.loc[s["variant"].eq("reduced_1harmonic_actual_exposure"), "mae"].iloc[0]
        )
        add(
            "sensitivity", corridor, "main_2019_aadt_for_2020", "mae_vs_main",
            aadt - main_mae,
            f"MAE {aadt:.3f} vs main {main_mae:.3f}; "
            f"{'reduces' if aadt < main_mae else 'does not reduce'} error",
            "member3_model_variant_holdout_summary.csv",
        )
        add(
            "sensitivity", corridor, "reduced_1harmonic_actual_exposure", "mae_vs_main",
            reduced - main_mae,
            f"MAE {reduced:.3f} vs main {main_mae:.3f}; "
            f"{'reduces' if reduced < main_mae else 'does not reduce'} error",
            "member3_model_variant_holdout_summary.csv",
        )

    # main model vs the three benchmarks, read from T9 output
    for corridor in CORRIDORS:
        main_mae = float(
            t9[(t9["corridor"] == corridor) & (t9["method"] == "main")]["mae"].iloc[0]
        )
        for method in ("historical_mean", "seasonal_naive", "exposure_only"):
            base_mae = float(
                t9[(t9["corridor"] == corridor) & (t9["method"] == method)]["mae"].iloc[0]
            )
            add(
                "main_vs_baseline", corridor, method, "mae_difference_main_minus_baseline",
                main_mae - base_mae,
                f"main MAE {main_mae:.3f} vs {method} {base_mae:.3f}; "
                f"main {'lower' if main_mae < base_mae else 'higher'}",
                "holdout_model_comparison.csv (T9 output)",
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8")

    print("T10 C5 holdout diagnostics | n=4 test months per corridor")
    c5 = summ[summ["corridor"].eq("C5")]
    for _, r in c5.iterrows():
        print(
            f"C5 {r['variant']}: underpredicted {int(r['underpredicted_months'])}/4 "
            f"months, mean signed error {float(r['mean_signed_bias']):+.3f}"
        )
    for (corridor, variant), g in pred.groupby(["corridor", "variant"]):
        top = g.loc[g["absolute_error"].idxmax()]
        print(
            f"{corridor} {variant}: largest error {top['ym']} "
            f"(abs={float(top['absolute_error']):.2f}, signed={float(top['signed_error']):+.2f})"
        )
    for r in rows:
        if r["section"] in ("sensitivity", "main_vs_baseline"):
            print(f"{r['corridor']} {r['variant_or_method']}: {r['detail']}")
    print(f"Saved {OUT.relative_to(ROOT)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
