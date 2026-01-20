from app import app, db
from models import User

with app.app_context():
    # Replace 'Shafiq' with the EXACT username you just registered
    user = User.query.filter_by(username='Shafiq').first()
    
    if user:
        user.role = 'admin'
        user.is_approved = True
        db.session.commit()
        print(f"✅ SUCCESS: {user.username} is now an Approved Admin!")
    else:
        print("❌ ERROR: User not found. Make sure you registered the name correctly.")