"""
app.py – Combined Backend
  Project 1 : TravelTogether  (groups, destinations, group chat)
  Project 2 : Astra Safety    (tourist tracking, geo-fencing, anomalies, OTP)

Run locally:
    pip install -r requirements.txt
    python app.py
"""

import os, re, uuid, hashlib, threading, time, random
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit

# Optional Twilio
try:
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioRestException
    TWILIO_ENABLED = True
except ImportError:
    TWILIO_ENABLED = False

from database import (
    db,
    User, Destination, Group, GroupMember, GroupMessage,
    Tourist, SafetyZone, Alert, Anomaly,
    generate_id
)

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change_me_in_production')

# Database Strategy: Use Supabase pooler (port 6543) for Render/serverless compatibility
# Port 5432 = direct connection (blocked by some hosts like Render)
# Port 6543 = Supabase connection pooler (recommended for external deployments)
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    DATABASE_URL = 'postgresql+pg8000://postgres:AI_Defenders_2026@db.cicxpxpssoqetgvheqcg.supabase.co:6543/postgres'

# Fix Render's 'postgres://' prefix and ensure pg8000 driver is used
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+pg8000" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

# Handle SSL parameters for pg8000
connect_args = {}
if "pg8000" in DATABASE_URL:
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args['ssl_context'] = ssl_context
    
    # Strip sslmode from URL if present (redundant with connect_args)
    if "sslmode=" in DATABASE_URL:
        DATABASE_URL = re.sub(r'[?&]sslmode=[^&]+', '', DATABASE_URL)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Use NullPool when using Supabase connection pooler (Supavisor handles pooling)
from sqlalchemy.pool import NullPool
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': connect_args,
    'poolclass': NullPool,
}

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# Twilio setup
TWILIO_ACCOUNT_SID   = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN    = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER  = os.environ.get('TWILIO_PHONE_NUMBER')
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ENABLED and TWILIO_ACCOUNT_SID else None

# In-memory OTP store  {phone: {otp, timestamp}}
otp_storage = {}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def validate_password(password: str):
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if not re.search(r'[a-zA-Z]', password):
        return False, "Password must contain at least one letter."
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number."
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password):
        return False, "Password must contain at least one special character."
    return True, "OK"


