# Mess Attendance Management System - Complete Code Documentation

## 📋 Project Overview

A full-stack web application for managing mess/cafeteria attendance using QR code scanning and token-based subscriptions.

## 🗂️ Complete File Structure

```
mess-attendance-system/│├── backend/                        # Backend Python modules│   ├── __init__.py                # Package initialization│   ├── database.py                # Database models & configuration│   ├── schemas.py                 # Pydantic validation schemas│   ├── auth.py                    # Authentication & JWT handling│   ├── utils.py                   # Utility functions (QR, dates, etc.)│   ├── routes_auth.py             # Authentication endpoints│   ├── routes_user.py             # User-facing endpoints│   └── routes_admin.py            # Admin endpoints│├── static/                         # Static assets│   ├── css/│   │   └── style.css              # Main stylesheet│   └── js/│       ├── main.js                # Core JavaScript utilities│       ├── login.js               # Login page logic│       ├── register.js            # Registration page logic│       ├── dashboard.js           # User dashboard logic│       ├── scan.js                # QR scanner logic│       ├── calendar.js            # Attendance calendar│       ├── admin_dashboard.js     # Admin dashboard│       ├── admin_users.js         # User management│       ├── admin_qr.js            # QR code management│       └── admin_reports.js       # Reports and analytics│├── templates/                      # HTML templates│   ├── base.html                  # Base template with nav│   ├── index.html                 # Home/landing page│   ├── login.html                 # Login page│   ├── register.html              # Registration page│   ├── dashboard.html             # User dashboard│   ├── scan.html                  # QR scanning page│   ├── calendar.html              # Attendance calendar│   ├── admin_dashboard.html       # Admin dashboard│   ├── admin_users.html           # User management page│   ├── admin_qr.html              # QR management page│   └── admin_reports.html         # Reports page│├── main.py                        # FastAPI application entry point├── requirements.txt               # Python dependencies├── .env                           # Environment configuration├── start.sh                       # Linux/Mac startup script├── start.bat                      # Windows startup script└── README.md                      # Project documentation
```

## 🔧 Installation & Setup

### Quick Start

**Linux/Mac:**

```bash
chmod +x start.sh./start.sh
```

**Windows:**

```cmd
start.bat
```

**Manual Start:**

```bash
pip install -r requirements.txtpython main.py
```

Access at: `http://localhost:8000`

## 🔐 Default Credentials

**Admin Account:**

-   Email: `admin@mess.com`
-   Password: `admin123`

⚠️ **Change these credentials immediately in production!**

## 📊 Database Schema

### Users Table

```sql
- id (PK)- name- email (unique)- phone- password_hash- role (admin/user)- subscription_type (monthly_30/monthly_60)- tokens_remaining- created_at- is_active
```

### Attendance Table

```sql
- id (PK)- user_id (FK)- scan_time- date- meal_type (breakfast/lunch/dinner)
```

### TokenTransaction Table

```sql
- id (PK)- user_id (FK)- tokens_added- tokens_used- action (topup/scan)- timestamp- description
```

### QRConfig Table

```sql
- id (PK)- qr_secret (unique)- active- last_updated
```

## 🛣️ API Routes

### Authentication (`/api`)

-   `POST /register` - Register new user
-   `POST /login` - Login and get JWT token
-   `POST /logout` - Logout (client-side)

### User Routes (`/api/user`)

-   `GET /dashboard` - Get user dashboard data
-   `POST /attendance/scan` - Mark attendance via QR
-   `GET /attendance/history` - Get attendance history
-   `GET /attendance/calendar` - Get calendar view
-   `GET /profile` - Get user profile
-   `GET /tokens/balance` - Get token balance

### Admin Routes (`/api/admin`)

-   `GET /dashboard` - Admin dashboard statistics
-   `GET /users` - List all users
-   `GET /users/{id}` - Get specific user
-   `POST /users` - Create new user
-   `PUT /users/{id}` - Update user
-   `DELETE /users/{id}` - Deactivate user
-   `POST /users/{id}/tokens` - Add tokens to user
-   `GET /users/{id}/attendance` - User attendance report
-   `GET /users/low-tokens/list` - Users with low tokens
-   `GET /qr/config` - Get QR configuration
-   `POST /qr/generate` - Generate new QR code
-   `GET /reports/attendance-summary` - Attendance statistics
-   `GET /transactions/recent` - Recent token transactions

## 🎨 Frontend Pages

### Public Pages

1.  **Home (`/`)** - Landing page with features
2.  **Login (`/login`)** - User authentication
3.  **Register (`/register`)** - New user registration

### User Pages

1.  **Dashboard (`/dashboard`)** - Token balance, recent attendance
2.  **Scan QR (`/scan`)** - Camera QR scanner
3.  **Calendar (`/calendar`)** - Monthly attendance view

### Admin Pages

