import asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app

async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/v1/agents", json={"name": "X", "runtime": "test"})
        print("POST", r.status_code, r.json())
        r2 = await ac.get("/v1/agents")
        print("GET", r2.status_code, r2.json())

asyncio.run(main())
