# Re-run record — Member 3 revision restructure

- **Date and time:** 2026-11-20 04:59:31 +08:00
- **Repository:** `C:\Users\Lenovo\Documents\traffic_simulation`
- **Branch:** `integration/m3-revision` (no worktrees)
- **Commit at start of re-run:** `3cdad5d78d759f4fcd7a45d5b27e33f94d92821f`
- **Environment:** PowerShell; `$env:PROJECT_DIR=(Get-Location).Path`; `$env:PYTHONUTF8="1"`

## Package versions

| Component | Version |
|---|---|
| Python | 3.14.7 |
| pandas | 3.1.1 |
| numpy | 2.5.2 |
| statsmodels | 0.15.0 |
| scipy | 1.18.1 |

## Exact commands executed

```powershell
git pull                    # no upstream configured; completed with explicit ref below
git pull origin integration/m3-revision

$env:PROJECT_DIR=(Get-Location).Path
$env:PYTHONUTF8="1"

# Step 0
git status -sb
git ls-files src/work notebooks/work
python build_notebook.py --output C:\Users\Lenovo\AppData\Local\Temp\opencode\m3_rebuilt_notebook.ipynb

# Step 1
python -m jupyter nbconvert --to notebook --execute notebooks/metro_manila_traffic_simulation.ipynb --output-dir notebooks/executed --output metro_manila_traffic_simulation_executed.ipynb --ExecutePreprocessor.timeout=3600

# Step 2
git status --short
git diff --ignore-cr-at-eol --stat

# Step 3
python src/experiments/month_aware_allocation_test.py

# Step 4
python src/revision_checks/m3_1.py
python src/revision_checks/m3_2.py
python src/revision_checks/m3_5.py
python src/revision_checks/m3_6.py
python src/revision_checks/m3_7.py
python src/revision_checks/m3_8.py
python src/revision_checks/m3_9.py
python src/revision_checks/m3_10.py
python src/revision_checks/m3_11.py
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/revision_checks_runner.ipynb --ExecutePreprocessor.timeout=3600

# Step 5
git diff --ignore-cr-at-eol --stat -- results
```

## Step 0 — preconditions

| Check | Result |
|---|---|
| `git status -sb` | `## integration/m3-revision` — clean |
| `git ls-files src/work notebooks/work` | empty |
| `src/revision_checks/` exists | True |
| `src/experiments/month_aware_allocation_test.py` exists | True |
| `notebooks/revision_checks_runner.ipynb` exists | True |
| `archive/07_event_simulation.py` exists | False (`archive/` holds `legacy_07_event_simulation_5zone_500run.py`) |
| `python build_notebook.py --output <temp>` byte-identical to notebook | `fc /b`: "no differences encountered", exit 0; both SHA-256 `B2C432FDECFAD1566DFCEC9...` |

`git pull` reported "There is no tracking information for the current branch"; the pull was completed with the explicit refspec (`git pull origin integration/m3-revision`) → "Already up to date."

## Step 1 — main notebook execution (no `--inplace`)

`EVENT_CHECKS` output (every PASS/FAIL line):

```
EVENT SIMULATION VERIFICATION

PASS - Probability totals
PASS - Nonnegative incident counts
PASS - Valid simulation intervals
PASS - Valid roads
PASS - Valid hours
PASS - Valid dates
PASS - All incidents allocated
```

No FAIL lines. The conservation assert (`assert all(EVENT_CHECKS.values())`, cell 49 line 84) raised no error: the executed notebook contains zero error outputs.

Step 6 vs Step 8 comparison table:

```
Annual crashes: counts-only (Step 6) vs event-level (Step 8)

  corridor scenario       Step 6    Step 8     diff
  -------------------------------------------------
  EDSA     baseline        3,351     3,335    -0.5%
  EDSA     plus_10         3,679     3,675    -0.1%
  EDSA     plus_20         4,007     3,999    -0.2%
  EDSA     plus_30         4,345     4,333    -0.3%
  C5       baseline        1,302     1,314     0.9%
  C5       plus_10         1,435     1,439     0.3%
  C5       plus_20         1,563     1,577     0.9%
  C5       plus_30         1,698     1,712     0.8%

Largest disagreement: 0.9%
PASS — the two simulations agree to within Monte Carlo noise.
```

## Step 2 — main-output integrity