1.  **Admin Dashboard (`/admin`)** - Statistics overview
2.  **User Management (`/admin/users`)** - Manage users
3.  **QR Management (`/admin/qr`)** - Generate/view QR codes
4.  **Reports (`/admin/reports`)** - Attendance analytics

## 🔒 Security Features

1.  **JWT Authentication** - Secure token-based auth
2.  **Password Hashing** - BCrypt for passwords
3.  **Role-Based Access** - Admin vs User permissions
4.  **QR Encryption** - Secure QR code generation
5.  **Input Validation** - Pydantic schemas
6.  **CORS Protection** - Configurable CORS
7.  **SQL Injection Prevention** - SQLAlchemy ORM

## 📱 Key Features Implementation

### QR Code Scanning

-   Uses `html5-qrcode` library
-   Real-time camera feed
-   Automatic detection
-   Instant attendance marking

### Token Management

-   Automatic deduction on scan
-   Admin top-up capability
-   Low balance alerts
-   Transaction history

### Attendance Tracking

-   Prevents duplicate entries
-   Meal-time validation
-   Historical records
-   Calendar visualization

### Admin Controls

-   User CRUD operations
-   Token allocation
-   QR code regeneration
-   Comprehensive reports

## 🔄 Business Logic

### Attendance Rules

1.  One attendance per meal per day
2.  Must be within meal time windows
3.  Requires sufficient token balance
4.  Deducts 1 token per scan

### Meal Time Windows

-   **Breakfast:** 6:00 AM - 10:00 AM
-   **Lunch:** 12:00 PM - 3:00 PM
-   **Dinner:** 7:00 PM - 10:00 PM

### Subscription Plans

-   **Basic (monthly_30):** 30 tokens/month
-   **Premium (monthly_60):** 60 tokens/month

## 🚀 Deployment Guide

### Development

```bash
python main.py# Runs on http://localhost:8000
```

### Production

1.  **Environment Setup**

```bash
# Update .envSECRET_KEY=<strong-random-key>DATABASE_URL=postgresql://user:pass@host/dbDEBUG=False
```

2.  **Install Production Server**

```bash
pip install gunicorn
```

3.  **Run with Gunicorn**

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

4.  **Setup Nginx Reverse Proxy**

```nginx
server {    listen 80;    server_name yourdomain.com;        location / {        proxy_pass http://localhost:8000;        proxy_set_header Host $host;        proxy_set_header X-Real-IP $remote_addr;    }}
```

5.  **Enable SSL with Let's Encrypt**

```bash
certbot --nginx -d yourdomain.com
```

## 🧪 Testing

### Manual Testing Checklist

**User Flow:**

-    Register new user
-    Login with credentials
-    View dashboard
-    Scan QR code (need physical QR or mock)
-    Check token balance
-    View attendance calendar

**Admin Flow:**

-    Login as admin
-    View dashboard statistics
-    Create new user
-    Add tokens to user
-    Generate new QR code
-    View reports

## 📝 Configuration

### Environment Variables (.env)

```
APP_NAME=Mess Attendance SystemSECRET_KEY=your-secret-key-hereALGORITHM=HS256ACCESS_TOKEN_EXPIRE_MINUTES=1440DATABASE_URL=sqlite:///./mess_attendance.dbQR_SECRET=mess-qr-secret-keyDEBUG=TrueHOST=0.0.0.0PORT=8000
```

## 🐛 Troubleshooting

### Common Issues

**1. Database Errors**

```bash
# Delete and recreate databaserm mess_attendance.dbpython main.py
```

**2. Import Errors**

```bash
# Ensure all dependencies installedpip install -r requirements.txt
```

**3. QR Scanner Not Working**

-   Must use HTTPS or localhost
-   Allow camera permissions in browser
-   Supported browsers: Chrome, Firefox, Safari

**4. Authentication Failures**

-   Clear browser localStorage
-   Check token expiration (24 hours default)
-   Verify SECRET_KEY matches

## 📈 Future Enhancements

-    Mobile apps (iOS/Android)
-    Face recognition integration
-    Payment gateway for subscriptions
-    Email/SMS notifications
-    Multi-location support
-    Advanced analytics dashboard
-    Export to PDF/Excel
-    Real-time push notifications
-    Offline mode support
-    Biometric authentication

## 📚 Dependencies

### Backend

-   `fastapi` - Web framework
-   `uvicorn` - ASGI server
-   `sqlalchemy` - Database ORM
-   `python-jose` - JWT handling
-   `passlib` - Password hashing
-   `qrcode` - QR code generation
-   `pydantic` - Data validation

### Frontend

-   `html5-qrcode` - QR scanner
-   Vanilla JavaScript
-   Pure CSS (no frameworks)

## 🤝 Support

For issues or questions:

1.  Check API docs at `/docs`
2.  Review console logs
3.  Verify all dependencies installed
4.  Check `.env` configuration

## 📄 License

This project is provided as-is for educational and commercial use.

---

**Version:** 1.0.0**Last Updated:** February 2024**Maintained by:** Development Team