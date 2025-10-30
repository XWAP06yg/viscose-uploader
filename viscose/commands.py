from __future__ import annotations

import sys
import argparse
from pathlib import Path
from typing import Callable, Dict

from viscose_uploader.config import ConfigError, load_config
from viscose_uploader.google_client import GoogleClientError, build_google_client
from viscose_uploader.paths import AppPaths
from viscose_uploader.uploader import process_once, watch_and_process
from viscose_uploader.colors import SUCCESS, RESET

from .auth import run_auth
from .update import run_update


def resolve_paths(data_dir: Path | None) -> AppPaths:
    """Return the application paths, defaulting to the standard directory."""
    if data_dir is None:
        return AppPaths.default()
    return AppPaths(base_dir=data_dir.expanduser())


def build_client(paths: AppPaths):
    """Load configuration and initialise the Google client."""
    config = load_config(paths)
    use_service_account = config.auth_mode == "service_account"
    delegated_user = None if use_service_account else config.service_account_email
    client = build_google_client(
        paths,
        str(config.google_client_secrets),
        use_service_account=use_service_account,
        delegated_user=delegated_user,
    )
    return config, client


def handle_auth(paths: AppPaths, args: argparse.Namespace) -> int:
    try:
        run_auth(paths, force_manual=bool(getattr(args, "manual", False)))
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def handle_watch(paths: AppPaths, args: argparse.Namespace) -> int:
    try:
        config, client = build_client(paths)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1
    except GoogleClientError as exc:
        print(exc, file=sys.stderr)
        return 1

    watch_and_process(paths, config, client)
    return 0


def handle_upload(paths: AppPaths, args: argparse.Namespace) -> int:
    try:
        config, client = build_client(paths)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1
    except GoogleClientError as exc:
        print(exc, file=sys.stderr)
        return 1

    updated = process_once(paths, config, client, skip_processed=False)
    if updated:
        print(f"{SUCCESS}Personal bests updated.{RESET}")
    else:
        print("No new personal bests detected.")
    return 0


def handle_update(paths: AppPaths, args: argparse.Namespace) -> int:
    download_dir = paths.base_dir / "downloads"
    return run_update(download_dir)


CommandHandler = Callable[[AppPaths, argparse.Namespace], int]


COMMAND_HANDLERS: Dict[str, CommandHandler] = {
    "auth": handle_auth,
    "watch": handle_watch,
    "upload": handle_upload,
    "update": handle_update,
}
