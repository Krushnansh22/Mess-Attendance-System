"""
Mess Attendance System — FastAPI Backend
Static QR Edition v1.0
"""

import os
import json
import math
import uuid
import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import jwt
import bcrypt
from pydantic import BaseModel, EmailStr, field_validator

from sheets import SheetsClient, SheetError
from dotenv import load_dotenv
load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── IST timezone ─────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist() -> datetime:
    return datetime.now(IST)


# ── Environment ───────────────────────────────────────────────────────────────
def _require_env(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return v

MESS_QR_SECRET_KEY: str = ""
JWT_SECRET: str = ""
ADMIN_PASSCODE: str = ""
GPS_ENABLED: bool = False
MESS_LATITUDE: float = 0.0
MESS_LONGITUDE: float = 0.0
MESS_RADIUS_METRES: float = 50.0

sheets_client: Optional[SheetsClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global MESS_QR_SECRET_KEY, JWT_SECRET, ADMIN_PASSCODE
    global GPS_ENABLED, MESS_LATITUDE, MESS_LONGITUDE, MESS_RADIUS_METRES
    global sheets_client

    MESS_QR_SECRET_KEY = _require_env("MESS_QR_SECRET_KEY")
    JWT_SECRET = _require_env("JWT_SECRET")
    ADMIN_PASSCODE = _require_env("ADMIN_PASSCODE")
    GPS_ENABLED = os.getenv("GPS_ENABLED", "false").lower() == "true"
    MESS_LATITUDE = float(os.getenv("MESS_LATITUDE", "0"))
    MESS_LONGITUDE = float(os.getenv("MESS_LONGITUDE", "0"))
    MESS_RADIUS_METRES = float(os.getenv("MESS_RADIUS_METRES", "50"))

    sheets_client = SheetsClient()
    await sheets_client.init()
    logger.info("Sheets client initialised")
    yield
    logger.info("Shutting down")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Mess Attendance System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ── Meal Windows (IST) ────────────────────────────────────────────────────────
MEAL_WINDOWS = {
    "breakfast": (6, 10),    # 6:00–10:00
    "lunch":     (12, 15),   # 12:00–15:00
    "dinner":    (19, 22),   # 19:00–22:00
}

def get_active_meal(dt: datetime) -> Optional[str]:
    """Return the active meal type for a given IST datetime, or None."""
    h = dt.hour
    for meal, (start, end) in MEAL_WINDOWS.items():
        if start <= h < end:
            return meal
    return None


# ── JWT helpers ───────────────────────────────────────────────────────────────
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = 24

def create_token(user_id: str, email: str, is_admin: bool) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "is_admin": is_admin,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return decode_token(creds.credentials)


async def get_admin_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = decode_token(creds.credentials)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return payload


# ── Haversine distance ─────────────────────────────────────────────────────────
def haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Retry helper ──────────────────────────────────────────────────────────────
async def retry_with_backoff(coro_fn, max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            await coro_fn()
            return
        except Exception as exc:
            if attempt == max_attempts:
                logger.error("Background task failed after %d attempts: %s", max_attempts, exc)
            else:
                await asyncio.sleep(2 ** attempt)


# ── Pydantic models ──────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    admin_passcode: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters.")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty.")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ScanRequest(BaseModel):
    qr_payload: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class TopupRequest(BaseModel):
    email: str
    tokens: int
    plan: Optional[str] = None

    @field_validator("tokens")
    @classmethod
    def tokens_positive(cls, v):
        if v <= 0:
            raise ValueError("Tokens must be a positive integer.")
        return v


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.post("/auth/register", status_code=201)
async def register(body: RegisterRequest):
    existing = await sheets_client.find_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    is_admin = False
    if body.admin_passcode:
        if body.admin_passcode != ADMIN_PASSCODE:
            raise HTTPException(status_code=403, detail="Invalid admin passcode.")
        is_admin = True

    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(rounds=12)).decode()
    user_id = str(uuid.uuid4())
    now = now_ist().isoformat()

    user_row = {
        "id": user_id,
        "name": body.name,
        "email": body.email.lower(),
        "password_hash": pw_hash,
        "tokens_remaining": 0,
        "plan": "pay-as-you-go",
        "is_admin": str(is_admin),
        "created_at": now,
    }
    await sheets_client.append_user(user_row)
    await sheets_client.append_audit({
        "timestamp": now,
        "user_id": user_id,
        "action": "USER_REGISTER",
        "metadata": json.dumps({"email": body.email, "is_admin": is_admin}),
    })

    token = create_token(user_id, body.email.lower(), is_admin)
    return {
        "status": "success",
        "message": "Account created successfully.",
        "token": token,
        "user": {"id": user_id, "name": body.name, "email": body.email.lower(), "is_admin": is_admin},
    }


@app.post("/auth/login")
async def login(body: LoginRequest):
    user = await sheets_client.find_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        await sheets_client.append_audit({
            "timestamp": now_ist().isoformat(),
            "user_id": user["id"],
            "action": "LOGIN_FAIL",
            "metadata": json.dumps({"email": body.email}),
        })
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    is_admin = user.get("is_admin", "False").lower() == "true"
    token = create_token(user["id"], user["email"], is_admin)

    if is_admin:
        await sheets_client.append_audit({
            "timestamp": now_ist().isoformat(),
            "user_id": user["id"],
            "action": "ADMIN_LOGIN",
            "metadata": json.dumps({}),
        })

    return {
        "status": "success",
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "tokens_remaining": int(user.get("tokens_remaining", 0)),
            "plan": user.get("plan", "pay-as-you-go"),
            "is_admin": is_admin,
        },
    }


# ── Scan route ────────────────────────────────────────────────────────────────
@app.post("/scan")
async def scan(body: ScanRequest, background_tasks: BackgroundTasks,
               current_user: dict = Depends(get_current_user)):
    user_id = current_user["sub"]
    now = now_ist()
    today_str = now.date().isoformat()

    # 1. Fetch user record
    user = await sheets_client.find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    # Helper: write failure audit entry immediately (not as BackgroundTask),
    # because BackgroundTasks do not run after an HTTPException is raised.
    async def fail_audit(action: str, metadata: dict = {}):
        try:
            await sheets_client.append_audit({
                "timestamp": now.isoformat(),
                "user_id": user_id,
                "action": action,
                "metadata": json.dumps(metadata),
            })
        except Exception as exc:
            logger.error("Failed to write audit %s: %s", action, exc)

    # 2. Token check
    tokens = int(user.get("tokens_remaining", 0))
    if tokens <= 0:
        await fail_audit("SCAN_FAIL_NO_TOKENS")
        raise HTTPException(status_code=403, detail="Insufficient tokens. Please top up.")

    # 3. Time window check
    meal_type = get_active_meal(now)
    if not meal_type:
        await fail_audit("SCAN_FAIL_TIME_WINDOW", {"hour": now.hour})
        raise HTTPException(status_code=400, detail="No active meal window. Please scan during meal hours.")

    # 4. QR key check
    if body.qr_payload.strip() != MESS_QR_SECRET_KEY:
        await fail_audit("SCAN_FAIL_INVALID_QR", {"payload": body.qr_payload[:50]})
        raise HTTPException(status_code=401, detail="Invalid QR code.")

    # 5. Duplicate scan check
    already_scanned = await sheets_client.check_duplicate(user_id, meal_type, today_str)
    if already_scanned:
        await fail_audit("SCAN_FAIL_DUPLICATE", {"meal_type": meal_type, "date": today_str})
        raise HTTPException(status_code=409, detail=f"Already checked in for {meal_type}.")

    # 6. GPS check (optional)
    if GPS_ENABLED:
        if body.latitude is None or body.longitude is None:
            raise HTTPException(
                status_code=400,
                detail="Location required. Please allow location access and try again."
            )
        dist = haversine_metres(body.latitude, body.longitude, MESS_LATITUDE, MESS_LONGITUDE)
        if dist > MESS_RADIUS_METRES:
            await fail_audit("SCAN_FAIL_LOCATION", {
                "distance_m": round(dist, 1),
                "lat": body.latitude,
                "lon": body.longitude,
            })
            raise HTTPException(
                status_code=403,
                detail=f"Location mismatch. Must be at the mess to scan. (You are {round(dist)}m away)"
            )

    # ── All checks passed — write records asynchronously ──────────────────
    new_tokens = tokens - 1
    attendance_row = {
        "date": today_str,
        "timestamp": now.isoformat(),
        "user_id": user_id,
        "user_name": user["name"],
        "meal_type": meal_type,
    }
    audit_row = {
        "timestamp": now.isoformat(),
        "user_id": user_id,
        "action": "SCAN_SUCCESS",
        "metadata": json.dumps({"meal_type": meal_type, "tokens_after": new_tokens}),
    }

    async def write_records():
        await sheets_client.append_attendance(attendance_row)
        await sheets_client.update_tokens(user_id, new_tokens)
        await sheets_client.append_audit(audit_row)

    background_tasks.add_task(retry_with_backoff, write_records)

    return {
        "status": "success",
        "message": f"{meal_type.capitalize()} attendance recorded successfully.",
        "meal_type": meal_type,
        "tokens_remaining": new_tokens,
        "user_name": user["name"],
    }


# ── Student routes ────────────────────────────────────────────────────────────
@app.get("/attendance/me")
async def my_attendance(current_user: dict = Depends(get_current_user)):
    user_id = current_user["sub"]
    records = await sheets_client.get_attendance_by_user(user_id)
    return {"status": "success", "records": records}


@app.get("/tokens/me")
async def my_tokens(current_user: dict = Depends(get_current_user)):
    user_id = current_user["sub"]
    user = await sheets_client.find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {
        "status": "success",
        "tokens_remaining": int(user.get("tokens_remaining", 0)),
        "plan": user.get("plan", "pay-as-you-go"),
    }


# ── Admin routes ──────────────────────────────────────────────────────────────
@app.post("/admin/topup")
async def admin_topup(body: TopupRequest, background_tasks: BackgroundTasks,
                      admin: dict = Depends(get_admin_user)):
    user = await sheets_client.find_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=404, detail=f"No user found with email: {body.email}")

    new_tokens = int(user.get("tokens_remaining", 0)) + body.tokens
    await sheets_client.update_tokens(user["id"], new_tokens)

    if body.plan:
        await sheets_client.update_plan(user["id"], body.plan)

    background_tasks.add_task(
        retry_with_backoff,
        lambda: sheets_client.append_audit({
            "timestamp": now_ist().isoformat(),
            "user_id": user["id"],
            "action": "TOKEN_TOPUP",
            "metadata": json.dumps({
                "added": body.tokens,
                "new_balance": new_tokens,
                "by_admin": admin["sub"],
                "plan": body.plan,
            }),
        }),
    )

    return {
        "status": "success",
        "message": f"Added {body.tokens} tokens to {user['name']}.",
        "user_name": user["name"],
        "new_balance": new_tokens,
    }


