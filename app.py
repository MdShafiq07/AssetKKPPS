from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file, jsonify, send_from_directory
from config import Config
from extensions import db
from models import User, Key, Log, Booking
from datetime import datetime, timedelta
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import qrcode
import csv
import io
import os
import random
from sqlalchemy import extract
from io import BytesIO, StringIO

# ==========================================
# 0. APP INITIALIZATION & CONFIG
# ==========================================

# Initialize Extensions
mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize Plugins
    db.init_app(app)
    mail.init_app(app)
    
    # Setup Login Manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login' # Redirect here if not logged in
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create Database Tables if they don't exist
    with app.app_context():
        db.create_all()

    return app

app = create_app()

# ==========================================
# 1. AUTHENTICATION (The Entry Point)
# ==========================================

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    - GET: Shows the login form.
    - POST: Validates credentials and checks if account is approved.
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            if not user.is_approved:
                flash('Account is pending Admin approval.', 'warning')
                return redirect(url_for('login'))
                
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Failed. Check username and password.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles new user registration.
    - First registered user automatically becomes 'Admin'.
    - Subsequent users are 'User' and require Admin approval.
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken!', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
        else:
            hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
            is_first = User.query.count() == 0
            role = 'admin' if is_first else 'user'
            is_approved = True if is_first else False
            
            new_user = User(username=username, email=email, password=hashed_pw, role=role, is_approved=is_approved)
            db.session.add(new_user)
            db.session.commit()
            
            flash('Admin account set!' if is_first else 'Wait for Admin approval.', 'success')
            return redirect(url_for('login'))
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """Logs the user out and clears the session."""
    logout_user()
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """
    Initiates password recovery.
    - Generates a 6-digit code.
    - Sends it to the user's email via SMTP.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            code = str(random.randint(100000, 999999))
            user.reset_code = code
            user.reset_expiry = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()

            msg = Message("KeyHub Account Recovery", recipients=[user.email])
            msg.body = (f"Hello,\n\nYour username is: {user.username}\n"
                        f"Your reset code is: {code}\n\nValid for 10 minutes.")
            try:
                mail.send(msg)
                session['reset_email'] = user.email
                return redirect(url_for('verify_code'))
            except Exception as e:
                flash(f'Email error: {str(e)}', 'danger')
        else:
            flash('Email not found.', 'danger')
    return render_template('forgot_password.html')

@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    """
    Verifies the 6-digit recovery code.
    - If correct, resets the password to the new input.
    """
    if request.method == 'POST':
        code = request.form.get('code')
        new_pass = request.form.get('password')
        email = session.get('reset_email')
        user = User.query.filter_by(email=email).first()

        if user and user.reset_code == code and datetime.utcnow() < user.reset_expiry:
            user.password = generate_password_hash(new_pass, method='pbkdf2:sha256')
            user.reset_code = None
            db.session.commit()
            flash('Password reset successful!', 'success')
            return redirect(url_for('login'))
        flash('Invalid or expired code.', 'danger')
    return render_template('verify_code.html')

# ==========================================
# 2. MAIN DASHBOARD & USER ACTIONS
# ==========================================

@app.route('/dashboard')
@login_required
def dashboard():
    """
    The main hub.
    - Cleans up expired 'pending' requests (30s timeout).
    - Fetches available Keys and Equipment.
    - Shows the user's current bookings.
    """
    # 30-Second Auto Cleanup for pending requests
    threshold = datetime.utcnow() - timedelta(seconds=30)
    expired = Booking.query.filter(Booking.status == 'pending', Booking.request_date <= threshold).all()
    for b in expired:
        b.key.status = 'Available'
        db.session.delete(b)
    if expired: db.session.commit()

    # Get available assets separated by type
    available_keys = Key.query.filter_by(status='Available', type='Key').all()
    available_items = Key.query.filter_by(status='Available', type='Item').all()
    
    my_bookings = Booking.query.filter(Booking.user_id == current_user.id, Booking.status.in_(['pending', 'active'])).all()
    
    return render_template('dashboard.html', 
                           keys=available_keys, 
                           items=available_items, 
                           my_bookings=my_bookings)

@app.route('/request_key/<int:key_id>', methods=['POST'])
@login_required
def request_key(key_id):
    """
    User requests to borrow an item.
    - Sets item status to 'Borrowed'.
    - Creates a 'Pending' booking.
    - User has 30s to get it scanned by Admin.
    """
    asset = Key.query.get_or_404(key_id)
    duration = request.form.get('duration', default=4, type=int)
    
    if asset.status != 'Available':
        flash(f'Sorry! {asset.type} unavailable.', 'danger')
        return redirect(url_for('dashboard'))
    
    existing = Booking.query.filter(Booking.user_id == current_user.id, Booking.status.in_(['pending', 'active'])).first()
    if existing:
        flash('You already have an active request or item.', 'warning')
        return redirect(url_for('dashboard'))

    new_booking = Booking(user_id=current_user.id, key_id=asset.id, status='pending', duration_hours=duration)
    asset.status = 'Borrowed'
    db.session.add(new_booking)
    db.session.commit()
    
    flash(f'{asset.type} requested for {duration}h! Scan within 30s.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/active_keys')
@login_required
def active_keys():
    """
    Live Activity Monitor.
    - Admin: Sees ALL active/pending assets.
    - User: Sees only THEIR history and active items.
    """
    if current_user.role == 'admin':
        active_items = Booking.query.filter(Booking.status.in_(['active', 'pending'])).all()
    else:
        active_items = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.request_date.desc()).all()
        
    return render_template('active_keys.html', active_items=active_items, now=datetime.utcnow())

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    User Profile Page.
    - Allows password updates.
    - Shows recent personal activity logs.
    """
    if request.method == 'POST':
        new_password = request.form.get('password')
        if new_password:
            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
            db.session.commit()
            flash('Password updated successfully!', 'success')
        return redirect(url_for('profile'))
    user_logs = Log.query.filter_by(user_id=current_user.id).order_by(Log.timestamp.desc()).limit(10).all()
    return render_template('profile.html', logs=user_logs)

