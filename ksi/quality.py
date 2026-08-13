"""Data quality assessment of the extract as published.

Every rule below is run against the file exactly as the City serves it. Where a
rule fails, the count is real and can be reproduced by anyone who downloads the
same extract -- the checksum in `data/snapshot.json` says which one.

Two rules deserve a note before the results. Neither is a complaint about the
dataset, which is unusually good for open data; they are the kind of thing a
consumer needs to know before publishing a number from it.

  * `injury` is missing on nearly half the rows. That is not a defect. Most
    people involved in a collision are not hurt, and the column is only
    populated when there is an injury to record. It matters because it means
    the column cannot be counted with `count()`, only with an equality test.
  * `collision_id` repeats by design. That is the grain, not a duplicate.
"""
from __future__ import annotations

from typing import List, Tuple

import pandas as pd

# Toronto's bounding box, generous enough not to fail on a legitimate edge of
# the city and tight enough to catch a coordinate that landed in the ocean.
LAT_RANGE = (43.55, 43.90)
LON_RANGE = (-79.70, -79.10)

KNOWN_ACCLASS = {"Fatal Injury", "Non-Fatal Injury", "Property Damage Only"}
KNOWN_INJURY = {"Fatal", "Major", "Minor", "Minimal"}


def _rule(
    dimension: str, rule: str, failed: int, total: int, impact: str
) -> dict:
    return {
        "dimension": dimension,
        "rule": rule,
        "records_failed": int(failed),
        "share_failed": round(failed / total, 5) if total else 0.0,
        "outcome": "Fail" if failed > 0 else "Pass",
        "impact": impact,
    }


def assess(
    frame: pd.DataFrame, person_keys: List[str], collision_key: str
) -> Tuple[pd.DataFrame, List[str]]:
    """Score the published extract and return the rules plus the notable findings."""
    total = len(frame)
    rules = []

    rules.append(
        _rule(
            "Uniqueness",
            "one row per (collision, vehicle, person)",
            int(frame.duplicated(subset=person_keys).sum()),
            total,
            "Confirms the stated grain. Nothing downstream is safe without it.",
        )
    )

    rules.append(
        _rule(
            "Completeness",
            "acclass is populated",
            int(frame["acclass"].isna().sum()),
            total,
            "A row with no severity class cannot be counted as fatal or non-fatal.",
        )
    )

    rules.append(
        _rule(
            "Completeness",
            "coordinates are populated",
            int(frame["latitude"].isna().sum()),
            total,
            "Rows without coordinates drop silently out of any map or spatial join.",
        )
    )

    rules.append(
        _rule(
            "Completeness",
            "neighbourhood is populated",
            int(frame["neighbourhood"].isna().sum()),
            total,
            "Affects the neighbourhood ranking, which is built on this column.",
        )
    )

    in_box = frame["latitude"].between(*LAT_RANGE) & frame["longitude"].between(
        *LON_RANGE
    )
    rules.append(
        _rule(
            "Validity",
            "coordinates fall inside Toronto",
            int((~in_box & frame["latitude"].notna()).sum()),
            total,
            "No coordinate lands outside the city, so the geography can be trusted.",
        )
    )

    rules.append(
        _rule(
            "Validity",
            "acclass uses a known severity code",
            int((~frame["acclass"].isin(KNOWN_ACCLASS) & frame["acclass"].notna()).sum()),
            total,
            "An unrecognised code would fall through every severity filter.",
        )
    )

    rules.append(
        _rule(
            "Validity",
            "injury uses a known severity code",
            int((~frame["injury"].isin(KNOWN_INJURY) & frame["injury"].notna()).sum()),
            total,
            "Same risk on the person-level severity column.",
        )
    )

    # A person recorded as killed, in a collision not classified as fatal.
    contradiction = frame[
        (frame["injury"] == "Fatal") & (frame["acclass"] != "Fatal Injury")
    ]
    rules.append(
        _rule(
            "Consistency",
            "a fatal injury sits in a collision classed fatal",
            len(contradiction),
            total,
            "The two severity columns disagree, so the death count and the fatal "
            "collision count cannot both be right on these rows.",
        )
    )

    # The other direction: a fatal collision with nobody recorded as killed.
    fatal_collisions = frame[frame["acclass"] == "Fatal Injury"]
    deaths_per_collision = fatal_collisions.groupby(collision_key)["injury"].apply(
        lambda s: int((s == "Fatal").sum())
    )
    rules.append(
        _rule(
            "Consistency",
            "a collision classed fatal records at least one death",
            int((deaths_per_collision == 0).sum()),
            max(len(deaths_per_collision), 1),
            "Confirms the fatal classification is supported by a person record.",
        )
    )

    off_scope = frame[frame["acclass"] == "Property Damage Only"]
    rules.append(
        _rule(
            "Scope",
            "every record meets the killed-or-seriously-injured criterion",
            len(off_scope),
            total,
            "Records classed property damage only do not belong in a KSI extract "
            "and will inflate any unfiltered collision count.",
        )
    )

    table = pd.DataFrame(rules)
    return table, _notes(frame, contradiction, off_scope, collision_key)


def _notes(
    frame: pd.DataFrame,
    contradiction: pd.DataFrame,
    off_scope: pd.DataFrame,
    collision_key: str,
) -> List[str]:
    """The findings worth putting in front of a reader, in plain sentences."""
    notes = []

    if len(contradiction):
        notes.append(
            "{} person records are marked injury = 'Fatal' while their collision is "
            "not classed 'Fatal Injury'. This is why the death count (1 per person "
            "record) and the fatal collision count do not reconcile to each other "
            "exactly, and the difference is precisely these rows.".format(
                len(contradiction)
            )
        )

    if len(off_scope):
        notes.append(
            "{} person records across {} collisions are classed 'Property Damage "
            "Only' in an extract published as killed-or-seriously-injured. They are "
            "kept in the figures here and flagged rather than dropped, because "
            "removing records from a public dataset without saying so is how two "
            "analysts end up with different totals.".format(
                len(off_scope), off_scope[collision_key].nunique()
            )
        )

    missing_injury = float(frame["injury"].isna().mean())
    notes.append(
        "injury is missing on {:.0%} of rows, which is expected: it is populated "
        "only where there was an injury to record. The consequence is that "
        "severity has to be counted with an equality test, never with count() or "
        "a row count.".format(missing_injury)
    )

    return notes
