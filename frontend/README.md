# 🍽️ Mess Attendance System — Static QR Edition v1.0

A zero-cost, production-ready web application for digitising student meal attendance in hostel mess halls. Students scan a permanently printed QR code to mark their presence at Breakfast, Lunch, or Dinner. All records land in Google Sheets.

---

## Architecture

```
Student Browser (PWA)
  ↓  HTTPS POST /scan (JWT + QR payload)
FastAPI on Render/Railway (stateless Python)
  ↓  gspread async write via BackgroundTasks
Google Sheets API (Attendance + Audit + Users)
  ↓  Admin opens Google Sheets on tablet
Mess Manager sees real-time rows
```

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- A Google Cloud project with Sheets API enabled
- A Google Service Account JSON key
- A Google Sheet shared with the service account email

### 1. Clone & install

```bash
git clone <repo-url>
cd mess-attendance
pip install -r backend/requirements.txt
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your real values
```

Required variables:

| Variable | Description |
|---|---|
| `MESS_QR_SECRET_KEY` | The string encoded in your printed QR code |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Base64-encoded service account JSON |
| `GOOGLE_SHEET_ID` | ID from the Google Sheets URL |
| `JWT_SECRET` | Random 256-bit hex string |
| `ADMIN_PASSCODE` | Passcode required for admin registration |

Generate `JWT_SECRET`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Encode service account JSON:
```bash
base64 -w 0 service_account.json
```

### 3. Run

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000)

---

## Deployment (Render — Free Tier)

1. Fork this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service → connect your repo
3. Use these settings:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables in the Render dashboard
5. Deploy — your app is live

---

## Docker

```bash
# Build
docker build -t mess-attendance .

# Run (replace with your .env values)
docker run -p 8000:8000 \
  -e MESS_QR_SECRET_KEY=MESS_LOCATION_01_SECURE_KEY \
  -e GOOGLE_SHEET_ID=... \
  -e GOOGLE_SERVICE_ACCOUNT_JSON=... \
  -e JWT_SECRET=... \
  -e ADMIN_PASSCODE=... \
  mess-attendance
```

---

## Google Sheets Setup

1. Create a new Google Sheet with these exact sheet tab names:
   - `Users`
   - `Attendance`
   - `Audit`

   *(The app auto-creates these with correct headers on first run if they don't exist.)*

2. Share the sheet with your service account email (Editor access).

3. Get the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/**<SHEET_ID>**/edit`

---

## QR Code Generation

1. Go to any free QR generator (e.g., [qr-code-generator.com](https://qr-code-generator.com))
2. Enter your `MESS_QR_SECRET_KEY` value as the content
3. Download as PNG
4. Print at minimum A5 size (148 × 210 mm)
5. Laminate and affix to the mess entry wall

---

## API Reference

### Public

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register student/admin account |
| `POST` | `/auth/login` | Login → JWT token |
| `GET`  | `/health` | Server status + active meal window |

### Student (JWT required)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/scan` | Submit QR scan |
| `GET`  | `/attendance/me` | My attendance history |
| `GET`  | `/tokens/me` | My token balance |

### Admin (Admin JWT required)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/admin/topup` | Add tokens to a student |
| `GET`  | `/admin/attendance` | Full attendance log |
| `GET`  | `/admin/users` | All user accounts |
| `GET`  | `/admin/audit` | Security audit log |

---

## Scan Validation Pipeline (in order)

1. **Token check** — `tokens_remaining > 0`
2. **Time window** — current IST time within Breakfast/Lunch/Dinner window
3. **QR key check** — payload matches `MESS_QR_SECRET_KEY`
4. **Duplicate check** — no prior scan for this user × meal × today
5. **GPS check** *(optional)* — coordinates within `MESS_RADIUS_METRES` of mess

---

## Meal Windows (IST)

| Meal | Start | End |
|---|---|---|
| Breakfast | 06:00 | 10:00 |
| Lunch | 12:00 | 15:00 |
| Dinner | 19:00 | 22:00 |

---

## Token Plans

| Plan | Tokens | Top-up Trigger |
|---|---|---|
| Monthly | 90 | Start of each month |
| Weekly | 21 | Each Monday |
| Pay-as-you-go | Manual | After cash payment |

---

## Registering an Admin Account

When registering, enter the `ADMIN_PASSCODE` in the "Admin Passcode" field. Leave it blank for a regular student account.

---

## GPS Verification (Optional)

Set `GPS_ENABLED=true` and configure:
```
MESS_LATITUDE=17.6868
MESS_LONGITUDE=75.9104
MESS_RADIUS_METRES=50
```

Students must physically be within 50m of the mess GPS anchor point to scan. Useful if students share QR code photos.

---

## Security Model

| Threat | Mitigation |
|---|---|
| Remote scanning (WhatsApp photo) | GPS location check; narrow time windows |
| Double-tap / shared scanning | One scan per user per meal per day |
| QR forgery | HMAC key validation; key only in server `.env` |
| JWT theft | 24h expiry; all events logged in Audit sheet |

---

## Architecture Notes

- **Stateless design** — safe for free-tier hibernation on Render/Railway
- **Background writes** — Google Sheets writes happen after HTTP 200 is returned, preventing API latency from impacting UX
- **Retry with backoff** — failed writes retry up to 3× with exponential backoff; permanent failures logged to stderr
- **IST enforcement** — all meal windows and timestamps use `UTC+5:30`
- **Denormalised `user_name`** — stored in Attendance sheet for admin readability without JOIN operations
- **gspread sync→async** — the synchronous gspread library is run via `asyncio.run_in_executor` to avoid blocking the event loop

---

## File Structure

```
mess-attendance/
├── backend/
│   ├── main.py          # FastAPI app, routes, validation logic
│   ├── sheets.py        # Google Sheets async client
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html       # Full PWA (single-file SPA)
│   ├── manifest.json    # PWA manifest
│   ├── sw.js            # Service worker
│   └── icons/           # App icons (192px, 512px)
├── Dockerfile
├── render.yaml
└── README.md
```
