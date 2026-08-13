"""The analysis itself, with every figure computed at a stated grain.

Each function says in its name and its docstring which grain it works on.
Collision-level questions ("how many collisions happened in this
neighbourhood") are answered from the collision table; people-level questions
("who is being killed") are answered from the person rows. Mixing the two is
the mistake this whole repository is organised to avoid.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

VULNERABLE = ["pedestrian", "cyclist", "motorcyclist"]
CIRCUMSTANCE_FLAGS = [
    "aggressive",
    "distracted",
    "red_light",
    "heavy_truck",
    "school_child",
    "older_adult",
]


def _is_true(series: pd.Series) -> pd.Series:
    """The flags arrive as booleans or as the strings 'True'/'False'."""
    return series.astype(str).str.lower() == "true"


def last_full_year(people: pd.DataFrame) -> int:
    """The most recent year the extract covers end to end."""
    return int(people["year"].max() - 1)


def yearly_trend(
    collisions: pd.DataFrame, people: pd.DataFrame, first_year: int, final_year: int
) -> pd.DataFrame:
    """Collisions and casualties per year. Collision grain and person grain, side by side."""
    coll = collisions[collisions["year"].between(first_year, final_year)]
    ppl = people[people["year"].between(first_year, final_year)]

    by_year = coll.groupby("year").agg(
        ksi_collisions=("collision_id", "nunique"),
        fatal_collisions=("acclass", lambda s: int((s == "Fatal Injury").sum())),
    )
    casualties = ppl.groupby("year").agg(
        people_involved=("injury", "size"),
        people_killed=("injury", lambda s: int((s == "Fatal").sum())),
        people_seriously_injured=("injury", lambda s: int((s == "Major").sum())),
    )

    table = by_year.join(casualties).reset_index()
    table["deaths_per_100_collisions"] = (
        100 * table["people_killed"] / table["ksi_collisions"]
    ).round(1)
    return table


def road_user_outcomes(people: pd.DataFrame, min_group: int) -> pd.DataFrame:
    """Who is involved and who dies. Person grain -- the only grain that can answer this."""
    table = (
        people.groupby("road_user")
        .agg(
            people_involved=("injury", "size"),
            killed=("injury", lambda s: int((s == "Fatal").sum())),
            seriously_injured=("injury", lambda s: int((s == "Major").sum())),
        )
        .reset_index()
    )
    table = table[table["people_involved"] >= min_group]
    table["fatality_rate"] = (table["killed"] / table["people_involved"]).round(4)
    return table.sort_values("fatality_rate", ascending=False).reset_index(drop=True)


def vulnerable_share_by_year(
    collisions: pd.DataFrame, first_year: int, final_year: int
) -> pd.DataFrame:
    """Share of KSI collisions involving a pedestrian, cyclist or motorcyclist."""
    coll = collisions[collisions["year"].between(first_year, final_year)]
    rows = []
    for year, group in coll.groupby("year"):
        row = {"year": int(year), "ksi_collisions": len(group)}
        for flag in VULNERABLE:
            row[flag] = round(float(_is_true(group[flag]).mean()), 4)
        rows.append(row)
    return pd.DataFrame(rows)


def hour_profile(collisions: pd.DataFrame, min_group: int) -> pd.DataFrame:
    """When collisions happen, and what share of them are fatal. Collision grain."""
    table = (
        collisions.dropna(subset=["hour"])
        .groupby(collisions["hour"].astype("Int64"))
        .agg(
            collisions=("collision_id", "nunique"),
            fatal=("acclass", lambda s: int((s == "Fatal Injury").sum())),
        )
        .reset_index()
        .rename(columns={"hour": "hour_of_day"})
    )
    table["fatal_share"] = np.where(
        table["collisions"] >= min_group, (table["fatal"] / table["collisions"]).round(4), np.nan
    )
    return table


def neighbourhood_ranking(
    collisions: pd.DataFrame, top_n: int, min_group: int
) -> pd.DataFrame:
    """Where KSI collisions concentrate. Collision grain, counts only.

    Deliberately reported as counts and not as a risk rate. A rate needs a
    denominator this file does not contain -- population, or vehicle-kilometres
    travelled -- and dividing by neither produces a ranking that mostly
    reflects how busy a place is. That limitation is stated in the report
    rather than papered over with a per-capita figure the data cannot support.
    """
    table = (
        collisions.dropna(subset=["neighbourhood"])
        .groupby("neighbourhood")
        .agg(
            ksi_collisions=("collision_id", "nunique"),
            fatal_collisions=("acclass", lambda s: int((s == "Fatal Injury").sum())),
        )
        .reset_index()
    )
    table["fatal_share"] = np.where(
        table["ksi_collisions"] >= min_group,
        (table["fatal_collisions"] / table["ksi_collisions"]).round(4),
        np.nan,
    )
    return table.sort_values("ksi_collisions", ascending=False).head(top_n).reset_index(
        drop=True
    )


def condition_breakdown(collisions: pd.DataFrame, column: str, min_group: int) -> pd.DataFrame:
    """Collisions by a road or environment condition. Collision grain."""
    table = (
        collisions.dropna(subset=[column])
        .groupby(column)
        .agg(
            collisions=("collision_id", "nunique"),
            fatal=("acclass", lambda s: int((s == "Fatal Injury").sum())),
        )
        .reset_index()
    )
    table["share_of_collisions"] = (table["collisions"] / table["collisions"].sum()).round(4)
    table["fatal_share"] = np.where(
        table["collisions"] >= min_group, (table["fatal"] / table["collisions"]).round(4), np.nan
    )
    return table.sort_values("collisions", ascending=False).reset_index(drop=True)


def flag_summary(collisions: pd.DataFrame) -> pd.DataFrame:
    """How often each circumstance flag appears, at collision grain."""
    total = len(collisions)
    rows: List[dict] = []
    for flag in CIRCUMSTANCE_FLAGS + VULNERABLE:
        flagged = _is_true(collisions[flag])
        subset = collisions[flagged]
        rows.append(
            {
                "flag": flag,
                "collisions": int(flagged.sum()),
                "share_of_collisions": round(float(flagged.mean()), 4),
                "fatal_share": round(
                    float((subset["acclass"] == "Fatal Injury").mean()), 4
                )
                if len(subset)
                else np.nan,
            }
        )
    baseline = float((collisions["acclass"] == "Fatal Injury").mean())
    table = pd.DataFrame(rows)
    table["vs_baseline"] = (table["fatal_share"] / baseline).round(2)
    return table.sort_values("collisions", ascending=False).reset_index(drop=True)


def headline(
    collisions: pd.DataFrame,
    people: pd.DataFrame,
    trend: pd.DataFrame,
    road_users: pd.DataFrame,
) -> dict:
    """The handful of numbers the report and README both quote."""
    first, last = int(trend["year"].min()), int(trend["year"].max())
    first_row = trend[trend["year"] == first].iloc[0]
    last_row = trend[trend["year"] == last].iloc[0]

    pedestrians = road_users[road_users["road_user"] == "pedestrian"]
    drivers = road_users[road_users["road_user"] == "driver"]

    return {
        "first_year": first,
        "last_full_year": last,
        "collisions_total": int(collisions["collision_id"].nunique()),
        "people_total": int(len(people)),
        "people_killed_total": int((people["injury"] == "Fatal").sum()),
        "fatal_collisions_total": int(
            (collisions["acclass"] == "Fatal Injury").sum()
        ),
        "ksi_collisions_first_year": int(first_row["ksi_collisions"]),
        "ksi_collisions_last_year": int(last_row["ksi_collisions"]),
        "ksi_change_pct": round(
            100
            * (last_row["ksi_collisions"] - first_row["ksi_collisions"])
            / first_row["ksi_collisions"],
            1,
        ),
        "fatal_collisions_first_year": int(first_row["fatal_collisions"]),
        "fatal_collisions_last_year": int(last_row["fatal_collisions"]),
        "pedestrian_fatality_rate": float(pedestrians["fatality_rate"].iloc[0]),
        "driver_fatality_rate": float(drivers["fatality_rate"].iloc[0]),
        "pedestrian_vs_driver": round(
            float(pedestrians["fatality_rate"].iloc[0])
            / float(drivers["fatality_rate"].iloc[0]),
            1,
        ),
        "pedestrians_killed": int(pedestrians["killed"].iloc[0]),
    }
