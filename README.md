# Mess Attendance Management System

A comprehensive QR code and token-based mess attendance management system built with FastAPI and modern web technologies.

## Features

### User Features
- 🔐 Secure user authentication (JWT-based)
- 📱 QR code scanning for attendance marking
- 🎫 Token-based meal subscription system
- 📅 Calendar view of attendance history
- 💳 Two subscription plans (Basic: 30 tokens, Premium: 60 tokens)
- ⏰ Meal-time based attendance (Breakfast, Lunch, Dinner)
- 🚫 Duplicate attendance prevention
- 📊 Personal dashboard with statistics

### Admin Features
- 👥 User management (CRUD operations)
- 🎫 Token allocation and top-up
- 📊 Comprehensive dashboard with statistics
- 📈 Attendance tracking and reports
- 🔄 QR code generation and regeneration
- ⚠️ Low token alerts
- 📋 User attendance history viewing

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - SQL toolkit and ORM
- **SQLite** - Database (PostgreSQL ready)
- **JWT** - Authentication
- **Pydantic** - Data validation
- **QRCode** - QR code generation
- **Passlib** - Password hashing

### Frontend
- **HTML5/CSS3** - Structure and styling
- **JavaScript (ES6+)** - Interactivity
- **html5-qrcode** - QR code scanning
- **FullCalendar** - Calendar visualization

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup Steps

1. **Clone or download the project**
```bash
cd mess-attendance-system
```

2. **Create a virtual environment**
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Linux/Mac
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Edit the `.env` file and update the following:
```env
SECRET_KEY=your-secret-key-change-this-in-production-minimum-32-characters
ADMIN_EMAIL=admin@mess.com
ADMIN_PASSWORD=admin123
```

⚠️ **IMPORTANT**: Change the SECRET_KEY and ADMIN_PASSWORD in production!

5. **Run the application**
```bash
python main.py
```

The application will be available at: `http://localhost:8000`

## Default Credentials

**Admin Account:**
- Email: `admin@mess.com`
- Password: `admin123`

⚠️ Change these credentials after first login!

## Usage Guide

### For Users

1. **Registration**
   - Navigate to `/register`
   - Fill in your details
   - Select a subscription plan (optional)
   - Submit to create account

2. **Login**
   - Go to `/login`
   - Enter your credentials
   - You'll be redirected to your dashboard

3. **Scan QR Code**
   - Click "Scan QR" from the dashboard
   - Allow camera access
   - Point camera at the mess QR code
   - Attendance will be marked automatically

4. **View Attendance**
   - Click "Calendar" to see your attendance history
   - Green dates indicate present
   - View detailed records in the table

### For Admins

1. **Login as Admin**
   - Use admin credentials to login
   - You'll be redirected to admin dashboard

2. **Manage Users**
   - View all users in the user management section
   - Add new users with the "Add New User" button
   - Top-up tokens for users
   - Delete inactive users

3. **QR Code Management**
   - View current QR code on dashboard
   - Print/display QR code at mess entrance
   - Regenerate QR code if needed (invalidates old one)

4. **Monitor Attendance**
   - View today's attendance count
   - Check users with low tokens
   - Export reports (feature can be enhanced)

## API Documentation

Once the application is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

#### Authentication
- `POST /register` - Register new user
- `POST /login` - Login and get JWT token
- `GET /me` - Get current user info

#### User Endpoints
- `GET /user/dashboard` - Get user dashboard data
- `POST /user/attendance/scan` - Mark attendance via QR scan
- `GET /user/attendance/history` - Get attendance history
- `GET /user/tokens/balance` - Get token balance

#### Admin Endpoints
- `GET /admin/dashboard` - Get admin dashboard stats
- `GET /admin/users` - List all users
- `POST /admin/users` - Create new user
- `PUT /admin/users/{id}` - Update user
- `DELETE /admin/users/{id}` - Delete user
- `POST /admin/users/{id}/topup` - Add tokens to user
- `GET /admin/qr/current` - Get current QR code
- `POST /admin/qr/regenerate` - Generate new QR code

## Database Schema

### Users Table
- id, name, email, phone, password_hash
- role (admin/user)
- subscription_type (monthly_30/monthly_60)
- tokens_remaining
- is_active, created_at

### Attendance Table
- id, user_id, scan_time, date
- meal_type (breakfast/lunch/dinner)

### TokenTransactions Table
- id, user_id, tokens_added, tokens_used
- action (topup/scan)
- description, timestamp

### QRConfig Table
- id, qr_secret, active, last_updated

## Meal Timings

- **Breakfast**: 6:00 AM - 10:00 AM
- **Lunch**: 12:00 PM - 3:00 PM
- **Dinner**: 7:00 PM - 10:00 PM

Attendance can only be marked during these times.

## Subscription Plans

| Plan | Meals/Day | Tokens | Best For |
|------|-----------|--------|----------|
| Basic | 1 | 30 | Single meal per day |
| Premium | 2 | 60 | Two meals per day |

Each QR scan deducts 1 token.

## Security Features

- ✅ JWT-based authentication
- ✅ Password hashing with bcrypt
- ✅ QR code signature verification
- ✅ Role-based access control
- ✅ Duplicate attendance prevention
- ✅ SQL injection protection (SQLAlchemy ORM)
- ✅ CSRF protection

## Deployment

### For Production

1. **Use PostgreSQL instead of SQLite**
```env
DATABASE_URL=postgresql://user:password@localhost/mess_attendance
```

2. **Set strong SECRET_KEY**
```python
import secrets
print(secrets.token_urlsafe(32))
```

3. **Use HTTPS**
- Deploy behind nginx with SSL certificate

4. **Environment Variables**
- Use environment variables instead of .env file
- Never commit .env to version control

5. **Run with Gunicorn**
```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Troubleshooting

### Camera not working
- Ensure HTTPS is enabled (required for camera access)
- Check browser permissions
- Try different browser

### Database errors
- Delete `mess_attendance.db` and restart
- Check SQLAlchemy version compatibility

### Token errors
- Check SECRET_KEY in .env
- Clear browser localStorage
- Re-login

## Future Enhancements

- [ ] Mobile app (React Native/Flutter)
- [ ] Face recognition verification
- [ ] Payment gateway integration
- [ ] SMS/Email notifications
- [ ] Advanced analytics dashboard
- [ ] Export reports (PDF/Excel)
- [ ] Multi-mess support
- [ ] Biometric authentication

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is open source and available under the MIT License.

## Support

For issues and questions:
- Create an issue in the repository
- Email: support@mess-attendance.com (example)

## Acknowledgments

- FastAPI for the amazing web framework
- html5-qrcode for QR code scanning
- FullCalendar for calendar visualization
- SQLAlchemy for database ORM

---

**Built with ❤️ for efficient mess management**
