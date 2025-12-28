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

async def recognize_invoice(image_bytes: bytes) -> dict:
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
    
    try:
        response = model.generate_content([
            {'mime_type': 'image/jpeg', 'data': image_bytes},
            prompt
        ])
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e), "Items": []}