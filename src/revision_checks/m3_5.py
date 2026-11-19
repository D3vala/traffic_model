"""Task 5: peak-hour uncertainty by day-level bootstrap resampling. Refs #T5.

Resamples whole calendar dates (not individual reports) within each corridor,
because reports cluster within days. UNKNOWN_TIME reports are excluded.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "results" / "processed" / "incidents_clean.csv"
OUT = ROOT / "results" / "tables" / "peak_hour_uncertainty.csv"

SEED = 20260919  # cfg.RANDOM_SEED in the notebook
N_DRAWS = 2000
CORRIDORS = ("EDSA", "C5")
REFERENCE_HOUR = {"EDSA": 7, "C5": 15}  # hours stated in the manuscript
MODELLED_CLASS = "CRASH"


def load_modelled_reports():
    df = pd.read_csv(CLEAN)
    keep = (
        df["in_window"].astype(str).str.lower().isin(["true", "1", "yes"])
        & df["incident_class"].eq(MODELLED_CLASS)
        & df["corridor"].isin(CORRIDORS)
    )
    hist = df.loc[keep, ["date", "corridor", "hour"]].copy()
    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
    hist["hour"] = pd.to_numeric(hist["hour"], errors="coerce")
    # Exclude UNKNOWN_TIME: missing or out-of-range hours.
    hist = hist[hist["hour"].notna() & hist["hour"].between(0, 23)].copy()
    hist["hour"] = hist["hour"].astype(int)
    return hist


def bootstrap_shares(hours_by_day, n_draws, rng):
    """Return (n_draws, 24) share matrix; days are the resampling unit."""
    n_days = len(hours_by_day)
    counts = np.zeros((n_draws, 24), dtype=np.int64)
    for b in range(n_draws):
        picked = rng.integers(0, n_days, size=n_days)
        hours = np.concatenate([hours_by_day[i] for i in picked])
        counts[b] = np.bincount(hours, minlength=24)
    return counts / counts.sum(axis=1, keepdims=True)


def main():
    hist = load_modelled_reports()
    rows = []
    print(f"T5 peak-hour uncertainty | draws={N_DRAWS} seed={SEED}")
    print(f"Reports used: {len(hist):,} (UNKNOWN_TIME excluded)")
    for corridor in CORRIDORS:
        sub = hist[hist["corridor"].eq(corridor)]
        days = [g["hour"].to_numpy() for _, g in sub.groupby("date", sort=True)]
        rng = np.random.default_rng(SEED + (0 if corridor == "EDSA" else 1))
        shares = bootstrap_shares(days, N_DRAWS, rng)
        winners = np.argmax(shares, axis=1)  # ties resolved to earlier hour
        win_counts = np.bincount(winners, minlength=24)

        ref_hour = REFERENCE_HOUR[corridor]
        ref_pct = 100.0 * win_counts[ref_hour] / N_DRAWS
        other_counts = win_counts.copy()
        other_counts[ref_hour] = -1
        other_hour = int(np.argmax(other_counts))
        non_ref_draws = N_DRAWS - int(win_counts[ref_hour])
        other_pct = (
            100.0 * win_counts[other_hour] / non_ref_draws
            if non_ref_draws
            else np.nan
        )

        observed = sub["hour"].value_counts(normalize=True).reindex(
            range(24), fill_value=0.0
        )
        for hour in range(24):
            lo, hi = np.percentile(shares[:, hour], [2.5, 97.5])
            rows.append(
                {
                    "corridor": corridor,
                    "hour": hour,
                    "observed_share": float(observed.loc[hour]),
                    "ci95_low": float(lo),
                    "ci95_high": float(hi),
                    "bootstrap_largest_pct": 100.0 * win_counts[hour] / N_DRAWS,
                    "reference_hour": ref_hour,
                    "reference_largest_pct": ref_pct,
                    "otherwise_modal_hour": other_hour,
                    "otherwise_modal_pct_of_non_reference_draws": other_pct,
                    "reports_used": len(sub),
                    "distinct_dates": len(days),
                    "n_draws": N_DRAWS,
                    "seed": SEED,
                    "note": (
                        "Bootstrap resamples whole dates within corridor; "
                        "UNKNOWN_TIME excluded. Largest share = largest observed "
                        "hourly share of reports, not collision risk. "
                        "Ties resolved to earlier hour."
                    ),
                }
            )
        print(
            f"{corridor}: hour {ref_hour:02d} largest in {ref_pct:.1f}% of draws; "
            f"otherwise hour {other_hour:02d} wins most often "
            f"({other_pct:.1f}% of non-{ref_hour:02d} winning draws)"
        )
        top = np.argsort(-win_counts)[:3]
        print("  top winning hours: " + ", ".join(f"{int(h):02d}" for h in top))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8")
    print(f"Saved {OUT.relative_to(ROOT)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
