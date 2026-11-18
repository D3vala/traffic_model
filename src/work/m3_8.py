"""Task 8: audit whether the incident data contain a consistent severity variable. Refs #T8.

No severity proxy is built. If no consistent measure exists, severity is
reported as unmodeled.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "mmda_social_media_incidents_2018_2020.csv"
CLEAN = ROOT / "results" / "processed" / "incidents_clean.csv"
PSA = ROOT / "data" / "psa_metro_manila_road_crashes_2013_2024.csv"
OUT_CSV = ROOT / "results" / "tables" / "severity_variable_audit.csv"
OUT_LOG = ROOT / "results" / "logs" / "severity_check_notes.txt"

REASONS = {
    "Date": "Calendar date of report; not a severity outcome.",
    "Time": "Time of report; not a severity outcome.",
    "City": "Location label; not a severity outcome.",
    "Location": "Free-text location; not a severity outcome.",
    "Latitude": "Coordinate; not a severity outcome.",
    "Longitude": "Coordinate; not a severity outcome.",
    "High_Accuracy": "Geolocation quality flag; not a severity outcome.",
    "Direction": "Travel direction; not a severity outcome.",
    "Type": (
        "Free-text incident label (e.g. VEHICULAR ACCIDENT, stalled vehicle); "
        "no fatal / injury / property-damage coding."
    ),
    "Lanes_Blocked": "Number of lanes blocked; an operational detail, not a severity outcome.",
    "Involved": "Vehicle descriptions (e.g. TAXI AND MC); no casualty status.",
    "Tweet": "Unstructured social-media text; no coded severity field.",
    "Source": "Tweet URL; not a severity outcome.",
    "hour": "Hour of report; not a severity outcome.",
    "incident_class": "Broad outcome class (CRASH/STALL/etc.), not severity.",
    "corridor": "Corridor label; not a severity outcome.",
    "geo_valid": "Coordinate validity flag; not a severity outcome.",
    "in_window": "Estimation-window flag; not a severity outcome.",
}
SEVERITY_TERMS = ("FATAL", "INJUR", "DEAD", "CASUALT", "SERIOUS", "MINOR")


def sample_values(series, limit=5, width=42):
    vals = series.dropna().astype(str).unique()[:limit]
    return " | ".join(v[:width] for v in vals)


def audit_frame(name, frame):
    rows = []
    for field in frame.columns:
        s = frame[field]
        rows.append({
            "dataset": name,
            "field": field,
            "dtype": str(s.dtype),
            "non_null": int(s.notna().sum()),
            "missing_pct": 100.0 * float(s.isna().mean()),
            "n_unique": int(s.nunique(dropna=True)),
            "sample_values": sample_values(s),
            "consistent_severity_measure": "No",
            "reason": REASONS.get(field, "No coded severity scale documented."),
        })
    return rows


def main():
    raw = pd.read_csv(RAW)
    clean = pd.read_csv(CLEAN)
    psa = pd.read_csv(PSA)

    rows = audit_frame("mmda_social_media_incidents_2018_2020.csv", raw)
    rows += audit_frame("incidents_clean.csv", clean)

    type_values = raw["Type"].dropna().astype(str).unique()
    hits = {
        term: [v for v in type_values if term in v.upper()]
        for term in SEVERITY_TERMS
    }
    found = {t: v for t, v in hits.items() if v}
    rows.append({
        "dataset": "mmda_social_media_incidents_2018_2020.csv",
        "field": "Type severity-term scan",
        "dtype": "text scan",
        "non_null": len(type_values),
        "missing_pct": 0.0,
        "n_unique": len(type_values),
        "sample_values": "; ".join(f"{k}: {v}" for k, v in found.items())[:200],
        "consistent_severity_measure": "No",
        "reason": (
            "No fatal/injury/casualty terms found in Type values."
            if not found else
            "Sporadic text terms are not a consistent coded severity scale."
        ),
    })
    rows.append({
        "dataset": "conclusion",
        "field": "severity_variable",
        "dtype": "n/a",
        "non_null": 0,
        "missing_pct": 0.0,
        "n_unique": 0,
        "sample_values": "",
        "consistent_severity_measure": "No",
        "reason": (
            "No consistent, defensible severity variable exists in the incident "
            "feed. Severity remains unmodeled. No proxy was built."
        ),
    })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8")

    notes = [
        "Task 8 - severity variable check (Refs #T8)",
        "",
        f"Audited {RAW.relative_to(ROOT)} ({len(raw):,} rows) and "
        f"{CLEAN.relative_to(ROOT)} ({len(clean):,} rows).",
        "Type is a free-text incident label; it does not code fatal, non-fatal "
        "injury, or property-damage outcomes.",
        "Lanes_Blocked is a lane count, Involved lists vehicles, and Tweet is "
        "unstructured social-media text. None is a consistent severity measure.",
        f"Type severity-term scan searched {SEVERITY_TERMS}: "
        + ("no matching terms." if not found else f"sporadic matches {found}."),
        f"{PSA.relative_to(ROOT)} contains annual Fatal, NonFatalInjury and "
        "DamageToProperty columns, but these are external aggregate counts, "
        "not per-report MMDA severity values; they were not used to assign "
        "severity to any incident.",
        "",
        "Conclusion: no consistent, defensible severity variable is available. "
        "Severity remains unmodeled. No severity proxy was built.",
    ]
    OUT_LOG.write_text("\n".join(notes) + "\n", encoding="utf-8")

    print(f"T8 severity audit | raw rows={len(raw):,} clean rows={len(clean):,}")
    print(f"Type unique labels: {len(type_values)}; severity-term matches: {found}")
    print("Conclusion: no consistent severity variable; severity remains unmodeled.")
    print(f"Saved {OUT_CSV.relative_to(ROOT)} ({len(rows)} rows)")
    print(f"Saved {OUT_LOG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
