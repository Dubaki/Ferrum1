import json
import base64
from openai import AsyncOpenAI
from core.config import settings

# Настройка клиента OpenRouter
client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# Модель Qwen 2.5 VL - лучшая для таблиц и русского языка
MODEL_ID = "qwen/qwen-2.5-vl-72b-instruct:free"

async def recognize_invoice(image_bytes: bytes) -> dict:
    print(f"DEBUG: Запуск OCR. Модель: {MODEL_ID}")
    
    try:
        # Кодируем картинку в base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        prompt = """
        Ты профессиональный бухгалтер-оператор. Твоя задача - извлечь данные из скана накладной (УПД, ТОРГ-12) для импорта в 1С.
        
        Инструкции:
        1. Найди ИНН продавца (SupplierINN).
        2. Найди итоговую сумму документа с НДС (TotalSum).
        3. Для каждой строки товара найди:
           - Артикул или Код товара (ItemArticle). Если его нет, оставь пустую строку.
           - Наименование (ItemName).
           - Количество (Quantity).
           - Цену (Price).
           - Сумму (Total).
        
        Верни данные СТРОГО в формате JSON без Markdown разметки:
        {
            "SupplierINN": "строка (только цифры)",
            "DocNumber": "строка",
            "DocDate": "строка (ДД.ММ.ГГГГ)",
            "TotalSum": число (float),
            "Items": [
                {
                    "ItemName": "строка",
                    "ItemArticle": "строка",
                    "Quantity": число,
                    "Price": число,
                    "Total": число
                }
            ]
        }
        """

        response = await client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            extra_headers={
                "HTTP-Referer": "https://telegram-bot-app.com", 
                "X-Title": "1C Invoice Scanner",
            },
            temperature=0.1,
        )

        content = response.choices[0].message.content
        print("DEBUG: Ответ получен")

        # Очистка JSON от возможных markdown-тегов
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        # Парсинг JSON
        result = json.loads(content.strip())

        # Валидация и нормализация данных (защита от некорректных данных AI)
        if "Items" in result and isinstance(result["Items"], list):
            validated_items = []
            for item in result["Items"]:
                # Нормализуем данные товара
                normalized_item = {
                    "ItemArticle": str(item.get("ItemArticle") or item.get("itemArticle") or item.get("article") or ""),
                    "ItemName": str(item.get("ItemName") or item.get("itemName") or item.get("name") or "Товар"),
                    "Quantity": max(0.001, float(item.get("Quantity") or item.get("quantity") or item.get("qty") or 1)),
                    "Price": max(0, float(item.get("Price") or item.get("price") or 0)),
                }
                # Вычисляем Total с округлением
                normalized_item["Total"] = round(normalized_item["Quantity"] * normalized_item["Price"], 2)
                validated_items.append(normalized_item)

            result["Items"] = validated_items

            # Вычисляем общую сумму, если её нет
            if "TotalSum" not in result or not result["TotalSum"]:
                result["TotalSum"] = round(sum(item["Total"] for item in validated_items), 2)

        print(f"DEBUG: Распознано товаров: {len(result.get('Items', []))}")
        return result

    except Exception as e:
        print(f"CRITICAL ERROR OCR: {e}")
        return {"error": str(e), "Items": []}