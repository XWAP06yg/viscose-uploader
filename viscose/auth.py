from __future__ import annotations

import json
import random
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from viscose_uploader.config import (
    AppConfig,
    DEFAULT_SCORE_HEADERS,
    write_config,
)
from viscose_uploader.paths import AppPaths
from .gcloud_embed import find_gcloud, run_gcloud, gcloud_json
from viscose_uploader.colors import (
    ACCENT,
    BOLD,
    INFO,
    MUTED,
    PROMPT,
    RESET,
    SUCCESS,
    WARNING,
    ERROR,
)

SERVICE_ACCOUNT_HELP_URL = "https://console.cloud.google.com/iam-admin/serviceaccounts"
API_ENABLE_URL = (
    "https://console.cloud.google.com/flows/enableapi?apiid=sheets.googleapis.com"
)


GOOGLE_CLOUD_SDK_URL = "https://cloud.google.com/sdk/docs/install"


def run_auth(paths: AppPaths, *, force_manual: bool = False) -> None:
    paths.ensure()

    # Prefer automated flow via gcloud if available (bundled or installed)
    if not force_manual and find_gcloud():
        _print_header("Viscose Setup — Google Cloud (Automated)")
        _run_auth_with_gcloud(paths)
        return

    # Fallback: manual key import
    _print_header("Viscose Setup — Manual Credentials")
    if not force_manual:
        print(
            f"{WARNING}gcloud was not detected on this machine.{RESET}\n"
            f"{INFO}Install the Google Cloud SDK{RESET} "
            f"({ACCENT}{GOOGLE_CLOUD_SDK_URL}{RESET}) to enable the automated flow, "
            f"or rerun {ACCENT}viscose auth --manual{RESET} to jump straight here.\n"
            f"{MUTED}Continuing with the manual credential import workflow.{RESET}"
        )
    else:
        print(
            f"{INFO}Running manual credential import as requested by --manual.{RESET}"
        )
    setup_steps = [
        f"Open {ACCENT}{SERVICE_ACCOUNT_HELP_URL}{RESET}",
        "Create (or reuse) a project for personal use",
        "Add a service account with the 'Editor' role",
        "Generate a JSON key and download it",
        f"Ensure the Sheets API is enabled ({ACCENT}{API_ENABLE_URL}{RESET})",
    ]
    for idx, step in enumerate(setup_steps, start=1):
        print(f"  {MUTED}{idx}.{RESET} {step}")
    print()

    key_source = _prompt_path("Path to the downloaded service account JSON key")
    key_data = _load_service_account(key_source)

    key_target = paths.base_dir / "service_account.json"
    if key_source.resolve() != key_target.resolve():
        shutil.copy2(key_source, key_target)
        print(f"{INFO}Key copied to{RESET} {ACCENT}{key_target}{RESET}")

    _write_common_config(
        paths, key_target, str(key_data.get("client_email") or "").strip()
    )

    _print_next_steps()


def _write_common_config(paths: AppPaths, key_path: Path, account_email: str) -> None:
    sheet_id = _prompt_google_sheet_id()
    stats_root = _determine_stats_root()
    if not stats_root.exists():
        print(
            f"{WARNING}Warning{RESET}: {ACCENT}{stats_root}{RESET} does not exist yet. "
            "The uploader will create it if needed."
        )

    headers = list(DEFAULT_SCORE_HEADERS)
    worksheet_filter: Optional[list[str]] = None
    poll_interval = 1.0

    config = AppConfig(
        sheet_id=sheet_id,
        stats_root=stats_root,
        google_client_secrets=key_path,
        poll_interval=poll_interval,
        score_header_candidates=headers,
        worksheet_filter=worksheet_filter,
        auth_mode="service_account",
        service_account_email=account_email or None,
    )

    write_config(paths, config)

    print(f"\n{SUCCESS}Configuration complete!{RESET}")
    print(f"  Config: {ACCENT}{paths.config_file}{RESET}")
    print(f"  Service account key: {ACCENT}{key_path}{RESET}")
    print(
        f"\n{BOLD}{WARNING}ACTION REQUIRED{RESET}: Share your Google Sheet with this service account:\n"
        f"  {BOLD}{ACCENT}{account_email}{RESET}\n"
        f"{MUTED}Grant at least Editor access so uploads can update the sheet.{RESET}"
    )


def _run_auth_with_gcloud(paths: AppPaths) -> None:
    _ensure_gcloud_login()
    project_id = _select_or_create_project()
    _enable_apis(project_id)
    account_email = _configure_service_account(paths, project_id)

    key_path = paths.base_dir / "service_account.json"
    _write_common_config(paths, key_path, account_email)

    _print_next_steps()


