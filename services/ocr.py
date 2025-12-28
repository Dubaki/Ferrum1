import google.generativeai as genai
import json
import asyncio
from core.config import settings

# Настройка API
genai.configure(api_key=settings.GOOGLE_API_KEY)

_active_model = None

def get_model():
    """
    Автоматически выбирает доступную модель, чтобы не гадать названия.
    """
    global _active_model
    if _active_model:
        return _active_model

    target_name = "models/gemini-1.5-flash" # Запасной вариант
    try:
        print("🔍 Запрашиваем у Google список доступных моделей...")
        # Получаем список моделей, которые умеют генерировать контент
        models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        names = [m.name for m in models]
        print(f"📋 Доступно: {names}")

        # ПРИОРИТЕТ: Ищем легкие модели (Flash), у них выше лимиты на бесплатном тарифе
        priority_list = [
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-001",
            "models/gemini-1.5-flash-002",
            "models/gemini-1.5-flash-8b",
        ]

        # Проверяем по списку приоритетов
        for p in priority_list:
            if p in names:
                target_name = p
                break
        else:
            # Если Flash не нашли, ищем любую с 'flash' в названии
            for n in names:
                if "flash" in n.lower():
                    target_name = n
                    break
            else:
                # Если совсем ничего нет, берем последнюю (как крайняя мера)
                if models:
                    target_name = models[-1].name
            
    except Exception as e:
        print(f"⚠️ Ошибка получения списка моделей: {e}")

    print(f"✅ Выбрана модель: {target_name}")
    _active_model = genai.GenerativeModel(
        model_name=target_name,
        generation_config={"temperature": 0.1}
    )
    return _active_model

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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            model_instance = get_model()
            response = await model_instance.generate_content_async([
                {'mime_type': mime_type, 'data': image_bytes},
                prompt
            ])
            
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
                    wait_time = 10 * (attempt + 1)
                    print(f"⏳ Превышен лимит квот. Ждем {wait_time} сек...")
                    await asyncio.sleep(wait_time)
                    continue

            # ЕСЛИ ОШИБКА 404 - ВЫВОДИМ СПИСОК ДОСТУПНЫХ МОДЕЛЕЙ В ЛОГ
            if "404" in str(e) or "not found" in str(e).lower():
                print("⚠️ Модель не найдена. Список доступных моделей:")
                try:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            print(f" - {m.name}")
                except Exception as list_err:
                    print(f"Не удалось получить список моделей: {list_err}")
                    
            return {"error": str(e), "Items": []}