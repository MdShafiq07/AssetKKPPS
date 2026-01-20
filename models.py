from extensions import db
from datetime import datetime
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False) # 'admin' or 'user'
    is_approved = db.Column(db.Boolean, default=False)
    
    # For Email Password Reset
    reset_code = db.Column(db.String(6), nullable=True)
    reset_expiry = db.Column(db.DateTime, nullable=True)

class Key(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # NEW: To distinguish between 'Key' and 'Item'
    type = db.Column(db.String(20), default='Key', nullable=False) 
    # This stores Room Name OR Item Name (e.g., 'Bilik BK1' or 'Laptop HP #01')
    room_name = db.Column(db.String(150), nullable=False)
    # This stores Key ID OR Asset Serial Number (e.g., 'K101' or 'LAP-HP-001')
    key_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), default='Available') # Available, Borrowed
    # Optional: Only used if type == 'Key'
    level = db.Column(db.String(50), nullable=True) 

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    key_id = db.Column(db.Integer, db.ForeignKey('key.id'), nullable=False)
    request_date = db.Column(db.DateTime, default=datetime.utcnow) 
    status = db.Column(db.String(20), default='pending') # pending, active, completed
    duration_hours = db.Column(db.Integer, default=4) 
    
    user = db.relationship('User', backref='bookings')
    key = db.relationship('Key', backref='bookings')

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    key_id = db.Column(db.Integer, db.ForeignKey('key.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False) # e.g., 'Picked Up (4h)', 'Returned'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('logs', lazy=True))
    key = db.relationship('Key', backref=db.backref('logs', lazy=True))