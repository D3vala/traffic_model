# Member 3 task brief (conference revision)

Commit this file as `docs/member3_task_brief.md`.

Part 1 is the brief as written by the group. Part 2 is coordinator clarifications
added after reading the notebook. If the two ever conflict, raise it with the
group instead of choosing silently.

---

## Part 1. The brief

I am Coding Member 3 of a three-person group revising a conference paper and Python/Jupyter project about social-media-reported traffic collisions on EDSA and C5.

The first coding member has already completed part of the conference revision.

Before changing anything, read:

`docs/member3_handoff_from_member1.md`

Use these current files as the authoritative starting point:

`notebooks/metro_manila_traffic_simulation.ipynb`

`src/event_level_simulation.py`

The main notebook already contains a new Step 5.1 that performs the following work for me:

- explicit monthly AADT x days exposure alignment;
- current two-harmonic model;
- reduced one-harmonic model;
- January-February 2020 sensitivity using 2019 AADT;
- current calendar-year AADT version;
- full coefficient table;
- fitted coefficient covariance matrix;
- month-level holdout predictions for all four model/exposure variants.

Do NOT recreate or refit those four variants unless there is an actual implementation error.

After running the updated notebook, use:

`results/tables/member3_model_variant_holdout_predictions.csv`

and

`results/tables/member3_model_variant_holdout_summary.csv`

for the C5 holdout analysis.

The 2019-AADT version is only a sensitivity test. Do not describe it as the true January-February 2020 traffic volume.

Do not promote the reduced one-harmonic model or any sensitivity version to the final model. The group will decide that after all reviewer checks are complete.

My assigned tasks are below.

### 1. DIFFERENTIAL CORRIDOR REPORTING SENSITIVITY

The MMDA social-media incident feed does not have a matched authoritative EDSA/C5 registry from which true capture rates can be estimated.

Do not invent capture rates.

Let:

cE = hypothetical EDSA reporting fraction

cC = hypothetical C5 reporting fraction.

Use:

corrected rate ratio = observed EDSA/C5 rate ratio x cC/cE.

Calculate how large a difference in relative reporting between EDSA and C5 would be required to reverse the observed EDSA-greater-than-C5 ordering.

Test several clearly labelled hypothetical reporting differences.

These are sensitivity assumptions, not corrected true rates.

Save:

`results/tables/reporting_bias_sensitivity.csv`

Also write:

`results/logs/reporting_bias_notes.txt`

### 2. TIME-OF-DAY REPORTING SENSITIVITY

The observed hourly collision pattern may be affected by differences in social-media reporting activity.

Test hypothetical hourly reporting changes of approximately:

+-10%
+-20%
+-30%

Check how often the observed EDSA 7 AM and C5 3 PM peak-hour conclusions remain unchanged.

Do not describe these hypothetical percentages as measured reporting rates.

Save:

`results/tables/hour_reporting_sensitivity.csv`

### 3. MONTH-AWARE EVENT ALLOCATION

The current event-level implementation preserves:

corridor x zone x hour

but does not condition the allocation distribution on month.

Create a revised allocation method that preserves:

corridor x month-of-year x zone x hour.

Because an 18-month sample will create sparse month-zone-hour cells, do not simply use unsmoothed raw proportions.

Use a simple documented smoothing or shrinkage method toward the existing corridor-wide zone x hour distribution.

The method should ensure:

- probabilities sum to one for every relevant corridor/month;
- no simulated event is lost;
- sparse historical cells do not automatically create unreasonable zero probabilities;
- the original six-zone definition is retained.

Export:

`results/processed/monthly_zone_hour_profile.csv`

Do not claim this creates official road-segment risk.

### 4. ZONE BOUNDARIES AND ZONE DESCRIPTION

Export:

`results/processed/zone_boundaries.csv`

Columns should include at least:

corridor
zone
historical_reports
projected_min
projected_max
centroid_lat
centroid_lon

The six zones must continue to be described as approximate analytical groups based on historical coordinates, not official MMDA or engineering road segments.

Do not call them hotspots merely because simulated counts differ.

### 5. PEAK-HOUR UNCERTAINTY

