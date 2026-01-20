from app import app, db
from models import Key

# Create the application context so we can talk to the DB
with app.app_context():
    # 1. Create the tables based on models.py
    db.create_all()
    
    # 2. Check if the test key exists
    existing_key = Key.query.filter_by(key_number='00000').first()
    
    if not existing_key:
        # Create the new key with the required 'level' field
        new_key = Key(
            room_name='Test Room', 
            key_number='00000', 
            status='Available', 
            level='Aras 1'
        )
        db.session.add(new_key)
        db.session.commit()
        print("✅ SUCCESS: Key 00000 for 'Test Room' created!")
    else:
        print("ℹ️ NOTE: Key 00000 already exists.")

    # 3. Print all keys to be sure
    all_keys = Key.query.all()
    print(f"Current Keys in Database: {all_keys}")