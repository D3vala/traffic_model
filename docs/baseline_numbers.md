# Baseline numbers and run record

This note records the baseline artifacts in the integration checkout. The simulation outputs below are Monte Carlo expected counts and intervals, not observed crash totals. Observed report totals and model-based expected annual counts are different quantities.

## Model parameters and simulation run

`results/processed/model_params.json` records:

```text
family=negbin; alpha=0.0235678391959799; rate_per=100000
estimation_window=2018-09 through 2020-02; n_months=18
baseline_aadt: EDSA=405882, C5=236060
window_rate: C5=1.3284019258412034, EDSA=2.529106550462365
covariance_order: const, is_c5, t, t_x_c5, sin1, cos1, sin2, cos2, log_feed
```

The file contains a 9-by-9 coefficient covariance matrix and notes that it was added for joint coefficient sampling. `results/logs/simulation_log.txt` records a run at 2026-11-18 09:07:58 with 1,000 Monte Carlo runs per scenario.

## Baseline scenario: expected annual counts

From `results/tables/simulation_results.csv`, for `scenario=baseline`, `elasticity=1.0`, and `trend=frozen`:

| Corridor | Monte Carlo mean | p05-p95 simulation interval |
|---|---:|---:|
| EDSA | 3,350.798 (about 3,351) | 2,889–3,887 |
| C5 | 1,302.395 (about 1,302) | 1,088–1,542 |

These are expected counts under the baseline scenario. They are not observed counts. The corresponding observed crash-report totals in the estimation window are 5,429 for EDSA and 1,680 for C5; those cover 18 months and must not be presented as the simulated annual expectations.

The earlier simulation figures supplied for comparison were 3,376 (EDSA) and 1,334 (C5). Relative to those figures, the current means are lower by about 25 and 32, respectively. The current parameter file includes the covariance matrix, but the log does not independently establish that it caused the difference.

## Step 4: expected hourly allocation

`results/logs/simulation_log.txt` reports these baseline expected counts per year by hour:

```text
hr    EDSA     C5
 0     49.6    7.8
 1     23.6    3.9
 2     10.5    7.0
 3     10.5    3.9
 4     44.7    7.0
 5     96.8   14.8
 6    175.0   46.8
 7    259.4   89.0
 8    243.9  100.7
 9    223.4   78.1
10    192.4   66.4
11    183.1   97.6
12    164.4   68.7
13    102.4   47.6
14    180.6   85.9
15    230.8  139.8
16    220.9  119.5
17    181.2   66.4
18    166.3   59.3
19    172.5   53.1
20    135.9   58.6
21     83.8   48.4
22    108.0   13.3
23     91.2   18.7

EDSA: modal hour 07:00; busiest 4 hours carry 28.6% of expected counts
C5: modal hour 15:00; busiest 4 hours carry 35.1% of expected counts
```

## Member 3 holdout file listing

The following files are present under `results/tables/`:

```text
member3_model_variant_holdout_predictions.csv  6,164 bytes
member3_model_variant_holdout_summary.csv      1,372 bytes
```

These are holdout-analysis artifacts, not baseline observed counts.

## Validation log

Filesystem timestamp for `results/logs/validation_log.txt`: **2026-11-18 09:08:00 Asia/Manila** (**2026-11-18 01:08:00 UTC**). This is the file's modification time, distinct from the simulation run timestamp above.

The validation tail reports:

```text
PSA 2020/2019 ratio: 0.534
The MMDA feed cannot produce a comparable 2020 ratio at all, because
July and August hold zero rows. That is precisely why the window stops
at February 2020.
(2019 MMDA crash rows, all corridors, for reference: 7,326)

==========================================================================
SUMMARY
==========================================================================
34 of 34 checks passed.
No check failed.

  wrote results\figures\fig10_psa_crosscheck.png
```
