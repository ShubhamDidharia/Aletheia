import os
import json
import redis.asyncio as redis
from typing import AsyncGenerator, Dict, Any, Optional

# Singleton connection pool
_redis_pool = None

def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        
        # Upstash / general remote Redis compatibility tweaks
        kwargs = {"decode_responses": True}
        if redis_url.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = "none"
            # Keep connections alive (important for Upstash pub/sub)
            kwargs["health_check_interval"] = 30
            
        _redis_pool = redis.from_url(redis_url, **kwargs)
    return _redis_pool

async def save_checkpoint(session_id: str, state: Dict[str, Any], ttl: int = 3600) -> None:
    client = get_redis()
    key = f"checkpoint:{session_id}"
    state_json = json.dumps(state)
    await client.set(key, state_json, ex=ttl)

async def load_checkpoint(session_id: str) -> Optional[Dict[str, Any]]:
    client = get_redis()
    key = f"checkpoint:{session_id}"
    state_json = await client.get(key)
    if state_json:
        return json.loads(state_json)
    return None

async def delete_checkpoint(session_id: str) -> None:
    client = get_redis()
    key = f"checkpoint:{session_id}"
    await client.delete(key)

async def publish_event(session_id: str, event: Dict[str, Any]) -> None:
    client = get_redis()
    channel = f"research:{session_id}"
    await client.publish(channel, json.dumps(event))

async def subscribe(session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
    client = get_redis()
    pubsub = client.pubsub()
    channel = f"research:{session_id}"
    
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
    finally:
        await pubsub.unsubscribe(channel)
        # Handle deprecation warning: use aclose if available, else close
        if hasattr(pubsub, "aclose"):
            await pubsub.aclose()
        else:
            await pubsub.close()
