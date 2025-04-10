import httpx

REACT_BACKEND_URL = "https://vandertyson-restlesstre-xnr399i6hhz.ws-us118.gitpod.io/api"

async def get_package_policy(package_name: str):
    url = f"{REACT_BACKEND_URL}/packages/{package_name}/policy"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            return response.text
        return f"Không tìm thấy gói {package_name}"
