# SAFAR

SAFAR is a Flask app that combines travel groups, chat, tourist registration, live safety tracking, alerts, and optional IoT integration.

## Project Structure

```text
SAFAR/
|-- app.py
|-- database.py
|-- requirements.txt
|-- .env
|-- static/
|   |-- style.css
|   |-- script.js
|   |-- group_chat.js
|   `-- images/
`-- templates/
    |-- index.html
    |-- auth.html
    |-- groups.html
    |-- group_chat.html
    |-- travel.html
    |-- about.html
    |-- user_dashboard.html
    `-- admin_dashboard.html
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `.env`

```env
SECRET_KEY=your_flask_secret_key
ALLOW_UNSAFE_WERKZEUG=1
HOST=127.0.0.1
PORT=5050
REQUIRE_REMOTE_DB=1
ALLOW_SQLITE_FALLBACK=0

DATABASE_URL=postgresql+pg8000://postgres.<project-ref>:your_password@aws-<region>.pooler.supabase.com:5432/postgres
DB_CONNECT_TIMEOUT=20

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

BLYNK_AUTH_TOKEN=your_blynk_token
```

Twilio is optional. If it is not configured, OTPs are printed to the console.

Blynk is optional. The IoT polling loop only works when a token is configured for the user or in `BLYNK_AUTH_TOKEN`.

### 3. Run

```bash
python app.py
```

The local default is `http://127.0.0.1:5050`.

## Deployment

### Render start command

```bash
gunicorn --worker-class gthread --threads 100 --bind 0.0.0.0:$PORT app:app
```

### Required deployment env vars

- `SECRET_KEY`
- `DATABASE_URL`

## Main API Areas

- Auth: `/api/auth/...`
- OTP: `/api/otp/...`
- Travel groups: `/api/tt/...`
- Safety: `/api/safety/...`
- Admin: `/api/admin/...`

## Notes

- Special characters in the database password are supported.
- SQLite fallback is available only when `ALLOW_SQLITE_FALLBACK=1`.
