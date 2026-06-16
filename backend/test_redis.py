import asyncio
import redis.asyncio as redis
import os
import dotenv

dotenv.load_dotenv()

async def test():
    c = redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)
    try:
        print("Ping result:", await c.ping())
    except Exception as e:
        print("Error:", e)
    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(test())
