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
    timeout=45.0, # Увеличиваем тайм-аут (Vercel может ждать дольше)
    max_retries=1, # Один повтор на уровне библиотеки
)

# СПИСОК МОДЕЛЕЙ (Failover)
# Если первая модель недоступна или выдает ошибку, бот попробует следующую.
MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.0-flash-lite-preview-02-05:free",
    "google/gemini-2.0-pro-exp-02-05:free",
    "qwen/qwen-2.5-vl-72b-instruct:free"
]

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

        last_error = None

        # 2. Перебираем модели, пока одна не сработает
        for model_id in MODELS:
            print(f"DEBUG: Пробуем модель: {model_id}")
            try:
                response = await client.chat.completions.create(
                    model=model_id,
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
                print(f"DEBUG: Ответ получен от {model_id}")
                
                # 4. Очистка от Markdown
                cleaned_content = content
                if "```json" in content:
                    cleaned_content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    cleaned_content = content.split("```")[1].split("```")[0]
                    
                return json.loads(cleaned_content.strip())

            except Exception as e:
                print(f"⚠️ Ошибка модели {model_id}: {e}")
                last_error = e
                continue # Пробуем следующую модель
        
        # Если ни одна модель не сработала
        raise last_error if last_error else Exception("Все модели недоступны")

    except Exception as e:
        print(f"CRITICAL ERROR OCR: {e}")
        # Возвращаем пустую структуру, чтобы фронтенд не падал
        return {"error": str(e), "Items": []}