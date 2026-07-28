"""Läufe auf die Platte schreiben und wieder einsammeln.

Alles landet in einer einzigen JSON-Datei unter ~/.tippgeist/history.json.
Kaputte oder halb geschriebene Dateien kosten hier keinen Lauf: gelesen wird
defensiv, geschrieben wird atomar über eine temporäre Datei.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from .engine import Run

SCHEMA_VERSION = 1
MAX_RUNS = 2000


def home() -> Path:
    override = os.environ.get("TIPPGEIST_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".tippgeist"


def history_file() -> Path:
    return home() / "history.json"


def load_runs() -> List[Run]:
    path = history_file()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    runs: List[Run] = []
    for entry in raw.get("runs", []):
        try:
            runs.append(Run.from_dict(entry))
        except (TypeError, ValueError):
            continue
    return runs


def save_run(run: Run) -> None:
    runs = load_runs()
    runs.append(run)
    if len(runs) > MAX_RUNS:
        runs = runs[-MAX_RUNS:]
    write_runs(runs)


def write_runs(runs: List[Run]) -> None:
    path = history_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": SCHEMA_VERSION, "runs": [r.to_dict() for r in runs]}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    tmp.replace(path)


def runs_for(text_id: str, runs: Optional[List[Run]] = None) -> List[Run]:
    pool = load_runs() if runs is None else runs
    return [r for r in pool if r.text_id == text_id]


def best_for(text_id: str, runs: Optional[List[Run]] = None) -> Optional[Run]:
    candidates = runs_for(text_id, runs)
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.wpm)


def last_for(text_id: str, runs: Optional[List[Run]] = None) -> Optional[Run]:
    candidates = runs_for(text_id, runs)
    return candidates[-1] if candidates else None
