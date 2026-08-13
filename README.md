# toronto-ksi-collisions

**Twenty years of Toronto's killed-or-seriously-injured collisions — starting with what one row actually means.**

The City of Toronto publishes every collision in which someone was killed or
seriously injured, back to 2006, refreshed daily. It is a good dataset with one
property that quietly breaks analysis built on it: **one row is one person, not
one collision.**

The average collision involves 2.7 people, and the severity of the collision is
copied onto every one of their rows. So counting rows overstates every
collision-level figure by roughly that factor — and the result looks entirely
plausible, which is what makes it dangerous.

> This is an analysis project whose first deliverable is a **denominator**.
> The charts come after, computed at a grain that has been established rather
> than assumed.

---

## The result

> ```sql
> SELECT COUNT(*) FROM ksi WHERE acclass = 'Fatal Injury'   -- 2,927
> ```
> **That is not fatal collisions (1,061), and it is not deaths (1,094).** It is
> the number of *people who were present at* a fatal collision — about 2.8x
> either number a reader would assume it was.

📄 **The report:** [`assets/Toronto_KSI_Report.pdf`](assets/Toronto_KSI_Report.pdf)
— 8 pages. Also readable as [`results/ksi_report.md`](results/ksi_report.md).

Every headline figure, the naive answer beside the right one:

| question | naive: count rows | correct | overstated by |
|---|---|---|---|
| How many KSI collisions are in this file? | 20,670 | **7,580** | 2.73x |
| How many collisions were fatal? | 2,927 | **1,061** | 2.76x |
| How many people were killed? | 2,927 | **1,094** | 2.68x |
| How many collisions involved a pedestrian? | 8,436 | **3,386** | 2.49x |
| How many were flagged red-light running? | 1,689 | **472** | 3.58x |
| How many involved a heavy truck? | 2,788 | **928** | 3.00x |

*(Full table, twelve figures, in [`results/reconciliation.csv`](results/reconciliation.csv).)*

Then the analysis itself:

![KSI collisions per year, and deaths per 100 collisions](assets/trend.png)

> **Serious collisions nearly halved. The share that kill someone went up.**
> KSI collisions fell 47% between 2006 and 2025 (481 to 254), while deaths per
> 100 KSI collisions rose from 11.9 to 15.7.

![Fatality rate by road user](assets/road_user_fatality.png)

> **A pedestrian in one of these collisions dies eight times as often as a
> driver** — 16.5% against 2.1%. Pedestrians are 601 of the 1,094 people killed,
> **55% of all deaths**, while being 18% of the people involved.

*(Everything regenerates with `python run.py`; the PDF with `python scripts/make_report_pdf.py`.)*

## What it does

1. **Establishes the grain by measurement, not by reading column names.** For
   every column: does its value ever differ between two people in the same
   collision? Only multi-person collisions can settle it. 30 columns never vary
   (collision facts), 17 do (person facts), 4 are identifiers.
2. **Reconciles twelve headline figures** at both grains, so the size of the
   error is visible rather than argued about. Overstatement runs 2.3x to 3.7x.
3. **Assesses data quality** against ten rules on the file exactly as published.
4. **Runs the analysis** — twenty-year trend, road user fatality rates,
   time-of-day, neighbourhood concentration, circumstance flags — each function
   naming the grain it works on.
5. **Records what it ran on.** The extract refreshes daily, so every run writes
   `data/snapshot.json` with row counts, date range and a SHA-256, and the
   report quotes it.

## What I found in the data

Three real defects, all small, all reproducible by anyone who downloads the same
file:

- **Six person records are marked `injury = 'Fatal'` while their collision is
  not classed `'Fatal Injury'`.** The two severity columns contradict each
  other, and those six rows are precisely why deaths (1,094) and fatal
  collisions (1,061) do not reconcile cleanly.
- **Eighteen records across eight collisions are classed "Property Damage
  Only"** — in a dataset published as *killed or seriously injured*.
- One row carries no severity class at all; three have no coordinates.

All of them are kept in the figures and flagged, not dropped. Silently removing
records from a public dataset is how two analysts end up with different totals.

## What this analysis deliberately does not claim

The report has a limitations section, and these are the two that constrain it most:

- **There is no exposure denominator.** No population, traffic volume or
  distance travelled. So no count here can become a risk rate, and none is
  presented as one. The neighbourhood ranking is reported as counts for exactly
  this reason — a "most dangerous neighbourhood" list built without exposure
  mostly measures how busy a place is.
- **The rising death rate has two explanations and this data cannot separate
  them.** Either the collisions being prevented are disproportionately the
  survivable ones, or the reporting threshold for "serious injury" tightened
  over twenty years. A death is hard to misclassify; a serious injury is a
  judgement.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run.py                        # fetch the current extract, rebuild everything
python run.py --no-refresh           # reuse the cached copy
python scripts/make_report_pdf.py    # render the report to PDF
pytest -q                            # 19 tests
```

No API key and no account — the City's CKAN portal is open, and the single
network call in this repository is the one that fetches the CSV.

## Project layout

```
ksi/
  ingest.py      # fetch from the open data portal, checksum the snapshot
  grain.py       # measures which columns are collision-level vs person-level
  reconcile.py   # naive answer beside the right one, for each headline figure
  quality.py     # ten data quality rules on the published extract
  analysis.py    # trend, road users, hours, neighbourhoods, flags
  plots.py       # the four report figures
  report.py      # one block list rendered to both Markdown and HTML
run.py           # end-to-end
tests/
  test_grain.py        # six-row fixture with hand-checked answers
  test_live_extract.py # invariants that hold whatever today's numbers are
docs/walkthrough.md    # the study notes
```

## Design choices worth noting

- **The grain is measured, not assumed.** `classify_columns` uses only
  multi-person collisions, because in a single-person collision every column is
  trivially constant and including them would classify the entire file as
  collision-level.
- **Person-level columns are dropped, never aggregated, when building the
  collision table.** Taking the first driver's age as "the age" of a collision
  is how a plausible number that means nothing gets into a report.
- **The tests are split by what can change.** The dataset refreshes daily, so
  value-pinned tests would fail on a Tuesday for no reason and teach everyone to
  ignore the suite. The fixture tests pin exact answers; the live tests pin
  relationships.
- **The partial final year is excluded from every trend** and named in the
  report, rather than plotted as a collapse.
- **The report is generated from the same code as the results**, so the two
  cannot drift apart.

## Source and licence

City of Toronto Open Data Portal, *Motor Vehicle Collisions Involving Killed or
Seriously Injured Persons*, published by Toronto Police Service and refreshed
daily. Retrieved over the public CKAN API. Coverage is the City of Toronto only.

The code in this repository is MIT licensed. The data belongs to the City of
Toronto and is subject to the portal's own terms.
