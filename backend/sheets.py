"""
Google Sheets async client for Mess Attendance System.

Sheet structure (all in one Google Sheets document):
  Sheet 1: Users      — id, name, email, password_hash, tokens_remaining, plan, is_admin, created_at
  Sheet 2: Attendance — date, timestamp, user_id, user_name, meal_type
  Sheet 3: Audit      — timestamp, user_id, action, metadata
  Sheet 4: QRCodes    — timestamp, admin_id, payload
"""

import os
import json
import asyncio
import logging
from functools import partial
from typing import Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Column definitions (1-indexed, matching sheet header order)
USERS_HEADERS    = ["id", "name", "email", "password_hash", "tokens_remaining", "plan", "is_admin", "created_at"]
ATTEND_HEADERS   = ["date", "timestamp", "user_id", "user_name", "meal_type"]
AUDIT_HEADERS    = ["timestamp", "user_id", "action", "metadata"]
QR_HEADERS       = ["timestamp", "admin_id", "payload"]


class SheetError(Exception):
    pass


def _row_to_dict(headers: list[str], row: list) -> dict:
    """Zip a header list with a row, padding short rows with empty strings."""
    padded = list(row) + [""] * (len(headers) - len(row))
    return dict(zip(headers, padded))


class SheetsClient:
    """Thread-safe async wrapper around gspread (sync library run in executor)."""

    def __init__(self):
        self._gc: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._users_ws: Optional[gspread.Worksheet] = None
        self._attend_ws: Optional[gspread.Worksheet] = None
        self._audit_ws: Optional[gspread.Worksheet] = None
        self._qr_ws: Optional[gspread.Worksheet] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def init(self):
        self._loop = asyncio.get_event_loop()
        await self._loop.run_in_executor(None, self._sync_init)

    def _sync_init(self):
        service_account_val = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        if not service_account_val or not sheet_id:
            raise SheetError(
                "GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_ID env vars are required."
            )

        import base64

        # Accept either raw JSON or base64-encoded JSON.
        # If the value starts with '{' it's already plain JSON; otherwise
        # assume it's base64 and decode it first.
        stripped = service_account_val.strip()
        if stripped.startswith("{"):
            # Raw JSON pasted directly into .env
            raw_json = stripped
        else:
            # Base64-encoded JSON (e.g. from: base64 -w 0 service_account.json)
            try:
                raw_json = base64.b64decode(stripped).decode("utf-8")
            except Exception as exc:
                raise SheetError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON is neither valid JSON nor valid base64. "
                    "Set it to the raw contents of your service account JSON file, or "
                    "base64-encode it with: base64 -w 0 service_account.json"
                ) from exc

        try:
            service_account_info = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise SheetError(f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON: {exc}") from exc

        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, SCOPES)
        self._gc = gspread.authorize(creds)
        self._spreadsheet = self._gc.open_by_key(sheet_id)
        self._users_ws  = self._ensure_worksheet("Users",      USERS_HEADERS)
        self._attend_ws = self._ensure_worksheet("Attendance", ATTEND_HEADERS)
        self._audit_ws  = self._ensure_worksheet("Audit",      AUDIT_HEADERS)
        self._qr_ws     = self._ensure_worksheet("QRCodes",    QR_HEADERS)

    def _ensure_worksheet(self, title: str, headers: list[str]) -> gspread.Worksheet:
        try:
            ws = self._spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self._spreadsheet.add_worksheet(title=title, rows=5000, cols=len(headers))
            ws.append_row(headers, value_input_option="RAW")
            logger.info("Created worksheet '%s'", title)
        else:
            # Ensure header row exists
            existing = ws.row_values(1)
            if not existing:
                ws.append_row(headers, value_input_option="RAW")
        return ws

    async def _run(self, fn, *args, **kwargs):
        """Run a sync gspread call in the thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    # ── Users ──────────────────────────────────────────────────────────────────

    async def append_user(self, user: dict):
        row = [user.get(h, "") for h in USERS_HEADERS]
        await self._run(self._users_ws.append_row, row, value_input_option="RAW")

    async def find_user_by_email(self, email: str) -> Optional[dict]:
        email = email.lower().strip()
        all_rows = await self._run(self._users_ws.get_all_values)
        if len(all_rows) < 2:
            return None
        headers = all_rows[0]
        for row in all_rows[1:]:
            d = _row_to_dict(headers, row)
            if d.get("email", "").lower() == email:
                return d
        return None

    async def find_user_by_id(self, user_id: str) -> Optional[dict]:
        all_rows = await self._run(self._users_ws.get_all_values)
        if len(all_rows) < 2:
            return None
        headers = all_rows[0]
        for row in all_rows[1:]:
            d = _row_to_dict(headers, row)
            if d.get("id") == user_id:
                return d
        return None

    async def update_tokens(self, user_id: str, new_tokens: int):
        all_rows = await self._run(self._users_ws.get_all_values)
        if len(all_rows) < 2:
            raise SheetError("Users sheet is empty or missing headers.")
        headers = all_rows[0]
        try:
            id_col = headers.index("id") + 1
            tok_col = headers.index("tokens_remaining") + 1
        except ValueError as e:
            raise SheetError(f"Users sheet missing expected column: {e}")
        for i, row in enumerate(all_rows[1:], start=2):
            d = _row_to_dict(headers, row)
            if d.get("id") == user_id:
                await self._run(self._users_ws.update_cell, i, tok_col, new_tokens)
                return
        raise SheetError(f"User {user_id} not found for token update.")

    async def update_plan(self, user_id: str, plan: str):
        all_rows = await self._run(self._users_ws.get_all_values)
        if len(all_rows) < 2:
            raise SheetError("Users sheet is empty.")
        headers = all_rows[0]
        try:
            plan_col = headers.index("plan") + 1
        except ValueError:
            raise SheetError("Users sheet missing 'plan' column.")
        for i, row in enumerate(all_rows[1:], start=2):
            d = _row_to_dict(headers, row)
            if d.get("id") == user_id:
                await self._run(self._users_ws.update_cell, i, plan_col, plan)
                return
        raise SheetError(f"User {user_id} not found for plan update.")

    async def get_all_users(self) -> list[dict]:
        all_rows = await self._run(self._users_ws.get_all_values)
        if len(all_rows) < 2:
            return []
        headers = all_rows[0]
        return [_row_to_dict(headers, row) for row in all_rows[1:] if any(row)]

    # ── Attendance ─────────────────────────────────────────────────────────────

    async def append_attendance(self, record: dict):
        row = [record.get(h, "") for h in ATTEND_HEADERS]
        await self._run(self._attend_ws.append_row, row, value_input_option="RAW")

    async def check_duplicate(self, user_id: str, meal_type: str, date_str: str) -> bool:
        all_rows = await self._run(self._attend_ws.get_all_values)
        if len(all_rows) < 2:
            return False
        headers = all_rows[0]
        for row in all_rows[1:]:
            d = _row_to_dict(headers, row)
            if (
                d.get("user_id") == user_id
                and d.get("meal_type") == meal_type
                and d.get("date") == date_str
            ):
                return True
        return False

    async def get_attendance_by_user(self, user_id: str) -> list[dict]:
        all_rows = await self._run(self._attend_ws.get_all_values)
        if len(all_rows) < 2:
            return []
        headers = all_rows[0]
        return [
            _row_to_dict(headers, row)
            for row in all_rows[1:]
            if _row_to_dict(headers, row).get("user_id") == user_id
        ]

    async def get_all_attendance(self, from_date: Optional[str] = None,
                                  to_date: Optional[str] = None) -> list[dict]:
        all_rows = await self._run(self._attend_ws.get_all_values)
        if len(all_rows) < 2:
            return []
        headers = all_rows[0]
        result = []
        for row in all_rows[1:]:
            if not any(row):
                continue
            d = _row_to_dict(headers, row)
            date_val = d.get("date", "")
            if from_date and date_val < from_date:
                continue
            if to_date and date_val > to_date:
                continue
            result.append(d)
        return result

    # ── Audit ──────────────────────────────────────────────────────────────────

    async def append_audit(self, record: dict):
        row = [record.get(h, "") for h in AUDIT_HEADERS]
        await self._run(self._audit_ws.append_row, row, value_input_option="RAW")

    async def get_audit_log(self) -> list[dict]:
        all_rows = await self._run(self._audit_ws.get_all_values)
        if len(all_rows) < 2:
            return []
        headers = all_rows[0]
        return [_row_to_dict(headers, row) for row in all_rows[1:] if any(row)]

    # ── QR Codes ───────────────────────────────────────────────────────────────

    async def append_qr_code(self, record: dict):
        row = [record.get(h, "") for h in QR_HEADERS]
        await self._run(self._qr_ws.append_row, row, value_input_option="RAW")