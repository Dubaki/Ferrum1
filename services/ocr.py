import google.generativeai as genai
import json
from core.config import settings

# Настройка API
genai.configure(api_key=settings.GOOGLE_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config={
        "temperature": 0.1,
        "response_mime_type": "application/json"
    }
)

async def recognize_invoice(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    prompt = """
    Проанализируй изображение накладной (УПД, ТОРГ-12).
    Извлеки данные в JSON формате:
    {
        "SupplierINN": "ИНН продавца (только цифры)",
        "DocNumber": "Номер документа",
        "DocDate": "Дата (ДД.ММ.ГГГГ)",
        "Items": [
            {
                "ItemName": "Название товара",
                "ItemArticle": "Артикул (если есть)",
                "Quantity": число,
                "Price": число,
                "Total": число
            }
        ]
    }
    """
    
    if not mime_type:
        mime_type = "image/jpeg"

    try:
        response = await model.generate_content_async([
            {'mime_type': mime_type, 'data': image_bytes},
            prompt
        ])
        return json.loads(response.text)
    except Exception as e:
        print(f"OCR Error: {e}")
        return {"error": str(e), "Items": []}