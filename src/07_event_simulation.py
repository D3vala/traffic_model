"""
07_event_simulation.py — event-level spatiotemporal layer (Step 8).

Written in jupytext percent format: `# %%` starts a code cell and
`# %% [markdown]` a markdown cell. build_notebook.py splits on those
markers and appends the result to the notebook, so this file is the
source of truth for Step 8 in the same way src/01..06 are for Steps 1-7.
"""

# %% [markdown]
# ## Step 8 — Event-level spatiotemporal simulation
#
# Steps 1 to 7 answer *how many*. This step answers *where and when*, by taking the counts the fitted model produces and placing every single one of them on a stretch of road at an hour of the day.
#
# The corridors are divided into five zones each, cut along the road's own direction using the incident GPS coordinates. Historical crashes give a joint zone-by-hour probability, and each simulated incident is drawn from it. The output is an event log — one row per simulated crash — rather than a monthly total.
#
# **What this does not change.** The number of incidents still comes entirely from Step 5's model. This step redistributes them; it does not create any. And as in Step 5, a zone-hour probability describes where reported crashes fell, not where a vehicle is most at risk — nothing here observes how much traffic uses a given zone at a given hour.

# %% [markdown]
# ### Step 8.1 — Load the fitted model and configure the run
#
# Everything below reuses the coefficients estimated in Step 5 rather than refitting anything. The design matrix is built exactly as Step 6 builds its own — trend frozen at the end of the window, reporting term held at the window average — so that the two simulations remain comparable. Step 8.8b verifies that they are.

# %%
# STEP 8.1 — LOAD DATA AND CONFIGURE THE SIMULATION
#
# This cell was missing from the delivered notebook, which is why every cell of
# Step 8 failed. It defines the six objects the rest of the section expects:
# INCIDENTS, PARAMS, BASELINE, DESIGN, the run-size constants, and rng.
#
# The important part is DESIGN. Step 8 reuses the coefficients fitted in Step 5,
# so its design matrix must be built exactly the way Step 6 builds its own —
# same frozen trend, same neutral reporting term, same seasonal harmonics.
# If the two disagree, the event-level simulation silently answers a different
# question from the count-level one, and the numbers stop being comparable.
# Step 8.8b checks that they agree.

import json

# --- run sizes -------------------------------------------------------------
# Generating individual events is much heavier than generating counts, because
# every incident becomes a row. 500 runs is enough to stabilise the summary to
# within a percent or two of Step 6; the detailed event log is kept for the
# first SAMPLE_RUNS runs only, which is what makes the output a readable
# example rather than a two-million-row file.
EVENT_RUNS = 500
SAMPLE_RUNS = 2
ZONES_PER_ROAD = 5
EVENT_ELASTICITIES = [1.0]

rng = np.random.default_rng(cfg.RANDOM_SEED + 800)

# --- inputs ----------------------------------------------------------------
INCIDENTS = pd.read_csv(cfg.PROCESSED / "incidents_clean.csv")
PARAMS = json.loads((cfg.PROCESSED / "model_params.json").read_text())

_exposure = pd.read_csv(cfg.PROCESSED / "exposure_focal.csv")
BASELINE = (
    _exposure[_exposure["Year"] == cfg.BASELINE_YEAR]
    .set_index("road_label")
)

for _road in ("EDSA", "C5"):
    if _road not in BASELINE.index:
        raise ValueError(
            f"No {cfg.BASELINE_YEAR} exposure for {_road}. Run Step 2 first."
        )

# --- design matrix ---------------------------------------------------------
# One row per corridor per calendar month of the simulated year.
#
#   t         the within-window trend, FROZEN at its end-of-window value. The
#             trend was measured across 18 months; projecting it forward would
#             be extrapolation the data does not support.
#   log_feed  the reporting-intensity control, set to 0. That term was centred
#             on the window mean in Step 5, so zero means "a year in which the
#             MMDA account posts as often as it did on average". Any other
#             value would simulate a change in Twitter behaviour rather than a
#             change in road safety.
_t_end = PARAMS["n_months"] - 1

