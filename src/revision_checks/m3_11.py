"""Task 11: structured PSA / MMDA comparison using project files only. Refs #T11.

Each cell is one or two complete sentences. The PSA series remains external
context and cannot independently validate EDSA or C5 counts.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "tables" / "psa_mmda_comparison.csv"

ROWS = [
    {
        "dimension": "outcome definition",
        "mmda_feed": (
            "The feed records labelled traffic incidents such as VEHICULAR "
            "ACCIDENT and stalls. The modelled outcome is the CRASH class only."
        ),
        "psa_series": (
            "PSA reports annual crash totals split into Fatal, NonFatalInjury "
            "and DamageToProperty counts."
        ),
        "source": (
            "incidents_clean.csv (Type, incident_class); "
            "psa_metro_manila_road_crashes_2013_2024.csv (columns)"
        ),
    },
    {
        "dimension": "geographic coverage",
        "mmda_feed": (
            "Reports are assigned to EDSA, C5 or OTHER. Only EDSA and C5 are "
            "modelled."
        ),
        "psa_series": "PSA crash statistics cover Metro Manila.",
        "source": (
            "incidents_clean.csv (corridor); notebook Step 8.2; "
            "docs/member3_task_brief.md, Part 1, Section 11: PSA/MMDA Comparison"
        ),
    },
    {
        "dimension": "collection system",
        "mmda_feed": (
            "The incident source is the MMDA social-media feed. Raw Source "
            "fields are Twitter status URLs."
        ),
        "psa_series": (
            "PSA republishes MMDA/MMARAS administrative records; PSA does not "
            "operate an independent collection system."
        ),
        "source": (
            "2024 Philippine Statistical Yearbook, Table 13.20 (printed p. 13-26) "
            "and Table 17.9 (printed p. 17-16): "
            "https://psa.gov.ph/system/files/psy/2024-PSY_Final-revised_as-of-July-29-signed.pdf"
        ),
    },
    {
        "dimension": "time resolution",
        "mmda_feed": (
            "Each report has a date and hour. Estimation uses the 18 complete "
            "months from September 2018 to February 2020."
        ),
        "psa_series": "PSA figures are annual, from 2013 through 2024.",
        "source": (
            "incidents_clean.csv (date, hour); README.md, Section 11, Understand the "
            "evidence and limitations; psa_metro_manila_road_crashes_2013_2024.csv "
            "(Year); notebook dataset metadata cell"
        ),
    },
    {
        "dimension": "known completeness",
        "mmda_feed": (
            "Missing posts do not establish that no crash occurred. No matched "
            "authoritative EDSA or C5 registry exists, so capture rates cannot "
            "be estimated."
        ),
        "psa_series": (
            "Neither PSA/MMDA/MMARAS completeness nor EDSA/C5 capture rates "
            "are established."
        ),
        "source": (
            "2024 Philippine Statistical Yearbook, Table 13.20 (printed p. 13-26) "
            "and Table 17.9 (printed p. 17-16): "
            "https://psa.gov.ph/system/files/psy/2024-PSY_Final-revised_as-of-July-29-signed.pdf"
        ),
    },
    {
        "dimension": "role in this study",
        "mmda_feed": (
            "The feed supplies outcome counts and within-year timing for the "
            "model."
        ),
        "psa_series": (
            "The PSA series is external context only and cannot independently "
            "validate EDSA/C5 counts. It is not used in model estimation."
        ),
        "source": (
            "2024 Philippine Statistical Yearbook, Table 13.20 (printed p. 13-26) "
            "and Table 17.9 (printed p. 17-16): "
            "https://psa.gov.ph/system/files/psy/2024-PSY_Final-revised_as-of-July-29-signed.pdf"
        ),
    },
]


def main():
    cells = [
        row[key]
        for row in ROWS
        for key in ("mmda_feed", "psa_series")
    ]
    assert len(cells) == len(set(cells)), "duplicated cell text"
    assert not any(
        "|" in str(value)
        for row in ROWS
        for value in row.values()
    ), "markdown pipe found"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ROWS).to_csv(OUT, index=False, encoding="utf-8")

    print(f"T11 PSA/MMDA comparison | {len(ROWS)} dimensions")
    for row in ROWS:
        print(f"Dimension: {row['dimension']}")
        print(f"MMDA: {row['mmda_feed']}")
        print(f"PSA: {row['psa_series']}")
        print(f"Source: {row['source']}")
    print(f"Saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
