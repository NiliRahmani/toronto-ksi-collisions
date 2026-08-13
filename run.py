"""Fetch the KSI extract, run the analysis and write the report.

    python run.py                 download the current extract and rebuild everything
    python run.py --no-refresh    reuse the cached copy in data/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from ksi import analysis, grain, ingest, plots, quality, reconcile, report

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
ASSETS = ROOT / "assets"
DATA = ROOT / "data"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Toronto KSI collision analysis.")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument(
        "--no-refresh", action="store_true", help="Use the cached extract."
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    collision_key = cfg["grain"]["collision_key"]
    person_keys = cfg["grain"]["person_keys"]
    min_group = cfg["analysis"]["min_group_size"]

    for folder in (RESULTS, ASSETS, DATA):
        folder.mkdir(parents=True, exist_ok=True)

    raw = ingest.load(cfg, ROOT, refresh=not args.no_refresh)
    snapshot = ingest.write_snapshot(raw, cfg, ROOT, DATA / "snapshot.json")

    classification = grain.classify_columns(raw, collision_key)
    collisions = grain.add_dates(
        grain.add_people_counts(
            grain.to_collisions(raw, classification, collision_key), raw, collision_key
        )
    )
    people = grain.add_dates(raw)

    quality_table, quality_notes = quality.assess(raw, person_keys, collision_key)
    reconciliation = reconcile.build(raw, collision_key)
    pedestrian_note = reconcile.pedestrian_note(raw, collision_key)

    final_year = analysis.last_full_year(people)
    trend = analysis.yearly_trend(
        collisions, people, cfg["analysis"]["first_full_year"], final_year
    )
    road_users = analysis.road_user_outcomes(people, min_group)
    vulnerable = analysis.vulnerable_share_by_year(
        collisions, cfg["analysis"]["first_full_year"], final_year
    )
    hours = analysis.hour_profile(collisions, min_group)
    neighbourhoods = analysis.neighbourhood_ranking(
        collisions, cfg["analysis"]["top_neighbourhoods"], min_group
    )
    flags = analysis.flag_summary(collisions)
    conditions = pd.concat(
        [
            analysis.condition_breakdown(collisions, column, min_group).assign(
                condition_type=column
            )
            for column in ("light", "rdsfcond", "road_class")
        ],
        ignore_index=True,
    )
    headline = analysis.headline(collisions, people, trend, road_users)

    plots.write_all(trend, road_users, neighbourhoods, hours, ASSETS)

    results = {
        "cfg": cfg,
        "snapshot": snapshot,
        "reconciliation": reconciliation,
        "pedestrian_note": pedestrian_note,
        "quality": quality_table,
        "quality_notes": quality_notes,
        "trend": trend,
        "road_users": road_users,
        "neighbourhoods": neighbourhoods,
        "flags": flags,
        "headline": headline,
        "collision_column_count": int(
            (classification["level"] == "collision").sum()
        ),
        "person_column_count": int((classification["level"] == "person").sum()),
        "contradiction_count": int(
            ((raw["injury"] == "Fatal") & (raw["acclass"] != "Fatal Injury")).sum()
        ),
    }

    for name, frame in (
        ("column_grain", classification),
        ("reconciliation", reconciliation),
        ("data_quality", quality_table),
        ("yearly_trend", trend),
        ("road_user_outcomes", road_users),
        ("vulnerable_share_by_year", vulnerable),
        ("hour_profile", hours),
        ("neighbourhood_ranking", neighbourhoods),
        ("circumstance_flags", flags),
        ("conditions", conditions),
    ):
        frame.to_csv(RESULTS / "{}.csv".format(name), index=False)

    (RESULTS / "headline_figures.json").write_text(
        json.dumps(headline, indent=2, default=str), encoding="utf-8"
    )

    md_path, _ = report.write(results, RESULTS, cfg["report"]["title"])

    print()
    print(
        "{:,} person rows -> {:,} collisions ({:.1f} people each)".format(
            snapshot["person_rows"],
            snapshot["collisions"],
            snapshot["person_rows"] / snapshot["collisions"],
        )
    )
    print(
        "{:,} people killed across {:,} fatal collisions".format(
            headline["people_killed_total"], headline["fatal_collisions_total"]
        )
    )
    print(
        "KSI collisions {} to {}: {:,} -> {:,} ({:+.1f}%)".format(
            headline["first_year"],
            headline["last_full_year"],
            headline["ksi_collisions_first_year"],
            headline["ksi_collisions_last_year"],
            headline["ksi_change_pct"],
        )
    )
    print("Report: {}".format(md_path.relative_to(ROOT)))


if __name__ == "__main__":
    main()