@app.get("/admin/attendance")
async def admin_attendance(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    admin: dict = Depends(get_admin_user),
):
    records = await sheets_client.get_all_attendance(from_date, to_date)
    return {"status": "success", "count": len(records), "records": records}


@app.get("/admin/audit")
async def admin_audit(admin: dict = Depends(get_admin_user)):
    records = await sheets_client.get_audit_log()
    return {"status": "success", "count": len(records), "records": records}


@app.get("/admin/users")
async def admin_users(admin: dict = Depends(get_admin_user)):
    users = await sheets_client.get_all_users()
    # Strip password hashes before returning
    safe = [
        {k: v for k, v in u.items() if k != "password_hash"}
        for u in users
    ]
    return {"status": "success", "count": len(safe), "users": safe}


@app.post("/admin/qr/generate")
async def admin_generate_qr(admin: dict = Depends(get_admin_user), background_tasks: BackgroundTasks = BackgroundTasks()):
    global MESS_QR_SECRET_KEY
    new_qr_payload = str(uuid.uuid4())
    
    # 1. Update in-memory
    MESS_QR_SECRET_KEY = new_qr_payload
    
    # 2. Update .env (persist)
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
        
        with open(env_path, "w") as f:
            for line in lines:
                if line.startswith("MESS_QR_SECRET_KEY="):
                    f.write(f"MESS_QR_SECRET_KEY={new_qr_payload}\n")
                else:
                    f.write(line)
                    
    # 3. Log into Sheets
    background_tasks.add_task(
        retry_with_backoff,
        lambda: sheets_client.append_qr_code({
            "timestamp": now_ist().isoformat(),
            "admin_id": admin["sub"],
            "payload": new_qr_payload,
        })
    )
    
    # 4. Also add an audit log
    background_tasks.add_task(
        retry_with_backoff,
        lambda: sheets_client.append_audit({
            "timestamp": now_ist().isoformat(),
            "user_id": admin["sub"],
            "action": "ADMIN_GENERATE_QR",
            "metadata": json.dumps({
                "payload": new_qr_payload,
            }),
        })
    )
    
    return {"status": "success", "payload": new_qr_payload, "message": "New QR code generated and saved."}


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    now = now_ist()
    meal = get_active_meal(now)
    return {
        "status": "ok",
        "server_time_ist": now.isoformat(),
        "active_meal": meal,
        "gps_enabled": GPS_ENABLED,
    }


# ── Static files (serve frontend) ─────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
