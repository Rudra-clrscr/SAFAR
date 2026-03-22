# SAFAR — Smart & Safe Travel Platform

SAFAR is a unified travel platform combining **group-based trip planning** and **real-time tourist safety monitoring** into a single Flask application.

---

## Project Structure

```
SAFAR/
├── app.py               ← Main Flask app (all routes + APIs)
├── database.py          ← SQLAlchemy models
├── requirements.txt     ← Python dependencies
├── .env                 ← Environment variables (create this yourself)
├── .gitignore
├── static/
│   ├── style.css
│   ├── script.js
│   ├── group_chat.js
│   └── images/
│       ├── hero_bg.png
│       ├── dest_goa.png
│       ├── dest_jaipur.png
│       ├── dest_kerala.png
│       ├── dest_manali.png
│       └── dest_varanasi.png
└── templates/
    ├── index.html
    ├── auth.html
    ├── groups.html
    ├── group_chat.html
    ├── travel.html
    ├── about.html
    ├── user_dashboard.html
    ├── safety_dashboard.html
    └── admin_dashboard.html
```

---

## Quick Start

### USB / Portable setup (recommended)
If you run this project from a USB drive and want to keep your `C:` drive clean:

```bat
setup_usb_shared.bat   :: one-time per USB drive
fix_install.bat
run_usb.bat
```

This uses:
- USB-wide shared packages in `X:\tools\py-shared` (one-time install)
- project-local extras in `.\portable_packages`
- direct run via `run_usb.bat`

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create `.env`
```
SECRET_KEY=your_flask_secret_key
DATABASE_URL=sqlite:///combined_app.db       # or PostgreSQL URI for production
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx        # optional
TWILIO_AUTH_TOKEN=your_auth_token             # optional
TWILIO_PHONE_NUMBER=+1234567890              # optional
```
> Twilio is **optional** — OTPs are printed to the console if not configured.

### 3. Run
```bash
python app.py
```
App runs at `http://localhost:5000`.

### Deploy on Render
Set the **Start Command** to:
```bash
gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:$PORT
```

---

## API Reference

### Auth — `/api/auth/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user (+ optional tourist profile) |
| POST | `/api/auth/login`    | Login with username+password **or** phone+OTP |
| GET  | `/api/auth/logout`   | Logout |

### OTP — `/api/otp/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/otp/send`   | Send OTP to phone number |
| POST | `/api/otp/verify` | Verify OTP |

### Travel Groups — `/api/tt/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/tt/destinations`          | List all destinations |
| POST   | `/api/tt/destinations`          | Create a destination |
| PUT    | `/api/tt/destinations/<id>`     | Update a destination |
| DELETE | `/api/tt/destinations/<id>`     | Delete a destination |
| GET    | `/api/tt/destinations/popular`  | Top destinations by group count |
| GET    | `/api/tt/groups`                | List groups |
| POST   | `/api/tt/groups`                | Create a group |
| GET    | `/api/tt/groups/<id>`           | Get a group |
| DELETE | `/api/tt/groups/<id>`           | Delete a group (owner only) |
| POST   | `/api/tt/groups/<id>/join`      | Join a group |
| POST   | `/api/tt/groups/<id>/leave`     | Leave a group |
| GET    | `/api/tt/groups/<id>/members`   | List group members |
| GET    | `/api/tt/groups/<id>/messages`  | Get last 100 messages |
| POST   | `/api/tt/groups/<id>/messages`  | Send a message |
| GET    | `/api/tt/my-groups`             | Current user's groups |

### Safety — `/api/safety/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/safety/register`        | Create tourist profile |
| POST | `/api/safety/update_location` | Push GPS location |
| POST | `/api/safety/panic`           | Trigger panic alert |
| GET  | `/api/safety/zones`           | List safety zones |
| GET  | `/api/safety/my_profile`      | Tourist's own profile |

### Admin — `/api/admin/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/tourists`  | All tourist records |
| GET | `/api/admin/alerts`    | Latest 50 alerts |
| GET | `/api/admin/anomalies` | Active anomalies |

---

## Real-time Chat (Socket.IO)

| Event (emit)    | Payload | Description |
|-----------------|---------|-------------|
| `join`          | `{ group_id }` | Join a chat room |
| `leave`         | `{ group_id }` | Leave a chat room |
| `send_message`  | `{ group_id, message }` | Send a message |

| Event (listen)  | Payload | Description |
|-----------------|---------|-------------|
| `new_message`   | `{ sender, message, timestamp }` | Receive a message |
| `status`        | `{ message }` | Room join confirmation |

---

## Database Models

| Model | Feature | Key fields |
|-------|---------|------------|
| `User` | Core | username, password (hashed), email, phone |
| `Destination` | Travel | name, country |
| `Group` | Travel | name, type, owner, destination, member_count |
| `GroupMember` | Travel | group, user, role, join_status |
| `GroupMessage` | Travel | group, sender, message, timestamp |
| `Tourist` | Safety | links to User, kyc_id, safety_score, last_known_location |
| `SafetyZone` | Safety | name, lat/lon, radius, regional_score |
| `Alert` | Safety | tourist, alert_type, location, timestamp |
| `Anomaly` | Safety | tourist, anomaly_type, description, status |

---

## Team
- Aryan "The LEDA" Agarwal
- Dev 'CR' Saxena
- Rachit 'Moong_Daal' Kanchan
- Anurag 'Anni' Singh
- Rudra 'The Great' Singh
