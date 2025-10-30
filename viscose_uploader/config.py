from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .paths import AppPaths

DEFAULT_SCORE_HEADERS = ["High Score", "Your Score", "Score", "PB"]


class ConfigError(RuntimeError):
    """Raised when the configuration file is missing or invalid."""


@dataclass
class AppConfig:
    sheet_id: str
    stats_root: Path
    google_client_secrets: Path
    poll_interval: float = 5.0
    score_header_candidates: List[str] = field(
        default_factory=lambda: list(DEFAULT_SCORE_HEADERS)
    )
    worksheet_filter: Optional[List[str]] = None
    auth_mode: Optional[str] = None
    service_account_email: Optional[str] = None


def _ensure_list(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    raise ConfigError("Expected a list or comma-separated string.")


def load_config(paths: AppPaths) -> AppConfig:
    config_path = paths.config_file
    if not config_path.exists():
        raise ConfigError(
            f"No config found at {config_path}. Run the setup script or 'python -m viscose_uploader init' first."
        )

    with config_path.open("r", encoding="utf-8-sig") as handle:
        contents = json.load(handle)

    sheet_id = str(contents.get("sheet_id", "")).strip()
    if not sheet_id:
        raise ConfigError("Config is missing 'sheet_id'.")

    stats_root_raw = str(contents.get("stats_root", "")).strip()
    if not stats_root_raw:
        raise ConfigError("Config is missing 'stats_root'.")
    stats_root = Path(stats_root_raw).expanduser()

    secrets_path_raw = str(contents.get("google_client_secrets", "")).strip()
    if not secrets_path_raw:
        raise ConfigError("Config is missing 'google_client_secrets'.")
    google_client_secrets = Path(secrets_path_raw).expanduser()

    poll_interval_raw = contents.get("poll_interval", 5.0)
    try:
        poll_interval = float(poll_interval_raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError("poll_interval must be numeric.") from exc

    user_headers = _ensure_list(
        contents.get("score_headers") or contents.get("score_header_candidates")
    )
    combined_headers: List[str] = []
    seen = set()
    for candidate in user_headers + DEFAULT_SCORE_HEADERS:
        lower = candidate.lower()
        if lower not in seen:
            combined_headers.append(candidate)
            seen.add(lower)
    headers = combined_headers

    worksheet_filter = _ensure_list(contents.get("worksheet_filter"))
    if not worksheet_filter:
        worksheet_filter = None

    return AppConfig(
        sheet_id=sheet_id,
        stats_root=stats_root,
        google_client_secrets=google_client_secrets,
        poll_interval=poll_interval,
        score_header_candidates=headers,
        worksheet_filter=worksheet_filter,
        auth_mode=str(contents.get("auth_mode")).strip()
        if contents.get("auth_mode")
        else None,
        service_account_email=str(contents.get("service_account_email")).strip()
        if contents.get("service_account_email")
        else None,
    )


def write_config(paths: AppPaths, config: AppConfig) -> None:
    payload = {
        "sheet_id": config.sheet_id,
        "stats_root": str(config.stats_root),
        "google_client_secrets": str(config.google_client_secrets),
        "poll_interval": config.poll_interval,
        "score_headers": config.score_header_candidates,
    }
    if config.worksheet_filter:
        payload["worksheet_filter"] = config.worksheet_filter
    if config.auth_mode:
        payload["auth_mode"] = config.auth_mode
    if config.service_account_email:
        payload["service_account_email"] = config.service_account_email

    paths.ensure()
    with paths.config_file.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
