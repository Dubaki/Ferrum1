from fastapi import FastAPI, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types, F
import os
from aiogram.types import WebAppInfo
from services.ocr import recognize_invoice
from services.onec import send_to_1c
from core.config import settings
import json

app = FastAPI()
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# --- БЕЗОПАСНОСТЬ ---
# Формируем секретный путь. Теперь URL будет выглядеть так:
# https://ваш-проект.vercel.app/api/webhook/lkh45lk54lddksn
WEBHOOK_PATH = f"/api/webhook/{settings.WEBHOOK_SECRET}"

# --- ЛОГИКА БОТА ---
@dp.message(F.command == "start")
async def cmd_start(message: types.Message):
    # Ссылка на Web App (на Vercel)
    # Vercel раздает статику из папки public, поэтому index.html доступен по корню или по имени
    web_app_url = f"{settings.BASE_URL}/index.html"
    
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📱 Скан Накладной", web_app=WebAppInfo(url=web_app_url))]],
        resize_keyboard=True
    )
    await message.answer("Привет! Нажми кнопку для сканирования накладной.", reply_markup=kb)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    # Получаем JSON от Web App
    try:
        data = json.loads(message.web_app_data.data)
        await message.answer("⏳ Данные получены, отправляю в 1С...")
        
        # Интеграция с 1С
        result = await send_to_1c(data)
        
        if result.get("success"):
            # Если 1С вернула успех
            doc_num = result.get('doc_number', 'б/н')
            await message.answer(f"✅ Документ создан в 1С!\nНомер: {doc_num}")
        else:
            # Если ошибка (или 1С недоступна)
            err = result.get('error', 'Неизвестная ошибка')
            await message.answer(f"❌ Ошибка 1С: {err}")
            
    except Exception as e:
        await message.answer(f"Ошибка чтения данных: {e}")

# --- API ЭНДПОИНТЫ ---

# 1. ЗАЩИЩЕННЫЙ ВЕБХУК
# Telegram будет стучаться именно сюда. Посторонние этот адрес не знают.
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 2. СКАНЕР (Фронтенд шлет сюда фото)
@app.post("/api/scan")
async def scan_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    result = await recognize_invoice(content)
    return result

# 3. УСТАНОВКА ВЕБХУКА (Технический эндпоинт)
# Вызовите его один раз в браузере после деплоя, чтобы сказать Телеграму новый адрес
@app.get("/api/set_webhook")
async def set_webhook():
    webhook_url = f"{settings.BASE_URL}{WEBHOOK_PATH}"
    
    # Метод API Telegram: setWebhook
    await bot.set_webhook(webhook_url)
    
    return {
        "status": "webhook set successfully", 
        "url": webhook_url
    }

# --- ЛОКАЛЬНЫЙ ЗАПУСК ---
# Если папка public существует, раздаем её содержимое (для локальных тестов)
if os.path.exists("public"):
    app.mount("/", StaticFiles(directory="public", html=True), name="static")