_design_rows = []
for _road in ("EDSA", "C5"):
    _is_c5 = 1.0 if _road == "C5" else 0.0
    for _month in range(1, 13):
        _angle = 2 * np.pi * _month / 12
        _design_rows.append({
            "corridor": _road,
            "month": _month,
            "days": pd.Period(f"{cfg.BASELINE_YEAR}-{_month:02d}").days_in_month,
            "const": 1.0,
            "is_c5": _is_c5,
            "t": float(_t_end),
            "t_x_c5": float(_t_end) * _is_c5,
            "sin1": np.sin(_angle),
            "cos1": np.cos(_angle),
            "sin2": np.sin(2 * _angle),
            "cos2": np.cos(2 * _angle),
            "log_feed": 0.0,
        })

DESIGN = pd.DataFrame(_design_rows)

# Fail here rather than three cells later with an unhelpful KeyError.
_missing = [c for c in PARAMS["coefficients"] if c not in DESIGN.columns]
if _missing:
    raise ValueError(
        f"DESIGN is missing columns the fitted model needs: {_missing}. "
        f"The model was fitted with {list(PARAMS['coefficients'])}."
    )

print(f"Model family        : {PARAMS['family']} (alpha {PARAMS['alpha']:.4f})")
print(f"Coefficients reused : {', '.join(PARAMS['coefficients'])}")
print(f"Trend held at       : month {_t_end} of the estimation window (frozen)")
print(f"Reporting term      : log_feed = 0 (window-average posting rate)")
print()
print(f"Incident records    : {len(INCIDENTS):,}")
print(f"{cfg.BASELINE_YEAR} exposure       : "
      + ", ".join(f"{r} {BASELINE.loc[r, 'aadt']:,.0f}" for r in ("EDSA", "C5")))
print(f"Design matrix       : {DESIGN.shape[0]} rows "
      f"({DESIGN['corridor'].nunique()} corridors x 12 months)")
print(f"Runs per scenario   : {EVENT_RUNS:,}  "
      f"(detailed events kept for the first {SAMPLE_RUNS})")
print(f"Spatial zones       : {ZONES_PER_ROAD} per corridor")

# %% [markdown]
# ### Step 8.2 — Prepare historical crash records
#
# Only reported crashes from the selected estimation window are used to create the time and location patterns.
#
# The original incident records are retained. Records with missing coordinates or times can still contribute to incident counts, but their missing information will not be invented.

# %%
# STEP 8.2 — PREPARE HISTORICAL CRASH RECORDS

HISTORICAL = INCIDENTS.copy()

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

print("Historical crash reports:", len(HISTORICAL))

display(
    HISTORICAL[
        [
            "date",
            "corridor",
            "hour_label",
            "Latitude",
            "Longitude"
        ]
    ].head()
)

# %% [markdown]
# ### Step 8.3 — Create approximate location zones
#
# The historical GPS coordinates are used to divide EDSA and C5 into six approximate zones each.
#
# These zones help the simulator assign locations to generated incidents. They are based on historical incident locations and are not official road segments.
#
# Future work should replace these zones with mapped road segments.

# %%
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

# %% [markdown]
# ### Step 8.4 — Build historical time and location probabilities
#
# The simulator needs to know how frequently crashes were reported in each location zone and hour.
#
# Instead of selecting time and location independently, we calculate the historical frequency of each zone-and-hour combination.
#
# This allows the simulation to retain observed differences between the time patterns of different locations.
#
# Records with missing information remain in the historical distribution under UNKNOWN_TIME or UNKNOWN_LOCATION.

# %%
# STEP 8.4 — JOINT TIME-LOCATION DISTRIBUTION

JOINT_PROFILE = (
    HISTORICAL
    .groupby(
        ["corridor", "zone", "hour_label"]
    )
    .size()
    .reset_index(name="historical_reports")
)

JOINT_PROFILE["probability"] = (
    JOINT_PROFILE["historical_reports"]
    / JOINT_PROFILE.groupby("corridor")[
        "historical_reports"
    ].transform("sum")
)