# ==========================================
# 3. QR SYSTEM & SCANNING
# ==========================================

@app.route('/generate_qr/<int:booking_id>')
@login_required
def generate_qr(booking_id):
    """
    Generates a dynamic QR code image.
    - Encodes 'APPROVE-ID' (for pickup) or 'RETURN-ID' (for returning).
    - Returns the image directly from memory (no file saved).
    """
    booking = Booking.query.get_or_404(booking_id)
    qr_data = f"APPROVE-{booking.id}" if booking.status == 'pending' else f"RETURN-{booking.id}"
    img = qrcode.make(qr_data)
    buf = BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/scan')
@login_required
def scan_page():
    """Renders the Admin Scanner Interface (Camera/USB)."""
    if current_user.role != 'admin': return redirect(url_for('dashboard'))
    return render_template('scan.html')

@app.route('/scan_qr', methods=['POST'])
@login_required
def scan_qr():
    """
    API endpoint that processes the scanned QR code.
    - Decodes 'ACTION-ID'.
    - Updates Booking status (Pending -> Active -> Completed).
    - Logs the transaction.
    """
    if current_user.role != 'admin': return jsonify({'status': 'error'}), 403
    data = request.get_json()
    qr_code = data.get('qr_code')
    try:
        action, b_id = qr_code.split('-')
        booking = Booking.query.get(b_id)
        if action == 'APPROVE':
            booking.status = 'active'
            log_msg = f'Picked Up {booking.key.type} ({booking.duration_hours}h)'
        else:
            booking.status = 'completed'
            booking.key.status = 'Available'
            log_msg = f'Returned {booking.key.type}'
        db.session.add(Log(user_id=booking.user_id, key_id=booking.key_id, action=log_msg))
        db.session.commit()
        return jsonify({'status': 'success', 'message': log_msg})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ==========================================
