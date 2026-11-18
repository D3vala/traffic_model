"""Task 6: temporal pattern stability with a split-half noise reference. Refs #T6.

The zone definition below is copied verbatim from Step 8.3 of the notebook;
only the output directory for its intermediate CSV is redirected to a scratch
folder so the authoritative processed table is not rewritten.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "results" / "processed" / "incidents_clean.csv"
OUT = ROOT / "results" / "tables" / "temporal_pattern_sensitivity.csv"

SEED = 20260919
N_REF = 200
ZONES_PER_ROAD = 6
EXPECTED_COUNTS = {
    "EDSA": [905, 905, 905, 904, 905, 905],
    "C5": [280, 280, 280, 280, 280, 280],
}
SEASON_NOTE = (
    "First half = 2018-09..2019-05; last half = 2019-06..2020-02. "
    "The halves cover different seasons, so differences mix seasonal "
    "composition with any other temporal change."
)


class cfg:
    MODELLED_CLASS = "CRASH"
    PROCESSED = Path(tempfile.gettempdir()) / "m3_t6_zone_check"


def display(obj):
    print(obj.to_string(index=False) if isinstance(obj, pd.DataFrame) else obj)


def build_historical():
    INCIDENTS = pd.read_csv(CLEAN)
    HISTORICAL = INCIDENTS.copy()

    # ---- Step 8.2 subset, copied from the notebook -------------------------
    def as_boolean(series):
        return (
            series.astype(str)
            .str.lower()
            .isin(["true", "1", "yes"])
        )

    HISTORICAL = HISTORICAL[
        as_boolean(HISTORICAL["in_window"])
        & HISTORICAL["incident_class"].eq(cfg.MODELLED_CLASS)
        & HISTORICAL["corridor"].isin(["EDSA", "C5"])
    ].copy()

    for column in ("hour", "Latitude", "Longitude"):
        HISTORICAL[column] = pd.to_numeric(
            HISTORICAL[column],
            errors="coerce"
        )

    HISTORICAL["zone"] = "UNKNOWN_LOCATION"

    HISTORICAL["hour_label"] = HISTORICAL["hour"].apply(
        lambda hour: (
            f"{int(hour):02d}"
            if pd.notna(hour) and 0 <= hour <= 23
            else "UNKNOWN_TIME"
        )
    )
    # ------------------------------------------------------------------------

    cfg.PROCESSED.mkdir(parents=True, exist_ok=True)

    # ---- Step 8.3, copied exactly from the notebook -------------------------
    # STEP 8.3 — CREATE APPROXIMATE SPATIAL ZONES

    ZONE_INFORMATION = []

    for road in ("EDSA", "C5"):

        valid = (
            HISTORICAL["corridor"].eq(road)
            & as_boolean(HISTORICAL["geo_valid"])
            & HISTORICAL["Latitude"].notna()
            & HISTORICAL["Longitude"].notna()
        )

        road_points = HISTORICAL.loc[
            valid,
            ["Latitude", "Longitude"]
        ].to_numpy(dtype=float)

        if len(road_points) < ZONES_PER_ROAD * 10:
            raise ValueError(
                f"Not enough valid GPS records for {road}."
            )

        # Approximate geographic coordinates in kilometres.
        scaled = road_points * np.array([111.0, 108.0])

        centered = scaled - scaled.mean(axis=0)

        # Find the main direction of the coordinate cloud.
        _, _, axes = np.linalg.svd(
            centered,
            full_matrices=False
        )

        projected = centered @ axes[0]

        if axes[0][0] < 0:
            projected *= -1

        # Divide the historical points into equal-sized groups.
        ranks = pd.Series(
            projected,
            index=HISTORICAL.index[valid]
        ).rank(method="first")

        zone_numbers = pd.qcut(
            ranks,
            q=ZONES_PER_ROAD,
            labels=False
        )

        HISTORICAL.loc[valid, "zone"] = [
            f"{road}_ZONE_{int(number) + 1:02d}"
            for number in zone_numbers
        ]

        for zone, group in HISTORICAL.loc[valid].groupby(
            "zone"
        ):

            ZONE_INFORMATION.append({
                "road": road,
                "zone": zone,
                "historical_reports": len(group),
                "latitude": group["Latitude"].mean(),
                "longitude": group["Longitude"].mean()
            })

    ZONES = pd.DataFrame(ZONE_INFORMATION)

    ZONES.to_csv(
        cfg.PROCESSED / "approximate_spatial_zones.csv",
        index=False
    )

    print("Location zones created:", len(ZONES))

    display(ZONES)
    # ------------------------------------------------------------------------

    actual = {
        road: ZONES.loc[ZONES["road"].eq(road)]
        .sort_values("zone")["historical_reports"].tolist()
        for road in ("EDSA", "C5")
    }
    if actual != EXPECTED_COUNTS:
        raise AssertionError(f"Zone counts mismatch: {actual}")
    print("Zone counts verified:", actual)

    month = pd.to_datetime(HISTORICAL["date"]).dt.to_period("M")
    HISTORICAL["period"] = np.where(
        month <= pd.Period("2019-05", "M"), "first_9m", "last_9m"
    )
    return HISTORICAL


def distribution(frame, kind):
    if kind == "hourly":
        s = frame["hour_label"]
    elif kind == "zone":
        s = frame["zone"]
    else:
        s = pd.Series(
            list(zip(frame["zone"], frame["hour_label"])), index=frame.index
        )
    return s.value_counts(normalize=True)


def tvd(p, q):
    idx = p.index.union(q.index)
    return 0.5 * float(
        (p.reindex(idx, fill_value=0.0) - q.reindex(idx, fill_value=0.0))
        .abs().sum()
    )


def noise_reference(frame, kind, rng):
    values = []
    labels = frame.index.to_numpy()
    for _ in range(N_REF):
        perm = rng.permutation(labels)
        half = len(perm) // 2
        a = frame.loc[perm[:half]]
        b = frame.loc[perm[half:2 * half]]
        values.append(tvd(distribution(a, kind), distribution(b, kind)))
    return float(np.median(values)), float(np.percentile(values, 95))


def main():
    hist = build_historical()
    rows = []
    print(f"\nT6 temporal stability | split-half reference draws={N_REF} seed={SEED}")
    for i, corridor in enumerate(("EDSA", "C5")):
        sub = hist[hist["corridor"].eq(corridor)]
        first = sub[sub["period"].eq("first_9m")]
        last = sub[sub["period"].eq("last_9m")]
        for j, kind in enumerate(("hourly", "zone", "joint")):
            observed = tvd(distribution(first, kind), distribution(last, kind))
            rng = np.random.default_rng(SEED + 100 * i + j)
            ref_median, ref_p95 = noise_reference(sub, kind, rng)
            exceeds = bool(observed > ref_p95)
            interpretation = (
                "First-vs-last TVD exceeds the 95th percentile of random "
                "split-half TVD; difference is larger than this noise reference."
                if exceeds else
                "First-vs-last TVD is within the random split-half noise "
                "reference; patterns remain broadly similar by this measure."
            )
            rows.append({
                "corridor": corridor,
                "distribution": kind,
                "n_first": len(first),
                "n_last": len(last),
                "tvd_first_vs_last": observed,
                "noise_ref_median_tvd": ref_median,
                "noise_ref_p95_tvd": ref_p95,
                "exceeds_noise_p95": exceeds,
                "interpretation": interpretation,
                "zone_counts_verified": True,
                "note": SEASON_NOTE,
            })
            print(
                f"{corridor} {kind:6s}: TVD={observed:.4f}  "
                f"split-half median={ref_median:.4f} p95={ref_p95:.4f}  "
                f"{'EXCEEDS' if exceeds else 'within'} noise reference"
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8")
    print(f"Saved {OUT.relative_to(ROOT)} ({len(rows)} rows)")
    print(SEASON_NOTE)


if __name__ == "__main__":
    main()