def _print_next_steps() -> None:
    print(
        f"\n{INFO}Next steps:{RESET}\n"
        f"  {ACCENT}viscose watch{RESET}\n"
        f"  {ACCENT}viscose upload{RESET}"
    )


def _ensure_gcloud_login() -> None:
    accounts = gcloud_json(["auth", "list"]) or []
    active = [a for a in accounts if a.get("status") == "ACTIVE"]
    if active:
        return
    print(f"{INFO}No active gcloud account found. Launching login...{RESET}")
    run_gcloud(["auth", "login"])
    accounts = gcloud_json(["auth", "list"]) or []
    if not any(a.get("status") == "ACTIVE" for a in accounts):
        raise RuntimeError(
            "Authentication failed. Re-run viscose auth after gcloud auth login."
        )


def _select_or_create_project() -> str:
    projects = gcloud_json(["projects", "list"]) or []
    if projects:
        print(f"\n{BOLD}{ACCENT}Existing Google Cloud projects:{RESET}")
        for idx, p in enumerate(projects, start=1):
            name = p.get("name", "")
            print(
                f"  {MUTED}[{idx}]{RESET} {ACCENT}{p['projectId']}{RESET}"
                f"{' - ' + name if name else ''}"
            )
        choice = input(
            f"{PROMPT}Enter the number of the project to use{RESET} "
            f"{MUTED}(press Enter to create a new project){RESET}: "
        ).strip()
        if choice.isdigit():
            i = int(choice)
            if 1 <= i <= len(projects):
                project_id = projects[i - 1]["projectId"]
                run_gcloud(["config", "set", "project", project_id])
                return project_id

    default_id = f"viscose-benchmarks-{random.randint(10**6, 10**8 - 1)}"
    while True:
        project_id = (
            input(
                f"{PROMPT}New project ID{RESET} {MUTED}[default: {default_id}]{RESET}: "
            ).strip()
            or default_id
        )
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project_id):
            print(
                f"{WARNING}Project IDs must be 6-30 chars, start with a letter, and contain letters, digits, or hyphens.{RESET}"
            )
            continue
        break
    project_name = (
        input(
            f"{PROMPT}Project name{RESET} {MUTED}(press Enter to reuse the ID){RESET}: "
        ).strip()
        or project_id
    )
    print(f"{INFO}Creating project{RESET} {ACCENT}{project_id}{RESET}...")
    run_gcloud(["projects", "create", project_id, f"--name={project_name}"])
    run_gcloud(["config", "set", "project", project_id])
    return project_id


def _enable_apis(project_id: str) -> None:
    print(
        f"{INFO}Enabling Google Sheets API (and Drive API for good measure)...{RESET}"
    )
    try:
        run_gcloud(
            ["services", "enable", "sheets.googleapis.com", "drive.googleapis.com"]
        )
    except RuntimeError as exc:
        print(
            f"{WARNING}Could not enable APIs automatically{RESET} ({exc}). "
            "You may need to enable them manually via the Cloud Console."
        )


def _configure_service_account(paths: AppPaths, project_id: str) -> str:
    def prompt_name() -> str:
        default_name = "viscose-uploader"
        while True:
            raw = (
                input(
                    f"{PROMPT}Service account name{RESET} "
                    f"{MUTED}[default: {default_name}]{RESET}: "
                ).strip()
                or default_name
            )
            cleaned = raw.lower()
            if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", cleaned):
                print(
                    f"{WARNING}Name must be 6-30 characters, start with a letter, "
                    f"and contain letters, digits, or hyphens.{RESET}"
                )
                continue
            return cleaned

    name = prompt_name()
    email = f"{name}@{project_id}.iam.gserviceaccount.com"

    existing = (
        gcloud_json(["iam", "service-accounts", "list", f"--project={project_id}"])
        or []
    )
    if not any(a.get("email") == email for a in existing):
        print(f"{INFO}Creating service account{RESET} {ACCENT}{email}{RESET}...")
        run_gcloud(
            [
                "iam",
                "service-accounts",
                "create",
                name,
                "--display-name=Viscose Benchmarks Uploader",
                f"--project={project_id}",
            ]
        )
    else:
        print(f"{INFO}Service account already exists{RESET}: {ACCENT}{email}{RESET}")

    print(f"{INFO}Granting project editor role to the service account...{RESET}")
    run_gcloud(
        [
            "projects",
            "add-iam-policy-binding",
            project_id,
            f"--member=serviceAccount:{email}",
            "--role=roles/editor",
        ]
    )

    key_path = paths.base_dir / "service_account.json"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"{INFO}Generating new service account key...{RESET}")
    try:
        run_gcloud(
            [
                "iam",
                "service-accounts",
                "keys",
                "create",
                str(key_path),
                f"--iam-account={email}",
            ]
        )
    except RuntimeError as exc:
        message = str(exc)
        if _is_key_quota_error(message):
            if _offer_key_cleanup(email):
                print(
                    f"{INFO}Retrying key generation after removing an old key...{RESET}"
                )
                try:
                    run_gcloud(
                        [
                            "iam",
                            "service-accounts",
                            "keys",
                            "create",
                            str(key_path),
                            f"--iam-account={email}",
                        ]
                    )
                except RuntimeError as retry_exc:
                    _print_key_limit_help(email, str(retry_exc))
                    raise RuntimeError(
                        "Failed to generate a new service account key. "
                        "See details above."
                    ) from retry_exc
                return email
            _print_key_limit_help(email, message)
        raise RuntimeError(
            "Failed to generate a new service account key. See details above."
        ) from exc
    return email


