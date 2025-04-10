from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Dict, Any

from deepseek_client import call_deepseek
from function_router import handle_function_call

app = FastAPI()


class ChatPayload(BaseModel):
    messages: List[Dict[str, str]]


@app.post("/chat")
async def chat(payload: ChatPayload):
    messages = payload.messages

    # Lần 1: gửi cho DeepSeek để xem có function_call không
    response = await call_deepseek(messages)

    if "function_call" in response["message"]:
        func_call = response["message"]["function_call"]
        result = await handle_function_call(func_call)

        # Append result từ function vào messages
        messages.append({
            "role": "function",
            "name": func_call["name"],
            "content": result
        })

        # Gọi lại DeepSeek để lấy phản hồi cuối
        final_response = await call_deepseek(messages)
        return {"reply": final_response["message"]["content"]}

    else:
        return {"reply": response["message"]["content"]}
