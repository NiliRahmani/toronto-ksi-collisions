"""Assembles the report.

Written once as an ordered list of blocks and rendered to both Markdown and
HTML, so the two copies cannot drift apart.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple

import pandas as pd

Block = Tuple[str, Any]

CSS = """
:root { color-scheme: light; }
body {
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  color: #0b0b0b; background: #fcfcfb;
  margin: 0 auto; padding: 32px 40px 56px; max-width: 860px;
  font-size: 10.5pt; line-height: 1.55;
}
h1 { font-size: 21pt; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 13.5pt; margin: 30px 0 10px; padding-bottom: 6px;
     border-bottom: 1px solid #e1e0d9; }
p { margin: 0 0 10px; }
ul { margin: 0 0 12px; padding-left: 20px; }
li { margin-bottom: 5px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0 18px;
        font-size: 8.6pt; font-variant-numeric: tabular-nums; }
th { text-align: left; background: #f0efec; color: #52514e;
     font-weight: 600; padding: 6px 8px; border-bottom: 1px solid #c3c2b7; }
td { padding: 5px 8px; border-bottom: 1px solid #e1e0d9; vertical-align: top; }
tr:last-child td { border-bottom: 1px solid #c3c2b7; }
figure { margin: 16px 0 20px; }
figure img { width: 100%; border: 1px solid #e1e0d9; border-radius: 4px; }
figcaption { font-size: 8.5pt; color: #898781; margin-top: 6px; }
.meta { color: #52514e; font-size: 9.5pt; margin-bottom: 22px; }
.callout { background: #f0efec; border-left: 3px solid #2a78d6;
           padding: 12px 16px; margin: 16px 0 20px; }
.callout p:last-child { margin-bottom: 0; }
@page { size: A4; margin: 14mm 14mm 16mm; }
h2 { break-after: avoid; }
table, figure { break-inside: avoid; }
"""


def heading(level: int, text: str) -> Block:
    return ("h{}".format(level), text)


def paragraph(text: str) -> Block:
    return ("p", text)


def bullets(items: List[str]) -> Block:
    return ("ul", items)


def table(frame: pd.DataFrame) -> Block:
    return ("table", frame)


def figure(path: str, caption: str) -> Block:
    return ("figure", (path, caption))


def callout(text: str) -> Block:
    return ("callout", text)


def meta(text: str) -> Block:
    return ("meta", text)


def _typeset(text: str) -> str:
    """Source stays ASCII; the rendered report gets a real dash."""
    return str(text).replace(" -- ", " \u2014 ")


def _typeset_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if out[column].dtype == object:
            out[column] = out[column].map(_typeset)
    return out


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(c).replace("_", " ") for c in frame.columns]
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("|" + "|".join(["---"] * len(columns)) + "|")
    for _, row in _typeset_frame(frame).iterrows():
        cells = [str(v).replace("|", "/").replace("\n", " ") for v in row.tolist()]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_markdown(blocks: List[Block]) -> str:
    out: List[str] = []
    for kind, payload in blocks:
        if kind.startswith("h") and len(kind) == 2:
            out.append("{} {}".format("#" * int(kind[1]), payload))
        elif kind == "p":
            out.append(_typeset(payload))
        elif kind == "meta":
            out.append("*{}*".format(_typeset(payload)))
        elif kind == "callout":
            out.append("> {}".format(_typeset(payload)))
        elif kind == "ul":
            out.append("\n".join("- {}".format(_typeset(i)) for i in payload))
        elif kind == "table":
            out.append(_markdown_table(payload))
        elif kind == "figure":
            path, caption = payload
            out.append("![{}]({})\n\n*{}*".format(caption, path, caption))
    return "\n\n".join(out) + "\n"


def _escape(text: str) -> str:
    safe = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _typeset(safe)


def render_html(blocks: List[Block], title: str) -> str:
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>{}</title>".format(_escape(title)),
        "<style>{}</style></head><body>".format(CSS),
    ]
    for kind, payload in blocks:
        if kind.startswith("h") and len(kind) == 2:
            out.append("<{0}>{1}</{0}>".format(kind, _escape(payload)))
        elif kind == "p":
            out.append("<p>{}</p>".format(_escape(payload)))
        elif kind == "meta":
            out.append('<p class="meta">{}</p>'.format(_escape(payload)))
        elif kind == "callout":
            out.append('<div class="callout"><p>{}</p></div>'.format(_escape(payload)))
        elif kind == "ul":
            items = "".join("<li>{}</li>".format(_escape(i)) for i in payload)
            out.append("<ul>{}</ul>".format(items))
        elif kind == "table":
            out.append(
                _typeset_frame(payload).to_html(
                    index=False, border=0, escape=True, na_rep=""
                )
            )
        elif kind == "figure":
            path, caption = payload
            out.append(
                '<figure><img src="{}"><figcaption>{}</figcaption></figure>'.format(
                    path, _escape(caption)
                )
            )
    out.append("</body></html>")
    return "\n".join(out)


def build(results: dict) -> List[Block]:
    cfg = results["cfg"]
    key = results["headline"]
    snapshot = results["snapshot"]
    ped = results["pedestrian_note"]

    blocks: List[Block] = [
        heading(1, cfg["report"]["title"]),
        meta(
            "{}  |  {}  |  Source: City of Toronto Open Data, retrieved {}  |  "
            "{:,} person records across {:,} collisions".format(
                cfg["report"]["subtitle"],
                cfg["report"]["author"],
                snapshot["retrieved_utc"][:10],
                snapshot["person_rows"],
                snapshot["collisions"],
            )
        ),
        heading(2, "1. What one row is"),
        callout(
            "The file has one row per person involved in a collision, not one row per "
            "collision. The average collision involves {:.1f} people. Counting rows "
            "therefore overstates every collision-level figure by roughly that factor, "
            "and the error is invisible -- the numbers look plausible.".format(
                snapshot["person_rows"] / snapshot["collisions"]
            )
        ),
        paragraph(
            "This was not assumed from the column names. Every column was tested: for "
            "each one, does its value ever differ between two people in the same "
            "collision? {} columns never vary within a collision, which makes them "
            "facts about the collision copied onto each person row. {} columns do vary, "
            "which makes them facts about the person. Four are identifiers.".format(
                results["collision_column_count"], results["person_column_count"]
            )
        ),
        paragraph(
            "The consequence is not academic. `acclass`, the severity of the collision, "
            "is one of the collision-level columns. Filtering rows on it and counting "
            "them answers neither of the two questions a reader would be asking."
        ),
        table(results["reconciliation"]),
        paragraph(
            "The two correct answers in the third row are different from each other and "
            "both are right: {:,} collisions were fatal, and {:,} people died in them. "
            "The gap is the collisions that killed more than one person, plus {} records "
            "discussed in section 2. Which number belongs in a headline depends on "
            "whether the sentence is about crashes or about people, and that is a "
            "decision to make deliberately rather than by accident of query.".format(
                key["fatal_collisions_total"],
                key["people_killed_total"],
                results["contradiction_count"],
            )
        ),
        paragraph(
            "The same trap sits under the word pedestrian. Collisions involving a "
            "pedestrian: {:,}. People present in those collisions: {:,}. Pedestrians "
            "actually involved: {:,}. Pedestrians killed: {:,}. All four are legitimate "
            "answers to questions that sound identical when spoken aloud.".format(
                ped["collisions_involving_a_pedestrian"],
                ped["people_in_those_collisions"],
                ped["pedestrians_involved"],
                ped["pedestrians_killed"],
            )
        ),
        heading(2, "2. Data quality"),
        paragraph(
            "Rules were run against the extract exactly as published. The dataset is in "
            "good condition; the failures below are small, and they are recorded because "
            "a consumer needs to know about them before quoting a number, not as a "
            "criticism of the publisher."
        ),
        table(results["quality"]),
        bullets(results["quality_notes"]),
        heading(2, "3. Twenty years of KSI collisions"),
        paragraph(
            "{} to {}. The final year in the extract is partial and is excluded from "
            "every trend in this report rather than plotted as a collapse.".format(
                key["first_year"], key["last_full_year"]
            )
        ),
        figure(
            "../assets/trend.png",
            "KSI collisions per year, and deaths per 100 KSI collisions.",
        ),
        callout(
            "KSI collisions fell {:.0f}% between {} and {}, from {:,} to {:,}. Deaths per "
            "100 KSI collisions moved the other way, from {:.1f} to {:.1f}. Fewer "
            "collisions reach this threshold than twenty years ago, and a larger share "
            "of the ones that do are fatal.".format(
                abs(key["ksi_change_pct"]),
                key["first_year"],
                key["last_full_year"],
                key["ksi_collisions_first_year"],
                key["ksi_collisions_last_year"],
                results["trend"].iloc[0]["deaths_per_100_collisions"],
                results["trend"].iloc[-1]["deaths_per_100_collisions"],
            )
        ),
        paragraph(
            "Two readings fit that pattern and this data cannot separate them. Either "
            "the collisions being prevented are disproportionately the survivable ones, "
            "or the reporting threshold for a serious injury has tightened over twenty "
            "years so that fewer non-fatal cases enter the file. A fatality is hard to "
            "misclassify; a serious injury is a judgement. Anyone using this trend to "
            "argue that roads have become more lethal per collision needs to rule the "
            "second explanation out first, and nothing in this extract does that."
        ),
        table(results["trend"]),
        heading(2, "4. Who is being killed"),
        paragraph(
            "This is a person-level question, so it is answered from the person rows. "
            "The rate below is the share of people involved, in that role, who died."
        ),
        figure("../assets/road_user_fatality.png", "Fatality rate by road user."),
        paragraph(
            "A pedestrian involved in a KSI collision dies {:.0f} times as often as a "
            "driver involved in one ({:.1%} against {:.1%}). Pedestrians are {:,} of the "
            "{:,} people killed in the whole extract -- {:.0%} of deaths -- while making "
            "up {:.0%} of the people involved.".format(
                key["pedestrian_vs_driver"],
                key["pedestrian_fatality_rate"],
                key["driver_fatality_rate"],
                key["pedestrians_killed"],
                key["people_killed_total"],
                key["pedestrians_killed"] / key["people_killed_total"],
                ped["pedestrians_involved"] / key["people_total"],
            )
        ),
        table(results["road_users"]),
        paragraph(
            "The `owner` row is a data artefact rather than a finding: it records the "
            "registered owner of a vehicle, who is frequently not present, which is why "
            "the category shows zero injuries of any kind. It is left in the table so "
            "the totals reconcile."
        ),
        heading(2, "5. When and where"),
        figure("../assets/hour_of_day.png", "KSI collisions by hour of day."),
        figure(
            "../assets/neighbourhoods.png",
            "The {} neighbourhoods with the most KSI collisions.".format(
                cfg["analysis"]["top_neighbourhoods"]
            ),
        ),
        paragraph(
            "The neighbourhood ranking is deliberately reported as counts and not as a "
            "risk rate. A rate needs a denominator this file does not contain -- "
            "resident population, or better, vehicle and pedestrian kilometres travelled "
            "through the area. Dividing by neither produces a ranking that largely "
            "reflects how busy a place is, which is worth knowing but is not the same as "
            "how dangerous it is. Treating this list as a danger ranking would be the "
            "second-biggest error available in this dataset, after the one in section 1."
        ),
        table(results["neighbourhoods"]),
        heading(2, "6. Circumstances"),
        paragraph(
            "Each flag is a collision-level attribute, so these are collision counts. "
            "The final column compares the fatal share of flagged collisions against the "
            "fatal share of all KSI collisions."
        ),
        table(results["flags"]),
        paragraph(
            "These are associations in a file that only contains collisions serious "
            "enough to be recorded. Every rate here is conditional on a KSI collision "
            "having already happened, so none of them is the risk of anything. A flag "
            "with a high fatal share tells you which collisions turn out worst once they "
            "occur; it does not tell you what causes them or how often they occur."
        ),
        heading(2, "7. What this analysis cannot tell you"),
        bullets(
            [
                "There is no exposure denominator. Without population, traffic volume or "
                "distance travelled, no count here can become a risk rate, and none is "
                "presented as one.",
                "The file contains only collisions where someone was killed or seriously "
                "injured. It cannot say anything about collisions in general, or about "
                "how often a given circumstance leads to a collision.",
                "Serious injury is a reported judgement and its threshold may have "
                "shifted over twenty years. This directly affects the section 3 trend.",
                "The circumstance flags are assigned by the reporting officer. They "
                "record what was recorded, not what happened.",
                "The extract is refreshed daily and figures move as historical records "
                "are amended. Everything here was computed from the snapshot identified "
                "in section 8.",
                "Association is not cause. Nothing in this report supports a causal "
                "claim, and none is made.",
            ]
        ),
        heading(2, "8. Reproducing this"),
        paragraph(
            "The extract is refreshed daily, so the exact copy behind these numbers is "
            "recorded rather than described. Rerun `python run.py` against the current "
            "file and compare the snapshot to see precisely what changed."
        ),
        table(
            pd.DataFrame(
                [
                    {"field": k, "value": str(v)}
                    for k, v in snapshot.items()
                ]
            )
        ),
        paragraph(
            "Source: City of Toronto Open Data Portal, Motor Vehicle Collisions "
            "Involving Killed or Seriously Injured Persons. Retrieved over the public "
            "CKAN API with no key or account. The data is published by Toronto Police "
            "Service and covers the City of Toronto only."
        ),
    ]
    return blocks


def write(results: dict, out_dir: Path, title: str) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    blocks = build(results)

    md_path = out_dir / "ksi_report.md"
    html_path = out_dir / "ksi_report.html"
    md_path.write_text(render_markdown(blocks), encoding="utf-8")
    html_path.write_text(render_html(blocks, title), encoding="utf-8")
    return md_path, html_path
