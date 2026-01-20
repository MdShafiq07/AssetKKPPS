import os
from dotenv import load_dotenv

# 1. Load the secrets from the .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'default-secret-key'

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # --- RENDER DEPLOYMENT FIX ---
    # Render provides 'postgres://' but SQLAlchemy needs 'postgresql://'
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = database_url or \
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'key_app.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Updated Email Configuration with defaults
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT') or 587)
    # This logic ensures it is True only if the .env says 'True'
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    # Add this to help avoid "Sender" errors
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_USERNAME')