"""Tests for the grain logic, on a fixture with hand-checked answers.

The real extract is refreshed daily, so pinning tests to its current numbers
would mean a suite that fails every time the City publishes. The fixture below
is small enough to verify by eye and contains one of each situation the code
has to handle, including the fatal-injury-in-a-non-fatal-collision
contradiction that the published data actually contains.

`test_live_extract.py` covers the invariants that must hold on the real file
whatever today's numbers are.
"""
from __future__ import annotations

import pandas as pd
import pytest

from ksi import analysis, grain, quality, reconcile

PERSON_KEYS = ["collision_id", "veh_no", "per_no"]


@pytest.fixture
def sample():
    """Three collisions, six people.

    C1  fatal collision, 3 people, 1 killed and 2 seriously injured
    C2  non-fatal collision, 1 person, seriously injured
    C3  non-fatal collision, 2 people, but one is recorded as killed
    """
    rows = [
        # collision_id, veh_no, per_no, acclass,            injury,  road_user,    pedestrian
        (1, 1, 1, "Fatal Injury", "Fatal", "pedestrian", True),
        (1, 1, 2, "Fatal Injury", "Major", "driver", True),
        (1, 2, 1, "Fatal Injury", "Major", "passenger", True),
        (2, 1, 1, "Non-Fatal Injury", "Major", "cyclist", False),
        (3, 1, 1, "Non-Fatal Injury", "Fatal", "driver", False),
        (3, 1, 2, "Non-Fatal Injury", None, "passenger", False),
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "collision_id", "veh_no", "per_no", "acclass",
            "injury", "road_user", "pedestrian",
        ],
    )
    frame["_id"] = range(1, len(frame) + 1)
    frame["accdate"] = [
        "2023-03-01T08:00:00", "2023-03-01T08:00:00", "2023-03-01T08:00:00",
        "2023-06-15T18:30:00", "2024-01-20T22:10:00", "2024-01-20T22:10:00",
    ]
    frame["neighbourhood"] = ["Downtown"] * 3 + ["Scarborough"] + ["Etobicoke"] * 2
    frame["latitude"] = [43.65] * 3 + [43.77] + [43.62] * 2
    frame["longitude"] = [-79.38] * 3 + [-79.25] + [-79.53] * 2
    for flag in ("cyclist", "motorcyclist", "aggressive", "distracted",
                 "red_light", "heavy_truck", "school_child", "older_adult"):
        frame[flag] = False
    return frame


def test_person_key_is_unique(sample):
    unique, duplicated = grain.check_person_key(sample, PERSON_KEYS)
    assert unique
    assert duplicated == 0


def test_columns_are_classified_by_measurement(sample):
    classification = grain.classify_columns(sample, "collision_id")
    level = dict(zip(classification["column"], classification["level"]))

    # Constant within every multi-person collision.
    assert level["acclass"] == "collision"
    assert level["neighbourhood"] == "collision"
    assert level["pedestrian"] == "collision"
    # Varies between people in the same collision.
    assert level["injury"] == "person"
    assert level["road_user"] == "person"
    assert level["collision_id"] == "identifier"


def test_collision_table_drops_person_columns(sample):
    classification = grain.classify_columns(sample, "collision_id")
    collisions = grain.to_collisions(sample, classification, "collision_id")

    assert len(collisions) == 3
    assert "injury" not in collisions.columns
    assert "road_user" not in collisions.columns
    assert "acclass" in collisions.columns


def test_people_counts_attach_to_the_collision(sample):
    classification = grain.classify_columns(sample, "collision_id")
    collisions = grain.add_people_counts(
        grain.to_collisions(sample, classification, "collision_id"),
        sample,
        "collision_id",
    )
    by_id = collisions.set_index("collision_id")

    assert by_id.loc[1, "people_involved"] == 3
    assert by_id.loc[1, "people_killed"] == 1
    assert by_id.loc[1, "people_seriously_injured"] == 2
    assert by_id.loc[3, "people_killed"] == 1


def test_reconciliation_separates_rows_collisions_and_deaths(sample):
    table = reconcile.build(sample, "collision_id").set_index("question")

    total = table.loc["How many KSI collisions are in this file?"]
    assert total["naive_answer"] == 6
    assert total["correct_answer"] == 3

    fatal = table.loc["How many collisions were fatal?"]
    assert fatal["naive_answer"] == 3      # three people in the one fatal collision
    assert fatal["correct_answer"] == 1

    killed = table.loc["How many people were killed?"]
    assert killed["naive_answer"] == 3
    assert killed["correct_answer"] == 2   # one in C1, one mislabelled in C3


def test_naive_row_count_overstates_collisions(sample):
    table = reconcile.build(sample, "collision_id")
    assert (table["overstated_by"] >= 1).all()
    assert table["overstated_by"].max() > 1


def test_quality_catches_the_severity_contradiction(sample):
    table, notes = quality.assess(sample, PERSON_KEYS, "collision_id")
    rules = table.set_index("rule")

    contradiction = rules.loc["a fatal injury sits in a collision classed fatal"]
    assert contradiction["outcome"] == "Fail"
    assert contradiction["records_failed"] == 1

    supported = rules.loc["a collision classed fatal records at least one death"]
    assert supported["outcome"] == "Pass"
    assert any("Fatal" in note for note in notes)


def test_quality_passes_a_clean_file(sample):
    clean = sample[sample["collision_id"] != 3].copy()
    table, _ = quality.assess(clean, PERSON_KEYS, "collision_id")
    rules = table.set_index("rule")

    assert rules.loc["a fatal injury sits in a collision classed fatal"]["outcome"] == "Pass"
    assert rules.loc["coordinates fall inside Toronto"]["outcome"] == "Pass"


def test_road_user_rates_use_the_person_grain(sample):
    people = grain.add_dates(sample)
    table = analysis.road_user_outcomes(people, min_group=1).set_index("road_user")

    assert table.loc["pedestrian", "people_involved"] == 1
    assert table.loc["pedestrian", "fatality_rate"] == 1.0
    assert table.loc["passenger", "fatality_rate"] == 0.0


def test_dates_are_parsed_once(sample):
    dated = grain.add_dates(sample)
    assert dated.loc[0, "year"] == 2023
    assert dated.loc[0, "hour"] == 8
    assert dated.loc[4, "year"] == 2024
