import os
import json
import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import ValidationError

from schemas.messages import StartMissionMessage, UserResponseMessage
from graph.agent_graph import (
    run_mission,
    resume_mission,
    get_pending_interrupt,
    has_thread,
)
from services import redis_service
from services.llm import LLMError
from services.tavily import TavilyError

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("aletheia")

REQUIRED_KEYS = {
    "GEMINI_API_KEY": "the Planner and Analyst agents (Google AI Studio)",
    "TAVILY_API_KEY": "web search (tavily.com)",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
    for key in missing:
        log.error("MISSING %s — required for %s. Add it to backend/.env", key, REQUIRED_KEYS[key])
    if not missing:
        log.info("API keys present: %s", ", ".join(REQUIRED_KEYS))

    if not await redis_service.ping():
        log.warning(
            "Running in DEGRADED mode without Redis. Missions work, but state "
            "is lost on restart and cannot be shared across workers."
        )
    yield


app = FastAPI(title="Aletheia API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip() for o in
        os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active[session_id] = websocket

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        # Only drop the mapping if it still points at this socket, so a fast
        # reconnect isn't torn down by the old connection's cleanup.
        if self.active.get(session_id) is websocket:
            del self.active[session_id]

    async def send(self, session_id: str, message: dict) -> None:
        ws = self.active.get(session_id)
        if ws is None:
            return
        try:
            await ws.send_json(message)
        except Exception as e:
            log.info("Dropping send to %s: %s", session_id, e)


manager = ConnectionManager()
running_missions: dict[str, asyncio.Task] = {}


def _friendly_error(exc: Exception) -> str:
    """Turn an internal failure into something the user can act on."""
    if isinstance(exc, (LLMError, TavilyError)):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


def _extract_interrupt(final_state: dict) -> Optional[dict]:
    """
    ainvoke() returns the state with an '__interrupt__' key when a node calls
    interrupt(). Returns the interrupt payload, or None if the graph finished.
    """
    interrupts = (final_state or {}).get("__interrupt__")
    if not interrupts:
        return None
    value = getattr(interrupts[0], "value", interrupts[0])
    if isinstance(value, dict):
        return value
    return {"question": str(value), "options": [], "gate_id": ""}


async def _publish_awaiting(session_id: str, payload: dict) -> None:
    log.info("[PAUSE] %s | %s", session_id, payload.get("question"))
    await redis_service.publish_event(session_id, {
        "type": "AWAITING_INPUT",
        "question": payload.get("question", "Input required"),
        "options": payload.get("options", []),
        "gate_id": payload.get("gate_id", ""),
    })
    state = await redis_service.load_checkpoint(session_id)
    if state:
        state["status"] = "awaiting_input"
        await redis_service.save_checkpoint(session_id, state)


async def _finalize(session_id: str, final_state: dict, query: str) -> None:
    sources = [
        s.model_dump(mode="json") if hasattr(s, "model_dump") else s
        for s in final_state.get("sources", [])
    ]
    decisions = final_state.get("decisions", [])
    claims = final_state.get("claims", [])
    ui = final_state.get("ui", "report")

    # The Visualizer writes the analysis; fall back to a factual summary if it
    # was unavailable, so COMPLETE is never empty.
    narrative = (final_state.get("narrative") or "").strip()
    if not narrative:
        narrative = (
            f"Researched “{query}” across {len(final_state.get('completed_steps', []))} "
            f"search tasks and gathered {len(sources)} verified sources."
        )
    if decisions:
        narrative += " Your decisions: " + "; ".join(d["label"] for d in decisions) + "."

    await redis_service.publish_event(session_id, {
        "type": "COMPLETE",
        "ui": ui,
        "data": {
            ui: final_state.get("ui_data", {}),
            "claims": claims,
            "dropped_claims": final_state.get("dropped_claims", 0),
            "sources": sources,
            "tasks": final_state.get("completed_steps", []),
            "decisions": decisions,
        },
        "narrative": narrative,
    })
    await redis_service.delete_checkpoint(session_id)
    log.info("[DONE] %s | ui=%s | %d claims | %d sources",
             session_id, ui, len(claims), len(sources))


async def _drive(session_id: str, coro, query: str) -> None:
    """Run a mission (or a resume) and translate its outcome into events."""
    try:
        final_state = await coro
        pending = _extract_interrupt(final_state)

        # Deregister BEFORE announcing. Publishing costs several Redis round
        # trips, and the client can answer an AWAITING_INPUT the instant it
        # arrives — if this session still looked "running" at that moment the
        # reply would be rejected and the agent would stay parked forever.
        running_missions.pop(session_id, None)

        if pending:
            await _publish_awaiting(session_id, pending)
            return
        await _finalize(session_id, final_state, query)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error("Mission failed for %s: %s", session_id, e)
        traceback.print_exc()
        await redis_service.publish_event(session_id, {
            "type": "ERROR",
            "message": _friendly_error(e),
            "recoverable": False,
        })
    finally:
        running_missions.pop(session_id, None)


def _is_running(session_id: str) -> bool:
    task = running_missions.get(session_id)
    return task is not None and not task.done()


@app.get("/")
async def root():
    return {"status": "ok", "message": "Aletheia backend running"}


@app.get("/health")
async def health():
    # Probe live rather than reporting a cached flag — this is also what lets a
    # recovered Redis be picked up without restarting the backend.
    redis_ok = await redis_service.ping()
    return {
        "status": "ok",
        "redis": "ok" if redis_ok else "degraded",
        "missing_keys": [k for k in REQUIRED_KEYS if not os.getenv(k)],
    }


@app.websocket("/ws/research/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    subscriber_task: Optional[asyncio.Task] = None

    try:
        async def subscribe_loop():
            try:
                async for event in redis_service.subscribe(session_id):
                    await manager.send(session_id, event)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                log.error("Subscriber loop died for %s: %s", session_id, e)
                await manager.send(session_id, {
                    "type": "ERROR",
                    "message": f"Live update stream lost: {e}",
                    "recoverable": True,
                })

        subscriber_task = asyncio.create_task(subscribe_loop())

        # Replay whatever this session already emitted, so a page refresh
        # mid-mission restores the full thought stream instead of a blank feed.
        history = await redis_service.get_event_history(session_id)
        for event in history:
            await websocket.send_json(event)
        if history:
            log.info("Replayed %d event(s) to %s", len(history), session_id)

        # If the agent is parked on a decision gate, re-ask it on this socket —
        # unless the replay already ended on that exact question.
        pending = await get_pending_interrupt(session_id)
        if pending:
            last_ask = next(
                (e for e in reversed(history) if e.get("type") == "AWAITING_INPUT"), None
            )
            already_asked = last_ask and last_ask.get("question") == pending.get("question")
            if not already_asked:
                await websocket.send_json({
                    "type": "AWAITING_INPUT",
                    "question": pending.get("question", "Input required"),
                    "options": pending.get("options", []),
                    "gate_id": pending.get("gate_id", ""),
                })

        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send(session_id, {
                    "type": "ERROR", "message": "Malformed message.", "recoverable": True,
                })
                continue

            msg_type = message.get("type")

            # ── START_MISSION ────────────────────────────────────────────────
            if msg_type == "START_MISSION":
                try:
                    start = StartMissionMessage.model_validate(message)
                except ValidationError:
                    await manager.send(session_id, {
                        "type": "ERROR", "message": "START_MISSION needs a 'query'.",
                        "recoverable": True,
                    })
                    continue

                if not start.query.strip():
                    await manager.send(session_id, {
                        "type": "ERROR", "message": "Query cannot be empty.", "recoverable": True,
                    })
                    continue

                if _is_running(session_id):
                    await manager.send(session_id, {
                        "type": "ERROR",
                        "message": "A mission is already running in this session.",
                        "recoverable": True,
                    })
                    continue

                # Paused on a gate: don't restart, just re-ask the question.
                pending = await get_pending_interrupt(session_id)
                if pending:
                    await _publish_awaiting(session_id, pending)
                    continue

                checkpoint = await redis_service.load_checkpoint(session_id)
                resumable = (
                    checkpoint
                    and checkpoint.get("status") not in ("completed", None)
                    and await has_thread(session_id)
                )

                if resumable:
                    await redis_service.publish_event(session_id, {
                        "type": "STATUS_UPDATE",
                        "phase": "planning",
                        "description": "Reattaching to in-progress research...",
                    })
                else:
                    checkpoint = None
                    await redis_service.clear_event_history(session_id)
                    await redis_service.publish_event(session_id, {
                        "type": "STATUS_UPDATE",
                        "phase": "planning",
                        "description": f"Mission started: {start.query}",
                    })

                running_missions[session_id] = asyncio.create_task(
                    _drive(session_id, run_mission(session_id, start.query, checkpoint), start.query)
                )

            # ── USER_RESPONSE ────────────────────────────────────────────────
            elif msg_type == "USER_RESPONSE":
                try:
                    response = UserResponseMessage.model_validate(message)
                except ValidationError:
                    await manager.send(session_id, {
                        "type": "ERROR", "message": "USER_RESPONSE needs a 'choice'.",
                        "recoverable": True,
                    })
                    continue

                # Whether a decision is pending is decided by the graph, not by
                # our task bookkeeping — check it first so the error messages
                # can't contradict the agent's actual state.
                if not await get_pending_interrupt(session_id):
                    await manager.send(session_id, {
                        "type": "ERROR",
                        "message": (
                            "Still working — no decision is pending yet."
                            if _is_running(session_id)
                            else "No decision is pending for this session."
                        ),
                        "recoverable": True,
                    })
                    continue

                if _is_running(session_id):
                    # A resume for this gate is already in flight; a second one
                    # would run the graph twice.
                    await manager.send(session_id, {
                        "type": "ERROR",
                        "message": "That decision is already being applied.",
                        "recoverable": True,
                    })
                    continue

                log.info("[RESUME] %s choice=%r", session_id, response.choice)
                checkpoint = await redis_service.load_checkpoint(session_id)
                query = (checkpoint or {}).get("original_query") or (checkpoint or {}).get("query", "")

                running_missions[session_id] = asyncio.create_task(
                    _drive(session_id, resume_mission(session_id, response.choice), query)
                )

            else:
                await manager.send(session_id, {
                    "type": "ERROR",
                    "message": f"Unknown message type: {msg_type!r}",
                    "recoverable": True,
                })

    except WebSocketDisconnect:
        log.info("Client disconnected: %s (mission keeps running)", session_id)
    except Exception as e:
        log.error("WebSocket error for %s: %s", session_id, e)
        traceback.print_exc()
    finally:
        manager.disconnect(session_id, websocket)
        if subscriber_task:
            subscriber_task.cancel()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