def validate_email(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1]


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Returns distance in km between two GPS coordinates."""
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def get_current_user():
    """Returns the logged-in User object or None."""
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None


def get_current_tourist():
    """Returns Tourist linked to the current session or None."""
    uid = session.get('user_id')
    if not uid:
        return None
    return Tourist.query.filter_by(user_id=uid).first()


def find_or_create_destination(name: str) -> str | None:
    if not name or not name.strip():
        return None
    clean = name.strip().title()
    dest = Destination.query.filter_by(name=clean).first()
    if dest:
        return dest.id
    dest = Destination(id=generate_id(), name=clean)
    db.session.add(dest)
    db.session.commit()
    return dest.id


# ─────────────────────────────────────────────
# ANOMALY DETECTION (Astra)
# ─────────────────────────────────────────────

def check_for_anomalies():
    """Flags tourists inactive or exhibiting abnormal patterns using Isolation Forest."""
    with app.app_context():
        now = datetime.utcnow()
        active = Tourist.query.filter(Tourist.visit_end_date > now).all()
        if not active:
            return

        CRITICAL_SEC = 1200   # 20 min fallback
        WARNING_SEC  = 600    # 10 min fallback
        ten_ago = now - timedelta(minutes=10)

        data = []
        for t in active:
            idle = (now - t.last_updated_at).total_seconds()
            score = t.safety_score
            data.append([idle, score])

        if len(data) >= 3:
            try:
                from sklearn.ensemble import IsolationForest
                import numpy as np
                X = np.array(data)
                clf = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
                preds = clf.fit_predict(X)
                
                for idx, t in enumerate(active):
                    if preds[idx] == -1:  # Anomaly detected by Isolation Forest
                        recent = Anomaly.query.filter(
                            Anomaly.tourist_id == t.id,
                            Anomaly.timestamp > ten_ago
                        ).first()
                        if not recent:
                            idle_min = data[idx][0] / 60
                            desc = f"AI Detected (Isolation Forest): Idle {idle_min:.1f}m, Score: {data[idx][1]}"
                            db.session.add(Anomaly(tourist_id=t.id, anomaly_type="AI Behavioral Anomaly", description=desc))
            except ImportError:
                print("Missing scikit-learn for Isolation Forest, using fallback.")

        # Fallback for simple inactivity
        for t in active:
            idle = (now - t.last_updated_at).total_seconds()

            if idle > CRITICAL_SEC:
                atype = "Critical Inactivity (20+ min)"
            elif idle > WARNING_SEC:
                atype = "Warning Inactivity (10+ min)"
            else:
                continue

            recent = Anomaly.query.filter(
                Anomaly.tourist_id == t.id,
                Anomaly.timestamp > ten_ago
            ).first()

            if not recent:
                desc = f"Last update was {idle / 60:.1f} minutes ago."
                db.session.add(Anomaly(tourist_id=t.id, anomaly_type=atype, description=desc))

        db.session.commit()


# ─────────────────────────────────────────────
# INITIAL DATA SEED
# ─────────────────────────────────────────────

def seed_safety_zones():
    if SafetyZone.query.count() > 0:
        return
    zones = [
        # High-alert
        SafetyZone(name='High-Alert: Zone near LoC',                    latitude=34.5266, longitude=74.4735, radius=30,  regional_score=5),
        SafetyZone(name='High-Risk: Remote Southern Valley (J&K)',      latitude=33.7294, longitude=74.83,   radius=25,  regional_score=15),
        SafetyZone(name='High-Alert: India-China Border (Northeast)',   latitude=27.9881, longitude=88.825,  radius=40,  regional_score=10),
        # Tourist risk
        SafetyZone(name='Paharganj Area, Delhi',                        latitude=28.6439, longitude=77.2124, radius=20,  regional_score=45),
        SafetyZone(name='Baga Beach Area (Night), Goa',                 latitude=15.5562, longitude=73.7547, radius=30,  regional_score=55),
        SafetyZone(name='Isolated Ghats, Varanasi',                     latitude=25.282,  longitude=82.9563, radius=50,  regional_score=60),
        # North India
        SafetyZone(name='Leh City, Ladakh',                             latitude=34.165,  longitude=77.5771, radius=120, regional_score=95),
        SafetyZone(name="Lutyens' Delhi",                               latitude=28.6139, longitude=77.209,  radius=50,  regional_score=98),
        SafetyZone(name='Pink City, Jaipur',                            latitude=26.9124, longitude=75.7873, radius=40,  regional_score=90),
        SafetyZone(name='Golden Temple, Amritsar',                      latitude=31.62,   longitude=74.8765, radius=20,  regional_score=96),
        SafetyZone(name='Taj Mahal Complex, Agra',                      latitude=27.1751, longitude=78.0421, radius=20,  regional_score=98),
        SafetyZone(name='Hazratganj, Lucknow',                          latitude=26.8467, longitude=80.9462, radius=20,  regional_score=88),
        SafetyZone(name='Bareilly Cantt',                               latitude=28.349,  longitude=79.426,  radius=4,   regional_score=99),
        # South India
        SafetyZone(name='Hitech City, Hyderabad',                       latitude=17.4435, longitude=78.3519, radius=50,  regional_score=92),
        SafetyZone(name='Munnar Tea Gardens, Kerala',                   latitude=10.0889, longitude=77.0595, radius=50,  regional_score=88),
        # East India
        SafetyZone(name='Park Street, Kolkata',                         latitude=22.5529, longitude=88.3542, radius=50,  regional_score=87),
        SafetyZone(name='Bodh Gaya, Bihar',                             latitude=24.6961, longitude=84.9912, radius=50,  regional_score=92),
    ]
    db.session.bulk_save_objects(zones)
    db.session.commit()
    print("Seeded safety zones.")


# ─────────────────────────────────────────────
# ════════════════════════════════════════════
#  PAGE ROUTES
# ════════════════════════════════════════════
# ─────────────────────────────────────────────

@app.route('/')
def index():
    user = get_current_user()
    return render_template('index.html', username=user.username if user else None)

# --- Auth pages ---
@app.route('/register')
def register_page():
    return redirect(url_for('auth_page', register=1))

@app.route('/login')
def login_page():
    return redirect(url_for('auth_page'))

@app.route('/auth')
def auth_page():
    return render_template('auth.html')

# --- TravelTogether pages ---
@app.route('/groups', methods=['GET'])
def groups_page():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))

    # Build groups list with extra info for the template
    all_groups = Group.query.all()
    my_member_ids = [m.group_id for m in user.memberships] if user.memberships else []
    groups = []
    for g in all_groups:
        owner = db.session.get(User, g.owner_id)
        groups.append({
            'group_id':          g.id,
            'group_name':        g.name,
            'group_description': g.description,
            'group_type':        g.group_type,
            'owner_id':          g.owner_id,
            'owner_name':        owner.username if owner else 'Unknown',
            'destination_name':  g.destination.name if g.destination else None,
            'member_count':      g.member_count,
            'is_member':         g.id in my_member_ids,
        })

    # Build destinations list
    dests = Destination.query.order_by(Destination.name).all()
    destinations = [{'destination_id': d.id, 'destination_name': d.name, 'country': d.country} for d in dests]

    return render_template('groups.html', user=user, username=user.username, groups=groups, destinations=destinations)


@app.route('/groups', methods=['POST'])
def groups_create():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))

    name       = (request.form.get('group_name') or '').strip()
    group_type = request.form.get('group_type', 'Public')
    dest_name  = request.form.get('destination_name')
    desc       = request.form.get('group_description')

    if not name:
        return redirect(url_for('groups_page'))

    dest_id = find_or_create_destination(dest_name) if dest_name else None

    group = Group(
        id             = generate_id(),
        name           = name,
        description    = desc,
        group_type     = group_type,
        owner_id       = user.id,
        destination_id = dest_id,
    )
    db.session.add(group)
    db.session.flush()

    member = GroupMember(
        id       = generate_id(),
        group_id = group.id,
        user_id  = user.id,
        role     = 'Owner',
    )
    db.session.add(member)
    db.session.commit()
    return redirect(url_for('groups_page'))


@app.route('/groups/join/<group_id>')
def groups_join(group_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))

    group = db.session.get(Group, group_id)
    if not group:
        return redirect(url_for('groups_page'))

    existing = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if not existing and group.member_count < group.max_members:
        status = 'Pending' if group.group_type == 'Private' else 'Approved'
        db.session.add(GroupMember(
            id=generate_id(), group_id=group_id, user_id=user.id, role='Member', join_status=status,
        ))
        if status == 'Approved':
            group.member_count += 1
        db.session.commit()
    return redirect(url_for('groups_page'))


@app.route('/groups/leave/<group_id>')
def groups_leave(group_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))

    member = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if member and member.role != 'Owner':
        group = db.session.get(Group, group_id)
        db.session.delete(member)
        if group and member.join_status == 'Approved':
            group.member_count = max(0, group.member_count - 1)
        db.session.commit()
    return redirect(url_for('groups_page'))


@app.route('/groups/delete/<group_id>')
def groups_delete(group_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))

    group = db.session.get(Group, group_id)
    if group and group.owner_id == user.id:
        db.session.delete(group)
        db.session.commit()
    return redirect(url_for('groups_page'))


@app.route('/groups/chat/<group_id>')
def chat_page(group_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))
    group = db.session.get(Group, group_id)
    if not group:
        return "Group not found", 404

    # Fetch members
    member_rows = (
        db.session.query(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .filter(GroupMember.group_id == group_id, GroupMember.join_status == 'Approved')
        .all()
    )
    members = [{'username': u.username, 'role': m.role} for m, u in member_rows]

    # Fetch messages
    msgs = (
        GroupMessage.query
        .filter_by(group_id=group_id)
        .order_by(GroupMessage.timestamp.asc())
        .limit(100)
        .all()
    )
    messages = [{
        'sender_name': m.sender.username,
        'message':     m.message,
        'timestamp':   m.timestamp.strftime('%H:%M'),
    } for m in msgs]

    return render_template('group_chat.html',
        group_id=group.id,
        group_name=group.name,
        username=user.username,
        members=members,
        messages=messages,
        destination_name=group.destination.name if group.destination else None,
        member_count=group.member_count,
    )


# --- Destinations management (form-based) ---
@app.route('/destinations/add', methods=['POST'])
def destinations_add():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))
    name    = (request.form.get('destination_name') or '').strip().title()
    country = (request.form.get('country') or '').strip().title()
    if name:
        dest_id = find_or_create_destination(name)
        if country:
            dest = db.session.get(Destination, dest_id)
            if dest:
                dest.country = country
                db.session.commit()
    return redirect(url_for('groups_page'))


@app.route('/destinations/edit/<dest_id>', methods=['POST'])
def destinations_edit(dest_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))
    dest = db.session.get(Destination, dest_id)
    if dest:
        name = (request.form.get('destination_name') or '').strip().title()
        country = (request.form.get('country') or '').strip().title()
        if name:
            dest.name = name
        if country:
            dest.country = country
        db.session.commit()
    return redirect(url_for('groups_page'))


@app.route('/destinations/delete/<dest_id>')
def destinations_delete(dest_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))
    dest = db.session.get(Destination, dest_id)
    if dest:
        db.session.delete(dest)
        db.session.commit()
    return redirect(url_for('groups_page'))


# --- Astra Safety pages ---
@app.route('/profile')
def profile_page():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))
    tourist = get_current_tourist()
    if not tourist:
        return redirect(url_for('auth_page'))
    return render_template('profile.html', user=user, tourist=tourist)

@app.route('/admin')
def admin_dashboard_page():
    return render_template('admin_dashboard.html')

@app.route('/travel')
def travel_page():
    user = get_current_user()
    return render_template('travel.html', username=user.username if user else None)

@app.route('/about')
def about_page():
    user = get_current_user()
    return render_template('about.html', username=user.username if user else None)

@app.route('/user')
def user_dashboard_page():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))

    # Find the user's current group (first approved membership)
    membership = GroupMember.query.filter_by(user_id=user.id, join_status='Approved').first()
    group = None
    members = []
    if membership:
        g = db.session.get(Group, membership.group_id)
        if g:
            group = {
                'group_id':          g.id,
                'group_name':        g.name,
                'group_description': g.description,
                'group_type':        g.group_type,
                'owner_id':          g.owner_id,
                'destination_name':  g.destination.name if g.destination else None,
                'member_count':      g.member_count,
            }
            member_rows = (
                db.session.query(GroupMember, User)
                .join(User, User.id == GroupMember.user_id)
                .filter(GroupMember.group_id == g.id, GroupMember.join_status == 'Approved')
                .all()
            )
            members = [{'username': u.username, 'role': m.role} for m, u in member_rows]

    return render_template('user_dashboard.html', user=user, group=group, members=members)


@app.route('/user/edit', methods=['POST'])
def user_edit():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_page'))
    phone  = request.form.get('phone_no')
    gender = request.form.get('gender')
    bio    = request.form.get('bio')
    if phone is not None:
        user.phone = phone
    if gender is not None:
        user.gender = gender
    if bio is not None:
        user.bio = bio
    db.session.commit()
    return redirect(url_for('user_dashboard_page'))


# ─────────────────────────────────────────────
# ════════════════════════════════════════════
#  AUTH API  (/api/auth/...)
# ════════════════════════════════════════════
# ─────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """
    Register a new user (TravelTogether account).
    Optionally also creates a Tourist profile if KYC data is supplied.

    Body (JSON):
        username, password, email
        [phone, gender, bio]                  — optional user fields
        [kyc_id, kyc_type, visit_duration_days] — optional tourist fields
    """
    data = request.get_json(force=True)

    # --- Validate required fields ---
    for field in ('username', 'password', 'email'):
        if not data.get(field):
            return jsonify({'error': f'{field} is required.'}), 400

    if not validate_email(data['email']):
        return jsonify({'error': 'Invalid email address.'}), 400

    ok, msg = validate_password(data['password'])
    if not ok:
        return jsonify({'error': msg}), 400

    # --- Create User ---
    user = User(
        id       = generate_id(),
        username = data['username'].strip(),
        password = hash_password(data['password']),
        email    = data['email'].strip().lower(),
        phone    = data.get('phone'),
        gender   = data.get('gender'),
        bio      = data.get('bio'),
    )
    db.session.add(user)

    try:
        db.session.flush()   # get user.id before commit
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Database Error: {e}'}), 409

    # --- Optionally create Tourist profile ---
    tourist = None
    if data.get('kyc_id') and data.get('kyc_type') and data.get('visit_duration_days'):
        phone = data.get('phone') or ''


        end_date      = datetime.utcnow() + timedelta(days=int(data['visit_duration_days']))
        unique_string = f"{data['username']}:{data['kyc_id']}:{datetime.utcnow()}"
        digital_id    = hashlib.sha256(unique_string.encode()).hexdigest()

        tourist = Tourist(
            user_id        = user.id,
            digital_id     = digital_id,
            name           = data.get('name') or data['username'],
            phone          = phone,
            kyc_id         = data['kyc_id'],
            kyc_type       = data['kyc_type'],
            visit_end_date = end_date,
        )
        db.session.add(tourist)

    db.session.commit()
    session['user_id'] = user.id

    return jsonify({
        'message': 'Registration successful.',
        'user_id': user.id,
        'has_tourist_profile': tourist is not None,
    }), 201


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """
    Login with username+password  OR  phone+OTP (Astra-style).

    Body options:
        { "username": "...", "password": "..." }
        { "phone": "+91...", "otp_verified": true }
    """
    data = request.get_json(force=True)

    if data.get('username') and data.get('password'):
        user = User.query.filter_by(username=data['username']).first()
        if not user or user.password != hash_password(data['password']):
            return jsonify({'error': 'Invalid credentials.'}), 401
        session['user_id'] = user.id
        return jsonify({'message': 'Login successful.', 'user_id': user.id}), 200

    if data.get('phone'):
        # Tourist phone-only login (OTP must have been verified separately)
        if not data.get('otp_verified'):
            return jsonify({'error': 'OTP verification required.'}), 403
        tourist = Tourist.query.filter_by(phone=data['phone']).order_by(Tourist.id.desc()).first()
        if not tourist:
            return jsonify({'error': 'No tourist profile found for this number.'}), 404
        if tourist.user_id:
            session['user_id'] = tourist.user_id
        session['tourist_id'] = tourist.id
        return jsonify({'message': 'Tourist login successful.', 'tourist_id': tourist.id}), 200

    return jsonify({'error': 'Provide username+password or phone.'}), 400


@app.route('/api/auth/logout')
def api_logout():
    session.clear()
    return redirect(url_for('index'))


# ─────────────────────────────────────────────
# ════════════════════════════════════════════
#  OTP API  (/api/otp/...)
# ════════════════════════════════════════════
# ─────────────────────────────────────────────

@app.route('/api/otp/send', methods=['POST'])
def api_send_otp():
    data  = request.get_json(force=True)
    phone = data.get('phone', '').strip()

    if not phone:
        return jsonify({'error': 'Phone number is required.'}), 400
    if not phone.startswith('+'):
        return jsonify({'error': 'Phone must be in E.164 format (e.g. +91xxxxxxxxxx).'}), 400

    otp = str(random.randint(100000, 999999))
    otp_storage[phone] = {'otp': otp, 'timestamp': datetime.utcnow()}

    if twilio_client:
        try:
            twilio_client.messages.create(
                body=f"Your verification code is: {otp}",
                from_=TWILIO_PHONE_NUMBER,
                to=phone,
            )
        except Exception as e:
            print(f"Twilio error: {e}")
            print(f"[DEV FALLBACK] OTP for {phone}: {otp}")
            return jsonify({
                'error': f'Twilio failed: {str(e)}', 
                'dev_otp': otp,
                'message': 'Failed to send SMS, but OTP generated for terminal.'
            }), 200
    else:
        # Dev mode: print OTP to console instead of sending SMS
        print(f"[DEV] OTP for {phone}: {otp}")

    return jsonify({'message': 'OTP sent.'}), 200


@app.route('/api/otp/verify', methods=['POST'])
def api_verify_otp():
    data        = request.get_json(force=True)
    phone       = data.get('phone', '').strip()
    otp_attempt = data.get('otp', '').strip()

    if phone not in otp_storage:
        return jsonify({'error': 'OTP not requested or already used.'}), 404

    info = otp_storage[phone]
    if datetime.utcnow() > info['timestamp'] + timedelta(minutes=5):
        del otp_storage[phone]
        return jsonify({'error': 'OTP expired.'}), 410

    if info['otp'] != otp_attempt:
        return jsonify({'error': 'Invalid OTP.'}), 400

    del otp_storage[phone]
    return jsonify({'message': 'OTP verified.', 'verified': True}), 200


# ─────────────────────────────────────────────
# ════════════════════════════════════════════
#  TRAVEL TOGETHER API  (/api/tt/...)
# ════════════════════════════════════════════
# ─────────────────────────────────────────────

# ── Destinations ──────────────────────────────

@app.route('/api/tt/destinations', methods=['GET'])
def tt_get_destinations():
    dests = Destination.query.order_by(Destination.name).all()
    return jsonify([{'id': d.id, 'name': d.name, 'country': d.country} for d in dests])


@app.route('/api/tt/destinations', methods=['POST'])
def tt_create_destination():
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip().title()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400

    dest_id = find_or_create_destination(name)
    dest    = db.session.get(Destination, dest_id)
    if data.get('country'):
        dest.country = data['country'].strip().title()
        db.session.commit()

    return jsonify({'id': dest.id, 'name': dest.name, 'country': dest.country}), 201


@app.route('/api/tt/destinations/<dest_id>', methods=['PUT'])
def tt_update_destination(dest_id):
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({'error': 'Not found.'}), 404
    data = request.get_json(force=True)
    if data.get('name'):
        dest.name = data['name'].strip().title()
    if data.get('country'):
        dest.country = data['country'].strip().title()
    db.session.commit()
    return jsonify({'message': 'Updated.', 'id': dest.id})


@app.route('/api/tt/destinations/<dest_id>', methods=['DELETE'])
def tt_delete_destination(dest_id):
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({'error': 'Not found.'}), 404
    db.session.delete(dest)
    db.session.commit()
    return jsonify({'message': 'Deleted.'})


@app.route('/api/tt/destinations/popular')
def tt_popular_destinations():
    from sqlalchemy import func
    rows = (
        db.session.query(Destination.name, func.count(Group.id).label('cnt'))
        .join(Group, Group.destination_id == Destination.id)
        .group_by(Destination.name)
        .order_by(func.count(Group.id).desc())
        .limit(int(request.args.get('limit', 5)))
        .all()
    )
    return jsonify([{'name': r.name, 'group_count': r.cnt} for r in rows])


# ── Groups ────────────────────────────────────

@app.route('/api/tt/groups', methods=['GET'])
def tt_list_groups():
    """List public groups, or groups for the logged-in user."""
    user = get_current_user()
    if not user:
        groups = Group.query.filter_by(group_type='Public').all()
    else:
        # Return all public groups + groups the user belongs to
        my_ids  = [m.group_id for m in user.memberships]
        groups  = Group.query.filter(
            (Group.group_type == 'Public') | (Group.id.in_(my_ids))
        ).all()

    return jsonify([{
        'id':          g.id,
        'name':        g.name,
        'description': g.description,
        'type':        g.group_type,
        'owner_id':    g.owner_id,
        'destination': g.destination.name if g.destination else None,
        'member_count': g.member_count,
        'max_members':  g.max_members,
        'created_at':   g.created_at.isoformat(),
    } for g in groups])


@app.route('/api/tt/groups', methods=['POST'])
def tt_create_group():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated.'}), 401

    data = request.get_json(force=True)
    name       = (data.get('name') or '').strip()
    group_type = data.get('type', 'Public')
    dest_name  = data.get('destination')

    if not name:
        return jsonify({'error': 'Group name is required.'}), 400
    if group_type not in ('Public', 'Private'):
        return jsonify({'error': "type must be 'Public' or 'Private'."}), 400

    dest_id = find_or_create_destination(dest_name) if dest_name else None

    group = Group(
        id             = generate_id(),
        name           = name,
        description    = data.get('description'),
        group_type     = group_type,
        owner_id       = user.id,
        destination_id = dest_id,
        max_members    = int(data.get('max_members', 50)),
    )
    db.session.add(group)
    db.session.flush()

    member = GroupMember(
        id       = generate_id(),
        group_id = group.id,
        user_id  = user.id,
        role     = 'Owner',
    )
    db.session.add(member)
    db.session.commit()

    return jsonify({'message': 'Group created.', 'group_id': group.id}), 201


@app.route('/api/tt/groups/<group_id>', methods=['GET'])
def tt_get_group(group_id):
    g = db.session.get(Group, group_id)
    if not g:
        return jsonify({'error': 'Not found.'}), 404
    return jsonify({
        'id': g.id, 'name': g.name, 'description': g.description,
        'type': g.group_type, 'owner_id': g.owner_id,
        'destination': g.destination.name if g.destination else None,
        'member_count': g.member_count, 'max_members': g.max_members,
    })


@app.route('/api/tt/groups/<group_id>/join', methods=['POST'])
def tt_join_group(group_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated.'}), 401

    group = db.session.get(Group, group_id)
    if not group:
        return jsonify({'error': 'Group not found.'}), 404
    if group.member_count >= group.max_members:
        return jsonify({'error': 'Group is full.'}), 400

    existing = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if existing:
        return jsonify({'error': 'Already a member.'}), 409

    status = 'Pending' if group.group_type == 'Private' else 'Approved'
    db.session.add(GroupMember(
        id       = generate_id(),
        group_id = group_id,
        user_id  = user.id,
        role     = 'Member',
        join_status = status,
    ))
    if status == 'Approved':
        group.member_count += 1
    db.session.commit()

    return jsonify({'message': f'Joined group (status: {status}).'}), 200


@app.route('/api/tt/groups/<group_id>/leave', methods=['POST'])
def tt_leave_group(group_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated.'}), 401

    member = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if not member:
        return jsonify({'error': 'Not a member.'}), 404
    if member.role == 'Owner':
        return jsonify({'error': 'Owner cannot leave. Delete the group instead.'}), 403

    group = db.session.get(Group, group_id)
    db.session.delete(member)
    if group and member.join_status == 'Approved':
        group.member_count = max(0, group.member_count - 1)
    db.session.commit()

    return jsonify({'message': 'Left group.'})


@app.route('/api/tt/groups/<group_id>', methods=['DELETE'])
def tt_delete_group(group_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated.'}), 401

    group = db.session.get(Group, group_id)
    if not group:
        return jsonify({'error': 'Not found.'}), 404
    if group.owner_id != user.id:
        return jsonify({'error': 'Only the owner can delete this group.'}), 403

    db.session.delete(group)
    db.session.commit()
    return jsonify({'message': 'Group deleted.'})


@app.route('/api/tt/groups/<group_id>/members')
def tt_group_members(group_id):
    members = (
        db.session.query(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .filter(GroupMember.group_id == group_id,
                GroupMember.join_status == 'Approved')
        .all()
    )
    return jsonify([{
        'username':  u.username,
        'email':     u.email,
        'role':      m.role,
        'joined_at': m.joined_at.isoformat(),
    } for m, u in members])


@app.route('/api/tt/groups/<group_id>/messages')
def tt_group_messages(group_id):
    msgs = (
        GroupMessage.query
        .filter_by(group_id=group_id)
        .order_by(GroupMessage.timestamp.asc())
        .limit(100)
        .all()
    )
    return jsonify([{
        'id':        m.id,
        'sender':    m.sender.username,
        'message':   m.message,
        'timestamp': m.timestamp.isoformat(),
    } for m in msgs])


@app.route('/api/tt/groups/<group_id>/messages', methods=['POST'])
def tt_send_message(group_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated.'}), 401

    member = GroupMember.query.filter_by(
        group_id=group_id, user_id=user.id, join_status='Approved'
    ).first()
    if not member:
        return jsonify({'error': 'Not a member of this group.'}), 403

    data = request.get_json(force=True)
    text = (data.get('message') or '').strip()
    if not text:
        return jsonify({'error': 'Message cannot be empty.'}), 400

    msg = GroupMessage(
        group_id  = group_id,
        sender_id = user.id,
        message   = text,
    )
    db.session.add(msg)
    db.session.commit()

    # Broadcast to room via SocketIO
    socketio.emit('new_message', {
        'sender':    user.username,
        'message':   text,
        'timestamp': msg.timestamp.isoformat(),
    }, room=group_id)

    return jsonify({'message': 'Sent.', 'id': msg.id}), 201


@app.route('/api/tt/my-groups')
def tt_my_groups():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated.'}), 401

    rows = (
        db.session.query(Group, GroupMember, Destination)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .outerjoin(Destination, Destination.id == Group.destination_id)
        .filter(GroupMember.user_id == user.id)
        .all()
    )
    return jsonify([{
        'id':          g.id,
        'name':        g.name,
        'type':        g.group_type,
        'role':        m.role,
        'destination': d.name if d else None,
        'member_count': g.member_count,
    } for g, m, d in rows])


# ─────────────────────────────────────────────
# ════════════════════════════════════════════
#  ASTRA SAFETY API  (/api/safety/...)
# ════════════════════════════════════════════
# ─────────────────────────────────────────────

@app.route('/api/safety/register', methods=['POST'])
def safety_register():
    """
    Creates a Tourist profile for an existing User, or standalone if no user session.
    Body: name, phone, kyc_id, kyc_type, visit_duration_days
    """
    data = request.get_json(force=True)

    required = ('name', 'phone', 'kyc_id', 'kyc_type', 'visit_duration_days')
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required.'}), 400

    # No unique restrictions on phone or kyc_id

    end_date  = datetime.utcnow() + timedelta(days=int(data['visit_duration_days']))
    unique_s  = f"{data['name']}:{data['kyc_id']}:{datetime.utcnow()}"
    digital_id = hashlib.sha256(unique_s.encode()).hexdigest()

    user_id = session.get('user_id')
    tourist = Tourist(
        user_id        = user_id,
        digital_id     = digital_id,
        name           = data['name'],
        phone          = data['phone'],
        kyc_id         = data['kyc_id'],
        kyc_type       = data['kyc_type'],
        visit_end_date = end_date,
    )
    db.session.add(tourist)
    db.session.commit()
    session['tourist_id'] = tourist.id

    return jsonify({'message': 'Tourist profile created.', 'tourist_id': tourist.id}), 201


@app.route('/api/safety/update_location', methods=['POST'])
def safety_update_location():
    tourist_id = session.get('tourist_id')
    if not tourist_id:
        tourist = get_current_tourist()
        if tourist:
            tourist_id = tourist.id
    if not tourist_id:
        return jsonify({'error': 'Not authenticated as a tourist.'}), 401

    data = request.get_json(force=True)
    lat, lon = data.get('latitude'), data.get('longitude')
    if lat is None or lon is None:
        return jsonify({'error': 'latitude and longitude are required.'}), 400

    tourist = db.session.get(Tourist, tourist_id)
    if not tourist:
        return jsonify({'error': 'Tourist not found.'}), 404

    # Resolve active anomalies on any location update
    Anomaly.query.filter_by(tourist_id=tourist.id, status='active').update({'status': 'resolved'})

    tourist.last_known_location = f"Lat: {lat}, Lon: {lon}"
    tourist.last_updated_at     = datetime.utcnow()

    # Geo-fence scoring
    current_zone_score = None
    for zone in SafetyZone.query.all():
        if haversine(lat, lon, zone.latitude, zone.longitude) <= zone.radius:
            if current_zone_score is None or zone.regional_score < current_zone_score:
                current_zone_score = zone.regional_score

            if zone.regional_score < 40:
                ten_ago = datetime.utcnow() - timedelta(minutes=10)
                breach  = Alert.query.filter(
                    Alert.tourist_id == tourist.id,
                    Alert.alert_type.like('%Geo-fence%'),
                    Alert.timestamp > ten_ago,
                ).first()
                if not breach:
                    db.session.add(Alert(
                        tourist_id = tourist.id,
                        location   = tourist.last_known_location,
                        alert_type = f"Geo-fence Breach: {zone.name}",
                    ))

    if current_zone_score is not None:
        if current_zone_score < tourist.safety_score:
            tourist.safety_score = current_zone_score
        elif current_zone_score > 80 and tourist.safety_score < 100:
            tourist.safety_score = min(100, tourist.safety_score + 1)

    db.session.commit()
    return jsonify({'message': 'Location updated.', 'safety_score': tourist.safety_score}), 200


@app.route('/api/safety/panic', methods=['POST'])
def safety_panic():
    tourist_id = session.get('tourist_id') or (get_current_tourist().id if get_current_tourist() else None)
    if not tourist_id:
        return jsonify({'error': 'Not authenticated.'}), 401

    tourist = db.session.get(Tourist, tourist_id)
    if not tourist:
        return jsonify({'error': 'Tourist not found.'}), 404

    db.session.add(Alert(
        tourist_id = tourist.id,
        location   = tourist.last_known_location,
        alert_type = 'Panic Button',
    ))
    tourist.safety_score = 0
    db.session.commit()
    return jsonify({'message': 'Panic alert registered.'}), 200


@app.route('/api/safety/zones')
def safety_zones():
    zones = SafetyZone.query.all()
    return jsonify([{
        'name':           z.name,
        'latitude':       z.latitude,
        'longitude':      z.longitude,
        'radius':         z.radius,
        'regional_score': z.regional_score,
    } for z in zones])


@app.route('/api/safety/my_profile')
def safety_my_profile():
    tourist = get_current_tourist()
    if not tourist:
        return jsonify({'error': 'No tourist profile found.'}), 404
    return jsonify({
        'id':                   tourist.id,
        'name':                 tourist.name,
        'phone':                tourist.phone,
        'safety_score':         tourist.safety_score,
        'last_known_location':  tourist.last_known_location,
        'visit_end_date':       tourist.visit_end_date.isoformat(),
        'last_updated_at':      tourist.last_updated_at.isoformat(),
    })


# ── Admin / Dashboard ─────────────────────────

@app.route('/api/admin/tourists')
def admin_tourists():
    tourists = Tourist.query.all()
    return jsonify([{
        'id':                  t.id,
        'name':                t.name,
        'phone':               t.phone,
        'safety_score':        t.safety_score,
        'last_known_location': t.last_known_location,
        'visit_end_date':      t.visit_end_date.isoformat(),
    } for t in tourists])


@app.route('/api/admin/alerts')
def admin_alerts():
    alerts = Alert.query.order_by(Alert.timestamp.desc()).limit(50).all()
    return jsonify([{
        'tourist_name': a.tourist.name,
        'alert_type':   a.alert_type,
        'location':     a.location,
        'timestamp':    a.timestamp.strftime('%d-%b-%Y %H:%M:%S'),
    } for a in alerts])


@app.route('/api/admin/anomalies')
def admin_anomalies():
    anomalies = (
        Anomaly.query.filter_by(status='active')
        .order_by(Anomaly.timestamp.desc())
        .limit(50).all()
    )
    return jsonify([{
        'tourist_name': a.tourist.name,
        'anomaly_type': a.anomaly_type,
        'description':  a.description,
        'timestamp':    a.timestamp.strftime('%d-%b-%Y %H:%M:%S'),
    } for a in anomalies])


# Cron endpoint (call from external scheduler)
@app.route('/cron/anomaly-check/<secret_key>')
def cron_anomaly_check(secret_key):
    cron_secret = os.environ.get('CRON_SECRET_KEY')
    if not cron_secret or secret_key != cron_secret:
        return jsonify({'error': 'Unauthorized.'}), 401
    check_for_anomalies()
    return jsonify({'message': 'Anomaly check complete.'}), 200


# ─────────────────────────────────────────────
# ════════════════════════════════════════════
#  SOCKET IO EVENTS  (real-time group chat)
# ════════════════════════════════════════════
# ─────────────────────────────────────────────

@socketio.on('join')
def on_join(data):
    room = data.get('group_id')
    if room:
        join_room(room)
        emit('status', {'message': f"Joined room {room}"}, room=room)

@socketio.on('leave')
def on_leave(data):
    room = data.get('group_id')
    if room:
        leave_room(room)

@socketio.on('send_message')
def on_send_message(data):
    """
    Expect: { group_id, message }
    Session must contain user_id.
    """
    user = get_current_user()
    if not user:
        return

    group_id = data.get('group_id')
    text     = (data.get('message') or '').strip()
    if not group_id or not text:
        return

    member = GroupMember.query.filter_by(
        group_id=group_id, user_id=user.id, join_status='Approved'
    ).first()
    if not member:
        return

    msg = GroupMessage(group_id=group_id, sender_id=user.id, message=text)
    db.session.add(msg)
    db.session.commit()

    emit('new_message', {
        'sender':    user.username,
        'message':   text,
        'timestamp': msg.timestamp.isoformat(),
    }, room=group_id)


# ─────────────────────────────────────────────
# DB INIT + SERVER ENTRY POINTS
# ─────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        seed_safety_zones()
        print("Database ready.")


def run_server(host='0.0.0.0', port=5000, debug=False):
    """Entry point used by main.py / web.py launchers."""
    init_db()
    socketio.run(app, host=host, port=port, debug=debug)


def anomaly_loop():
    while True:
        try:
            check_for_anomalies()
        except Exception as e:
            print(f"Anomaly loop error: {e}")
        time.sleep(300)

@app.before_request
def start_anomaly_thread():
    if not hasattr(app, 'anomaly_thread_started'):
        app.anomaly_thread_started = True
        threading.Thread(target=anomaly_loop, daemon=True).start()


if __name__ == '__main__':
    run_server(debug=True)
