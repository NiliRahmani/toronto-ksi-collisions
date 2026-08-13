"""Fetch the KSI extract from the City of Toronto open data portal.

The dataset is refreshed daily, which is a problem for a repository whose
results are committed: rerun it next week and the numbers move. So every run
writes `data/snapshot.json` recording the row count, the date range and a
checksum of the file the results were actually built from. Anyone can compare
their download against it and see exactly what changed.

No key or account is needed. The portal is open and the only network call in
this repository is the one below.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

PACKAGE_SHOW = "{portal}/api/3/action/package_show"
TIMEOUT = 120


def resolve_url(cfg: dict) -> str:
    """Ask the portal which URL currently serves the CSV we want."""
    source = cfg["source"]
    response = requests.get(
        PACKAGE_SHOW.format(portal=source["portal"]),
        params={"id": source["package"]},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    resources = response.json()["result"]["resources"]

    for resource in resources:
        if resource["name"].endswith(source["resource_suffix"]):
            return resource["url"]
    raise RuntimeError(
        "No resource ending in {} on package {}".format(
            source["resource_suffix"], source["package"]
        )
    )


def download(cfg: dict, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = resolve_url(cfg)

    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(cfg: dict, root: Path, refresh: bool = True) -> pd.DataFrame:
    """Return the raw extract, downloading it unless a cached copy will do.

    Falls back to the cache when the portal cannot be reached, so the analysis
    still runs on a train with no signal. It says which one it used.
    """
    cache = root / cfg["source"]["cache"]

    if refresh or not cache.exists():
        try:
            download(cfg, cache)
            origin = "downloaded"
        except (requests.RequestException, RuntimeError) as error:
            if not cache.exists():
                raise SystemExit(
                    "Could not reach the open data portal and no cached copy "
                    "exists at {}. Original error: {}".format(cache, error)
                )
            origin = "cache (portal unreachable)"
    else:
        origin = "cache"

    frame = pd.read_csv(cache, low_memory=False)
    print("Extract {}: {:,} rows from {}".format(origin, len(frame), cache.name))
    return frame


def write_snapshot(frame: pd.DataFrame, cfg: dict, root: Path, path: Path) -> dict:
    """Record what this run was built from, so the committed results stay checkable."""
    cache = root / cfg["source"]["cache"]
    dates = pd.to_datetime(frame["accdate"], errors="coerce")

    snapshot = {
        "package": cfg["source"]["package"],
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": checksum(cache),
        "person_rows": int(len(frame)),
        "collisions": int(frame["collision_id"].nunique()),
        "columns": int(frame.shape[1]),
        "earliest_collision": dates.min().strftime("%Y-%m-%d"),
        "latest_collision": dates.max().strftime("%Y-%m-%d"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot
