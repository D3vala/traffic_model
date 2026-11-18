# Baseline numbers and run record

This note records the baseline artifacts present in this checkout on 2026-11-18. The simulation log is the source for the Step 3 baseline counts and Step 4 hourly allocation. Values are expected counts from the Monte Carlo simulation, not observed crash totals or a complete crash registry.

## Step 4 check: hourly allocation

The current `results/logs/simulation_log.txt` reports the following expected baseline counts per year by hour:

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

EDSA: modal hour 07:00, busiest 4 hours carry 28.6% of all crashes
C5: modal hour 15:00, busiest 4 hours carry 35.1% of all crashes
```

The modal hours are descriptive model allocations. The separate bootstrap summary supplied for manuscript review says EDSA 7 AM is the largest in about 76% of draws, with 8 AM competing; C5 3 PM is largest in about 91%, with 4 PM competing. Do not turn either into a claim about the most dangerous hour.

## Model parameter record

The current `results/processed/model_params.json` records:

```text
family=negbin; alpha=0.0235678391959799; rate_per=100000
estimation_window=2018-09 through 2020-02; n_months=18
baseline_aadt: EDSA=405882, C5=236060
window_rate: C5=1.3284019258412034, EDSA=2.529106550462365
covariance_order: const, is_c5, t, t_x_c5, sin1, cos1, sin2, cos2, log_feed
```

The parameter file contains a 9-by-9 coefficient covariance matrix. Its revision note says the matrix was added for joint coefficient sampling. The simulation log identifies the current simulation run as 2026-11-18 09:07:58, with 1,000 Monte Carlo runs per scenario.

## Member 3 holdout file listing

The two Member 3 files present under `results/tables/` are:

```text
member3_model_variant_holdout_predictions.csv  6,164 bytes
member3_model_variant_holdout_summary.csv      1,372 bytes
```

The summary file reports, for the main actual-exposure variant, C5 MAE 38.5944, RMSE 45.1200, MAPE 32.4469%, mean signed bias -38.5944, and 4 of 4 holdout months underpredicted. EDSA reports MAE 40.3485, RMSE 49.7450, MAPE 15.6662%, mean signed bias -26.9609, and 2 of 4 months underpredicted. These are holdout diagnostics and should not be confused with the annual baseline scenario totals below.

## Baseline count comparison and change

The current `results/logs/simulation_log.txt`, Step 3 (trend frozen, elasticity 1.0), reports:

| Corridor | Current baseline mean | Earlier figure supplied for comparison | Difference |
|---|---:|---:|---:|
| EDSA | 3,351 | 3,376 | -25 |
| C5 | 1,302 | 1,334 | -32 |

The changed counts are consistent with the addition/update of Member 1's coefficient covariance matrix and joint parameter draws; the current log itself does not attribute the difference, so treat that cause as the project team's explanation rather than a conclusion independently established by this log. Preserve both the current logged values and the earlier values in the audit trail. Use the current baseline log before changing manuscript numbers.

## Validation tail

The tail of `results/logs/validation_log.txt` is:

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

## Manuscript notes from the current review

These are supplied review findings, recorded here so they are available alongside the baseline evidence:

- Hourly peak uncertainty: EDSA 7 AM leads in about 76% of bootstrap draws; C5 3 PM leads in about 91%, with 8 AM and 4 PM as competitors.
- Temporal pattern stability: hourly and zone patterns shifted between the first and last nine-month halves by more than noise. Wording that implies a stable spatial pattern needs revision.
- Month-aware allocation: unsupported by the 18-month record.
- Severity: unmodeled because there is no consistent severity measure.
- Day of week: Tuesday has the largest share on both corridors; descriptive only.
- Baseline counts: cite 3,351 (EDSA) and 1,302 (C5) for the current run, retaining 3,376 and 1,334 as earlier run values in change notes.

## Scope of changes in this documentation pass

This pass added this documentation file only. No model, parameter, simulation, validation, Member 3, or manuscript source files were edited. The workspace had no tracked changes before this file was added. The recorded artifacts were read from the checkout; the simulation and validation were not rerun for this note.
