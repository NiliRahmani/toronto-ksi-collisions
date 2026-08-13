"""Figures for the report.

Same palette and chrome as my other analysis repositories, so the charts read
as one set. The colours were checked for colour-vision deficiency separation
against the light surface before being used.

One rule worth stating because it is broken so often: no chart here puts two
different measures on two y-axes. Where two measures belong together, they get
two stacked panels sharing an x-axis, which lets the reader compare them
without the scale of one being chosen to flatter the other.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"]
CRITICAL = "#d03b3b"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK_SECONDARY,
        "text.color": INK,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
    }
)


def _style(ax, xlabel: str = "", ylabel: str = "", title: str = "") -> None:
    if title:
        ax.set_title(title, color=INK, loc="left", pad=10, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)


def trend(table: pd.DataFrame, path: Path) -> None:
    """Two panels on one x-axis: how many, and how deadly."""
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(8.0, 6.6), sharex=True, gridspec_kw={"hspace": 0.28}
    )

    top.plot(
        table["year"], table["ksi_collisions"], color=SERIES[0], linewidth=2.0,
        marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5,
    )
    _style(top, "", "KSI collisions", "Collisions fell by nearly half")
    top.set_ylim(bottom=0)
    # First label sits below its point, so it does not run into the panel title.
    for year, offset in (
        (table["year"].min(), (10, -14)),
        (table["year"].max(), (-6, 10)),
    ):
        row = table[table["year"] == year].iloc[0]
        top.annotate(
            "{:,}".format(int(row["ksi_collisions"])),
            (row["year"], row["ksi_collisions"]),
            textcoords="offset points", xytext=offset, ha="center",
            fontsize=9, color=INK_SECONDARY,
        )

    bottom.plot(
        table["year"], table["deaths_per_100_collisions"], color=SERIES[1], linewidth=2.0,
        marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5,
    )
    _style(bottom, "", "Deaths per 100 KSI collisions", "The ones that still happen are deadlier")
    bottom.set_ylim(bottom=0)
    for year, offset in (
        (table["year"].min(), (10, -14)),
        (table["year"].max(), (-6, 10)),
    ):
        row = table[table["year"] == year].iloc[0]
        bottom.annotate(
            "{:.1f}".format(row["deaths_per_100_collisions"]),
            (row["year"], row["deaths_per_100_collisions"]),
            textcoords="offset points", xytext=offset, ha="center",
            fontsize=9, color=INK_SECONDARY,
        )

    bottom.set_xticks(table["year"][::2])
    # subplots_adjust rather than tight_layout, which does not handle the
    # shared-x two-panel arrangement.
    fig.subplots_adjust(left=0.11, right=0.97, top=0.93, bottom=0.08, hspace=0.30)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def road_user_fatality(table: pd.DataFrame, path: Path) -> None:
    """Fatality rate by road user, person grain."""
    data = table[table["people_involved"] > 0].sort_values("fatality_rate")
    fig, ax = plt.subplots(figsize=(7.6, 4.8))

    colors = [CRITICAL if r >= 0.10 else SERIES[0] for r in data["fatality_rate"]]
    ax.barh(
        data["road_user"], data["fatality_rate"], color=colors,
        edgecolor=SURFACE, linewidth=1.5, height=0.68,
    )

    for y, (rate, killed, involved) in enumerate(
        zip(data["fatality_rate"], data["killed"], data["people_involved"])
    ):
        ax.text(
            rate + 0.004, y,
            "{:.1%}   {:,} of {:,}".format(rate, int(killed), int(involved)),
            va="center", fontsize=8.5, color=INK_SECONDARY,
        )

    ax.set_xlim(0, data["fatality_rate"].max() * 1.45)
    ax.xaxis.set_major_formatter(lambda v, _: "{:.0%}".format(v))
    _style(ax, "Share of those involved who were killed", "",
           "A pedestrian in a KSI collision is far likelier to die than a driver")
    ax.grid(axis="y", visible=False)

    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def neighbourhoods(table: pd.DataFrame, path: Path) -> None:
    """Where KSI collisions concentrate. Counts, not rates -- see the report."""
    data = table.sort_values("ksi_collisions")
    fig, ax = plt.subplots(figsize=(8.4, 6.4))

    ax.barh(
        data["neighbourhood"], data["ksi_collisions"], color=SERIES[0],
        edgecolor=SURFACE, linewidth=1.5, height=0.7,
    )
    for y, value in enumerate(data["ksi_collisions"]):
        ax.text(value + 1.5, y, "{:,}".format(int(value)), va="center",
                fontsize=8.5, color=INK_SECONDARY)

    ax.set_xlim(0, data["ksi_collisions"].max() * 1.16)
    _style(ax, "KSI collisions, 2006 to date", "",
           "Where KSI collisions concentrate")
    ax.grid(axis="y", visible=False)

    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def hour_of_day(table: pd.DataFrame, path: Path) -> None:
    """Collision count by hour, collision grain."""
    fig, ax = plt.subplots(figsize=(8.0, 4.4))

    ax.bar(
        table["hour_of_day"].astype(int), table["collisions"], color=SERIES[0],
        edgecolor=SURFACE, linewidth=1.2, width=0.78,
    )
    peak = table.loc[table["collisions"].idxmax()]
    ax.annotate(
        "busiest hour: {:02d}:00, {:,} collisions".format(
            int(peak["hour_of_day"]), int(peak["collisions"])
        ),
        (int(peak["hour_of_day"]), peak["collisions"]),
        textcoords="offset points", xytext=(0, 12), ha="center",
        fontsize=8.5, color=INK_SECONDARY,
    )

    ax.set_xticks(range(0, 24, 2))
    ax.set_ylim(0, table["collisions"].max() * 1.18)
    _style(ax, "Hour of day", "KSI collisions", "When KSI collisions happen")
    ax.grid(axis="x", visible=False)

    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_all(
    trend_table: pd.DataFrame,
    road_user_table: pd.DataFrame,
    neighbourhood_table: pd.DataFrame,
    hour_table: pd.DataFrame,
    out_dir: Path,
) -> List[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trend(trend_table, out_dir / "trend.png")
    road_user_fatality(road_user_table, out_dir / "road_user_fatality.png")
    neighbourhoods(neighbourhood_table, out_dir / "neighbourhoods.png")
    hour_of_day(hour_table, out_dir / "hour_of_day.png")
    return ["trend.png", "road_user_fatality.png", "neighbourhoods.png", "hour_of_day.png"]