`git status --short` after the notebook run:

```
 M notebooks/executed/metro_manila_traffic_simulation_executed.ipynb
 M results/logs/incident_log.txt
 M results/logs/model_log.txt
 M results/logs/preprocessing_log.txt
 M results/logs/simulation_log.txt
 M results/logs/validation_log.txt
 M results/tables/model_summary.txt
```

The six named main Step 8 CSVs (`event_joint_profile.csv`, `event_scenario_summary.csv`, `event_zone_hour_summary.csv`, `event_vs_count_comparison.csv`, `approximate_spatial_zones.csv`, `sample_simulated_events.csv`) show no content change.

Timestamp-only differences (`git diff --ignore-cr-at-eol`):

| File | Differing lines |
|---|---|
| `results/logs/incident_log.txt` | `03_incident_analysis.py — run 2026-11-18 09:07:54` → `2026-11-20 04:57:02` |
| `results/logs/model_log.txt` | `04_model.py — run 2026-11-18 09:07:55` → `2026-11-20 04:57:03`; GLM `Date:` `Wed, 18 Nov 2026` → `Fri, 20 Nov 2026`, `Time:` `09:07:55` → `04:57:04` |
| `results/logs/preprocessing_log.txt` | `Generated:` and `Run:` `2026-11-18 09:07:53` → `2026-11-20 04:57:01` |
| `results/logs/simulation_log.txt` | `05_simulation.py — run 2026-11-18 09:07:58` → `2026-11-20 04:57:08` |
| `results/logs/validation_log.txt` | `06_validation.py — run 2026-11-18 09:08:00` → `2026-11-20 04:57:09` |
| `results/tables/model_summary.txt` | GLM `Date:`/`Time:` lines only (`18 Nov`/`09:07:55` → `20 Nov`/`04:57:04`) |

## Step 3 — month-aware test

```
CONSTANT CHECK [PASS]: EVENT_RUNS, SAMPLE_RUNS, ZONES_PER_ROAD, EVENT_ELASTICITIES match src/event_level_simulation.py (read via ast, not imported)

Validation Summary Table:
  [PASS] Monthly probabilities sum to 1.0 per corridor/month
  [PASS] Nonnegative simulated incident counts
  [PASS] Simulation intervals ordered (p05 <= median <= p95)
  [PASS] Valid corridors (EDSA, C5)
  [PASS] Valid hours (00-23, UNKNOWN_TIME)
  [PASS] Valid calendar dates in sample events
  [PASS] Valid days for the month
  [PASS] Exact count conservation (no events lost)
  [PASS] Sample events only runs 1-2 at elasticity 1.0
  [PASS] Month-aware monthly counts equal original Step 8.5 counts
  [PASS] Step 6 vs Step 8 agreement (< 5.0% discrepancy gate)

Step 8.5 agreement: maximum absolute difference across all 24 keys and
  six summary statistics = 0 (tolerance 1e-8)
Largest disagreement vs Step 6: 0.90% (Threshold: < 5.00%)
ALL TASKS COMPLETED SUCCESSFULLY
```

`git status --short` after this run shows no change to the main Step 8 outputs (the six CSVs listed in Step 2 remain clean).

## Step 4 — revision checks (last 3 lines of each)

