from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from .config import AppConfig
from .google_client import GoogleSheetsClient, GoogleClientError
from .paths import AppPaths
from .state import AppState, load_state, save_state
from .stats import ScenarioRun, StatsParseError, iter_stats_files, parse_stats_file
from .colors import ACCENT, SUCCESS, RESET


def _format_score(value: float) -> str:
    if math.isclose(value, round(value), rel_tol=0, abs_tol=1e-6):
        return str(int(round(value)))
    return f"{value}"


def process_once(
    paths: AppPaths,
    config: AppConfig,
    client: GoogleSheetsClient,
    *,
    skip_processed: bool = True,
) -> bool:
    state = load_state(paths)
    new_runs, processed_paths = _collect_runs(
        config.stats_root, state.processed_files, skip_processed=skip_processed
    )
    if not new_runs:
        state.processed_files = processed_paths[-500:]
        save_state(paths, state)
        return False

    updated = False
    for run in new_runs:
        scenario_state = state.scenario_entry(run.scenario)
        try:
            worksheet, score_cell, scenario_cell = client.resolve_target_cell(
                config.sheet_id,
                run.scenario,
                config.score_header_candidates,
                config.worksheet_filter,
                scenario_state.worksheet,
                scenario_state.score_cell,
                scenario_state.scenario_cell,
            )
        except GoogleClientError as exc:
            print(
                f"[WARN] Skipping update for '{run.scenario}': {exc}", file=sys.stderr
            )
            continue

        scenario_state.worksheet = worksheet
        scenario_state.score_cell = score_cell
        scenario_state.scenario_cell = scenario_cell

        current_best = scenario_state.best_score
        is_new_personal_best = current_best is None or run.score > current_best
        if is_new_personal_best:
            target_value = run.score
            scenario_state.best_score = run.score
        else:
            target_value = current_best if current_best is not None else run.score

        if target_value is None:
            continue

        sheet_value = client.get_numeric_cell(config.sheet_id, worksheet, score_cell)
        if sheet_value is not None and math.isclose(
            sheet_value, target_value, rel_tol=1e-6, abs_tol=1e-6
        ):
            if not is_new_personal_best:
                continue

        mirror_cells = client.find_mirror_cells(
            config.sheet_id,
            worksheet,
            score_cell,
            config.score_header_candidates,
        )

        range_ref = f"'{worksheet}'!{score_cell}"
        formatted_value = _format_score(target_value)
        if is_new_personal_best:
            print(
                f"{SUCCESS}Updating{RESET} {ACCENT}{run.scenario}{RESET} "
                f"on {ACCENT}{worksheet}{RESET} with score {SUCCESS}{formatted_value}{RESET} (new PB)"
            )
        else:
            print(
                f"{ACCENT}Syncing{RESET} {ACCENT}{run.scenario}{RESET} "
                f"on {ACCENT}{worksheet}{RESET} to score {SUCCESS}{formatted_value}{RESET}"
            )
        client.update_cell(config.sheet_id, range_ref, target_value)

        if mirror_cells:
            print(f"  {ACCENT}Also syncing{RESET} columns {', '.join(mirror_cells)}")
            for extra_cell in mirror_cells:
                range_extra = f"'{worksheet}'!{extra_cell}"
                client.update_cell(config.sheet_id, range_extra, target_value)

        updated = True

    state.processed_files = processed_paths[-500:]
    save_state(paths, state)
    return updated


def watch_and_process(
    paths: AppPaths,
    config: AppConfig,
    client: GoogleSheetsClient,
) -> None:
    print("Starting watch loop. Press Ctrl+C to stop.")
    poll_interval = max(config.poll_interval, 1.0)
    try:
        while True:
            updated = process_once(paths, config, client)
            if updated:
                print(f"{SUCCESS}Personal bests updated.{RESET}")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nStopped watch loop.")


def _collect_runs(
    stats_root: Path,
    processed: Sequence[str],
    *,
    skip_processed: bool,
) -> Tuple[List[ScenarioRun], List[str]]:
    processed_set = set(processed)
    processed_paths: List[str] = list(processed)
    runs: List[ScenarioRun] = []

    for csv_path in sorted(
        iter_stats_files(stats_root), key=lambda p: p.stat().st_mtime
    ):
        path_str = str(csv_path)
        if skip_processed and path_str in processed_set:
            continue
        if path_str not in processed_set:
            processed_paths.append(path_str)
            processed_set.add(path_str)
        try:
            runs.append(parse_stats_file(csv_path))
        except StatsParseError as exc:
            print(f"[WARN] Failed to parse {csv_path}: {exc}", file=sys.stderr)
            continue

    return runs, processed_paths