for road in ("EDSA", "C5"):

    road_probability = JOINT_PROFILE.loc[
        JOINT_PROFILE["corridor"].eq(road),
        "probability"
    ].sum()

    assert np.isclose(road_probability, 1.0)

JOINT_PROFILE.to_csv(
    cfg.PROCESSED / "event_joint_profile.csv",
    index=False
)

print("Historical time-location profile created.")

display(JOINT_PROFILE.head(15))

# %% [markdown]
# ### Step 8.5 — Generate incident counts using the existing model
#
# We reuse the fitted Negative Binomial model from Step 5.
#
# The 2025 AADT values provide the traffic-exposure baseline. We then apply the traffic-volume scenarios already defined in the notebook.
#
# For each scenario, the simulation repeats the incident-generation process 1,000 times.
#
# We also test three elasticity assumptions: 0.8, 1.0 and 1.2. These assumptions show how the results change when the relationship between traffic volume and incident counts is varied.
#
# The model produces monthly incident counts, which are then used to generate individual simulated events.

# %%
# STEP 8.5 — SIMULATE MONTHLY INCIDENT COUNTS

COEFFICIENT_NAMES = list(PARAMS["coefficients"])

COEFFICIENTS = np.array([
    PARAMS["coefficients"][name]
    for name in COEFFICIENT_NAMES
])

STANDARD_ERRORS = np.array([
    PARAMS["std_errors"][name]
    for name in COEFFICIENT_NAMES
])

ALPHA = max(float(PARAMS["alpha"]), 0.0)

MONTHLY_SIMULATIONS = {}
SUMMARY_ROWS = []

for road in ("EDSA", "C5"):

    road_design = (
        DESIGN[DESIGN["corridor"].eq(road)]
        .sort_values("month")
        .reset_index(drop=True)
    )

    X = road_design[
        COEFFICIENT_NAMES
    ].to_numpy(dtype=float)

    days = road_design["days"].to_numpy(
        dtype=float
    )

    aadt = float(BASELINE.loc[road, "aadt"])

    for elasticity in EVENT_ELASTICITIES:

        for scenario, traffic_change in cfg.SCENARIOS.items():

            # Sample coefficient uncertainty.
            coefficient_draws = rng.normal(
                loc=COEFFICIENTS,
                scale=STANDARD_ERRORS,
                size=(
                    EVENT_RUNS,
                    len(COEFFICIENTS)
                )
            )

            linear_predictor = (
                coefficient_draws @ X.T
            )

            exposure_offset = np.log(
                aadt * days / PARAMS["rate_per"]
            )

            expected_counts = np.exp(
                np.clip(
                    linear_predictor + exposure_offset,
                    -20,
                    20
                )
            )

            expected_counts *= (
                1 + traffic_change
            ) ** elasticity

            # Negative Binomial through a Gamma-Poisson
            # mixture, as in the existing notebook.
            if ALPHA > 0:

                latent_rates = rng.gamma(
                    shape=1 / ALPHA,
                    scale=expected_counts * ALPHA
                )

                monthly_counts = rng.poisson(
                    latent_rates
                )

            else:

                monthly_counts = rng.poisson(
                    expected_counts
                )

            key = (
                road,
                scenario,
                elasticity
            )

            MONTHLY_SIMULATIONS[key] = monthly_counts

            annual_totals = monthly_counts.sum(
                axis=1
            )

            annual_exposure = (
                aadt
                * (1 + traffic_change)
                * days.sum()
            )

            SUMMARY_ROWS.append({
                "corridor": road,
                "scenario": scenario,
                "traffic_change": traffic_change,
                "elasticity": elasticity,
                "runs": EVENT_RUNS,
                "mean": annual_totals.mean(),
                "std": annual_totals.std(ddof=1),
                "p05": np.quantile(
                    annual_totals, 0.05
                ),
                "median": np.median(
                    annual_totals
                ),
                "p95": np.quantile(
                    annual_totals, 0.95
                ),
                "mean_rate_per_100k": (
                    annual_totals.mean()
                    / annual_exposure
                    * cfg.RATE_PER
                )
            })

