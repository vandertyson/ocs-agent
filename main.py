import json
import requests
import uuid
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from typing import Dict, List
import uvicorn

app = FastAPI()

# Enable CORS (cho WebSocket handshake trên Replit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả vì Replit dùng domain động
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo DeepSeek client
client = OpenAI(
    api_key="your-deepseek-api-key-here",  # Thay bằng API key của bạn
    base_url="https://api.deepseek.com")

# Load tools từ JSON
tools_file = Path("function_schemas.json")
try:
    with tools_file.open("r", encoding="utf-8") as f:
        raw_tools = json.load(f)
    tools = [{"type": "function", "function": tool} for tool in raw_tools]
except FileNotFoundError:
    raise Exception(f"Lỗi: Không tìm thấy {tools_file}.")
except json.JSONDecodeError:
    raise Exception(f"Lỗi: {tools_file} chứa JSON không hợp lệ.")

# Load prompt từ Markdown
prompt_file = Path("prompt.md")
try:
    with prompt_file.open("r", encoding="utf-8") as f:
        system_prompt = f.read()
except FileNotFoundError:
    raise Exception(f"Lỗi: Không tìm thấy {prompt_file}.")
except UnicodeDecodeError:
    raise Exception(f"Lỗi: Không thể giải mã {prompt_file} dưới dạng UTF-8.")

# In-memory conversation store và trạng thái xử lý
conversations: Dict[str, List[Dict]] = {}
processing: Dict[str, bool] = {}


# Function to call remote API (mocked for demo)
def call_sql_api(query):
    # Mock response for demo (replace with actual API call)
    upper = query.upper()
    url = ""
    if "SELECT" in upper:
        url = "https://34ee5145-restless-tree-1740.ptson117.workers.dev/api/sql/query"
    elif "INSERT" in upper or "UPDATE" in upper or "DELETE" in upper:
        url = "https://34ee5145-restless-tree-1740.ptson117.workers.dev/api/sql/mutate"

    try:
        headers = {
            "Content-Type": "application/json",
        }
        payload = {"query": query}
        response = requests.post(url,
                                 json=payload,
                                 headers=headers,
                                 timeout=10)
        print("response from backend: ", response.json())
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": f"api call error: {str(e)}"}


# WebSocket endpoint xử lý tin nhắn và đẩy progress/response
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    conversation_id = str(uuid.uuid4())

    conversations[conversation_id] = [{
        "role": "system",
        "content": system_prompt
    }]
    processing[conversation_id] = False

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message")
            if not message:
                await websocket.send_json(
                    {"error": "Không có nội dung tin nhắn."})
                continue

            if processing[conversation_id]:
                await websocket.send_json(
                    {"error": "Đang xử lý tin nhắn trước đó, vui lòng đợi."})
                continue

            processing[conversation_id] = True
            messages = conversations[conversation_id]
            messages.append({"role": "user", "content": message})
            await websocket.send_json({"progress": f"Bạn: {message}"})

            max_iterations = 10
            iteration = 0

            while iteration < max_iterations:
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat", messages=messages, tools=tools)
                except Exception as e:
                    await websocket.send_json(
                        {"error": f"Lỗi DeepSeek API: {str(e)}"})
                    break

                message_response = response.choices[0].message
                messages.append(message_response)

                if not hasattr(
                        message_response,
                        "tool_calls") or not message_response.tool_calls:
                    await websocket.send_json(
                        {"response": message_response.content})
                    break

                for tool_call in message_response.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        await websocket.send_json(
                            {"error": "Lỗi: Đối số tool call không hợp lệ."})
                        break

                    query = arguments.get("query")
                    if not query:
                        await websocket.send_json(
                            {"error": "Lỗi: Thiếu tham số query."})
                        break

                    description = message_response.content or (
                        "Đang truy vấn thông tin..." if function_name
                        == "run_sql_query" else "Đang cập nhật dữ liệu...")
                    await websocket.send_json({"progress": description})

                    if function_name == "run_sql_query":
                        if "SELECT" not in query.upper():
                            await websocket.send_json({
                                "error":
                                "Lỗi: run_sql_query chỉ dùng cho câu SELECT."
                            })
                            break

                        result = call_sql_api(query)
                        result_str = json.dumps(result)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_str
                        })

                    elif function_name == "run_sql_mutation":
                        if not any(op in query.upper()
                                   for op in ["INSERT", "UPDATE", "DELETE"]):
                            await websocket.send_json({
                                "error":
                                "Lỗi: run_sql_mutation chỉ dùng cho INSERT, UPDATE, DELETE."
                            })
                            break

                        result = call_sql_api(query)
                        result_str = json.dumps(result)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_str
                        })

                    else:
                        await websocket.send_json({
                            "error":
                            f"Lỗi: Hàm không xác định: {function_name}"
                        })
                        break

                iteration += 1

            if iteration >= max_iterations:
                await websocket.send_json(
                    {"error": "Lỗi: Đạt giới hạn số lần gọi hàm."})

            processing[conversation_id] = False

    except WebSocketDisconnect:
        if conversation_id in conversations:
            del conversations[conversation_id]
        if conversation_id in processing:
            del processing[conversation_id]


if __name__ == "__main__":
    # Replit yêu cầu chạy trên port 80
    uvicorn.run("main:app", host="0.0.0.0", port=80)
