# NOTES.md — MMDA Traffic Crash Simulator

Working notes, assumptions, deviations, open questions. Mirrors Section 14 of the build brief.

---

## Phase 0 — Design plan

### Token table (as specified in brief §6.2–6.4, restated for review)

| Group | Tokens |
|---|---|
| Surfaces | `--asphalt #1E2329`, `--asphalt-2 #2B3138`, `--concrete #EEF0F2`, `--paper #FCFCFB`, `--hairline #D9DCDF` |
| Text | `--ink #14181C`, `--ink-2 #52514E`, `--ink-3 #6B6A65`, `--on-dark #F2F4F5`, `--on-dark-2 #B9C0C7` |
| Corridors | `--edsa #2A78D6` / `-ink #1F5FB0` / `-light #5B9BEA`; `--c5 #EB6834` / `-ink #C24A1A` / `-light #F08A5D` |
| Accent | `--paint #F6C945` (lane dashes, slider thumb, focus on dark, selected stop underline, trust border) |
| Spacing / size | 8px grid, content `1120px`, side padding `clamp(16px,4vw,48px)`, section rhythm 72/48px |
| Radii by role | route plates `6px`, panels `14px`, pills/segments `999px` — deliberately different, no shadows anywhere |

### Type roles

| Role | Font | Spec |
|---|---|---|
| H1 | Barlow Condensed 600 | `clamp(2.25rem,5vw,4rem)` / 1.02, sentence case |
| Big numbers | Barlow Condensed 600 | `clamp(3.5rem,8vw,6rem)`, tabular-nums |
| Section headings, panel titles | Barlow Semi Condensed 600 | 1.5rem / 1.2 |
| Body, labels, captions | Barlow 400/500 | 17px / 1.55; captions 15px; nothing below 15px |

Fallbacks: `"Barlow Condensed","Arial Narrow",system-ui,sans-serif` (same pattern for the others). Google Fonts preconnect + `display=swap`.

### Layout, one sentence per section

1. **Hero (asphalt):** credit line and "About the data" link, H1 + subline, then the one bold object — a 96px road strip whose paint-yellow thumb slides between four scenario stops while 40–52 CSS vehicles drift across two lanes (20–26 on screens up to 719px wide) — followed by a live line of AADT × (1 + change).
2. **Reported crashes in one year (concrete):** heading left, assumption segmented control right, then two flat paper panels (route plate, big mean, fixed-axis range plot with Today hairline, plain range sentence, delta + rate) over the count-vs-rate note and the MC-noise footnote.
3. **When and where (concrete):** SVG hour chart (two direct-labelled lines, top-4 dots, peak callout, draggable hour cursor, Play/Pause + All day) beside the schematic zone map (equal-count stretches, hour-scaled circles, required caption); one auto-generated peak sentence and the overnight-noise caveat below.
4. **How far to trust this (paper):** five plain-language caveats with a 3px paint left border, the "34 of 34 checks passed" pill opening a `<details>` of the six check groups, and a `<details>` explaining the simulation in five steps (the only place jargon appears).
5. **Footer (asphalt):** credit, data sources, run details from `meta`, Copy link.

### Review against brief §6.1 "avoid" list

- Cream/serif/terracotta? No — asphalt + concrete + road-paint yellow, condensed sans throughout.
- Identical rounded cards with one soft shadow? No shadows at all; radii differ by role (6/14/999).
- Gradient washes / glassmorphism / blobs? None. The only gradient-like element is the hard-stop repeating dash used for the lane marking (a road marking, not decoration).
- Tracked ALL-CAPS eyebrows, `A · B · C` strings, `→` buttons, mono labels? None; sentence case everywhere, no arrow glyphs.
- Single-word headline emphasis? None — colour emphasis only on numbers ≥ 40px, as specified.
- Fade-up on scroll / hover lift? None; motion only from vehicles (one ambient), tweens, band slides, playback.
- Numbered 01/02/03 markers? None; the caveats are an unnumbered list.
- **Changed during review:** the first draft put a paint-yellow pill around the section heading; removed — yellow is reserved for the slider, lane dashes, focus ring, selected stop, and the trust border.

