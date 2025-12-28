from fastapi import FastAPI, Request, UploadFile, File
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import WebAppInfo
from services.ocr import recognize_invoice
from services.onec import send_to_1c
from core.config import settings
import json

app = FastAPI()
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# --- Логика Бота ---
@dp.message(F.command == "start")
async def cmd_start(message: types.Message):
    # Ссылка на Web App (на Vercel)
    web_app_url = f"{settings.BASE_URL}/index.html"
    
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📱 Скан Накладной", web_app=WebAppInfo(url=web_app_url))]],
        resize_keyboard=True
    )
    await message.answer("Привет! Нажми кнопку для сканирования накладной.", reply_markup=kb)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    # Получаем JSON от Web App и отправляем в 1С
    data = json.loads(message.web_app_data.data)
    await message.answer("⏳ Данные получены, отправляю в 1С...")
    
    # Интеграция с 1С
    result = await send_to_1c(data)
    
    if result.get("success"):
        await message.answer(f"✅ Документ создан! Номер: {result.get('doc_number', 'NEW')}")
    else:
        await message.answer(f"❌ Ошибка 1С: {result.get('error', 'Unknown')}")

# --- API Эндпоинты ---

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """Принимает обновления от Telegram"""
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/scan")
async def scan_endpoint(file: UploadFile = File(...)):
    """Принимает фото с фронтенда и шлет в Gemini"""
    content = await file.read()
    result = await recognize_invoice(content)
    return result

# Эндпоинт для установки вебхука (запустить один раз вручную в браузере)
@app.get("/api/set_webhook")
async def set_webhook():
    webhook_url = f"{settings.BASE_URL}/api/webhook"
    await bot.set_webhook(webhook_url)
    return {"webhook_url": webhook_url, "status": "set"}