| Script | Last 3 lines | Exit |
|---|---|---|
| `m3_1.py` | `Grid (all hypothetical): 0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 1.904` / `Saved results\tables\reporting_bias_sensitivity.csv (9 rows)` / `Saved results\logs\reporting_bias_notes.txt` | 0 |
| `m3_2.py` | `  worst-case d=0.2: peak 143.2 vs runner-up 183.6 -> REVERSED` / `  worst-case d=0.3: peak 125.3 vs runner-up 198.9 -> REVERSED` / `Saved results\tables\hour_reporting_sensitivity.csv (14 rows)` | 0 |
| `m3_5.py` | `C5: hour 15 largest in 91.0% of draws; otherwise hour 16 wins most often (96.1% of non-15 winning draws)` / `  top winning hours: 15, 16, 08` / `Saved results\tables\peak_hour_uncertainty.csv (48 rows)` | 0 |
| `m3_6.py` | `C5 joint : TVD=0.2955  split-half median=0.2095 p95=0.2335  EXCEEDS noise reference` / `Saved results\tables\temporal_pattern_sensitivity.csv (6 rows)` / `First half = 2018-09..2019-05; last half = 2019-06..2020-02...` | 0 |
| `m3_7.py` | `C5: total=1,680; busiest weekday=Tuesday (17.1% of reports)` / `Saved results\tables\day_of_week_profile.csv (14 rows)` / `Descriptive only. No day-specific traffic exposure is available...` | 0 |
| `m3_8.py` | `Conclusion: no consistent severity variable; severity remains unmodeled.` / `Saved results\tables\severity_variable_audit.csv (28 rows)` / `Saved results\logs\severity_check_notes.txt` | 0 |
| `m3_9.py` | `  C5   exposure_only   MAE=31.681 MAPE=25.67% pois_dev=74.94 nb_dev=24.62 bias=-30.619 cov90=N/A...` / `Saved results\tables\holdout_month_level.csv (32 rows)` / `Saved results\tables\holdout_model_comparison.csv (8 rows)` | 0 |
| `m3_10.py` | `C5 seasonal_naive: main MAE 38.594 vs seasonal_naive 22.250; main higher` / `C5 exposure_only: main MAE 38.594 vs exposure_only 31.681; main higher` / `Saved results\tables\c5_holdout_diagnostics.csv (34 rows)` | 0 |
| `m3_11.py` | `PSA: The PSA series is external context only and cannot independently validate EDSA/C5 counts...` / `Source: 2024 Philippine Statistical Yearbook...` / `Saved results\tables\psa_mmda_comparison.csv` | 0 |

Runner final manifest (all expected files `exists`):

```
exists: results/processed/monthly_zone_hour_profile.csv
exists: results/processed/zone_boundaries.csv
exists: results/logs/event_allocation_validation.txt
exists: results/logs/holdout_revision_summary.txt
exists: results/tables/peak_hour_uncertainty.csv
exists: results/tables/temporal_pattern_sensitivity.csv
exists: results/tables/day_of_week_profile.csv
exists: results/tables/severity_variable_audit.csv
exists: results/logs/severity_check_notes.txt
exists: results/tables/reporting_bias_sensitivity.csv
exists: results/logs/reporting_bias_notes.txt
exists: results/tables/hour_reporting_sensitivity.csv
exists: results/tables/holdout_month_level.csv
exists: results/tables/holdout_model_comparison.csv
exists: results/tables/c5_holdout_diagnostics.csv
exists: results/tables/psa_mmda_comparison.csv
```

## Step 5 — regenerated vs committed outputs

`git diff --ignore-cr-at-eol --stat -- results`:

```
 results/logs/incident_log.txt      | 2 +-
 results/logs/model_log.txt         | 6 +++---
 results/logs/preprocessing_log.txt | 4 ++--
 results/logs/simulation_log.txt    | 2 +-
 results/logs/validation_log.txt    | 2 +-
 results/tables/model_summary.txt   | 4 ++--
 6 files changed, 10 insertions(+), 10 deletions(-)
```

| T1–T11 output | Status |
|---|---|
| `results/processed/monthly_zone_hour_profile.csv` | identical |
| `results/processed/zone_boundaries.csv` | identical |
| `results/logs/event_allocation_validation.txt` | identical |
| `results/logs/holdout_revision_summary.txt` | identical |
| `results/tables/reporting_bias_sensitivity.csv` (T1) | identical |
| `results/logs/reporting_bias_notes.txt` (T1) | identical |
| `results/tables/hour_reporting_sensitivity.csv` (T2) | identical |
| `results/tables/peak_hour_uncertainty.csv` (T5) | identical |
| `results/tables/temporal_pattern_sensitivity.csv` (T6) | identical |
| `results/tables/day_of_week_profile.csv` (T7) | identical |
| `results/tables/severity_variable_audit.csv` (T8) | identical |
| `results/logs/severity_check_notes.txt` (T8) | identical |
| `results/tables/holdout_month_level.csv` (T9) | identical |
| `results/tables/holdout_model_comparison.csv` (T9) | identical |
| `results/tables/c5_holdout_diagnostics.csv` (T10) | identical |
| `results/tables/psa_mmda_comparison.csv` (T11) | identical |

The only differing files are the six timestamp-only files listed in Step 2. `grep src/work results/logs/holdout_revision_summary.txt` → **0 matches**.
