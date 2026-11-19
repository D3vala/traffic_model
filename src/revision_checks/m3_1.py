"""Task 1: differential corridor reporting sensitivity. Refs #T1.

Observed ratio R = (EDSA reports per vehicle-day) / (C5 reports per vehicle-day)
over the 18-month window. Confidence interval from a paired month bootstrap:
the same resampled months are used for both corridors. All reporting fractions
are hypothetical sensitivity assumptions, not estimated capture rates.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "results" / "processed" / "incident_monthly_panel.csv"
EXPOSURE = ROOT / "results" / "processed" / "exposure_alignment.csv"
OUT_CSV = ROOT / "results" / "tables" / "reporting_bias_sensitivity.csv"
OUT_LOG = ROOT / "results" / "logs" / "reporting_bias_notes.txt"

SEED = 20260919
N_BOOT = 2000
CORRIDORS = ("EDSA", "C5")


def load_paired_months():
    panel = pd.read_csv(PANEL)
    panel = panel[
        panel["in_window"].astype(str).str.lower().isin(["true", "1", "yes"])
        & panel["corridor"].isin(CORRIDORS)
    ].copy()
    exposure = pd.read_csv(EXPOSURE)

    merged = panel[["ym", "corridor", "crashes"]].merge(
        exposure[["ym", "corridor", "vehicle_passages"]],
        on=["ym", "corridor"],
        how="inner",
        validate="1:1",
    )
    crashes = merged.pivot(index="ym", columns="corridor", values="crashes")
    passages = merged.pivot(index="ym", columns="corridor", values="vehicle_passages")
    crashes = crashes.sort_index()[list(CORRIDORS)]
    passages = passages.reindex(index=crashes.index, columns=CORRIDORS)
    if crashes.isna().any().any() or passages.isna().any().any():
        raise ValueError("Missing in-window month/corridor cell after merge.")
    if list(crashes.columns) != list(CORRIDORS):
        raise ValueError("Unexpected corridor columns after pivot.")
    return crashes, passages


def main():
    crashes, passages = load_paired_months()
    months = list(crashes.index)
    n_months = len(months)
    y_crash = {c: crashes[c].to_numpy(float) for c in CORRIDORS}
    y_pass = {c: passages[c].to_numpy(float) for c in CORRIDORS}

    rate = {
        c: y_crash[c].sum() / y_pass[c].sum() for c in CORRIDORS
    }
    R = rate["EDSA"] / rate["C5"]
    one_over_R = 1.0 / R

    rng = np.random.default_rng(SEED)
    boot = np.empty(N_BOOT, dtype=float)
    for b in range(N_BOOT):
        idx = rng.integers(0, n_months, size=n_months)  # same months both corridors
        r_e = y_crash["EDSA"][idx].sum() / y_pass["EDSA"][idx].sum()
        r_c = y_crash["C5"][idx].sum() / y_pass["C5"][idx].sum()
        boot[b] = r_e / r_c
    ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])

    grid = [0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, R]
    rows = []
    for c_ratio in grid:
        corrected = R / c_ratio
        rows.append(
            {
                "scenario": "hypothetical",
                "is_hypothetical": True,
                "cE_over_cC": c_ratio,
                "corrected_rate_ratio_R_over_cRatio": corrected,
                "ordering": (
                    "EDSA greater" if corrected > 1
                    else "C5 greater (reversal)" if corrected < 1
                    else "break-even"
                ),
                "is_break_even": bool(np.isclose(c_ratio, R)),
                "is_reversal": bool(corrected < 1),
                "observed_R": R,
                "observed_R_ci95_low": ci_lo,
                "observed_R_ci95_high": ci_hi,
                "note": (
                    "HYPOTHETICAL cE/cC. corrected rate ratio = R x cC/cE = R / "
                    "(cE/cC). Break-even when cE/cC = R. Reversal needs cE/cC > R. "
                    "Not a measured capture rate."
                ),
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8")

    notes = [
        "Task 1 - differential corridor reporting sensitivity (Refs #T1)",
        "",
        f"Inputs: {PANEL.relative_to(ROOT)} (in_window, CRASH counts), "
        f"{EXPOSURE.relative_to(ROOT)} (vehicle_passages).",
        f"Window: {months[0]}..{months[-1]}, {n_months} complete months, paired by month.",
        f"EDSA crashes={int(y_crash['EDSA'].sum()):,}, "
        f"vehicle-days={y_pass['EDSA'].sum():,.0f}, rate={rate['EDSA']:.8g}/vehicle-day.",
        f"C5 crashes={int(y_crash['C5'].sum()):,}, "
        f"vehicle-days={y_pass['C5'].sum():,.0f}, rate={rate['C5']:.8g}/vehicle-day.",
        f"Observed ratio R = rate_EDSA / rate_C5 = {R:.4f}.",
        f"Paired month bootstrap ({N_BOOT} draws, seed {SEED}): R 95% CI "
        f"[{ci_lo:.4f}, {ci_hi:.4f}]. The same resampled months are used for both "
        "corridors; reports are not resampled individually.",
        "",
        "Corrected rate ratio = observed EDSA/C5 rate ratio x cC/cE = R / (cE/cC).",
        f"Break-even occurs when cE/cC = R ({R:.4f}).",
        f"Reversal of the observed EDSA-greater-than-C5 ordering needs cE/cC > R "
        f"(> {R:.4f}).",
        f"Since cE <= 1, a reversal requires C5 completeness below 1/R "
        f"(< {one_over_R:.4f}); this is a necessary condition, not an estimate.",
        "All cE/cC values in the table are hypothetical sensitivity assumptions. "
        "No capture rate is invented or estimated, and the corrected ratios are "
        "not corrected true rates.",
        "",
        f"Saved table: {OUT_CSV.relative_to(ROOT)}.",
    ]
    OUT_LOG.write_text("\n".join(notes) + "\n", encoding="utf-8")

    print(f"T1 reporting sensitivity | months={n_months} | paired bootstrap draws={N_BOOT} seed={SEED}")
    print(f"EDSA rate={rate['EDSA']:.8g}/vehicle-day  C5 rate={rate['C5']:.8g}/vehicle-day")
    print(f"Observed R={R:.4f}  paired-bootstrap 95% CI=[{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"Break-even cE/cC=R={R:.4f}; reversal needs cE/cC>R; with cE<=1, C5 completeness <1/R={one_over_R:.4f}")
    print("Grid (all hypothetical): " + ", ".join(f"{g:.4g}" for g in grid))
    print(f"Saved {OUT_CSV.relative_to(ROOT)} ({len(rows)} rows)")
    print(f"Saved {OUT_LOG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
