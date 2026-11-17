# MMDA Traffic Incident Simulation

A spatiotemporal Monte Carlo simulation of traffic crashes on EDSA and C5, built
on official NCTS/MMDA traffic counts and the MMDA incident feed, validated against
the PSA road-crash series.

Group 9 – AM3 · BACALLA, M.D.P. · CASTILLO, C.R.M. · CUEVA, X.L.A

## Research question

> Given a road's traffic exposure, how does the expected number of traffic
> incidents change under simulated increases in traffic volume, and how are those
> incidents distributed across the hours of the day?

## Running it

Open `MMDA_Traffic_Simulation.ipynb` and choose Runtime → Run all. On Colab the
first cell offers to upload this project if it is not already on the runtime.

The notebook ships **already executed**, so every result and all ten figures are
visible without running anything. Re-running simply reproduces them.

## Layout

```
MMDA_Traffic_Simulation.ipynb   the whole pipeline, in seven stages
data/                           the four inputs — read, never written
results/
├── figures/                    fig01 – fig13
├── tables/                     model summary, simulation results, event log
├── logs/                       a narrative log per stage
└── processed/                  intermediate tables
```

`data/` is never modified. Every correction happens in code, so the answer to what
was changed about the government's data is the notebook rather than a recollection.
`results/` is entirely generated and can be deleted and rebuilt at any time.

## The four inputs

| File | Rows | Role |
| --- | --- | --- |
| `AADT_2014_2025_combined.csv` | 252 | Exposure denominator |
| `mmda_incidents.csv` | 17,312 | Outcome counts and within-year timing |
| `edsa_violations.csv` | 16 | Descriptive context only |
| `psa_crashes.csv` | 12 | External validation only, never used in estimation |

The sources publish these under different names, and the PSA figures arrive as a
spreadsheet rather than a CSV. The appendix at the end of the notebook rebuilds
`data/` from original downloads, matching files by their columns rather than their
filenames.

## What the data forced

**The window is 18 months, not three years.** The incident feed runs Aug 2018 –
Dec 2020, but July and August 2020 contain zero records — a scraping outage, not a
quiet summer — and April–June collapsed under lockdown. A lockdown and a reporting
outage cannot be separated, so calendar-2020 cannot serve as a denominator. What
survives is September 2018 – February 2020: 18 consecutive complete months.

**The file is not an accident file.** Of 17,312 rows, 3,956 are stalled vehicles
and 569 are roadworks, rallies, vehicle fires and one shooting. Only 12,787 are
collisions. Treating every row as a crash inflates counts by 35%.

**Elasticity is not estimated, deliberately.** AADT is annual, so inside the window
exposure takes three values per corridor, confounded with a time trend and a
lockdown. `log(exposure)` enters as a fixed offset, asserting proportionality, and
departures from it are swept as a scenario parameter (0.8, 1.0, 1.2) rather than
reported as a measurement.

**The outcome is reported incidents.** The MMDA account's posting volume fell
about 18% per year across the window. Feed volume is therefore carried as a model
covariate, and two robustness checks — a placebo series of non-collision reports,
and the EDSA:C5 ratio, which cancels any feed-wide change — separate genuine change
from reporting change.

## Step 8 — event-level simulation

Steps 1–7 answer *how many*. Step 8 answers *where and when*, by taking the counts
the fitted model produces and placing each one on a stretch of road at an hour of
the day.

Each corridor is cut into five zones along its own direction, derived from the
incident GPS coordinates by projecting them onto the corridor's principal axis.
Historical crashes give a joint zone-by-hour probability, and every simulated
incident is drawn from it. The output is an event log — one row per simulated
crash, with road, month, day, hour, minute and zone — rather than a monthly total.

Step 8 creates no incidents of its own; it redistributes the ones Step 5's model
produces. Step 8.8b verifies this by comparing the event-level totals against the
count-only totals from Step 6. The two agree to within 1.6%, which is Monte Carlo
noise, and a larger gap would mean the two steps had drifted apart.

As in Step 5, a zone-hour probability describes where reported crashes fell, not
where a vehicle is most at risk — nothing here observes how much traffic uses a
given zone at a given hour.

**Not yet in the event layer:** day of week (simulated days are drawn uniformly
within the month, so the real weekday/weekend pattern is not reproduced), vehicle
involvement from the `Involved` field, vehicle-mix scenarios, and a
violation-scenario interface. These are extensions the architecture already
supports, not defects in what is built.

## What the model achieves

Four independent things had to go right, and each could have failed.

**It generalises.** Fitted on the first fourteen months and asked to predict four
it had never seen, it came within 15.9% on EDSA — from nine parameters estimated
on twenty-eight observations. On C5 the entire error is systematic and the scatter
is zero: every held-out month is under-predicted, by a growing amount, because the
C5 increase accelerated after the training cut-off. A model that is precisely low
for an identifiable reason is a better result than one that is randomly wrong, and
it means the C5 baseline is conservative rather than fragile.

**Two independent implementations agree.** Step 6 draws annual counts directly.
Step 8 draws monthly counts and allocates every one to a zone and an hour. They
were coded separately and agree to within 1.6% across all eight corridor-scenario
pairs.

**It survives an outside series it never saw.** PSA police records are excluded
from estimation entirely, so their corroboration of the 2019 level and the 46.6%
2020 collapse is evidence rather than circularity.

**The C5 finding holds under every specification tried.** No reporting control,
the endogenous one, and the exogenous one all put C5 between +28% and +47% per
year. It survives the placebo series, survives the corridor-ratio test, and is
understated on two independent grounds — it rose while the feed was getting
quieter, and the holdout shows the fitted trend is too shallow.

## Validation

34 automated checks, all passing. No check recomputes a result using the code that
produced it; each either recomputes from the raw file by a different route or tests
against the PSA series, which is held out of estimation entirely.
