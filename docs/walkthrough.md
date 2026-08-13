# Walkthrough

Notes I kept while building this, in the repository because they are what I
would want to read before talking about it.

---

## The project in one paragraph

Toronto publishes every collision in which someone was killed or seriously
injured, going back to 2006, refreshed daily. It is a good dataset and it has
one property that quietly breaks most analysis built on it: **one row is one
person, not one collision**. Nearly every published figure I could find counts
rows. This project establishes the grain first, reconciles the naive answer
against the right one for every headline figure, then runs the actual analysis
at the correct grain.

## Why the grain matters so much here

The average collision involves 2.7 people, and the severity of the collision is
written onto every one of their rows. So:

```sql
SELECT COUNT(*) FROM ksi WHERE acclass = 'Fatal Injury'   -- 2,927
```

That number is not fatal collisions (1,061) and not deaths (1,094). It is
*people who were present at a fatal collision*. It is 2.8x either of the
numbers a reader would assume, and nothing about it looks wrong.

I did not take this on faith from the column names. `grain.classify_columns`
measures it: for each column, does the value ever differ between two people in
the same collision? Only multi-person collisions can settle it, because in a
single-person collision every column is trivially constant. 30 columns never
vary — those are collision facts. 17 do — those are person facts.

## The numbers I should know cold

| | |
|---|---|
| Person rows / collisions | 20,670 / 7,580 (2.7 people each) |
| People killed | 1,094 |
| Fatal collisions | 1,061 |
| KSI collisions 2006 → 2025 | 481 → 254, down 47% |
| Deaths per 100 KSI collisions | 11.9 → 15.7, up |
| Pedestrian fatality rate | 16.5% (601 of 3,645) |
| Driver fatality rate | 2.1% (203 of 9,878) |
| Pedestrians as a share of all deaths | 55% |
| Overstatement range across headline figures | 2.3x to 3.7x |

## Questions I expect

**"What's the headline?"**
Toronto's serious collisions nearly halved in twenty years, but the share that
kill someone went up — 11.9 deaths per 100 KSI collisions in 2006, 15.7 in
2025. And more than half of everyone killed was on foot. A pedestrian in one of
these collisions dies eight times as often as a driver in one.

**"Why did the death rate go up? Are roads more dangerous?"**
I do not know, and I say so in the report. Two explanations fit and this data
cannot separate them. Either the collisions being prevented are
disproportionately the survivable ones, or the threshold for recording a
"serious injury" tightened over twenty years so fewer non-fatal cases enter the
file. A death is hard to misclassify; a serious injury is a judgement. Anyone
using this to argue roads got more lethal has to rule out the second one first.

**"Which neighbourhood is most dangerous?"**
That question cannot be answered from this file and I refused to answer it. I
report counts — West Humber-Clairville has the most KSI collisions at 234 — but
a danger ranking needs an exposure denominator: population, or better, vehicle
and pedestrian kilometres travelled. Without one, the ranking mostly measures
how busy a place is. Publishing it as a risk ranking would be the second-worst
error available in this dataset.

**"Did you find anything wrong with the data?"**
Three things, all small and all real. Six person records are marked
`injury = 'Fatal'` while their collision is not classed fatal — the two severity
columns contradict each other, and those six rows are exactly why deaths (1,094)
and fatal collisions (1,061) do not reconcile cleanly. Eighteen records across
eight collisions are classed "Property Damage Only" in a dataset published as
killed-or-seriously-injured. And one row has no severity class at all. I kept
all of them in and flagged them rather than dropping them, because silently
removing records from a public dataset is how two analysts get different totals.

**"Aggressive driving is flagged on 42% of collisions. Is it the main cause?"**
No, and the data cannot support a causal claim at all. Flagged collisions are
slightly *less* likely to be fatal than average (0.88x baseline). Heavy trucks
are the flag that stands out — 12% of collisions but 1.72x the baseline fatal
share. Every rate in the file is conditional on a serious collision having
already happened, so none of them is the risk of anything.

**"How do you handle the data changing daily?"**
Every run writes `data/snapshot.json` with the row count, date range and a
SHA-256 of the file the committed results were built from. Anyone can rerun and
diff against it. The tests are split for the same reason: `test_grain.py` uses a
six-row fixture with hand-checked answers, and `test_live_extract.py` asserts
invariants that hold whatever today's numbers are, so the suite does not fail on
a Tuesday because the City published.

**"What's the weakest part?"**
There is no exposure denominator anywhere in it, so nothing here is a risk rate
and I could not make one. And the file only contains serious collisions, so it
says nothing about collisions in general. Both are in the report's limitations
section rather than left for a reader to notice.
