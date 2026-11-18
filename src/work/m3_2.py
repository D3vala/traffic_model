"""Task 2: time-of-day reporting sensitivity. Refs #T2.

Part (a) is a deterministic percentage change in the peak hour's count that
would let the runner-up hour become larger. Part (b) multiplies each hour by an
independent uniform factor in [1-d, 1+d] for d = 0.1, 0.2, 0.3 and reports the
share of draws in which the peak hour stays the largest. A worst-case row
compares peak x (1-d) with runner-up x (1+d). UNKNOWN_TIME is excluded.
All changes are hypothetical, not measured reporting rates.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "results" / "processed" / "incidents_clean.csv"
OUT = ROOT / "results" / "tables" / "hour_reporting_sensitivity.csv"

SEED = 20260919
N_DRAWS = 2000
D_VALUES = (0.1, 0.2, 0.3)
CORRIDORS = ("EDSA", "C5")
REFERENCE = {"EDSA": 7, "C5": 15}  # hours stated in the manuscript
MODELLED_CLASS = "CRASH"


def load_hour_counts():
    df = pd.read_csv(CLEAN)
    keep = (
        df["in_window"].astype(str).str.lower().isin(["true", "1", "yes"])
        & df["incident_class"].eq(MODELLED_CLASS)
        & df["corridor"].isin(CORRIDORS)
    )
    hist = df.loc[keep, ["corridor", "hour"]].copy()
    hist["hour"] = pd.to_numeric(hist["hour"], errors="coerce")
    n_before = len(hist)
    # Exclude UNKNOWN_TIME: missing or out-of-range hours.
    hist = hist[hist["hour"].notna() & hist["hour"].between(0, 23)].copy()
    hist["hour"] = hist["hour"].astype(int)
    return hist, n_before - len(hist)


def main():
    hist, n_unknown = load_hour_counts()
    rows = []
    print(f"T2 hour reporting sensitivity | draws={N_DRAWS} seed={SEED} | UNKNOWN_TIME excluded={n_unknown}")
    for corridor in CORRIDORS:
        sub = hist[hist["corridor"].eq(corridor)]
        counts = sub["hour"].value_counts().reindex(range(24), fill_value=0).to_numpy(float)
        order = np.argsort(-counts, kind="stable")
        peak_hour, runner_hour = int(order[0]), int(order[1])
        peak_n, runner_n = counts[peak_hour], counts[runner_hour]

        # (a) deterministic: signed % change that brings peak down to runner-up
        pct_to_tie = (runner_n - peak_n) / peak_n * 100.0

        base = {
            "corridor": corridor,
            "peak_hour": peak_hour,
            "peak_count": int(peak_n),
            "runner_up_hour": runner_hour,
            "runner_up_count": int(runner_n),
            "reference_hour": REFERENCE[corridor],
            "reports_used": len(sub),
        }
        rows.append(
            {
                **base,
                "part": "a_deterministic",
                "d": "",
                "hypothetical_change_pct": pct_to_tie,
                "peak_unchanged_pct_of_draws": "",
                "worst_case_peak": "",
                "worst_case_runner_up": "",
                "worst_case_reversed": "",
                "is_hypothetical": True,
                "note": (
                    "HYPOTHETICAL. Signed percentage change in the peak hour count "
                    "that makes the runner-up as large; any larger decrease reverses "
                    "the ordering."
                ),
            }
        )

        # (b) random independent multiplicative factors per hour
        for d in D_VALUES:
            rng = np.random.default_rng(SEED + int(round(d * 100)) + (0 if corridor == "EDSA" else 50))
            factors = rng.uniform(1 - d, 1 + d, size=(N_DRAWS, 24))
            perturbed = counts[None, :] * factors
            winners = np.argmax(perturbed, axis=1)
            unchanged_pct = 100.0 * float((winners == peak_hour).mean())
            rows.append(
                {
                    **base,
                    "part": "b_random",
                    "d": d,
                    "hypothetical_change_pct": "",
                    "peak_unchanged_pct_of_draws": unchanged_pct,
                    "worst_case_peak": "",
                    "worst_case_runner_up": "",
                    "worst_case_reversed": "",
                    "is_hypothetical": True,
                    "note": (
                        f"HYPOTHETICAL. Each hour multiplied by an independent uniform "
                        f"factor in [1-{d}, 1+{d}] over {N_DRAWS} draws; percentage of "
                        "draws in which the observed peak hour remains the largest."
                    ),
                }
            )

        # worst case: peak x (1-d) vs runner-up x (1+d)
        for d in D_VALUES:
            wc_peak = peak_n * (1 - d)
            wc_runner = runner_n * (1 + d)
            rows.append(
                {
                    **base,
                    "part": "worst_case",
                    "d": d,
                    "hypothetical_change_pct": "",
                    "peak_unchanged_pct_of_draws": "",
                    "worst_case_peak": wc_peak,
                    "worst_case_runner_up": wc_runner,
                    "worst_case_reversed": bool(wc_runner > wc_peak),
                    "is_hypothetical": True,
                    "note": (
                        f"HYPOTHETICAL worst case at d={d}: peak x (1-{d}) versus "
                        f"runner-up x (1+{d}). Not a measured reporting rate."
                    ),
                }
            )

        print(
            f"{corridor}: peak hour {peak_hour:02d} ({int(peak_n)}), runner-up "
            f"{runner_hour:02d} ({int(runner_n)}); deterministic change to tie "
            f"{pct_to_tie:.1f}%"
        )
        for d in D_VALUES:
            unc = next(
                r["peak_unchanged_pct_of_draws"] for r in rows
                if r["corridor"] == corridor and r["part"] == "b_random" and r["d"] == d
            )
            print(f"  d={d:.1f}: peak unchanged in {unc:.1f}% of draws")
        for d in D_VALUES:
            wc = next(
                r for r in rows
                if r["corridor"] == corridor and r["part"] == "worst_case" and r["d"] == d
            )
            print(
                f"  worst-case d={d:.1f}: peak {wc['worst_case_peak']:.1f} vs "
                f"runner-up {wc['worst_case_runner_up']:.1f} -> "
                f"{'REVERSED' if wc['worst_case_reversed'] else 'peak still larger'}"
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8")
    print(f"Saved {OUT.relative_to(ROOT)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
