import httpx
import json

DEEPSEEK_API_KEY = "sk-c1025eafaea049909360bb3ef9add2a9"
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

with open("function_schemas.json") as f:
    FUNCTION_SCHEMAS = json.load(f)


async def call_deepseek(messages):
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "functions": FUNCTION_SCHEMAS,
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]
