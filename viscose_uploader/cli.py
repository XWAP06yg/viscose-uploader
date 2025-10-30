from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from viscose.commands import COMMAND_HANDLERS, resolve_paths


def build_parser() -> argparse.ArgumentParser:
    """Legacy CLI entry point retained for backwards compatibility."""
    parser = argparse.ArgumentParser(
        prog="viscose-uploader",
        description="Legacy entry point for the Viscose Benchmarks uploader.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the default data directory (defaults to ~/.viscose_uploader).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "auth", help="Run the interactive setup and authentication flow."
    )
    subparsers.add_parser("watch", help="Watch for new Kovaaks stats and upload PBs.")
    subparsers.add_parser("upload", help="Rescan all stats and synchronise the sheet.")

    init_parser = subparsers.add_parser(
        "init",
        help="Deprecated alias for 'auth' (legacy PowerShell workflow).",
    )
    init_parser.set_defaults(command="auth", _legacy_alias="init")

    return parser


def _normalise_args(argv: Optional[Sequence[str]]) -> Optional[List[str]]:
    if argv is None:
        return None
    return list(argv)


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(_normalise_args(argv))

    if getattr(args, "_legacy_alias", None) == "init":
        print(
            "The 'init' command is deprecated. Forwarding to 'viscose auth'.",
            file=sys.stderr,
        )

    paths = resolve_paths(args.data_dir)
    paths.ensure()

    handler = COMMAND_HANDLERS.get(args.command or "")
    if handler is None:
        parser.print_help()
        return 1
    return handler(paths)


__all__ = ["build_parser", "run_cli"]
