import json
import base64
import io
from openai import AsyncOpenAI
from core.config import settings
from pdf2image import convert_from_bytes
from PIL import Image

# Настройка клиента OpenRouter
client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# Модель Google Gemini 2.0 Flash - актуальная модель с vision
MODEL_ID = "google/gemini-2.0-flash-001"

async def recognize_invoice(file_bytes: bytes, is_pdf: bool = False) -> dict:
    print(f"DEBUG: Запуск OCR. Модель: {MODEL_ID}, PDF: {is_pdf}")

    try:
        # Если PDF - конвертируем все страницы в изображения
        if is_pdf:
            print("DEBUG: Конвертирую PDF в изображения...")
            images = convert_from_bytes(file_bytes, dpi=200)
            print(f"DEBUG: PDF содержит {len(images)} страниц(ы)")

            all_items = []
            doc_info = {}

            # Обрабатываем каждую страницу
            for page_num, image in enumerate(images, 1):
                print(f"DEBUG: Обрабатываю страницу {page_num}/{len(images)}")

                # Конвертируем PIL Image в bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG', quality=85)
                img_bytes = img_byte_arr.getvalue()

                # Распознаём страницу
                page_result = await recognize_single_image(img_bytes)

                # Собираем информацию
                if page_num == 1:
                    # Берём ИНН, номер, дату с первой страницы
                    doc_info = {
                        "SupplierINN": page_result.get("SupplierINN", ""),
                        "DocNumber": page_result.get("DocNumber", ""),
                        "DocDate": page_result.get("DocDate", "")
                    }

                # Собираем товары со всех страниц
                if page_result.get("Items"):
                    all_items.extend(page_result["Items"])

            # Объединяем результаты
            result = doc_info
            result["Items"] = all_items
            result["TotalSum"] = round(sum(item.get("Total", 0) for item in all_items), 2)

            print(f"DEBUG: Всего распознано товаров: {len(all_items)}")
            return result

        else:
            # Обычное изображение
            return await recognize_single_image(file_bytes)

    except Exception as e:
        print(f"CRITICAL ERROR OCR: {e}")
        return {"error": str(e), "Items": []}


async def recognize_single_image(image_bytes: bytes) -> dict:
    """Распознавание одного изображения"""
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