def _prompt_path(message: str) -> Path:
    while True:
        raw = input(f"{PROMPT}{message}{RESET}: ").strip().strip('"')
        if not raw:
            print(f"{WARNING}This field is required.{RESET}")
            continue
        path = Path(raw).expanduser()
        if path.is_file():
            print(f"{SUCCESS}Found file{RESET}: {ACCENT}{path}{RESET}")
            return path
        print(
            f"{ERROR}File not found{RESET}. "
            "Please provide a valid path to the JSON key."
        )


def _load_service_account(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON key: {exc}") from exc
    required_keys = {"client_email", "private_key", "token_uri"}
    missing = [key for key in required_keys if not data.get(key)]
    if missing:
        raise RuntimeError(
            f"Service account key is missing required fields: {', '.join(missing)}"
        )
    return data


def _is_key_quota_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "failed_precondition" in lowered
        or "quota" in lowered
        or "precondition check failed" in lowered
    )


def _offer_key_cleanup(email: str) -> bool:
    keys = _list_user_managed_keys(email)
    if not keys:
        print(
            f"{WARNING}Could not list existing user-managed keys automatically.{RESET} "
            "You may need to delete an old key manually."
        )
        return False

    _print_key_table(email, keys)

    if not _prompt_yes_no(
        "Delete one of these keys now to free up space?", default=False
    ):
        return False

    while True:
        choice = input(
            f"{PROMPT}Enter the number of the key to delete{RESET} "
            f"{MUTED}(or press Enter to cancel){RESET}: "
        ).strip()
        if not choice:
            print(f"{MUTED}Skipping automatic cleanup.{RESET}")
            return False
        if not choice.isdigit():
            print(f"{WARNING}Please enter a valid number.{RESET}")
            continue
        index = int(choice)
        if not (1 <= index <= len(keys)):
            print(f"{WARNING}Select a number between 1 and {len(keys)}.{RESET}")
            continue
        selected = keys[index - 1]
        key_id = selected["id"]
        if not _prompt_yes_no(
            f"Delete key {key_id}? This action cannot be undone.", default=False
        ):
            continue
        try:
            run_gcloud(
                [
                    "iam",
                    "service-accounts",
                    "keys",
                    "delete",
                    key_id,
                    f"--iam-account={email}",
                    "--quiet",
                ]
            )
        except RuntimeError as exc:
            print(
                f"{ERROR}Failed to delete key {key_id}:{RESET} {exc}\n"
                "Choose a different key or cancel."
            )
            if not _prompt_yes_no("Try deleting another key?", default=False):
                return False
            keys = _list_user_managed_keys(email)
            if not keys:
                print(f"{WARNING}No keys remain to delete automatically.{RESET}")
                return False
            _print_key_table(email, keys)
            continue

        print(f"{SUCCESS}Deleted key{RESET}: {ACCENT}{key_id}{RESET}")
        return True


def _list_user_managed_keys(email: str) -> list[dict[str, str]]:
    try:
        response = gcloud_json(
            [
                "iam",
                "service-accounts",
                "keys",
                "list",
                f"--iam-account={email}",
                "--managed-by=user",
            ]
        )
    except RuntimeError:
        return []

    keys: list[dict[str, str]] = []
    for entry in response or []:
        name = entry.get("name") or ""
        if not name:
            continue
        key_id = name.split("/")[-1]
        keys.append(
            {
                "id": key_id,
                "created": entry.get("validAfterTime") or "",
                "expires": entry.get("validBeforeTime") or "",
            }
        )
    keys.sort(key=lambda k: k["created"] or "")
    return keys


def _format_timestamp(raw: str) -> str:
    if not raw:
        return ""
    try:
        value = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw


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


