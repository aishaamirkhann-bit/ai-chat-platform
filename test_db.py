import asyncio
from app.database import AsyncSessionLocal
from app.auth.models import User
from app.auth.service import auth_service
from sqlalchemy import select

async def test():
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).limit(1))
            print("DB connection OK")
            u = User(
                name="Test User",
                email="testunique99@test.com",
                hashed_password=auth_service.hash_password("test123")
            )
            db.add(u)
            await db.commit()
            print("SUCCESS: User created!")
    except Exception as e:
        print(f"ERROR: {e}")

asyncio.run(test())