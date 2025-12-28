import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "test-secret")
    
    # Vercel отдает URL без протокола, добавляем https://
    _vercel_url = os.getenv("VERCEL_URL")
    if _vercel_url:
        BASE_URL = f"https://{_vercel_url}" if not _vercel_url.startswith("http") else _vercel_url
    else:
        BASE_URL = "https://your-project.vercel.app"
    
    # 1C Config
    ONEC_URL = os.getenv("ONEC_URL")
    ONEC_AUTH_USER = os.getenv("ONEC_AUTH_USER")
    ONEC_AUTH_PASS = os.getenv("ONEC_AUTH_PASS")

settings = Config()