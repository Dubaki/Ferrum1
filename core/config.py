import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

class Config:
    # Telegram
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my-secret-token")
    BASE_URL = os.getenv("VERCEL_URL")
    
    # AI (OpenRouter)
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    
    # 1C Integration
    ONEC_URL = os.getenv("ONEC_URL")
    ONEC_AUTH_USER = os.getenv("ONEC_AUTH_USER")
    ONEC_AUTH_PASS = os.getenv("ONEC_AUTH_PASS")

settings = Config()