# 4. INVENTORY MANAGEMENT (CRUD)
# ==========================================

@app.route('/add_key', methods=['GET', 'POST'])
@login_required
def add_key():
    """
    Inventory Manager Page.
    - Manual Add: Single item entry.
    - Batch Add: Upload CSV to add multiple.
    """
    if current_user.role != 'admin': return redirect(url_for('dashboard'))
    if request.method == 'POST':
        asset_type = request.form.get('type')
        room_name = request.form.get('room_name')
        key_num = request.form.get('key_number')
        level = request.form.get('level') if asset_type == 'Key' else None

        new_asset = Key(type=asset_type, room_name=room_name, key_number=key_num, level=level)
        db.session.add(new_asset)
        db.session.commit()
        flash(f'{asset_type} added to inventory.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_key.html')

@app.route('/delete_key/<int:key_id>', methods=['POST'])
@login_required
def delete_key(key_id):
    """Deletes a specific asset from the database."""
    if current_user.role != 'admin': return "Unauthorized", 403
    key = Key.query.get_or_404(key_id)
    db.session.delete(key)
    db.session.commit()
    flash('Item deleted.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/download_template')
@login_required
def download_template():
    """Generates a CSV template for Batch Uploads (Key or Item specific)."""
    template_type = request.args.get('type', 'Key') 
    
    si = io.StringIO()
    cw = csv.writer(si)
    
    if template_type == 'Item':
        cw.writerow(['room_name', 'key_number', 'type']) 
        cw.writerow(['Laptop HP', 'SN-001', 'Item'])    
        filename = "template_equipment.csv"
    else:
        cw.writerow(['room_name', 'key_number', 'type', 'level'])
        cw.writerow(['Bilik Kuliah 1', 'K-BK1', 'Key', 'Aras 1'])
        filename = "template_keys.csv"

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=filename)

