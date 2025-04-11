import json
import requests
from pathlib import Path
from openai import OpenAI

# Initialize the DeepSeek client
client = OpenAI(api_key="sk-c1025eafaea049909360bb3ef9add2a9",
                base_url="https://api.deepseek.com")

# Load tools from JSON file
tools_file = Path("function_schemas.json")
try:
    with tools_file.open("r", encoding="utf-8") as f:
        raw_tools = json.load(f)
    # Wrap tools in DeepSeek format
    tools = [{"type": "function", "function": tool} for tool in raw_tools]
except FileNotFoundError:
    print(f"Lỗi: Không tìm thấy {tools_file}.")
    exit(1)
except json.JSONDecodeError:
    print(f"Lỗi: {tools_file} chứa JSON không hợp lệ.")
    exit(1)

# Load prompt from Markdown file
prompt_file = Path("prompt_grok.md")
try:
    with prompt_file.open("r", encoding="utf-8") as f:
        system_prompt = f.read()
except FileNotFoundError:
    print(f"Lỗi: Không tìm thấy {prompt_file}.")
    exit(1)
except UnicodeDecodeError:
    print(f"Lỗi: Không thể giải mã {prompt_file} dưới dạng UTF-8.")
    exit(1)


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


# Define the conversation
messages = [
    {
        "role": "system",
        "content": system_prompt
    },
    {
        "role": "user",
        "content": "Xóa gói SM25K"
        # "Gói nào đắt nhất trong danh sách các gói cước của công ty?"
    }
]

# Process function calls iteratively
max_iterations = 10  # Prevent infinite loops
iteration = 0

while iteration < max_iterations:
    # Call DeepSeek
    try:
        response = client.chat.completions.create(model="deepseek-chat",
                                                  messages=messages,
                                                  tools=tools)
        print("response from deepseek: ", response)
    except Exception as e:
        print(f"Lỗi: Không thể gọi API DeepSeek: {str(e)}")
        exit(1)

    # Get the response message
    message = response.choices[0].message
    messages.append(message)

    # Check for tool calls
    if not hasattr(message, "tool_calls") or not message.tool_calls:
        # No tool calls, this is the final response
        print("Phản hồi:", message.content)
        break

    # Process each tool call
    for tool_call in message.tool_calls:
        function_name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            print("Lỗi: Đối số tool call không hợp lệ.")
            exit(1)

        query = arguments.get("query")
        if not query:
            print("Lỗi: Thiếu tham số query.")
            exit(1)

        # Handle functions separately
        if function_name == "run_sql_query":
            if "SELECT" not in query.upper():
                print("Lỗi: run_sql_query chỉ dùng cho câu SELECT.")
                exit(1)

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
                print(
                    "Lỗi: run_sql_mutation chỉ dùng cho câu INSERT, UPDATE, DELETE."
                )
                exit(1)

            result = call_sql_api(query)
            result_str = json.dumps(result)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str
            })

        else:
            print(f"Lỗi: Hàm không xác định: {function_name}.")
            exit(1)

    iteration += 1

if iteration >= max_iterations:
    print("Lỗi: Đạt giới hạn số lần gọi hàm. Có thể có vòng lặp vô hạn.")
