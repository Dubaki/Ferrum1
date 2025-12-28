import aiohttp
from core.config import settings

async def send_to_1c(data: dict):
    # Если URL не задан, возвращаем успех (режим отладки)
    if not settings.ONEC_URL:
        return {"success": True, "debug": "1C URL not set"}

    async with aiohttp.ClientSession() as session:
        auth = aiohttp.BasicAuth(settings.ONEC_AUTH_USER, settings.ONEC_AUTH_PASS)
        try:
            async with session.post(settings.ONEC_URL, json=data, auth=auth) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}