@app.route('/validate_batch', methods=['POST'])
@login_required
def validate_batch():
    """
    Step 1 of Batch Process:
    - Checks CSV headers.
    - Shows preview page (confirm_batch.html) before saving.
    """
    if current_user.role != 'admin': return redirect(url_for('dashboard'))

    file = request.files.get('csv_file')
    action = request.form.get('batch_action')
    
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a valid CSV file.', 'danger')
        return redirect(url_for('add_key'))

    temp_path = os.path.join('/tmp', 'temp_batch.csv') 
    file.save(temp_path)

    try:
        with open(temp_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = [h.strip() for h in reader.fieldnames] if reader.fieldnames else []
            
            required = ['key_number']
            if action == 'add':
                required = ['room_name', 'key_number', 'type']
            
            missing = [col for col in required if col not in headers]
            
            if missing:
                flash(f"Invalid Template! Missing columns: {', '.join(missing)}", 'danger')
                os.remove(temp_path)
                return redirect(url_for('add_key'))

            rows = list(reader)
            count = len(rows)
            preview = [f"{r.get('key_number')} - {r.get('room_name', '')}" for r in rows[:3]]
            
            session['batch_action'] = action
            return render_template('confirm_batch.html', action=action, count=count, preview=preview)

    except Exception as e:
        flash(f'Error reading file: {str(e)}', 'danger')
        return redirect(url_for('add_key'))

@app.route('/execute_batch', methods=['POST'])
@login_required
def execute_batch():
    """
    Step 2 of Batch Process:
    - Reads the temp CSV.
    - Writes changes (Add or Delete) to Database.
    - Cleans up temp file.
    """
    action = session.get('batch_action')
    temp_path = os.path.join('/tmp', 'temp_batch.csv') 
    
    if not os.path.exists(temp_path):
        flash('Session expired or file missing.', 'danger')
        return redirect(url_for('add_key'))

    count = 0
    try:
        with open(temp_path, 'r', encoding='utf-8-sig') as f:
            csv_input = csv.DictReader(f)
            for row in csv_input:
                clean_row = {k.strip(): v.strip() for k, v in row.items()}
                
                if action == 'add':
                    if not Key.query.filter_by(key_number=clean_row['key_number']).first():
                        new_asset = Key(
                            room_name=clean_row['room_name'],
                            key_number=clean_row['key_number'],
                            type=clean_row['type'],
                            level=clean_row.get('level')
                        )
                        db.session.add(new_asset)
                        count += 1
                
                elif action == 'delete':
                    asset = Key.query.filter_by(key_number=clean_row['key_number']).first()
                    if asset:
                        # Safety Check: Don't delete if actively borrowed
                        if not Booking.query.filter_by(key_id=asset.id, status='active').first():
                            db.session.delete(asset)
                            count += 1

        db.session.commit()
        flash(f'Success! Processed {count} items.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Database Error: {str(e)}', 'danger')
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
    return redirect(url_for('dashboard'))

# ==========================================
# 5. ADMIN USER MANAGEMENT & LOGS
# ==========================================

@app.route('/manage_users')
@login_required
def manage_users():
    """Admin page to view, approve, or delete users."""
    if current_user.role != 'admin': return redirect(url_for('dashboard'))
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('manage_users.html', users=users)

@app.route('/approve_user/<int:user_id>', methods=['POST'])
@login_required
def approve_user(user_id):
    """Approves a new user account so they can log in."""
    if current_user.role != 'admin': return "Unauthorized", 403
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    
    msg = Message("Account Approved - KeyHub", recipients=[user.email])
    msg.body = f"Hello {user.username}, your account has been approved!"
    try:
        mail.send(msg)
        db.session.commit()
        flash(f'User {user.username} approved.', 'success')
    except Exception as e:
        flash(f'Approved, but email failed: {str(e)}', 'warning')
        db.session.commit()
    return redirect(url_for('manage_users'))

@app.route('/reset_password/<int:user_id>', methods=['POST'])
@login_required
def reset_password(user_id):
    """Admin hard-reset for a user password (default: 123456)."""
    user = User.query.get_or_404(user_id)
    user.password = generate_password_hash('123456', method='pbkdf2:sha256')
    db.session.commit()
    flash(f'Reset {user.username} to 123456', 'info')
    return redirect(url_for('manage_users'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Permanently deletes a user account."""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('manage_users'))

@app.route('/logs')
@login_required
def logs():
    """View system audit logs (Who took what, when)."""
    if current_user.role != 'admin': return redirect(url_for('dashboard'))
    avail = db.session.query(extract('year', Log.timestamp).label('y'), extract('month', Log.timestamp).label('m')).distinct().all()
    all_logs = Log.query.order_by(Log.timestamp.desc()).all()
    months = [{'year': a.y, 'month': a.m} for a in avail]
    return render_template('logs.html', logs=all_logs, available_months=months)

@app.route('/export_logs')
@login_required
def export_logs():
    """Download logs as a CSV file."""
    if current_user.role != 'admin': return "Unauthorized", 403
    m, y = request.args.get('month', type=int), request.args.get('year', type=int)
    query = Log.query
    if m and y:
        query = query.filter(extract('month', Log.timestamp) == m, extract('year', Log.timestamp) == y)
    logs = query.order_by(Log.timestamp.desc()).all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Time', 'User', 'Action', 'Item/Room'])
    for l in logs:
        cw.writerow([l.timestamp.strftime('%Y-%m-%d %H:%M'), l.user.username, l.action, l.key.room_name])
    return send_file(BytesIO(si.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name="KMS_Logs.csv")

# ==========================================
# 6. PWA STATIC FILES
# ==========================================

@app.route('/sw.js')
def serve_sw():
    """Serves the Service Worker for Offline capabilities."""
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def serve_manifest():
    """Serves the App Manifest for 'Add to Home Screen'."""
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

# ==========================================
# 7. APP ENTRY POINT
# ==========================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)