"""
Bot configuration settings
"""
import os
from pathlib import Path
from decouple import config as decouple_config


def load_env():
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent.parent.parent / '.env'
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)


class Settings:
    """Bot settings"""
    
    # Telegram Bot
    BOT_TOKEN = decouple_config('BOT_TOKEN', default='')
    
    # Django Database
    DB_NAME = decouple_config('DB_NAME', default='db.sqlite3')
    DB_PATH = decouple_config('DB_PATH', default='../db.sqlite3')
    
    # Logging
    LOG_LEVEL = decouple_config('LOG_LEVEL', default='INFO')
    
    # PDF Settings
    PDF_TEMP_DIR = Path(__file__).parent.parent.parent / 'temp_pdfs'
    
    def __init__(self):
        """Validate settings on initialization"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set in environment variables")
        
        # Create temp directory if it doesn't exist
        self.PDF_TEMP_DIR.mkdir(exist_ok=True)


def get_settings() -> Settings:
    """Get bot settings instance"""
    return Settings()
