"""Task 7: descriptive day-of-week profile of reported collisions. Refs #T7.

Counts and shares are descriptive only. The denominator for the last column is
the number of calendar days of that weekday inside the 18-month estimation
window, because weekdays do not occur equally often.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "results" / "processed" / "incidents_clean.csv"
OUT = ROOT / "results" / "tables" / "day_of_week_profile.csv"

WINDOW_START = "2018-09-01"
WINDOW_END = "2020-02-29"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NOTE = (
    "Descriptive only. No day-specific traffic exposure is available; "
    "reports per calendar day is not collision risk."
)


def main():
    df = pd.read_csv(CLEAN)
    keep = (
        df["in_window"].astype(str).str.lower().isin(["true", "1", "yes"])
        & df["incident_class"].eq("CRASH")
        & df["corridor"].isin(["EDSA", "C5"])
    )
    hist = df.loc[keep, ["date", "corridor"]].copy()
    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
    hist["weekday"] = hist["date"].dt.day_name()

    calendar_days = (
        pd.Series(pd.date_range(WINDOW_START, WINDOW_END, freq="D"))
        .dt.day_name().value_counts()
    )
    print(
        f"T7 day-of-week profile | window {WINDOW_START}..{WINDOW_END} | "
        f"reports={len(hist):,}"
    )
    print("Calendar days per weekday in window:")
    print(calendar_days.reindex(DAYS).to_string())

    rows = []
    for corridor in ("EDSA", "C5"):
        sub = hist[hist["corridor"].eq(corridor)]
        total = len(sub)
        for weekday in DAYS:
            n = int(sub["weekday"].eq(weekday).sum())
            n_days = int(calendar_days.get(weekday, 0))
            rows.append({
                "corridor": corridor,
                "weekday": weekday,
                "day_group": "weekend" if weekday in ("Saturday", "Sunday") else "weekday",
                "reports": n,
                "share_of_reports": n / total if total else 0.0,
                "calendar_days_of_weekday_in_window": n_days,
                "reports_per_calendar_day": n / n_days if n_days else 0.0,
                "corridor_total_reports": total,
                "note": NOTE,
            })
        print(
            f"{corridor}: total={total:,}; busiest weekday="
            f"{sub['weekday'].value_counts().idxmax()} "
            f"({100 * sub['weekday'].value_counts().max() / total:.1f}% of reports)"
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8")
    print(f"Saved {OUT.relative_to(ROOT)} ({len(rows)} rows)")
    print(NOTE)


if __name__ == "__main__":
    main()
