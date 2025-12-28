from google import genai
from google.genai import types
import json
import asyncio
from core.config import settings

# Настройка API
client = genai.Client(api_key=settings.GOOGLE_API_KEY)

async def recognize_invoice(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    prompt = """
    Проанализируй изображение документа (Накладная, УПД, ТОРГ-12, Счет на оплату, Чек).
    Извлеки данные в строгом JSON формате. Соблюдай регистр ключей (PascalCase).

    ВАЖНО ПРО ЧИСЛА: В русских документах запятая (например "1,000" или "5,5") — это десятичный разделитель.
    Преобразуй их в формат JSON с точкой (например 1.0 или 5.5).
    Не путай с разделителем тысяч! "1,000" в графе количество — это число 1 (один), а не 1000.

    Структура:
    {
        "SupplierINN": "ИНН продавца (только цифры)",
        "DocNumber": "Номер документа",
        "DocDate": "Дата (ДД.ММ.ГГГГ)",
        "Items": [
            {
                "ItemName": "Название товара",
                "ItemArticle": "Артикул (или пустая строка)",
                "Quantity": число (float),
                "Price": число (float),
                "Total": число (float)
            }
        ]
    }
    """
    
    if not mime_type:
        mime_type = "image/jpeg"

    # Конфигурация генерации
    config = types.GenerateContentConfig(
        temperature=0.1
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model="gemini-1.5-flash",
                contents=[
                    types.Content(parts=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), types.Part.from_text(text=prompt)])
                ],
                config=config
            )
            
            text = response.text
            print(f"Gemini Raw Response: {text}") # Лог в терминал для отладки

            # Очищаем от markdown-обертки, если она есть
            text = text.replace("```json", "").replace("```", "").strip()
            
            return json.loads(text)
        except Exception as e:
            print(f"OCR Error (Attempt {attempt+1}): {e}")
            
            # ЕСЛИ ОШИБКА 429 (Quota) - ЖДЕМ И ПОВТОРЯЕМ
            if "429" in str(e) or "quota" in str(e).lower():
                if attempt < max_retries - 1:
                    wait_time = 2 # Уменьшаем время ожидания, чтобы уложиться в лимит Vercel
                    print(f"⏳ Превышен лимит квот. Ждем {wait_time} сек...")
                    await asyncio.sleep(wait_time)
                    continue

            # ЕСЛИ ОШИБКА 404 - ВЫВОДИМ СПИСОК ДОСТУПНЫХ МОДЕЛЕЙ В ЛОГ
            return {"error": str(e), "Items": []}