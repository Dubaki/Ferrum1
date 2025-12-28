import google.generativeai as genai
import os
from dotenv import load_dotenv

# Загружаем ключ из .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ Ошибка: GOOGLE_API_KEY не найден в .env")
else:
    genai.configure(api_key=api_key)
    print(f"🔍 Проверяем доступные модели для ключа: {api_key[:5]}...")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ Доступна: {m.name}")
    except Exception as e:
        print(f"❌ Ошибка при получении списка: {e}")