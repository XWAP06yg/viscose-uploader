from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from .commands import COMMAND_HANDLERS, resolve_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="viscose",
        description="Viscose Benchmarks command line interface.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the default data directory (defaults to ~/.viscose_uploader).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    auth_parser = subparsers.add_parser(
        "auth",
        aliases=["login"],
        help="Run the interactive setup and authentication flow.",
    )
    auth_parser.add_argument(
        "--manual",
        action="store_true",
        help="Skip gcloud detection and run the manual credential import.",
    )
    subparsers.add_parser("watch", help="Watch for new Kovaaks stats and upload PBs.")
    subparsers.add_parser("upload", help="Rescan all stats and synchronise the sheet.")
    subparsers.add_parser(
        "update",
        help="Check for CLI updates and download the latest installer.",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    paths = resolve_paths(args.data_dir)
    paths.ensure()

    handler = COMMAND_HANDLERS.get(args.command or "")
    if handler is None:
        parser.print_help()
        return 1
    return handler(paths, args)


if __name__ == "__main__":
    raise SystemExit(main())
