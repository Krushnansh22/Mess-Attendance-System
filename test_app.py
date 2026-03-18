"""
Integration tests — Mess Attendance System.
Uses a fully in-memory SheetsClient mock; no Google credentials needed.
Run:  python test_app.py
"""
import os, json, uuid, asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

# ── Set env vars BEFORE importing main ───────────────────────────────────────
os.environ["MESS_QR_SECRET_KEY"]             = "TEST_QR_KEY_001"
os.environ["JWT_SECRET"]                     = "test_jwt_secret_not_for_production_1234"
os.environ["ADMIN_PASSCODE"]                 = "admin123"
os.environ["GOOGLE_SHEET_ID"]                = "fake"
os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]    = "fake"
os.environ["GPS_ENABLED"]                    = "false"

# ── In-memory mock sheets ─────────────────────────────────────────────────────
class MockSheetsClient:
    def __init__(self):
        self._users:      list[dict] = []
        self._attendance: list[dict] = []
        self._audit:      list[dict] = []

    async def init(self): pass

    async def append_user(self, u):        self._users.append(u)
    async def append_attendance(self, r):  self._attendance.append(r)
    async def append_audit(self, r):       self._audit.append(r)

    async def find_user_by_email(self, email):
        email = email.lower()
        return next((u for u in self._users if u["email"].lower() == email), None)

    async def find_user_by_id(self, uid):
        return next((u for u in self._users if u["id"] == uid), None)

    async def check_duplicate(self, user_id, meal_type, date_str):
        return any(
            r["user_id"] == user_id and r["meal_type"] == meal_type and r["date"] == date_str
            for r in self._attendance
        )

    async def get_attendance_by_user(self, uid):
        return [r for r in self._attendance if r["user_id"] == uid]

    async def get_all_attendance(self, from_date=None, to_date=None):
        result = self._attendance[:]
        if from_date: result = [r for r in result if r["date"] >= from_date]
        if to_date:   result = [r for r in result if r["date"] <= to_date]
        return result

    async def get_audit_log(self): return self._audit[:]
    async def get_all_users(self):  return self._users[:]

    async def update_tokens(self, uid, new_tokens):
        for u in self._users:
            if u["id"] == uid:
                u["tokens_remaining"] = str(new_tokens)
                return
        raise Exception(f"User {uid} not found")

    async def update_plan(self, uid, plan):
        for u in self._users:
            if u["id"] == uid:
                u["plan"] = plan
                return

mock_sheets = MockSheetsClient()

# ── Import app and inject globals BEFORE TestClient is created ────────────────
import main as app_module
app_module.MESS_QR_SECRET_KEY  = "TEST_QR_KEY_001"
app_module.JWT_SECRET          = "test_jwt_secret_not_for_production_1234"
app_module.ADMIN_PASSCODE      = "admin123"
app_module.GPS_ENABLED         = False
app_module.MESS_LATITUDE       = 17.6868
app_module.MESS_LONGITUDE      = 75.9104
app_module.MESS_RADIUS_METRES  = 50.0
app_module.sheets_client       = mock_sheets

