"""What one row of this file actually is, and what follows from that.

The extract has one row per *person* involved in a collision, not one row per
collision. Roughly 2.7 people are involved in the average one. Collision-level
facts -- whether anyone died, the road surface, the neighbourhood, the nine
circumstance flags -- are copied onto every person row in that collision.

So `count(*) where acclass = 'Fatal Injury'` does not count fatal collisions
and does not count deaths. It counts *people who were present at* a fatal
collision, and it is nearly three times either of the numbers a reader would
assume it was.

Nothing here is guessed from the column names. `classify_columns` measures it:
for each column it asks whether the value ever varies between people in the
same collision. Columns that never vary are collision-level, by evidence.
"""
from __future__ import annotations

from typing import List, Tuple

import pandas as pd

# Columns that identify the row rather than describe it.
IDENTIFIERS = ["_id", "collision_id", "veh_no", "per_no"]


def check_person_key(frame: pd.DataFrame, keys: List[str]) -> Tuple[bool, int]:
    """Does the stated person key identify a row uniquely?"""
    duplicated = int(frame.duplicated(subset=keys).sum())
    return duplicated == 0, duplicated


def classify_columns(frame: pd.DataFrame, collision_key: str) -> pd.DataFrame:
    """Label every column collision-level or person-level, by measurement.

    Only collisions involving more than one person can settle the question --
    in a single-person collision every column is trivially constant, so
    including them would classify the whole file as collision-level.
    """
    sizes = frame.groupby(collision_key)[collision_key].transform("size")
    multi = frame[sizes > 1]

    rows = []
    for column in frame.columns:
        if column in IDENTIFIERS:
            level = "identifier"
            varying = 0
        else:
            varying = int(
                (multi.groupby(collision_key)[column].nunique(dropna=False) > 1).sum()
            )
            level = "person" if varying > 0 else "collision"
        rows.append(
            {
                "column": column,
                "level": level,
                "collisions_where_it_varies": varying,
                "missing_share": round(float(frame[column].isna().mean()), 4),
            }
        )

    order = {"identifier": 0, "collision": 1, "person": 2}
    table = pd.DataFrame(rows)
    return table.sort_values(
        ["level", "column"], key=lambda s: s.map(order) if s.name == "level" else s
    ).reset_index(drop=True)


def collision_level_columns(classification: pd.DataFrame) -> List[str]:
    return classification[classification["level"] == "collision"]["column"].tolist()


def person_level_columns(classification: pd.DataFrame) -> List[str]:
    return classification[classification["level"] == "person"]["column"].tolist()


def to_collisions(
    frame: pd.DataFrame, classification: pd.DataFrame, collision_key: str
) -> pd.DataFrame:
    """One row per collision, carrying only the facts that belong to a collision.

    Person-level columns are deliberately dropped rather than aggregated. Taking
    the first driver's age as "the age" of a collision is how a plausible number
    that means nothing gets into a report.
    """
    keep = [collision_key] + collision_level_columns(classification)
    collisions = frame[keep].drop_duplicates(subset=collision_key)
    return collisions.reset_index(drop=True)


def add_people_counts(
    collisions: pd.DataFrame, frame: pd.DataFrame, collision_key: str
) -> pd.DataFrame:
    """Attach the counts that can only be built from the person rows."""
    people = frame.groupby(collision_key).agg(
        people_involved=("_id", "size"),
        people_killed=("injury", lambda s: int((s == "Fatal").sum())),
        people_seriously_injured=("injury", lambda s: int((s == "Major").sum())),
    )
    return collisions.merge(people, on=collision_key, how="left")


def add_dates(frame: pd.DataFrame, date_column: str = "accdate") -> pd.DataFrame:
    """Parse the timestamp once, here, so no downstream module re-parses it."""
    out = frame.copy()
    parsed = pd.to_datetime(out[date_column], errors="coerce")
    out["collision_date"] = parsed.dt.date
    out["year"] = parsed.dt.year
    out["month"] = parsed.dt.month
    out["hour"] = parsed.dt.hour
    out["weekday"] = parsed.dt.day_name()
    return out