def _print_key_limit_help(email: str, message: str) -> None:
    print(
        f"{ERROR}Google Cloud rejected the key creation request.{RESET}\n"
        f"{WARNING}Most likely you have reached the limit of 10 active keys for this service account.{RESET}\n"
        f"{INFO}List user-managed keys:{RESET}\n"
        f'  {ACCENT}gcloud iam service-accounts keys list --iam-account={email} --managed-by=user --format="table(name.basename(), validAfterTime, validBeforeTime)"{RESET}\n'
        f"{INFO}Delete unused keys:{RESET}\n"
        f"  {ACCENT}gcloud iam service-accounts keys delete KEY_ID --iam-account={email} --quiet{RESET}\n"
        "Then rerun `viscose auth`.\n"
        f"The original error was: {message}"
    )


def _print_key_table(email: str, keys: list[dict[str, str]]) -> None:
    print(f"\n{INFO}Existing user-managed keys for {ACCENT}{email}{RESET}:")
    print(f"  {MUTED}#  Key ID            Created (UTC)        Expires{RESET}")
    for idx, key in enumerate(keys, start=1):
        key_id = key["id"]
        created = _format_timestamp(key["created"])
        expires = _format_timestamp(key["expires"]) if key["expires"] else "never"
        print(
            f"  {MUTED}{idx:>2}{RESET} {ACCENT}{key_id}{RESET}  {created:<19}  {expires}"
        )


def _prompt_headers() -> list[str]:
    default_headers = ", ".join(DEFAULT_SCORE_HEADERS)
    headers_input = input(
        f"{PROMPT}Comma separated header names for the score column{RESET} "
        f"{MUTED}[default: {default_headers}]{RESET}: "
    ).strip()
    if headers_input:
        user_headers = [h.strip() for h in headers_input.split(",") if h.strip()]
    else:
        user_headers = list(DEFAULT_SCORE_HEADERS)

    combined_headers: list[str] = []
    seen = set()
    for candidate in user_headers + list(DEFAULT_SCORE_HEADERS):
        if not candidate:
            continue
        key = candidate.lower()
        if key not in seen:
            combined_headers.append(candidate)
            seen.add(key)
    return combined_headers


def _prompt_worksheet_filter() -> Optional[list[str]]:
    worksheet_input = input(
        f"{PROMPT}Worksheet titles to scan{RESET} "
        f"{MUTED}(comma separated, leave blank to scan all tabs){RESET}: "
    ).strip()
    worksheets = [w.strip() for w in worksheet_input.split(",") if w.strip()]
    return worksheets or None


def _prompt_required(message: str) -> str:
    while True:
        value = input(f"{PROMPT}{message}{RESET}: ").strip()
        if value:
            return value
        print(f"{WARNING}This field is required.{RESET}")


def _prompt_google_sheet_id() -> str:
    print(
        f"{INFO}Paste the full Google Sheet URL or the sheet ID (between /d/ and /edit).{RESET}"
    )
    while True:
        raw = input(f"{PROMPT}Google Sheet URL or ID{RESET}: ").strip()
        if not raw:
            print(f"{WARNING}This field is required.{RESET}")
            continue
        sheet_id = _extract_sheet_id(raw)
        if sheet_id:
            print(f"{SUCCESS}Detected sheet ID{RESET}: {ACCENT}{sheet_id}{RESET}")
            return sheet_id
        print(
            f"{ERROR}Could not extract a sheet ID from that input.{RESET} "
            "Paste the share URL or the value shown between /d/ and /edit."
        )


def _prompt_float(message: str, *, default: float) -> float:
    while True:
        raw = input(
            f"{PROMPT}{message}{RESET} {MUTED}[default: {default}]{RESET}: "
        ).strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print(f"{WARNING}Please enter a numeric value.{RESET}")


def _extract_sheet_id(value: str) -> Optional[str]:
    value = value.strip()
    if not value:
        return None
    match = re.search(r"/d/([A-Za-z0-9-_]+)", value)
    if match:
        return match.group(1)
    match = re.search(r"[?&](?:key|id)=([A-Za-z0-9-_]+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9-_]{20,120}", value):
        return value
    return None


def _determine_stats_root() -> Path:
    default_path = Path(
        r"C:\Program Files (x86)\Steam\steamapps\common\FPSAimTrainer\FPSAimTrainer\stats"
    )
    print(
        f"\n{INFO}Kovaaks stats directory{RESET} "
        f"{MUTED}(press Enter to accept the default){RESET}"
    )
    while True:
        raw = (
            input(
                f"{PROMPT}Stats directory{RESET} {MUTED}[default: {default_path}]{RESET}: "
            )
            .strip()
            .strip('"')
        )
        if not raw:
            print(
                f"{SUCCESS}Using default stats directory{RESET}: "
                f"{ACCENT}{default_path}{RESET}"
            )
            return default_path
        stats_path = Path(raw).expanduser()
        print(
            f"{SUCCESS}Using custom stats directory{RESET}: {ACCENT}{stats_path}{RESET}"
        )
        return stats_path


def _print_header(title: str) -> None:
    print(f"\n{BOLD}{ACCENT}{title}{RESET}")