from fastapi.testclient import TestClient
# lifespan=False skips startup/shutdown hooks entirely
client = TestClient(app_module.app, raise_server_exceptions=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def register(name, email, password, admin_passcode=None):
    body = {"name": name, "email": email, "password": password}
    if admin_passcode:
        body["admin_passcode"] = admin_passcode
    return client.post("/auth/register", json=body)

def login(email, password):
    return client.post("/auth/login", json={"email": email, "password": password})

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

# ── Shared test state (set as each test runs, in order) ──────────────────────
student_token = None
admin_token   = None
student_id    = None

IST = timezone(timedelta(hours=5, minutes=30))

# ═══════════════════════════ TEST FUNCTIONS ═══════════════════════════════════

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "server_time_ist" in data
    assert "gps_enabled" in data
    print(f"  active_meal={data['active_meal']}, gps={data['gps_enabled']}")

def test_register_student():
    global student_token, student_id
    r = register("Rahul Sharma", "rahul@college.edu", "securepass")
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "success"
    assert "token" in data
    assert data["user"]["email"] == "rahul@college.edu"
    assert data["user"]["is_admin"] is False
    student_token = data["token"]
    student_id    = data["user"]["id"]
    print(f"  student_id={student_id[:8]}...")

def test_register_duplicate_email():
    r = register("Rahul 2", "rahul@college.edu", "anotherpass")
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"].lower()

def test_register_weak_password():
    r = register("Weak User", "weak@college.edu", "123")
    assert r.status_code == 422

def test_register_admin():
    global admin_token
    r = register("Admin User", "admin@college.edu", "adminpass", admin_passcode="admin123")
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["user"]["is_admin"] is True
    admin_token = data["token"]

def test_register_wrong_admin_passcode():
    r = register("Fake Admin", "fake@college.edu", "fakepass", admin_passcode="wrongcode")
    assert r.status_code == 403

def test_login_success():
    r = login("rahul@college.edu", "securepass")
    assert r.status_code == 200
    assert "token" in r.json()
    assert r.json()["user"]["name"] == "Rahul Sharma"

def test_login_wrong_password():
    r = login("rahul@college.edu", "wrongpass")
    assert r.status_code == 401

def test_login_nonexistent():
    r = login("nobody@college.edu", "somepass")
    assert r.status_code == 401

def test_tokens_zero_on_new_account():
    r = client.get("/tokens/me", headers=auth_headers(student_token))
    assert r.status_code == 200
    assert r.json()["tokens_remaining"] == 0

def test_scan_fails_no_tokens():
    r = client.post("/scan",
        json={"qr_payload": "TEST_QR_KEY_001"},
        headers=auth_headers(student_token))
    assert r.status_code == 403
    assert "tokens" in r.json()["detail"].lower()

def test_admin_topup():
    r = client.post("/admin/topup",
        json={"email": "rahul@college.edu", "tokens": 30, "plan": "monthly"},
        headers=auth_headers(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["new_balance"] == 30
    assert "Rahul" in data["user_name"]

def test_admin_topup_nonexistent_user():
    r = client.post("/admin/topup",
        json={"email": "ghost@college.edu", "tokens": 10},
        headers=auth_headers(admin_token))
    assert r.status_code == 404

def test_topup_requires_admin():
    r = client.post("/admin/topup",
        json={"email": "rahul@college.edu", "tokens": 10},
        headers=auth_headers(student_token))
    assert r.status_code == 403

def test_scan_invalid_qr():
    with patch("main.now_ist", return_value=datetime(2026, 3, 17, 13, 0, tzinfo=IST)):
        r = client.post("/scan",
            json={"qr_payload": "WRONG_QR_KEY"},
            headers=auth_headers(student_token))
    assert r.status_code == 401
    assert "invalid qr" in r.json()["detail"].lower()

def test_scan_no_active_window():
    # 11:00 IST — gap between breakfast and lunch
    with patch("main.now_ist", return_value=datetime(2026, 3, 17, 11, 0, tzinfo=IST)):
        r = client.post("/scan",
            json={"qr_payload": "TEST_QR_KEY_001"},
            headers=auth_headers(student_token))
    assert r.status_code == 400
    assert "meal window" in r.json()["detail"].lower()

def test_scan_success_lunch():
    with patch("main.now_ist", return_value=datetime(2026, 3, 17, 13, 0, tzinfo=IST)):
        r = client.post("/scan",
            json={"qr_payload": "TEST_QR_KEY_001"},
            headers=auth_headers(student_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "success"
    assert data["meal_type"] == "lunch"
    assert data["tokens_remaining"] == 29
    assert data["user_name"] == "Rahul Sharma"
    print(f"  tokens_remaining={data['tokens_remaining']}")

def test_scan_duplicate_lunch():
    with patch("main.now_ist", return_value=datetime(2026, 3, 17, 13, 30, tzinfo=IST)):
        r = client.post("/scan",
            json={"qr_payload": "TEST_QR_KEY_001"},
            headers=auth_headers(student_token))
    assert r.status_code == 409
    assert "already checked in" in r.json()["detail"].lower()

def test_scan_dinner_same_day():
    with patch("main.now_ist", return_value=datetime(2026, 3, 17, 19, 30, tzinfo=IST)):
        r = client.post("/scan",
            json={"qr_payload": "TEST_QR_KEY_001"},
            headers=auth_headers(student_token))
    assert r.status_code == 200, r.text
    assert r.json()["meal_type"] == "dinner"
    assert r.json()["tokens_remaining"] == 28

def test_attendance_me():
    r = client.get("/attendance/me", headers=auth_headers(student_token))
    assert r.status_code == 200
    records = r.json()["records"]
    assert len(records) == 2
    meals = {rec["meal_type"] for rec in records}
    assert meals == {"lunch", "dinner"}

def test_admin_attendance_all():
    r = client.get("/admin/attendance", headers=auth_headers(admin_token))
    assert r.status_code == 200
    assert r.json()["count"] == 2

def test_admin_attendance_date_filter():
    r = client.get("/admin/attendance?from_date=2026-03-17&to_date=2026-03-17",
                   headers=auth_headers(admin_token))
    assert r.status_code == 200
    assert r.json()["count"] == 2

def test_admin_attendance_future_filter_empty():
    r = client.get("/admin/attendance?from_date=2027-01-01",
                   headers=auth_headers(admin_token))
    assert r.status_code == 200
    assert r.json()["count"] == 0

def test_admin_users_no_password_hash():
    r = client.get("/admin/users", headers=auth_headers(admin_token))
    assert r.status_code == 200
    users = r.json()["users"]
    assert len(users) >= 2
    for u in users:
        assert "password_hash" not in u

def test_admin_audit_actions():
    r = client.get("/admin/audit", headers=auth_headers(admin_token))
    assert r.status_code == 200
    actions = {rec["action"] for rec in r.json()["records"]}
    for expected in ["SCAN_SUCCESS", "SCAN_FAIL_NO_TOKENS", "SCAN_FAIL_INVALID_QR",
                     "SCAN_FAIL_DUPLICATE", "TOKEN_TOPUP", "USER_REGISTER"]:
        assert expected in actions, f"Missing audit action: {expected}"

def test_unauthenticated_request():
    r = client.get("/tokens/me")
    assert r.status_code == 403

def test_invalid_jwt():
    r = client.get("/tokens/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401

def test_gps_missing_coords():
    app_module.GPS_ENABLED = True
    try:
        with patch("main.now_ist", return_value=datetime(2026, 3, 18, 13, 0, tzinfo=IST)):
            r = client.post("/scan",
                json={"qr_payload": "TEST_QR_KEY_001"},
                headers=auth_headers(student_token))
        assert r.status_code == 400
        assert "location" in r.json()["detail"].lower()
    finally:
        app_module.GPS_ENABLED = False

def test_gps_too_far():
    app_module.GPS_ENABLED = True
    try:
        with patch("main.now_ist", return_value=datetime(2026, 3, 18, 13, 0, tzinfo=IST)):
            r = client.post("/scan",
                json={
                    "qr_payload": "TEST_QR_KEY_001",
                    "latitude": 17.7000,   # ~1.5 km away
                    "longitude": 75.9200,
                },
                headers=auth_headers(student_token))
        assert r.status_code == 403
        assert "location mismatch" in r.json()["detail"].lower()
    finally:
        app_module.GPS_ENABLED = False

def test_gps_within_radius():
    app_module.GPS_ENABLED = True
    # Top up first (tokens are at 28 now, dinner already scanned on day 1)
    client.post("/admin/topup",
        json={"email": "rahul@college.edu", "tokens": 10},
        headers=auth_headers(admin_token))
    try:
        # New day — lunch (different date, no duplicate)
        with patch("main.now_ist", return_value=datetime(2026, 3, 18, 13, 0, tzinfo=IST)):
            r = client.post("/scan",
                json={
                    "qr_payload": "TEST_QR_KEY_001",
                    "latitude": 17.68682,   # ~3m from anchor
                    "longitude": 75.91042,
                },
                headers=auth_headers(student_token))
        assert r.status_code == 200, r.text
        assert r.json()["meal_type"] == "lunch"
    finally:
        app_module.GPS_ENABLED = False

def test_meal_windows_exhaustive():
    """All 24 hours — verify correct meal assignment."""
    expected_map = {}
    for h in range(24):
        if 6 <= h < 10:  expected_map[h] = "breakfast"
        elif 12 <= h < 15: expected_map[h] = "lunch"
        elif 19 <= h < 22: expected_map[h] = "dinner"
        else:              expected_map[h] = None

    for h, expected in expected_map.items():
        got = app_module.get_active_meal(datetime(2026, 3, 17, h, 0, tzinfo=IST))
        assert got == expected, f"Hour {h}: expected {expected!r} got {got!r}"
    print(f"  All 24 hours correct")

def test_haversine_zero_distance():
    from main import haversine_metres
    d = haversine_metres(17.6868, 75.9104, 17.6868, 75.9104)
    assert d < 0.01

def test_haversine_known_distance():
    from main import haversine_metres
    # Roughly 30m
    d = haversine_metres(17.6868, 75.9104, 17.6870, 75.9106)
    assert 20 < d < 50, f"Expected ~30m, got {d:.1f}m"

# ── Runner ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_health,
        test_register_student,
        test_register_duplicate_email,
        test_register_weak_password,
        test_register_admin,
        test_register_wrong_admin_passcode,
        test_login_success,
        test_login_wrong_password,
        test_login_nonexistent,
        test_tokens_zero_on_new_account,
        test_scan_fails_no_tokens,
        test_admin_topup,
        test_admin_topup_nonexistent_user,
        test_topup_requires_admin,
        test_scan_invalid_qr,
        test_scan_no_active_window,
        test_scan_success_lunch,
        test_scan_duplicate_lunch,
        test_scan_dinner_same_day,
        test_attendance_me,
        test_admin_attendance_all,
        test_admin_attendance_date_filter,
        test_admin_attendance_future_filter_empty,
        test_admin_users_no_password_hash,
        test_admin_audit_actions,
        test_unauthenticated_request,
        test_invalid_jwt,
        test_gps_missing_coords,
        test_gps_too_far,
        test_gps_within_radius,
        test_meal_windows_exhaustive,
        test_haversine_zero_distance,
        test_haversine_known_distance,
    ]

    passed = failed = 0
    for t in tests:
        name = t.__name__
        try:
            t()
            print(f"  ✅  {name}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ❌  {name}: {e}")
            failed += 1

    print(f"\n{'─'*52}")
    print(f"  {passed} passed  ·  {failed} failed  ·  {len(tests)} total")
    if failed:
        raise SystemExit(1)
