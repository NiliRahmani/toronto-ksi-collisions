"""Invariants that must hold on the real extract, whatever today's numbers are.

The City refreshes this dataset daily, so these assert relationships rather
than values. A test that pinned the death count would fail on a Tuesday for no
reason and teach everyone to ignore the suite.

Skipped when no extract has been downloaded yet, so `pytest` works on a clean
clone before `run.py` has been run.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ksi import analysis, grain, quality, reconcile

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "data" / "ksi_raw.csv"
PERSON_KEYS = ["collision_id", "veh_no", "per_no"]

pytestmark = pytest.mark.skipif(
    not EXTRACT.exists(),
    reason="No extract downloaded yet. Run python run.py first.",
)


@pytest.fixture(scope="module")
def raw():
    return pd.read_csv(EXTRACT, low_memory=False)


@pytest.fixture(scope="module")
def classification(raw):
    return grain.classify_columns(raw, "collision_id")


def test_the_file_is_person_grain(raw):
    unique, duplicated = grain.check_person_key(raw, PERSON_KEYS)
    assert unique, "{} rows share a person key".format(duplicated)
    assert len(raw) > raw["collision_id"].nunique(), (
        "If these were equal the file would be collision-grain and this whole "
        "analysis would need rewriting."
    )


def test_severity_is_a_collision_level_column(classification):
    level = dict(zip(classification["column"], classification["level"]))
    assert level["acclass"] == "collision"
    assert level["injury"] == "person"
    assert level["road_user"] == "person"


def test_both_grains_are_present(classification):
    counts = classification["level"].value_counts()
    assert counts.get("collision", 0) > 0
    assert counts.get("person", 0) > 0


def test_naive_answers_never_undercount(raw):
    table = reconcile.build(raw, "collision_id")
    assert (table["naive_answer"] >= table["correct_answer"]).all()
    assert (table["overstated_by"] > 1).all(), (
        "Every headline figure in this dataset is overstated by a row count. If "
        "one is not, the grain has changed."
    )


def test_deaths_are_at_least_the_number_of_fatal_collisions(raw):
    deaths = int((raw["injury"] == "Fatal").sum())
    fatal_collisions = raw[raw["acclass"] == "Fatal Injury"]["collision_id"].nunique()
    assert deaths >= fatal_collisions


def test_every_fatal_collision_records_a_death(raw):
    table, _ = quality.assess(raw, PERSON_KEYS, "collision_id")
    rule = table.set_index("rule").loc[
        "a collision classed fatal records at least one death"
    ]
    assert rule["outcome"] == "Pass"


def test_coordinates_stay_inside_toronto(raw):
    table, _ = quality.assess(raw, PERSON_KEYS, "collision_id")
    rule = table.set_index("rule").loc["coordinates fall inside Toronto"]
    assert rule["outcome"] == "Pass"


def test_trend_excludes_the_partial_final_year(raw):
    people = grain.add_dates(raw)
    final = analysis.last_full_year(people)
    assert final == int(people["year"].max()) - 1

    classified = grain.classify_columns(raw, "collision_id")
    collisions = grain.add_dates(
        grain.to_collisions(raw, classified, "collision_id")
    )
    trend = analysis.yearly_trend(collisions, people, 2006, final)
    assert trend["year"].max() == final
    assert int(people["year"].max()) not in set(trend["year"])


def test_pedestrian_counts_are_three_different_quantities(raw):
    note = reconcile.pedestrian_note(raw, "collision_id")
    assert (
        note["collisions_involving_a_pedestrian"]
        < note["pedestrians_involved"]
        < note["people_in_those_collisions"]
    )
    assert note["pedestrians_killed"] < note["pedestrians_involved"]
