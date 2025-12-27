# scripts/debug_request.py
import asyncio
from httpx import AsyncClient, ASGITransport
from main import app

async def debug():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GET debug
        r = await ac.get("/v1/payments/doctor-consults/remaining", params={"user_id":"user123"})
        print("GET /remaining status:", r.status_code)
        print(r.text)
        # POST debug
        r2 = await ac.post("/v1/payments/doctor-consults", json={"user_id":"user123"})
        print("POST / status:", r2.status_code)
        print(r2.text)

asyncio.run(debug())
