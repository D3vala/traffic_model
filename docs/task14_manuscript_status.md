# Task 14 manuscript status

No manuscript or manuscript draft was found in the repository. The archived presentation script and the project manual are not manuscript text. Please supply the manuscript text or numeric statements before a section-by-section changes list can be drafted. No manuscript content or affected section names are inferred here.

## Reviewer requests that could not be fulfilled with the available data

1. True capture rates for EDSA and C5: no matched authoritative registry exists. Only hypothetical sensitivity tables were produced (reporting_bias_sensitivity.csv).
2. A severity model: the incident feed has no consistent severity measure (severity_check_notes.txt). Severity remains unmodeled.
3. The true Jan-Feb 2020 traffic volume: the 2019-AADT version is a sensitivity test only.
4. Out-of-sample 90% predictive interval coverage for the main model: no covariance matrix from the 14-month training fit was saved, so coverage is reported as N/A (holdout_model_comparison.csv).
5. Day-of-week collision risk: no day-specific traffic exposure exists. The day-of-week profile is descriptive only.
6. Measured hourly reporting rates: none exist. The +/-10%, +/-20% and +/-30% changes are hypothetical.
7. PSA collection system and completeness facts: not documented in project files. The PSA source citation is pending a manual check.

## Results to compare against the manuscript

The following review findings were supplied for manuscript revision. They are findings and wording constraints, not quotations from manuscript sections. No manuscript text has been seen.

- Baseline expected annual counts: EDSA 3,351 (p05-p95 simulation interval 2,889-3,887) and C5 1,302 (1,088-1,542). Earlier figures were 3,376 and 1,334.
- Largest observed hourly shares: EDSA 7 AM in about 76% of day-level bootstrap draws (8 AM competes); C5 3 PM in about 91% (4 PM competes). Under hypothetical hourly reporting changes the EDSA peak is fragile.
- Observed EDSA/C5 rate ratio is 1.90 (95% CI 1.66-2.15). Reversal needs EDSA reporting to be about 1.9 times as complete as C5 reporting.
- Hourly and zone distributions differ between the first and last nine months by more than random split-half noise. The halves cover different seasons.
- Holdout (4 test months): the main model beats the baselines for EDSA but not for C5. C5 is underpredicted in 4 of 4 months. Using the 2019 AADT for Jan-Feb 2020 changes errors substantially, which is a sensitivity result and not the true 2020 volume.
- Month-aware allocation is not supported by 18 months of data (no evidence for a month effect).
- Day of week: Tuesday has the largest share of reports on both corridors; descriptive only.
- Event simulation: 6 zones per corridor, 1,000 runs, elasticities 0.8, 1.0, 1.2; largest Step 6 vs Step 8 difference 0.90%.