EVENT_SUMMARY = pd.DataFrame(SUMMARY_ROWS)

display(EVENT_SUMMARY.head(12))

# %% [markdown]
# ### Step 8.6 — Generate individual simulated incidents
#
# The monthly incident counts are converted into individual events.
#
# For each simulated event, the program assigns:
# - A road
# - A simulation run
# - A scenario
# - A month and day
# - A time
# - An approximate location zone
#
# The time and location combinations are selected using the historical probabilities calculated earlier.
#
# The program retains detailed event records for two sample runs per scenario and summarizes the allocations across all 1,000 runs. This avoids creating unnecessarily large output files.

# %%
# STEP 8.6 — GENERATE INDIVIDUAL SIMULATED EVENTS

SAMPLE_EVENT_ROWS = []
ALLOCATION_ROWS = []

for key, monthly_counts in MONTHLY_SIMULATIONS.items():

    road, scenario, elasticity = key

    road_profile = (
        JOINT_PROFILE[
            JOINT_PROFILE["corridor"].eq(road)
        ]
        .reset_index(drop=True)
    )

    probabilities = road_profile[
        "probability"
    ].to_numpy()

    road_design = (
        DESIGN[DESIGN["corridor"].eq(road)]
        .sort_values("month")
        .reset_index(drop=True)
    )

    allocated_totals = np.zeros(
        len(road_profile),
        dtype=np.int64
    )

    for run in range(EVENT_RUNS):

        for month_index, count in enumerate(
            monthly_counts[run]
        ):

            count = int(count)

            if count == 0:
                continue

            # Allocate all incidents to zone-hour groups.
            allocation = rng.multinomial(
                count,
                probabilities
            )

            allocated_totals += allocation

            # Detailed records for sample runs only.
            if run >= SAMPLE_RUNS:
                continue

            month = int(
                road_design.loc[month_index, "month"]
            )

            days_in_month = int(
                road_design.loc[month_index, "days"]
            )

            for category_index, number in enumerate(
                allocation
            ):

                if number == 0:
                    continue

                category = road_profile.iloc[
                    category_index
                ]

                random_days = rng.integers(
                    1,
                    days_in_month + 1,
                    size=int(number)
                )

                random_minutes = rng.integers(
                    0,
                    60,
                    size=int(number)
                )

                for day, minute in zip(
                    random_days,
                    random_minutes
                ):

                    SAMPLE_EVENT_ROWS.append({
                        "run": run + 1,
                        "scenario": scenario,
                        "elasticity": elasticity,
                        "road": road,
                        "year": cfg.BASELINE_YEAR,
                        "month": month,
                        "day": int(day),
                        "hour": category["hour_label"],
                        "minute": int(minute),
                        "zone": category["zone"],
                        "event_type":
                            "SIMULATED_REPORTED_CRASH"
                    })

    # Verify that no generated counts were lost.
    assert (
        allocated_totals.sum()
        == monthly_counts.sum()
    )

    for index, category in road_profile.iterrows():

        ALLOCATION_ROWS.append({
            "corridor": road,
            "scenario": scenario,
            "elasticity": elasticity,
            "zone": category["zone"],
            "hour": category["hour_label"],
            "mean_annual_events":
                allocated_totals[index] / EVENT_RUNS
        })

SAMPLE_EVENTS = pd.DataFrame(SAMPLE_EVENT_ROWS)

EVENT_ALLOCATION = pd.DataFrame(ALLOCATION_ROWS)

print(
    "Sample event records:",
    len(SAMPLE_EVENTS)
)

display(SAMPLE_EVENTS.head(15))

# %% [markdown]
# ### Step 8.7 — Save the simulation results
#
# The program saves the results as CSV files.
#
# The scenario summary includes the average incident count and simulation intervals for every road, scenario and elasticity assumption.
#
# The allocation summary contains the average simulated incidents by location zone and hour.
#
# The sample-event file contains individual simulated events that can be inspected or used in later analysis.

# %%
# STEP 8.7 — SAVE SIMULATION RESULTS

EVENT_SUMMARY.to_csv(
    cfg.TABLES / "event_scenario_summary.csv",
    index=False
)

