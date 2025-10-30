from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, BinaryIO

from viscose.version import __version__
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

INSTALLER_LAUNCHED_EXIT_CODE = 200

__all__ = [
    "run_update",
    "check_for_newer_release",
    "ReleaseInfo",
    "INSTALLER_LAUNCHED_EXIT_CODE",
]

DEFAULT_REPOSITORY = "XWAP06yg/viscose-uploader"
DEFAULT_ASSET_HINT = "Viscose-Setup.exe"
API_TEMPLATE = "https://api.github.com/repos/{repo}/releases/latest"
USER_AGENT = "viscose-cli-updater"


class UpdateError(RuntimeError):
    """Raised when an update step fails."""


@dataclass
class ReleaseAsset:
    name: str
    download_url: str
    size: int


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    name: str
    notes: str
    html_url: str
    asset: Optional[ReleaseAsset]


def check_for_newer_release() -> Optional[ReleaseInfo]:
    """Return the latest release if it is newer than the current version."""
    repo = os.getenv("VISCOSE_UPDATE_REPO", DEFAULT_REPOSITORY)
    asset_hint = os.getenv("VISCOSE_UPDATE_ASSET", DEFAULT_ASSET_HINT)
    token = os.getenv("VISCOSE_UPDATE_TOKEN")

    try:
        release = _fetch_latest_release(repo, asset_hint, token)
    except UpdateError:
        return None

    if not release.version:
        return None

    if not _is_newer_version(release.version, __version__):
        return None

    return release


def run_update(download_dir: Path) -> int:
    repo = os.getenv("VISCOSE_UPDATE_REPO", DEFAULT_REPOSITORY)
    asset_hint = os.getenv("VISCOSE_UPDATE_ASSET", DEFAULT_ASSET_HINT)
    token = os.getenv("VISCOSE_UPDATE_TOKEN")

    print(f"{INFO}Checking for updates for {ACCENT}{repo}{RESET}...")

    try:
        release = _fetch_latest_release(repo, asset_hint, token)
    except UpdateError as exc:
        print(f"{ERROR}{exc}{RESET}")
        return 1

    current_version = __version__

    if not release.version:
        print(
            f"{WARNING}Latest release does not expose a semantic version.{RESET} "
            f"See {ACCENT}{release.html_url}{RESET}"
        )
        return 1

    if not _is_newer_version(release.version, current_version):
        print(
            f"{SUCCESS}You are on the latest version{RESET} "
            f"({ACCENT}{current_version}{RESET})."
        )
        return 0

    print(
        f"{INFO}Update available!{RESET} "
        f"{ACCENT}{current_version}{RESET} → {BOLD}{ACCENT}{release.version}{RESET}"
    )
    print(f"Release: {release.name or release.tag}")
    print(f"Notes: {ACCENT}{release.html_url}{RESET}")
    if release.notes:
        print(f"\n{MUTED}Highlights:{RESET}\n{_format_release_notes(release.notes)}")

    asset = release.asset
    if asset is None:
        print(
            f"\n{WARNING}No downloadable installer asset matching "
            f"'{asset_hint}' was found.{RESET}\n"
            "Please download the update manually from the release page."
        )
        return 1

    if not _prompt_yes_no(
        "Download and launch the latest installer now?", default=True
    ):
        print(f"{MUTED}Update skipped by request.{RESET}")
        return 0

    try:
        installer_path = _download_asset(asset, download_dir)
    except UpdateError as exc:
        print(f"{ERROR}{exc}{RESET}")
        return 1

    print(f"{SUCCESS}Installer downloaded{RESET}: {ACCENT}{installer_path}{RESET}")

    try:
        _launch_installer(installer_path)
    except UpdateError as exc:
        print(
            f"{ERROR}Failed to launch installer automatically.{RESET} "
            f"Run it manually from:\n  {ACCENT}{installer_path}{RESET}\n"
            f"Details: {exc}"
        )
        return 1

    print(
        f"{INFO}Installer launched.{RESET} Complete the setup wizard, then "
        f"restart Viscose to use the updated version.\n"
        f"{WARNING}This window will now close so the installer can replace the executable.{RESET}"
    )
    return INSTALLER_LAUNCHED_EXIT_CODE


