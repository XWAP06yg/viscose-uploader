from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class ScenarioRun:
    scenario: str
    score: float
    source_file: Path


class StatsParseError(RuntimeError):
    pass


def parse_stats_file(path: Path, score_field: str = "Score") -> ScenarioRun:
    """Parse an exported Kovaaks stats CSV."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            scenario: Optional[str] = None
            score: Optional[float] = None
            for row in reader:
                if not row:
                    continue
                key = row[0].strip()
                if not key:
                    continue
                if key == "Scenario:" and len(row) > 1:
                    scenario = row[1].strip()
                if key == f"{score_field}:" and len(row) > 1:
                    score = _try_float(row[1])
                if scenario and score is not None:
                    break
    except FileNotFoundError as exc:
        raise StatsParseError(f"Stats file not found: {path}") from exc
    except OSError as exc:
        raise StatsParseError(f"Failed to read stats file {path}: {exc}") from exc

    if not scenario:
        raise StatsParseError(f"No 'Scenario:' entry found in {path}")
    if score is None:
        raise StatsParseError(f"No '{score_field}:' entry found in {path}")

    return ScenarioRun(scenario=scenario, score=score, source_file=path)


def _try_float(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise StatsParseError(
            f"Could not parse score value '{value}' as float"
        ) from exc


def iter_stats_files(root: Path) -> Iterable[Path]:
    """Yield all CSV files under the given directory (recursively)."""
    if not root.exists():
        return []
    return (path for path in root.rglob("*.csv") if path.is_file())