The manuscript currently reports EDSA's largest observed hourly share at approximately 7 AM and C5's at approximately 3 PM.

Add bootstrap uncertainty.

Repeatedly resample the historical observations, or suitable historical blocks if that is more appropriate, and calculate the hourly distribution again.

Report:

- percentage of bootstrap samples where EDSA 7 AM is the largest hourly share;
- percentage where C5 3 PM is the largest;
- confidence intervals for hourly shares;
- strongest competing hours.

Save:

`results/tables/peak_hour_uncertainty.csv`

Use wording such as:

"7 AM had the largest observed EDSA hourly share"

and not:

"7 AM is the most dangerous EDSA hour."

### 6. TEMPORAL PATTERN STABILITY

Split the 18-month estimation window into:

first 9 months
last 9 months.

Compare:

- hourly distributions;
- zone distributions;
- joint zone x hour distributions.

Report whether the main spatial and hourly patterns remain broadly similar or materially change.

Save:

`results/tables/temporal_pattern_sensitivity.csv`

Do not hide instability if it is found.

### 7. DAY-OF-WEEK DESCRIPTION

Use the existing incident Date field to create a descriptive day-of-week profile.

Save:

`results/tables/day_of_week_profile.csv`

This is descriptive only.

Do not call it day-of-week collision risk because matching day-specific traffic exposure is unavailable.

### 8. SEVERITY CHECK

Check whether the incident dataset contains a consistent and defensible severity variable.

If it does not, do not create a severity model.

Document instead that severity remains unmodeled because the available incident feed does not provide a consistent severity measure.

### 9. HOLDOUT BENCHMARKS

Keep the existing temporal split:

first 14 months = training

last 4 months = future test.

Do not recreate the four model/exposure variants already supplied by Member 1.

Instead add these simple benchmark methods:

- historical corridor mean;
- seasonal-naive prediction using the corresponding calendar month from the previous year;
- exposure-only corridor model.

Compare those benchmarks with the current main Negative Binomial model.

Report by corridor:

MAE
RMSE
MAPE
deviance
mean signed bias
90% predictive interval coverage where applicable.

Save:

`results/tables/holdout_model_comparison.csv`

and:

`results/tables/holdout_month_level.csv`

### 10. C5 UNDERPREDICTION

Use:

`results/tables/member3_model_variant_holdout_predictions.csv`

and:

`results/tables/member3_model_variant_holdout_summary.csv`

Do not refit those variants.

Report:

- how many held-out C5 months are underpredicted;
- mean signed C5 error;
- largest-error months;
- whether the 2019-AADT sensitivity reduces the error;
- whether the one-harmonic model reduces the error;
- how the main model compares with historical-mean, seasonal-naive and exposure-only baselines.

Save:

`results/tables/c5_holdout_diagnostics.csv`

Do not claim a cause for the C5 underprediction unless supported by the results.

### 11. PSA/MMDA COMPARISON

Create a structured comparison between:

MMDA social-media-reported collision feed

and

PSA Metro Manila road-crash statistics.

Compare:

outcome definition
geographic coverage
collection system
time resolution
known completeness
role in this study

Save:

`results/tables/psa_mmda_comparison.csv`

The PSA series must remain an external contextual comparison.

Do not describe it as direct validation of EDSA or C5 counts.

### 12. VALIDATION

Extend validation so that the new allocation method checks:

- probabilities sum to one;
- all simulated events are allocated;
- dates remain valid;
- hours remain valid;
- corridors remain EDSA/C5 only;
- sample-run restrictions remain correct;
- month-aware allocation does not change the count model totals.

Save:

`results/logs/event_allocation_validation.txt`

and:

`results/logs/holdout_revision_summary.txt`

### 13. FILE SAFETY

Do not manually modify files under:

`data/raw/`

Do not overwrite the group's only authoritative notebook while developing.

Create a temporary working copy:

`notebooks/work/carl_validation_revision.ipynb`

If the event-level Python file needs substantial changes, work first in:

`src/carl_event_level_simulation_work.py`

When the work is finished, provide the changed cells/code separately so the group can review and merge them into the authoritative files.