def _fetch_latest_release(
    repo: str, asset_hint: str, token: Optional[str]
) -> ReleaseInfo:
    url = API_TEMPLATE.format(repo=repo)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            hint = (
                "Ensure the repository exists and is public, or set VISCOSE_UPDATE_TOKEN "
                "with a GitHub personal access token that can read it."
            )
        elif exc.code == 401:
            hint = "Authentication failed. Check VISCOSE_UPDATE_TOKEN or repository visibility."
        else:
            hint = "Check the repository name or try again later."
        raise UpdateError(f"GitHub API responded with HTTP {exc.code}. {hint}") from exc
    except urllib.error.URLError as exc:
        raise UpdateError("Could not reach GitHub to check for updates.") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise UpdateError("Failed to parse GitHub release response.") from exc

    tag = str(data.get("tag_name") or "")
    version = _normalise_version_tag(tag)
    name = str(data.get("name") or "")
    notes = str(data.get("body") or "")
    html_url = str(data.get("html_url") or "")
    assets = data.get("assets") or []

    asset_obj = _select_asset(assets, asset_hint)

    return ReleaseInfo(
        tag=tag,
        version=version,
        name=name,
        notes=notes,
        html_url=html_url,
        asset=asset_obj,
    )


def _select_asset(assets: list[dict], asset_hint: str) -> Optional[ReleaseAsset]:
    for raw in assets:
        name = str(raw.get("name") or "")
        download_url = str(raw.get("browser_download_url") or "")
        if not name or not download_url:
            continue
        if asset_hint.lower() in name.lower():
            size = int(raw.get("size") or 0)
            return ReleaseAsset(name=name, download_url=download_url, size=size)
    return None


def _download_asset(asset: ReleaseAsset, base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)

    destination = base_dir / asset.name
    temp_handle = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
    temp_handle.close()
    temp_destination = Path(temp_handle.name)
    temp_destination.unlink(missing_ok=True)

    print(
        f"{INFO}Downloading{RESET} {ACCENT}{asset.name}{RESET} "
        f"({MUTED}{_format_size(asset.size)}{RESET})..."
    )

    request = urllib.request.Request(
        asset.download_url,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            temp_destination.open("wb") as handle,
        ):
            _stream_to_file(response, handle, asset.size)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"Download failed with HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise UpdateError("Network error while downloading the installer.") from exc
    except OSError as exc:
        raise UpdateError(f"Could not write installer file: {exc}") from exc

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.unlink()
        temp_destination.replace(destination)
    except OSError as exc:
        raise UpdateError(f"Failed to place installer at {destination}: {exc}") from exc

    return destination


def _stream_to_file(response, handle: BinaryIO, total_size: int) -> None:
    chunk_size = 1024 * 256
    downloaded = 0
    while True:
        chunk = response.read(chunk_size)
        if not chunk:
            break
        handle.write(chunk)
        downloaded += len(chunk)
        _print_progress(downloaded, total_size)
    if total_size:
        _print_progress(total_size, total_size)
    print()


def _print_progress(downloaded: int, total: int) -> None:
    if not total:
        return
    percent = downloaded / total * 100
    bar = f"{percent:6.2f}%"
    sys.stdout.write(f"\r{MUTED}{bar}{RESET}")
    sys.stdout.flush()


def _launch_installer(path: Path) -> None:
    try:
        subprocess.Popen([str(path)], shell=False)
    except OSError as exc:
        raise UpdateError(str(exc)) from exc


def _prompt_yes_no(message: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = (
            input(f"{PROMPT}{message}{RESET} {MUTED}{suffix}{RESET}: ").strip().lower()
        )
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print(f"{WARNING}Please answer yes or no.{RESET}")


def _format_release_notes(notes: str) -> str:
    lines = notes.strip().splitlines()
    limited = lines[:8]
    formatted = "\n".join(textwrap.fill(line, width=80) for line in limited if line)
    if len(lines) > len(limited):
        formatted += f"\n{MUTED}... (see release page for full notes){RESET}"
    return formatted


def _normalise_version_tag(tag: str) -> str:
    tag = tag.strip()
    if tag.lower().startswith("v"):
        tag = tag[1:]
    return tag


def _parse_version(value: str) -> tuple[int, ...]:
    parts = []
    for chunk in value.split("."):
        numeric = "".join(ch for ch in chunk if ch.isdigit())
        if not numeric:
            break
        parts.append(int(numeric))
    return tuple(parts)


def _is_newer_version(candidate: str, current: str) -> bool:
    return _parse_version(candidate) > _parse_version(current)


def _format_size(size: int) -> str:
    if not size:
        return "unknown size"
    step = 1024
    units = ["bytes", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < step or unit == units[-1]:
            if unit == "bytes":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= step
    return f"{size} bytes"
