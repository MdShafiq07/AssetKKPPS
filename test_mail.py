from app import app, mail, Message

with app.app_context():
    msg = Message("Test Email", recipients=["cryxalizgaming@gmail.com"])
    msg.body = "If you see this, your .env settings are 100% correct!"
    try:
        mail.send(msg)
        print("✅ Success! Check your inbox.")
    except Exception as e:
        print(f"❌ Failed! Error: {e}")