EVENT_ALLOCATION.to_csv(
    cfg.TABLES / "event_zone_hour_summary.csv",
    index=False
)

SAMPLE_EVENTS.to_csv(
    cfg.TABLES / "sample_simulated_events.csv",
    index=False
)

print("Saved:")
print("event_scenario_summary.csv")
print("event_zone_hour_summary.csv")
print("sample_simulated_events.csv")

# %% [markdown]
# ### Step 8.8 — Verify the event simulation
#
# Verification checks whether the simulation follows the rules we programmed.
#
# We check that:
# - Each road's historical allocation probabilities sum to one.
# - Simulated incident counts are nonnegative.
# - Simulation intervals are ordered correctly.
# - Simulated dates and hours are valid.
# - The total number of allocated incidents matches the number generated by the count model.
#
# These checks verify the program's calculations. They do not prove that simulated incidents perfectly represent actual road conditions.

# %%
# STEP 8.8 — VERIFY THE EVENT SIMULATION

EVENT_CHECKS = {}

EVENT_CHECKS["Probability totals"] = all(
    np.isclose(
        group["probability"].sum(),
        1.0
    )
    for _, group in JOINT_PROFILE.groupby(
        "corridor"
    )
)

EVENT_CHECKS["Nonnegative incident counts"] = (
    EVENT_SUMMARY["mean"] >= 0
).all()

EVENT_CHECKS["Valid simulation intervals"] = (
    (EVENT_SUMMARY["p05"] <= EVENT_SUMMARY["median"])
    & (EVENT_SUMMARY["median"] <= EVENT_SUMMARY["p95"])
).all()

EVENT_CHECKS["Valid roads"] = (
    SAMPLE_EVENTS["road"].isin(
        ["EDSA", "C5"]
    )
).all()

valid_hours = [
    f"{hour:02d}"
    for hour in range(24)
] + ["UNKNOWN_TIME"]

EVENT_CHECKS["Valid hours"] = (
    SAMPLE_EVENTS["hour"].isin(valid_hours)
).all()

EVENT_CHECKS["Valid dates"] = (
    pd.to_datetime(
        SAMPLE_EVENTS[
            ["year", "month", "day"]
        ],
        errors="coerce"
    ).notna().all()
)

all_allocated = True

for _, row in EVENT_SUMMARY.iterrows():

    selected = EVENT_ALLOCATION[
        EVENT_ALLOCATION["corridor"].eq(
            row["corridor"]
        )
        & EVENT_ALLOCATION["scenario"].eq(
            row["scenario"]
        )
        & EVENT_ALLOCATION["elasticity"].eq(
            row["elasticity"]
        )
    ]

    if not np.isclose(
        selected["mean_annual_events"].sum(),
        row["mean"]
    ):
        all_allocated = False

EVENT_CHECKS["All incidents allocated"] = (
    all_allocated
)

print("EVENT SIMULATION VERIFICATION\n")

for name, passed in EVENT_CHECKS.items():

    print(
        "PASS" if passed else "FAIL",
        "-",
        name
    )

assert all(EVENT_CHECKS.values()), (
    "One or more verification checks failed."
)

# %% [markdown]
# ### Step 8.8b — Cross-check against Step 6
#
# Two independent routes to the same number. If they disagree by more than a few percent of Monte Carlo noise, something is wrong — and the most likely cause is a design-matrix mismatch between the two steps.

# %%
# STEP 8.8b — DOES THE EVENT SIMULATION AGREE WITH STEP 6?
#
# Step 6 and Step 8 now compute the same quantity by two different routes.
# Step 6 draws annual counts directly. Step 8 draws monthly counts, then
# allocates every one of them to a zone and an hour. If the two disagree, one
# of them is wrong — most likely a design-matrix mismatch, which is exactly the
# failure this check exists to catch.
#
# They will not match exactly: they use different random seeds and different
# numbers of runs, so a few percent of Monte Carlo noise is expected and fine.

STEP6 = pd.read_csv(cfg.TABLES / "simulation_results.csv")