### 14. FINAL DELIVERABLES

Return:

- the modified working notebook;
- any modified event-allocation Python code;
- all requested CSV files;
- all requested validation logs;
- a short explanation of each result;
- a list of statements or numerical values in the current manuscript that must change;
- a list of any reviewer requests that could not be fulfilled because the required data does not exist.

Use plain academic language.

Do not invent data.

Do not claim causation.

Do not treat social-media reports as a complete crash registry.

Do not describe 2025 scenarios as forecasts.

Do not change Member 1's main model specification without group approval.

---

## Part 2. Coordinator clarifications (repo and workflow)

These do not change the brief. They record decisions made while setting up the repo.

**Paths and branches**

- Run everything from the repository root. The notebook sets `PROJECT_DIR = Path.cwd()` locally, so starting Jupyter from `notebooks/` would write to `notebooks/results/` and miss `data/`.
- Never commit to `main`. All work goes to feature branches and then into `integration/m3-revision` by pull request.
- Working scripts go in `src/work/` (named `carl_event_level_simulation_work.py` for allocation, `m3_<task>.py` for the rest). The notebook is assembled from them at the end, not edited in parallel.
- `app/` and `scripts/` are not touched in this work.
- Write all text files with `encoding="utf-8"`. Earlier Windows runs produced garbled dashes in logs.

**Zones (tasks 3, 4, 12)**

Zones come from Step 8.3 of the notebook, unchanged. For each corridor:

1. Keep rows with valid coordinates (`geo_valid`).
2. Convert to km (latitude x 111, longitude x 108) and centre on the corridor mean.
3. Project onto the first SVD axis; flip the sign if `axes[0][0] < 0`.
4. Rank with `method="first"` and split with `pd.qcut` into 6 equal-count groups.
5. Name them `EDSA_ZONE_01` to `06` and `C5_ZONE_01` to `06`.

Rows without valid coordinates are labelled `UNKNOWN_LOCATION`, and rows without a valid hour `UNKNOWN_TIME`. These are part of the existing joint profile. Keep them so no event is lost, and build the probability support from the categories that actually occur instead of assuming 6 x 24 = 144 cells.

`projected_min` and `projected_max` are the minimum and maximum projected value in each zone, in kilometres along the corridor's centred principal axis. They are not distances from any named landmark. Name the corridor column `corridor` (the notebook's own zone table calls it `road`).

**Month-aware allocation (task 3)**

Shrink toward the existing corridor-wide profile, not toward a uniform distribution:

```
p(z,h | corridor c, month m) = ( n[c,m,z,h] + kappa * p0[c,z,h] ) / ( N[c,m] + kappa )
```

`p0` is the current corridor-wide zone x hour probability from Step 8.4. Choose `kappa` by leave-one-month-out likelihood over {10, 25, 50, 100, 250}, and export the full grid result. Document that September to February appear twice in the 18-month window, March to August only once (2019), so month-of-year is confounded with year and trend.

Leave Step 8.5 count simulation untouched (`default_rng(RANDOM_SEED + 800)`). Change only the Step 8.6 allocation. Counts then equal Step 8.5 exactly by construction. The existing Step 8 versus Step 6 comparison keeps its 5% gate; do not claim zero deviation against Step 6.

**Validation extras (task 12)**

- Sample events exist only for runs 1 and 2 at elasticity 1.0 (the notebook condition is `run >= SAMPLE_RUNS or elasticity != 1.0`).
- Event days are valid for the month's number of days.
- Hours are 00 to 23 or `UNKNOWN_TIME`.

**Dependencies**

- Tasks 5, 6, 7, 8 and 11 need only `incidents_clean.csv` and the raw data and can start immediately.
- Tasks 1, 2, 9 and 10 need the baseline notebook run and the `member3_*` tables.
- Task 12 needs task 3 and 4 outputs.

**Wording**

Allowed: "approximate analytical zones", "largest observed hourly share", "reported collisions".
Not allowed: "hotspot", "official road segment", "most dangerous hour", "forecast" (for 2025 scenarios), "true January to February 2020 traffic".
