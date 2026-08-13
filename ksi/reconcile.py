"""The naive answer beside the right one, for every headline figure.

This is the part of the project I would show first. Each row takes a question a
reader would actually ask, gives the number a straightforward query returns,
gives the number that answers the question, and shows the gap.

The naive expressions are not strawmen. They are what you get by opening the
file, filtering on the obvious column and reading the row count -- which is
what a spreadsheet, a BI tool dropped straight onto the extract, or a quick
`SELECT COUNT(*)` all do by default.
"""
from __future__ import annotations

from typing import List

import pandas as pd

FLAG_LABELS = {
    "pedestrian": "collisions involving a pedestrian",
    "cyclist": "collisions involving a cyclist",
    "aggressive": "collisions flagged aggressive driving",
    "distracted": "collisions flagged distracted driving",
    "red_light": "collisions flagged red-light running",
    "heavy_truck": "collisions involving a heavy truck",
    "school_child": "collisions flagged school child",
    "older_adult": "collisions flagged older adult",
}


def _row(
    question: str,
    naive_method: str,
    naive_value: int,
    correct_method: str,
    correct_value: int,
) -> dict:
    factor = naive_value / correct_value if correct_value else float("nan")
    return {
        "question": question,
        "naive_method": naive_method,
        "naive_answer": int(naive_value),
        "correct_method": correct_method,
        "correct_answer": int(correct_value),
        "overstated_by": round(factor, 2),
    }


def build(frame: pd.DataFrame, collision_key: str = "collision_id") -> pd.DataFrame:
    """Reconcile the headline figures at both grains."""
    rows: List[dict] = []

    rows.append(
        _row(
            "How many KSI collisions are in this file?",
            "count of rows",
            len(frame),
            "count of distinct {}".format(collision_key),
            frame[collision_key].nunique(),
        )
    )

    fatal = frame[frame["acclass"] == "Fatal Injury"]
    rows.append(
        _row(
            "How many collisions were fatal?",
            "count of rows where acclass = 'Fatal Injury'",
            len(fatal),
            "distinct {} where acclass = 'Fatal Injury'".format(collision_key),
            fatal[collision_key].nunique(),
        )
    )

    rows.append(
        _row(
            "How many people were killed?",
            "count of rows where acclass = 'Fatal Injury'",
            len(fatal),
            "count of rows where injury = 'Fatal'",
            int((frame["injury"] == "Fatal").sum()),
        )
    )

    rows.append(
        _row(
            "How many people were seriously injured?",
            "count of rows where acclass = 'Non-Fatal Injury'",
            int((frame["acclass"] == "Non-Fatal Injury").sum()),
            "count of rows where injury = 'Major'",
            int((frame["injury"] == "Major").sum()),
        )
    )

    for flag, label in FLAG_LABELS.items():
        flagged = frame[frame[flag].astype(str).str.lower() == "true"]
        if flagged.empty:
            continue
        rows.append(
            _row(
                "How many {}?".format(label),
                "count of rows where {} is true".format(flag),
                len(flagged),
                "distinct {} where {} is true".format(collision_key, flag),
                flagged[collision_key].nunique(),
            )
        )

    return pd.DataFrame(rows)


def pedestrian_note(frame: pd.DataFrame, collision_key: str = "collision_id") -> dict:
    """The pedestrian flag and the pedestrian road user are different quantities.

    Worth separating explicitly, because both are legitimate answers to
    questions that sound identical when spoken aloud.
    """
    flagged = frame[frame["pedestrian"].astype(str).str.lower() == "true"]
    return {
        "collisions_involving_a_pedestrian": int(flagged[collision_key].nunique()),
        "people_in_those_collisions": int(len(flagged)),
        "pedestrians_involved": int((frame["road_user"] == "pedestrian").sum()),
        "pedestrians_killed": int(
            ((frame["road_user"] == "pedestrian") & (frame["injury"] == "Fatal")).sum()
        ),
    }
