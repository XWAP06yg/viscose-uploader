from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Sequence, Tuple


class GoogleClientError(RuntimeError):
    pass


def _ensure_dependencies() -> None:
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
    except ImportError as exc:
        raise GoogleClientError(
            "Missing Google API dependencies. Install them with:\n"
            "  pip install google-api-python-client google-auth google-auth-oauthlib"
        ) from exc


@dataclass
class GoogleSheetsClient:
    service: "googleapiclient.discovery.Resource"
    _sheet_cache: Dict[Tuple[str, str], List[List[str]]] = field(default_factory=dict)
    _sheet_list_cache: Dict[str, List[str]] = field(default_factory=dict)

    def resolve_target_cell(
        self,
        spreadsheet_id: str,
        scenario_name: str,
        header_candidates: Sequence[str],
        worksheet_filter: Optional[Sequence[str]] = None,
        cached_sheet: Optional[str] = None,
        cached_score_cell: Optional[str] = None,
        cached_scenario_cell: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Determine the worksheet and cell locations for the scenario and score.
        Returns (worksheet_title, score_cell_ref, scenario_cell_ref).
        """
        scenario_key = scenario_name.strip().lower()
        scenario_norm = _normalize_name(scenario_name)
        scenario_letters = _letters_only(scenario_name)
        headers = [item.strip().lower() for item in header_candidates if item.strip()]
        if not headers:
            headers = ["your score"]

        if cached_sheet and cached_score_cell and cached_scenario_cell:
            cached_values = self._get_sheet_values(spreadsheet_id, cached_sheet)
            if self._scenario_cell_matches(
                cached_values, cached_scenario_cell, scenario_key
            ) and self._score_cell_matches(cached_values, cached_score_cell, headers):
                return cached_sheet, cached_score_cell, cached_scenario_cell

        if spreadsheet_id in self._sheet_list_cache:
            sheet_titles = self._sheet_list_cache[spreadsheet_id]
        else:
            try:
                meta = (
                    self.service.spreadsheets()
                    .get(
                        spreadsheetId=spreadsheet_id,
                        fields="sheets(properties(title))",
                    )
                    .execute()
                )
            except Exception as exc:  # noqa: BLE001
                raise GoogleClientError(f"Failed to list sheets: {exc}") from exc
            sheet_titles = [
                sheet["properties"]["title"] for sheet in meta.get("sheets", [])
            ]
            self._sheet_list_cache[spreadsheet_id] = sheet_titles

        allowed_titles = (
            {title.strip() for title in worksheet_filter} if worksheet_filter else None
        )

        best_fallback: Optional[Tuple[str, str, str, int]] = None

        for title in sheet_titles:
            if allowed_titles and title not in allowed_titles:
                continue

            values = self._get_sheet_values(spreadsheet_id, title)
            if not values:
                continue

            progress_col = self._find_progress_column(values)
            score_columns = self._find_score_columns(values, headers)
            for row_idx, row in enumerate(values, start=1):
                for col_idx, cell in enumerate(row, start=1):
                    if isinstance(cell, str) and cell.strip().lower() == scenario_key:
                        scenario_cell = f"{_column_letter(col_idx)}{row_idx}"
                        score_col_idx = self._select_score_column(
                            col_idx, score_columns, progress_col
                        )
                        score_cell = f"{_column_letter(score_col_idx)}{row_idx}"
                    if isinstance(cell, str):
                        cell_norm = _normalize_name(cell)
                        cell_letters = _letters_only(cell)
                        if (
                            cell_norm == scenario_norm
                            or cell_letters == scenario_letters
                        ):
                            scenario_cell = f"{_column_letter(col_idx)}{row_idx}"
                            score_col_idx = self._select_score_column(
                                col_idx, score_columns, progress_col
                            )
                            score_cell = f"{_column_letter(score_col_idx)}{row_idx}"
                            diff = abs(len(cell_norm) - len(scenario_norm))
                            if best_fallback is None or diff < best_fallback[3]:
                                best_fallback = (
                                    title,
                                    score_cell,
                                    scenario_cell,
                                    diff,
                                )

        if best_fallback:
            return best_fallback[0], best_fallback[1], best_fallback[2]

        raise GoogleClientError(
            f"Could not locate scenario '{scenario_name}' or an update column in the Google Sheet."
        )

    def update_cell(self, spreadsheet_id: str, cell_ref: str, value: float) -> None:
        body = {"values": [[value]]}
        (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=cell_ref,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )

    def _scenario_cell_matches(
        self,
        sheet_values: List[List[str]],
        scenario_cell: str,
        scenario_key: str,
    ) -> bool:
        indexes = _cell_to_indexes(scenario_cell)
        if not indexes:
            return False
        row_idx, col_idx = indexes
        if row_idx >= len(sheet_values):
            return False
        row = sheet_values[row_idx]
        if col_idx >= len(row):
            return False
        cell_value = row[col_idx]
        if not isinstance(cell_value, str):
            return False
        return cell_value.strip().lower() == scenario_key

    def _score_cell_matches(
        self,
        sheet_values: List[List[str]],
        score_cell: str,
        header_candidates: Sequence[str],
    ) -> bool:
        indexes = _cell_to_indexes(score_cell)
        if not indexes:
            return False
        _, col_idx = indexes
        progress_col = self._find_progress_column(sheet_values)
        limit = min(len(sheet_values), 200)
        for row in sheet_values[:limit]:
            if col_idx < len(row):
                cell_value = row[col_idx]
                if (
                    isinstance(cell_value, str)
                    and cell_value.strip().lower() in header_candidates
                ):
                    return True
                if progress_col is not None:
                    progress_zero = progress_col - 1
                    if (
                        col_idx == progress_zero + 1
                        and progress_zero < len(row)
                        and isinstance(row[progress_zero], str)
                        and row[progress_zero].strip().lower() == "progress"
                    ):
                        return True
        return False

    def _get_sheet_values(self, spreadsheet_id: str, worksheet: str) -> List[List[str]]:
        cache_key = (spreadsheet_id, worksheet)
        if cache_key in self._sheet_cache:
            return self._sheet_cache[cache_key]
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=f"'{worksheet}'")
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            raise GoogleClientError(
                f"Failed to read worksheet '{worksheet}': {exc}"
            ) from exc
        values = result.get("values", [])
        self._sheet_cache[cache_key] = values
        return values

    def _find_score_columns(
        self,
        sheet_values: List[List[str]],
        header_candidates: Sequence[str],
    ) -> List[int]:
        columns: List[int] = []
        for row in sheet_values[:200]:  # scan top portion for headers
            for idx, value in enumerate(row, start=1):
                if (
                    isinstance(value, str)
                    and value.strip().lower() in header_candidates
                ):
                    if idx not in columns:
                        columns.append(idx)
        return columns

    def _select_score_column(
        self,
        scenario_col: int,
        score_columns: Sequence[int],
        progress_col: Optional[int],
    ) -> int:
        if score_columns:
            return score_columns[0]
        if progress_col is not None and progress_col > 1:
            return progress_col - 1
        # fallback heuristic: assume score column is a few columns to the right
        return max(1, scenario_col + 3)

    def _find_progress_column(self, sheet_values: List[List[str]]) -> Optional[int]:
        for row in sheet_values[:200]:
            for idx, value in enumerate(row, start=1):
                if isinstance(value, str) and value.strip().lower() == "progress":
                    return idx
        return None

    def find_mirror_cells(
        self,
        spreadsheet_id: str,
        worksheet: str,
        score_cell: str,
        header_candidates: Sequence[str],
    ) -> List[str]:
        values = self._get_sheet_values(spreadsheet_id, worksheet)
        indexes = _cell_to_indexes(score_cell)
        if not indexes:
            return []

        row_idx, col_idx = indexes
        score_col = col_idx + 1  # 1-based
        mirrors: List[int] = []
        header_set = {item.strip().lower() for item in header_candidates if item}
        header_set.add("high score")

        # Detect merged headers that leave a blank neighbour before "Progress"
        for header_row in values[:20]:
            if len(header_row) >= score_col:
                header_val = header_row[score_col - 1]
                if (
                    isinstance(header_val, str)
                    and header_val.strip().lower() in header_set
                ):
                    neighbour = (
                        header_row[score_col] if len(header_row) > score_col else ""
                    )
                    progress_candidate = (
                        header_row[score_col + 1]
                        if len(header_row) > score_col + 1
                        else ""
                    )
                    if (
                        (not isinstance(neighbour, str) or not neighbour.strip())
                        and isinstance(progress_candidate, str)
                        and progress_candidate.strip().lower() == "progress"
                    ):
                        mirrors.append(score_col + 1)
                    break

        # If the data row currently mirrors the value to the right, include it
        if row_idx < len(values):
            row = values[row_idx]
        if len(row) > col_idx + 1 and row[col_idx] == row[col_idx + 1]:
            mirror_col = score_col + 1
            if mirror_col not in mirrors:
                mirrors.append(mirror_col)

        return [f"{_column_letter(col)}{row_idx + 1}" for col in mirrors]

    def get_numeric_cell(
        self,
        spreadsheet_id: str,
        worksheet: str,
        cell_ref: str,
    ) -> Optional[float]:
        values = self._get_sheet_values(spreadsheet_id, worksheet)
        indexes = _cell_to_indexes(cell_ref)
        if not indexes:
            return None
        row_idx, col_idx = indexes
        if row_idx >= len(values):
            return None
        row = values[row_idx]
        if col_idx >= len(row):
            return None
        cell_value = row[col_idx]
        if isinstance(cell_value, (int, float)):
            return float(cell_value)
        if isinstance(cell_value, str):
            cleaned = cell_value.replace(",", "").strip()
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None


def build_google_client(
    paths: "AppPaths",
    credentials_file: str,
    *,
    use_service_account: bool = False,
    delegated_user: Optional[str] = None,
) -> GoogleSheetsClient:
    _ensure_dependencies()

    from googleapiclient.discovery import build

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    if use_service_account:
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise GoogleClientError(
                "Missing service account dependencies. Install them with:\n"
                "  pip install google-auth"
            ) from exc

        try:
            creds = service_account.Credentials.from_service_account_file(
                credentials_file,
                scopes=SCOPES,
            )
        except FileNotFoundError as exc:
            raise GoogleClientError(
                f"Service account file not found: {credentials_file}"
            ) from exc
        except ValueError as exc:
            raise GoogleClientError(
                f"Failed to load service account credentials from {credentials_file}: {exc}"
            ) from exc

        if delegated_user:
            creds = creds.with_subject(delegated_user)

        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return GoogleSheetsClient(service=service)

    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    token_path = paths.token_file
    creds: Optional[Credentials] = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with token_path.open("w", encoding="utf-8") as handle:
            handle.write(creds.to_json())

    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return GoogleSheetsClient(service=service)


def _column_letter(index: int) -> str:
    result = ""
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result or "A"


def _cell_to_indexes(cell: str) -> Optional[Tuple[int, int]]:
    if not cell:
        return None
    cell = cell.strip().upper()
    letters = ""
    digits = ""
    for char in cell:
        if char.isalpha():
            if digits:
                # letters should precede digits
                return None
            letters += char
        elif char.isdigit():
            digits += char
        else:
            return None
    if not letters or not digits:
        return None
    col_index = 0
    for char in letters:
        col_index = col_index * 26 + (ord(char) - 64)
    try:
        row_index = int(digits)
    except ValueError:
        return None
    if row_index <= 0:
        return None
    return row_index - 1, col_index - 1


def _normalize_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _letters_only(text: str) -> str:
    return re.sub(r"[^a-z]+", "", text.lower())
