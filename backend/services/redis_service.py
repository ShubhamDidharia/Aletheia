"""
Redis layer: pub/sub thought-stream, execution-state checkpoints, and search cache.

Redis is the bridge between the long-running agent task and the WebSocket
connection. If Redis is unreachable we fall back to an in-process broker so a
mission still runs end-to-end (single-worker only) instead of dying silently.
"""
import os
import json
import asyncio
import logging
from collections import defaultdict
from typing import AsyncGenerator, Dict, Any, Optional, List

import redis.asyncio as redis

from schemas.messages import validate_event

log = logging.getLogger("aletheia.redis")

# Keep the last N events per session so a reconnecting browser can replay
# everything it missed while disconnected.
EVENT_LOG_MAX = 500
EVENT_LOG_TTL = 3600
CHECKPOINT_TTL = 3600
SEARCH_CACHE_TTL = 900

_redis: Optional[redis.Redis] = None
_redis_ready: Optional[bool] = None  # None = untested, False = degraded
_degraded_warned = False


# ──────────────────────────────────────────────────────────────────────────────
# In-process fallback broker (used only when Redis is unavailable)
# ──────────────────────────────────────────────────────────────────────────────
class _LocalBroker:
    """Minimal pub/sub + key-value store so the app works without Redis."""

    def __init__(self) -> None:
        self.subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self.store: Dict[str, Any] = {}
        self.lists: Dict[str, List[str]] = defaultdict(list)

    def publish(self, channel: str, payload: str) -> None:
        for q in list(self.subscribers.get(channel, [])):
            q.put_nowait(payload)

    def subscribe(self, channel: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers[channel].append(q)
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        if q in self.subscribers.get(channel, []):
            self.subscribers[channel].remove(q)


_local = _LocalBroker()


def _mark_degraded(exc: Exception) -> None:
    global _redis_ready, _degraded_warned
    _redis_ready = False
    if not _degraded_warned:
        _degraded_warned = True
        log.warning(
            "Redis unavailable (%s: %s). Falling back to in-process broker. "
            "Missions still run, but state is lost on restart and cannot be "
            "shared across workers. Set a working REDIS_URL to fix.",
            type(exc).__name__, exc,
        )


def get_redis() -> Optional[redis.Redis]:
    """Return a Redis client, or None if we've already determined it's down."""
    global _redis
    if _redis_ready is False:
        return None
    if _redis is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        kwargs: Dict[str, Any] = {
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 15,
            "health_check_interval": 30,
            "retry_on_timeout": True,
        }
        if redis_url.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = "none"
        _redis = redis.from_url(redis_url, **kwargs)
    return _redis


async def ping() -> bool:
    """Probe Redis once at startup so degraded mode is visible in the logs."""
    global _redis_ready
    client = get_redis()
    if client is None:
        return False
    try:
        await client.ping()
        _redis_ready = True
        log.info("Redis connected.")
        return True
    except Exception as e:
        _mark_degraded(e)
        return False


def is_degraded() -> bool:
    return _redis_ready is False


# ──────────────────────────────────────────────────────────────────────────────
# Execution state checkpoints
# ──────────────────────────────────────────────────────────────────────────────
async def save_checkpoint(session_id: str, state: Dict[str, Any], ttl: int = CHECKPOINT_TTL) -> None:
    key = f"checkpoint:{session_id}"
    payload = json.dumps(state)
    client = get_redis()
    if client is not None:
        try:
            await client.set(key, payload, ex=ttl)
            return
        except Exception as e:
            _mark_degraded(e)
    _local.store[key] = payload


async def load_checkpoint(session_id: str) -> Optional[Dict[str, Any]]:
    key = f"checkpoint:{session_id}"
    client = get_redis()
    if client is not None:
        try:
            raw = await client.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            _mark_degraded(e)
    raw = _local.store.get(key)
    return json.loads(raw) if raw else None


async def delete_checkpoint(session_id: str) -> None:
    key = f"checkpoint:{session_id}"
    client = get_redis()
    if client is not None:
        try:
            await client.delete(key)
            return
        except Exception as e:
            _mark_degraded(e)
    _local.store.pop(key, None)


# ──────────────────────────────────────────────────────────────────────────────
# Thought stream: pub/sub + replayable event log
# ──────────────────────────────────────────────────────────────────────────────
async def publish_event(session_id: str, event: Dict[str, Any]) -> None:
    """
    Publish an event to the session channel AND append it to a capped log.

    Never raises: a broken thought-stream must not kill a running mission.
    """
    channel = f"research:{session_id}"
    log_key = f"events:{session_id}"
    payload = json.dumps(validate_event(event))

    client = get_redis()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.rpush(log_key, payload)
            pipe.ltrim(log_key, -EVENT_LOG_MAX, -1)
            pipe.expire(log_key, EVENT_LOG_TTL)
            pipe.publish(channel, payload)
            await pipe.execute()
            return
        except Exception as e:
            _mark_degraded(e)

    entries = _local.lists[log_key]
    entries.append(payload)
    del entries[:-EVENT_LOG_MAX]
    _local.publish(channel, payload)


async def get_event_history(session_id: str) -> List[Dict[str, Any]]:
    """Every event emitted so far this session, for replay after a reconnect."""
    log_key = f"events:{session_id}"
    client = get_redis()
    if client is not None:
        try:
            raw = await client.lrange(log_key, 0, -1)
            return [json.loads(r) for r in raw]
        except Exception as e:
            _mark_degraded(e)
    return [json.loads(r) for r in _local.lists.get(log_key, [])]


async def clear_event_history(session_id: str) -> None:
    log_key = f"events:{session_id}"
    client = get_redis()
    if client is not None:
        try:
            await client.delete(log_key)
            return
        except Exception as e:
            _mark_degraded(e)
    _local.lists.pop(log_key, None)


async def subscribe(session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
    """Yield events published to this session. Falls back to the local broker."""
    channel = f"research:{session_id}"
    client = get_redis()

    if client is not None:
        pubsub = None
        try:
            pubsub = client.pubsub()
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _mark_degraded(e)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(channel)
                    close = getattr(pubsub, "aclose", None) or pubsub.close
                    await close()
                except Exception:
                    pass

    # Degraded path
    q = _local.subscribe(channel)
    try:
        while True:
            payload = await q.get()
            yield json.loads(payload)
    finally:
        _local.unsubscribe(channel, q)


# ──────────────────────────────────────────────────────────────────────────────
# Search cache — avoid re-billing Tavily for a repeated query
# ──────────────────────────────────────────────────────────────────────────────
async def cache_get(key: str) -> Optional[Any]:
    client = get_redis()
    if client is not None:
        try:
            raw = await client.get(f"cache:{key}")
            return json.loads(raw) if raw else None
        except Exception as e:
            _mark_degraded(e)
    raw = _local.store.get(f"cache:{key}")
    return json.loads(raw) if raw else None


async def cache_set(key: str, value: Any, ttl: int = SEARCH_CACHE_TTL) -> None:
    payload = json.dumps(value)
    client = get_redis()
    if client is not None:
        try:
            await client.set(f"cache:{key}", payload, ex=ttl)
            return
        except Exception as e:
            _mark_degraded(e)
    _local.store[f"cache:{key}"] = payload
