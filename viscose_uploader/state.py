from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .paths import AppPaths


@dataclass
class ScenarioState:
    best_score: Optional[float] = None
    worksheet: Optional[str] = None
    score_cell: Optional[str] = None
    scenario_cell: Optional[str] = None


@dataclass
class AppState:
    scenarios: Dict[str, ScenarioState] = field(default_factory=dict)
    processed_files: List[str] = field(default_factory=list)

    def scenario_entry(self, name: str) -> ScenarioState:
        entry = self.scenarios.get(name)
        if entry is None:
            entry = ScenarioState()
            self.scenarios[name] = entry
        return entry


def load_state(paths: AppPaths) -> AppState:
    state_path = paths.state_file
    if not state_path.exists():
        return AppState()

    with state_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    processed_files = raw.get("processed_files", [])
    if not isinstance(processed_files, list):
        processed_files = []

    scenarios_raw = raw.get("scenarios", {})
    scenarios: Dict[str, ScenarioState] = {}
    if isinstance(scenarios_raw, dict):
        for name, data in scenarios_raw.items():
            if not isinstance(data, dict):
                continue
            scenarios[name] = ScenarioState(
                best_score=_to_optional_float(data.get("best_score")),
                worksheet=_optional_str(data.get("worksheet")),
                score_cell=_optional_str(data.get("score_cell")),
                scenario_cell=_optional_str(data.get("scenario_cell")),
            )
    else:
        # Backwards compatibility with previous structure
        scenarios = {}

    # handle legacy format where processed_files lived under each scenario
    if not processed_files and isinstance(scenarios_raw, dict):
        collected: List[str] = []
        for entry in scenarios_raw.values():
            files = entry.get("processed_files") if isinstance(entry, dict) else None
            if isinstance(files, list):
                collected.extend(str(item) for item in files)
        if collected:
            processed_files = collected[-500:]

    return AppState(
        scenarios=scenarios, processed_files=list(map(str, processed_files))
    )


def save_state(paths: AppPaths, state: AppState) -> None:
    paths.ensure()
    payload = {
        "processed_files": state.processed_files[-500:],
        "scenarios": {
            name: {
                "best_score": entry.best_score,
                "worksheet": entry.worksheet,
                "score_cell": entry.score_cell,
                "scenario_cell": entry.scenario_cell,
            }
            for name, entry in state.scenarios.items()
        },
    }
    with paths.state_file.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_optional_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