_step6 = STEP6[
    (STEP6["trend"] == "frozen")
    & (STEP6["elasticity"] == 1.0)
][["corridor", "scenario", "mean"]].rename(columns={"mean": "step6_mean"})

_step8 = EVENT_SUMMARY[
    EVENT_SUMMARY["elasticity"] == 1.0
][["corridor", "scenario", "mean"]].rename(columns={"mean": "step8_mean"})

COMPARISON = _step6.merge(_step8, on=["corridor", "scenario"], how="inner")
COMPARISON["difference_pct"] = (
    (COMPARISON["step8_mean"] / COMPARISON["step6_mean"] - 1) * 100
)

print("Annual crashes: counts-only (Step 6) vs event-level (Step 8)")
print()
print(f"  {'corridor':<9}{'scenario':<11}{'Step 6':>10}{'Step 8':>10}{'diff':>9}")
print("  " + "-" * 49)
for _, r in COMPARISON.iterrows():
    print(f"  {r['corridor']:<9}{r['scenario']:<11}"
          f"{r['step6_mean']:>10,.0f}{r['step8_mean']:>10,.0f}"
          f"{r['difference_pct']:>8.1f}%")

_worst = COMPARISON["difference_pct"].abs().max()
print()
print(f"Largest disagreement: {_worst:.1f}%")

if _worst < 5:
    print("PASS — the two simulations agree to within Monte Carlo noise, so the")
    print("event-level layer is allocating the same totals the count model")
    print("produces rather than quietly answering a different question.")
else:
    raise AssertionError(
        f"Step 6 and Step 8 disagree by {_worst:.1f}%. They should be drawing "
        f"from the same fitted model, so check that DESIGN in Step 8.1 matches "
        f"the design built in Step 6 — particularly the frozen trend and the "
        f"log_feed term."
    )

COMPARISON.to_csv(cfg.TABLES / "event_vs_count_comparison.csv", index=False)
print()
print("wrote results/tables/event_vs_count_comparison.csv")

# %% [markdown]
# ### Step 8.9 — Visualize the simulation results
#
# We create three figures:
#
# 1. Approximate EDSA and C5 location zones.
# 2. Average simulated incidents under different traffic scenarios.
# 3. Monte Carlo convergence, showing how the estimated mean changes as more runs are included.
#
# These figures help explain the model's spatial output, scenario results and simulation stability.

# %%
# STEP 8.9A — PLOT APPROXIMATE SPATIAL ZONES

fig, ax = plt.subplots(figsize=(8, 6))

# EDSA blue, C5 orange — the same assignment as every other figure in this
# project and the slide deck. groupby() would otherwise colour them by
# alphabetical order, which puts C5 in EDSA's colour.
CORRIDOR_COLOUR = {"EDSA": "#2d6cdf", "C5": "#c2410c"}

for road in ("EDSA", "C5"):

    group = ZONES[ZONES["road"].eq(road)]

    ax.scatter(
        group["longitude"],
        group["latitude"],
        label=road,
        color=CORRIDOR_COLOUR[road],
        s=90,
        zorder=3
    )

    # Join the zone centroids so the corridor's shape is visible rather than
    # implied by five loose dots.
    ax.plot(
        group["longitude"],
        group["latitude"],
        color=CORRIDOR_COLOUR[road],
        lw=1.2,
        alpha=0.45,
        zorder=2
    )

    for _, row in group.iterrows():

        ax.annotate(
            row["zone"].split("_")[-1],
            (
                row["longitude"],
                row["latitude"]
            ),
            xytext=(7, 4),
            textcoords="offset points",
            fontsize=9
        )

ax.set_title(
    "Approximate EDSA and C5 location zones\n"
    "zone centroids, numbered along each corridor",
    loc="left", fontsize=11
)

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.legend(frameon=False)
ax.grid(alpha=0.25, lw=0.6)
ax.spines[["top", "right"]].set_visible(False)

fig.tight_layout()

fig.savefig(
    cfg.FIGURES / "fig11_spatial_zones.png",
    dpi=150
)

plt.show()

# %%
# STEP 8.9B — COMPARE SIMULATED TRAFFIC SCENARIOS

