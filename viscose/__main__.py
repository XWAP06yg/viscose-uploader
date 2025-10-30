from __future__ import annotations

import shlex
import sys
import traceback
from typing import List, Optional, Tuple

from viscose_uploader.colors import (
    ACCENT,
    BOLD,
    ERROR,
    INFO,
    MUTED,
    PROMPT,
    RESET,
    SUCCESS,
    WARNING,
)

try:
    from .version import __version__
except ImportError:
    from viscose.version import __version__  # type: ignore[nofrom]

try:
    from .update import (
        INSTALLER_LAUNCHED_EXIT_CODE,
        ReleaseInfo,
        check_for_newer_release,
    )
except ImportError:
    from viscose.update import (  # type: ignore[nofrom]
        INSTALLER_LAUNCHED_EXIT_CODE,
        ReleaseInfo,
        check_for_newer_release,
    )

COMMAND_SUMMARY = "auth | watch | upload | update"

_UPDATE_NOTICE_CHECKED = False
_UPDATE_NOTICE_PRINTED = False
_AVAILABLE_RELEASE: Optional[ReleaseInfo] = None

try:  # pragma: no cover - import resolution differs when frozen
    from .cli import main
except ImportError:  # Running as frozen executable where package context is absent
    from viscose.cli import main  # type: ignore[nofrom]


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _maybe_warn_about_updates() -> None:
    global _UPDATE_NOTICE_CHECKED, _UPDATE_NOTICE_PRINTED, _AVAILABLE_RELEASE
    if not _UPDATE_NOTICE_CHECKED:
        _UPDATE_NOTICE_CHECKED = True
        try:
            _AVAILABLE_RELEASE = check_for_newer_release()
        except Exception:
            _AVAILABLE_RELEASE = None
    if _UPDATE_NOTICE_PRINTED or _AVAILABLE_RELEASE is None:
        return

    release = _AVAILABLE_RELEASE
    action = (
        "Run `viscose update` to install."
        if release.asset
        else f"Download the installer from {ACCENT}{release.html_url}{RESET}."
    )
    print(
        f"{WARNING}Update available{RESET}: "
        f"{ACCENT}{__version__}{RESET} → {BOLD}{ACCENT}{release.version}{RESET}. "
        f"{action}"
    )
    _UPDATE_NOTICE_PRINTED = True


def _print_banner() -> None:
    _maybe_warn_about_updates()
    print(
        f"{BOLD}{ACCENT}Viscose Benchmarks CLI{RESET} "
        f"{MUTED}· {COMMAND_SUMMARY} · Press Enter on an empty line to exit{RESET}"
    )
    print(
        f"{MUTED}Need help? Run {ACCENT}viscose --help{MUTED} from PowerShell or Command Prompt for usage details.{RESET}"
    )


def _prompt_for_args() -> Optional[List[str]]:
    prompt_arrow = f"{ACCENT}➤{RESET} "
    help_line = (
        f"{PROMPT}Enter a command{RESET} "
        f"{MUTED}({COMMAND_SUMMARY}, optionally with arguments; press Enter to exit){RESET}"
    )
    while True:
        raw = input(f"{help_line}\n{prompt_arrow}").strip()
        if not raw:
            return None
        try:
            # posix=False keeps Windows-style quoting behaviour
            return shlex.split(raw, posix=False)
        except ValueError as exc:
            print(f"{WARNING}Could not parse input{RESET}: {exc}")


def _prepare_argv() -> Tuple[Optional[List[str]], bool]:
    if len(sys.argv) > 1:
        return sys.argv[1:], False
    if _is_frozen():
        return None, True
    return sys.argv[1:], False


def _execute_command(argv: Optional[List[str]]) -> int:
    exit_code = 0
    if argv is None:
        return exit_code
    try:
        exit_code = main(argv)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            exit_code = exc.code
        else:
            if exc.code:
                print(f"{WARNING}{exc.code}{RESET}", file=sys.stderr)
            exit_code = 1
    except Exception:
        print(f"{ERROR}Unexpected error running viscose CLI:{RESET}", file=sys.stderr)
        traceback.print_exc()
        exit_code = 1
    return exit_code


def _interactive_loop() -> int:
    _print_banner()
    while True:
        args = _prompt_for_args()
        if args is None:
            print(f"\n{MUTED}Exiting Viscose CLI. Goodbye!{RESET}")
            return 0
        print()
        try:
            exit_code = _execute_command(args)
        except KeyboardInterrupt:
            print(f"\n{WARNING}Command interrupted by user.{RESET}")
            exit_code = 130
        else:
            if exit_code == 0:
                print(f"\n{SUCCESS}Command completed successfully.{RESET}")
            elif exit_code == INSTALLER_LAUNCHED_EXIT_CODE:
                print(
                    f"\n{INFO}Closing CLI to allow the installer to continue...{RESET}"
                )
                return 0
            else:
                print(f"\n{ERROR}Command exited with status {exit_code}.{RESET}")
        print()
        _print_banner()


if __name__ == "__main__":
    argv, prompted = _prepare_argv()
    if prompted:
        exit_code = _interactive_loop()
    else:
        exit_code = _execute_command(argv)
        if exit_code == INSTALLER_LAUNCHED_EXIT_CODE:
            exit_code = 0
    raise SystemExit(exit_code)