### One-liner for the memorable moment

The road slider: dragging traffic from Today to +30% increases the vehicle count proportionally while the two panels and the day replay below answer with the same scenario — one control, whole-page consequence. Extra cars enter distributed gaps; equal speeds keep cars from overlapping. Reduced-motion positions remain evenly spaced, and offscreen or hidden-tab traffic pauses.


## Assumptions (made to keep moving, per brief §0)

1. **Project root.** The brief's tree names the root `mmda-crash-simulator/`; this workspace *is* the project root (it holds the notebook, `data/`, `results/`), so `scripts/` and `app/` were created directly under `c:\Users\mearv\Documents\CSS142`.
2. **Notebook run.** `results/` did not exist, so the notebook was executed end-to-end (`python -m nbconvert --execute`) on 2026-09-24. All cells completed without error; validation reports 34 of 34 checks passed. `meta.runDate` is parsed from `results/logs/simulation_log.txt` (the actual run date, 2026-09-24 — the brief's schema example showed 2026-09-23 as a placeholder).
3. **Rates for assumptions 0.8 and 1.2.** `event_scenario_summary.csv` only ran elasticity 1.0 (Step 8 uses `EVENT_ELASTICITIES = [1.0]`). The exported rate for 1.0 is the event table verbatim (EDSA 2.22, C5 1.62 at baseline, as the brief shows). For 0.8 and 1.2 the rate is anchored to that table and scaled by the ratio of Step 6 means: `rate(c,e,s) = event_rate(c,s) × mean(c,e,s) / mean(c,1.0,s)`. Exposure is identical across assumptions, so the ratio of rates equals the ratio of means — this is arithmetic on two notebook tables, not a new statistic. It keeps the rate continuous when the assumption selector crosses 1.0.
4. **Peak share rounding.** The peak sentence shows 28.6% / 35.1% (the notebook's own figures) rather than the rounded 29% / 35% sketched in the wireframe — the notebook wins under "the notebook is the single source of truth."
5. **`windowCrashes`** (5,429 EDSA / 1,680 C5) is summed from `results/processed/incident_monthly_panel.csv` (`in_window == True`) and cross-checked against the validation log.
6. **Stretch S1 ("Draw a simulated year") is skipped** — it needs `np.percentile` changes inside the notebook's `simulate()`, and the brief says to skip it if the 99 quantiles are not already exported. They are not. `annualQuantiles` is `null`. S2 (Poisson day replay) is also skipped as stretch; the sticky control bar and Copy link (the other "Should" items) are implemented.
7. **`meta.alpha`** is exported at full precision (0.0235678…); the UI formats it to 4 dp (0.0236), matching the notebook's own print format.
8. **Range-plot band animation** uses CSS transitions on SVG geometry properties (`x`, `width`), supported by current browsers; where unsupported the band snaps (still correct, just unanimated).
9. **Hour chart y-axis** rescales with the scenario (only the range plots are required to have fixed axes); tick labels round to readable steps.

## Deviations from the brief

- None beyond the assumptions above. All 12 scenario × assumption × corridor combinations come verbatim from `simulation_results.csv` filtered to `trend == "frozen"`.

## Open questions for the team

1. Should the rate shown beside the headline count be Step 6-derived (count ÷ exposure = 2.19 for EDSA Today) instead of the Step 8 event-table value (2.22)? The brief designates `event_scenario_summary.csv` for the rate line, so 2.22 is used; the ~1.3% gap is the documented Step 6 vs Step 8 Monte Carlo difference (both are notebook tables).
2. If S1 is wanted later, add `np.percentile(arr, range(1, 100))` to `simulate()` in the notebook and re-run; the export script writes `annualQuantiles` as `null` until such a file appears.


## Build verification (end of Phase 7)

Executed headlessly against `file://` (no server), default state and `#s=30&e=1.2&h=19`:

- **Consistency (node `scripts/check_app_data.js`):** `|hours sum − mean| ≤ 9.1e-13`, `|zones sum − hour| ≤ 5.7e-14`, frozen-trend means/p05/p95 match Appendix B (3,376/2,559/4,427 … 1,766/1,091/2,699), `hourShare` sums to 1, all `zoneGivenHour` rows sum to 1, 24 annual entries.
- **Behaviour (CDP end-to-end):** Play steps 12 AM → 2 AM at 650 ms and Pause restores "Play"; stop buttons move thumb/panels/hash together (+20% → 4,061, delta 685, 506,074 vehicles, 12 of 13 vehicles shown); assumption 1.2 → 4,209 and rate 2.29; All day drops `h` from the hash; sticky bar appears only after the hero scrolls away; slider and hour-chart arrow keys work; `aria-live` region tracks "Showing 1 AM."; reload with `#s=20&e=0.8&h=7` restores +20% / more slowly / 7 AM (4,205 & 1,656 shown).
- **Console:** zero messages in default and hash states.
- **Responsive:** no horizontal scroll at 320 (`scrollWidth == 320`); no text below 15px anywhere at 320 (measured `getBoundingClientRect` on map labels, axis labels, callouts, end labels, range-plot labels); range plot and hour chart render 1:1 (no SVG upscaling) so SVG text keeps its true size.
- **Reduced motion:** emulated `prefers-reduced-motion: reduce` → vehicles `animation: none` at a static position, band transition `0.001s`.
- **Projector fold:** at 1366×768 the hero plus the tops of both result panels are visible without scrolling.
- **Lighthouse (headless Chrome, served over `http://127.0.0.1:8765`):** Accessibility **100**, Best Practices **100**, no audit below 1. The only issue found on the first pass was `errors-in-console`: the static server 404s on `/favicon.ico`, because the page declared no icon. Fixed with an inline SVG data-URI icon, so the page makes no icon request at all and scores 100 on the rerun. Contrast, link/button names, `label`, `meta-viewport`, `html-has-lang`, `document-title` and `deprecations` all pass.

### Hero traffic density update (2026-10-05)

The original Phase 7 vehicle counts above are historical. The current hero uses 40 / 44 / 48 / 52 active cars on desktop and 20 / 22 / 24 / 26 on narrow screens for Today / +10% / +20% / +30%. Code-level interaction checks passed for both button rows, the slider, breakpoint changes, saved scenarios, stable animation phases, animated/static spacing, and offscreen pause. JavaScript syntax and app-data consistency checks passed. The supplied screenshots were reviewed as layout references; a fresh desktop/mobile browser review was unavailable because the browser tool rejected local-file URLs. Existing screenshots predate this change.

## Additional deviations discovered during build

- **Hour-chart x ticks fall back to three labels** (12 AM · 12 PM · 12 AM) when the plot area is narrower than 300px — the five-label row from the brief collides below ~720px, and legibility wins. Desktop keeps all five.
- **Map label sizing:** SVG text scales with the `viewBox`, so `.zm-label` is bumped to 27 user-units below 420px viewport (rendered ≥ 15px at 320px) and `.zonemap` is capped at 460px so labels do not oversize on wide screens. Map labels also get a paper-coloured halo (`paint-order: stroke`) where they meet a circle — legibility, not decoration.
- **Headless Chrome clamps `--window-size` to 500px**, so screenshots were captured through CDP `Emulation.setDeviceMetricsOverride` for true 375/320px renders (noted in README).

## Designer critique pass (Phase 7, step 4)

Removed during review: the paint-yellow pill that originally wrapped the section heading (yellow is reserved for the slider/dashes/focus/selected stop/trust border); the H1 was widened from 21ch to 26ch so it sets in two lines and the first panels clear the 768px fold; peak callouts gained a paper halo after the 375px screenshot showed the C5 callout fighting the EDSA curve. Everything else on the page earns its place: route plates (identity), lane dashes and vehicles (the one motif), grid/north arrow/zone labels (map legibility), hairlines (structure).

One addition from the accessibility pass: the tab icon is an inline SVG (`data:` URI, no file, no request) — the asphalt plate with the paint-yellow bar and dot, the same mark the charts use.
