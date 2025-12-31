import json
import base64
import io
from PIL import Image
from openai import AsyncOpenAI
from core.config import settings

# --- КОНФИГУРАЦИЯ ---
# Мы используем клиент OpenAI, но меняем адрес (base_url) на OpenRouter
client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# ВЫБОР МОДЕЛИ
# Qwen-2.5-VL-72B - мощнейшая модель для зрения.
# :free в конце означает, что мы пробуем бесплатный шлюз. 
# Если будет глючить, уберите ":free", это будет стоить копейки ($0.00... за запрос).
MODEL_ID = "google/gemini-2.0-flash-exp:free"

def resize_image(image_bytes: bytes, max_size=(1024, 1024)) -> bytes:
    """Сжимает изображение до разумных размеров перед отправкой в AI"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Конвертируем в RGB, если это RGBA (чтобы сохранить в JPEG)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        image.thumbnail(max_size)
        
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=85)
        return output.getvalue()
    except Exception as e:
        print(f"Resize Error: {e}")
        return image_bytes

async def recognize_invoice(image_bytes: bytes) -> dict:
    print(f"DEBUG: Запуск OCR через OpenRouter. Модель: {MODEL_ID}")
    
    try:
        # 1. Сжимаем и кодируем картинку в Base64
        optimized_bytes = resize_image(image_bytes)
        base64_image = base64.b64encode(optimized_bytes).decode('utf-8')
        
        prompt = """
        Ты профессиональный бухгалтер. Твоя задача - извлечь данные из фотографии документа (УПД, Накладная, Счет).
        
        Верни СТРОГО валидный JSON (без Markdown разметки, просто текст JSON) следующей структуры:
        {
            "SupplierINN": "строка (только цифры ИНН поставщика, если не нашел - пустая строка)",
            "DocNumber": "строка (номер документа)",
            "DocDate": "строка (дата в формате ДД.ММ.ГГГГ)",
            "Items": [
                {
                    "ItemName": "строка (название товара)",
                    "Quantity": число (float),
                    "Price": число (float),
                    "Total": число (float)
                }
            ]
        }
        """

        # 2. Отправляем запрос
        response = await client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            # Эти заголовки требуют правила OpenRouter
            extra_headers={
                "HTTP-Referer": "https://telegram-bot.com", 
                "X-Title": "Invoice Scanner Bot",
            },
            temperature=0.1, # Минимальная креативность для точности
        )

        # 3. Получаем ответ
        content = response.choices[0].message.content
        print("DEBUG: Ответ получен от AI")
        
        # 4. Очистка от Markdown (иногда модель пишет ```json ... ```)
        cleaned_content = content
        if "```json" in content:
            cleaned_content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            cleaned_content = content.split("```")[1].split("```")[0]
            
        return json.loads(cleaned_content.strip())

    except Exception as e:
        print(f"CRITICAL ERROR OCR: {e}")
        # Возвращаем пустую структуру, чтобы фронтенд не падал
        return {"error": str(e), "Items": []}