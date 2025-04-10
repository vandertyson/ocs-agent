import json
from react_api_client import get_package_policy

async def handle_function_call(func_call):
    name = func_call["name"]
    args = json.loads(func_call["arguments"])

    if name == "get_package_policy":
        return await get_package_policy(args["package_name"])
    else:
        return "Function not implemented."
