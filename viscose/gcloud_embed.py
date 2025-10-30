from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Optional


def _exe_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller one-file sets this
        return Path(sys.executable).resolve().parent
    # Running from source
    return Path(__file__).resolve().parent


def _candidate_paths() -> list[Path]:
    base = _exe_dir()
    candidates: list[Path] = []
    # Side-by-side layouts that we will support in releases
    candidates.append(base / "google-cloud-sdk" / "bin" / "gcloud.cmd")
    candidates.append(base / "google-cloud-sdk" / "bin" / "gcloud.ps1")
    # Some users may put the SDK under a vendor folder
    candidates.append(base / "vendor" / "google-cloud-sdk" / "bin" / "gcloud.cmd")
    candidates.append(base / "vendor" / "google-cloud-sdk" / "bin" / "gcloud.ps1")

    # Installed on PATH: prefer .cmd, then .exe, then .ps1
    for name in ("gcloud.cmd", "gcloud.exe", "gcloud"):
        path = shutil.which(name)
        if path:
            candidates.append(Path(path))
            break
    ps1 = shutil.which("gcloud.ps1")
    if ps1:
        candidates.append(Path(ps1))
    return candidates


def find_gcloud() -> Optional[Path]:
    # Allow explicit override
    override = os.environ.get("VISCOSE_GCLOUD")
    if override:
        p = Path(override)
        if p.exists():
            return p

    for cand in _candidate_paths():
        if cand and cand.exists():
            return cand
    return None


def run_gcloud(args: Iterable[str]) -> str:
    bin_path = find_gcloud()
    if not bin_path:
        raise RuntimeError(
            "gcloud CLI not found. Ship 'google-cloud-sdk' next to viscose.exe or set VISCOSE_GCLOUD."
        )

    cmd: list[str]
    env = os.environ.copy()
    # Prefer the SDK's bundled python if available
    sdk_root = bin_path.parent.parent if bin_path.name.startswith("gcloud") else None
    if sdk_root and (sdk_root / "platform" / "bundledpython" / "python.exe").exists():
        env.setdefault(
            "CLOUDSDK_PYTHON",
            str(sdk_root / "platform" / "bundledpython" / "python.exe"),
        )

    if bin_path.suffix.lower() == ".ps1":
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(bin_path),
            *list(args),
        ]
    else:
        cmd = [str(bin_path), *list(args)]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "Unknown gcloud error"
        raise RuntimeError(message) from exc
    except FileNotFoundError as exc:
        raise RuntimeError("Failed to execute gcloud") from exc


def gcloud_json(args: Iterable[str]) -> Any:
    output = run_gcloud([*args, "--format=json"])
    if not output:
        return []
    return json.loads(output)

