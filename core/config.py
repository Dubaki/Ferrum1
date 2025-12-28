import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "test-secret")
    # Vercel автоматически добавляет https://, но проверим
    BASE_URL = os.getenv("VERCEL_URL")
    
    # 1C Config
    ONEC_URL = os.getenv("ONEC_URL")
    ONEC_AUTH_USER = os.getenv("ONEC_AUTH_USER")
    ONEC_AUTH_PASS = os.getenv("ONEC_AUTH_PASS")

settings = Config()