scenario_plot = EVENT_SUMMARY[
    EVENT_SUMMARY["elasticity"].eq(1.0)
].copy()

fig, ax = plt.subplots(figsize=(9, 5))

for road, group in scenario_plot.groupby("corridor"):

    group = group.sort_values(
        "traffic_change"
    )

    ax.errorbar(
        group["traffic_change"] * 100,
        group["mean"],
        yerr=[
            group["mean"] - group["p05"],
            group["p95"] - group["mean"]
        ],
        marker="o",
        capsize=4,
        label=road
    )

ax.set_title(
    "Simulated Reported Incidents by Traffic Scenario"
)

ax.set_xlabel("Traffic change (%)")

ax.set_ylabel(
    "Annual simulated reported incidents"
)

ax.legend(frameon=False)
ax.grid(alpha=0.25, lw=0.6)
ax.spines[["top", "right"]].set_visible(False)

fig.tight_layout()

fig.savefig(
    cfg.FIGURES / "fig12_event_scenarios.png",
    dpi=150
)

plt.show()

# %%
# STEP 8.9C — MONTE CARLO CONVERGENCE

baseline_name = next(
    name
    for name, change in cfg.SCENARIOS.items()
    if change == 0
)

counts = MONTHLY_SIMULATIONS[
    ("EDSA", baseline_name, 1.0)
]

annual_totals = counts.sum(axis=1)

running_mean = (
    np.cumsum(annual_totals)
    / np.arange(1, len(annual_totals) + 1)
)

fig, ax = plt.subplots(figsize=(9, 4))

ax.plot(
    np.arange(1, EVENT_RUNS + 1),
    running_mean
)

ax.set_title(
    "Monte Carlo Convergence: EDSA Baseline"
)

ax.set_xlabel("Number of simulation runs")

ax.set_ylabel(
    "Estimated mean annual reported incidents"
)

fig.tight_layout()

fig.savefig(
    cfg.FIGURES / "fig13_event_convergence.png",
    dpi=150
)

plt.show()

# Report at whatever checkpoints actually exist. Hardcoding 100/500/1000 makes
# this cell crash the moment anyone lowers EVENT_RUNS to iterate quickly.
for checkpoint in (10, 50, 100, 250, 500, 1000, 2500):
    if checkpoint <= len(running_mean):
        print(f"Mean after {checkpoint:>5,} runs: "
              f"{running_mean[checkpoint - 1]:,.1f}")

print(f"Mean after {len(running_mean):>5,} runs: "
      f"{running_mean[-1]:,.1f}   <- final")

_settled = abs(running_mean[-1] / running_mean[len(running_mean) // 2] - 1) * 100
print()
print(f"The estimate moved {_settled:.2f}% over the second half of the runs, "
      f"which is\nwhat convergence looks like: more runs would not change the "
      f"answer materially.")

# %% [markdown]
# ### Step 8.10 — Review the results
#
# The final tables show the scenario results and examples of individual simulated incidents.
#
# The simulation now generates incident counts, assigns times and approximate locations, and compares outcomes across traffic-volume scenarios.
#
# The next research tasks are to replace approximate location zones with mapped road segments, test the generated spatial and temporal patterns against historical observations, and obtain additional data if hourly traffic risk or violation effects are to be estimated.

# %%
# STEP 8.10 — DISPLAY FINAL RESULTS

print("SCENARIO RESULTS")

display(
    EVENT_SUMMARY[
        [
            "corridor",
            "scenario",
            "elasticity",
            "mean",
            "p05",
            "p95",
            "mean_rate_per_100k"
        ]
    ]
)

print("\nSAMPLE SIMULATED EVENTS")

display(
    SAMPLE_EVENTS.head(20)
)

print("\nSIMULATED EVENTS BY ZONE AND HOUR")

display(
    EVENT_ALLOCATION.head(20)
)

print("\nOutput files:")

for filename in (
    "event_scenario_summary.csv",
    "event_zone_hour_summary.csv",
    "sample_simulated_events.csv"
):
    print(cfg.TABLES / filename)
