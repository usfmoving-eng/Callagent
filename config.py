"""
Configuration management for USF Moving Company AI Agent
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'usf-moving-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
    PORT = int(os.getenv('PORT', 5000))
    
    # Company Information
    COMPANY_NAME = os.getenv('COMPANY_NAME', 'USF Moving Company')
    COMPANY_PHONE = os.getenv('COMPANY_PHONE', '(281) 743-4503')
    OFFICE_ADDRESS = os.getenv('OFFICE_ADDRESS', '2800 Rolido Dr Apt 238, Houston, TX 77063')
    WEBSITE = os.getenv('WEBSITE', 'https://www.usfhoustonmoving.com/')
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    
    # Google APIs
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    GOOGLE_SHEETS_CREDS = os.getenv('GOOGLE_SHEETS_CREDS')
    BOOKING_SHEET_ID = os.getenv('BOOKING_SHEET_ID')
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Email Configuration
    EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    
    # Pricing Configuration
    MILEAGE_FREE_RADIUS = int(os.getenv('MILEAGE_FREE_RADIUS', 20))
    MILEAGE_RATE = float(os.getenv('MILEAGE_RATE', 1.0))
    LONG_DISTANCE_PHONE = os.getenv('LONG_DISTANCE_PHONE', '(281) 743-4503')
    
    # Feature Flags
    ENABLE_CALL_RECORDING = os.getenv('ENABLE_CALL_RECORDING', 'True') == 'True'
    ENABLE_OUTBOUND_CALLS = os.getenv('ENABLE_OUTBOUND_CALLS', 'True') == 'True'
    ENABLE_SMS_NOTIFICATIONS = os.getenv('ENABLE_SMS_NOTIFICATIONS', 'True') == 'True'
    ENABLE_EMAIL_NOTIFICATIONS = os.getenv('ENABLE_EMAIL_NOTIFICATIONS', 'True') == 'True'
    ENABLE_BACKLINK_AUTOMATION = os.getenv('ENABLE_BACKLINK_AUTOMATION', 'False') == 'True'
    
    # Voice Settings
    VOICE_GENDER = os.getenv('VOICE_GENDER', 'female')
    VOICE_NAME = os.getenv('VOICE_NAME', 'Polly.Joanna')
    
    # Rate Limiting
    MAX_OUTBOUND_CALLS_PER_DAY = int(os.getenv('MAX_OUTBOUND_CALLS_PER_DAY', 50))
    MAX_BACKLINK_EMAILS_PER_DAY = int(os.getenv('MAX_BACKLINK_EMAILS_PER_DAY', 5))
    
    # Application Configuration
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
    
    @staticmethod
    def validate_config():
        """Validate that all required configuration is present"""
        required_vars = [
            'TWILIO_ACCOUNT_SID',
            'TWILIO_AUTH_TOKEN',
            'TWILIO_PHONE_NUMBER',
            'GOOGLE_MAPS_API_KEY',
            'GOOGLE_SHEETS_CREDS',
            'BOOKING_SHEET_ID'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """Get configuration based on environment"""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])