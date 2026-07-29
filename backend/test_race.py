"""
Regression test for the AWAITING_INPUT / USER_RESPONSE race.

The agent publishes AWAITING_INPUT and the client can answer the instant it
arrives — before the backend has finished its own post-publish bookkeeping.
If the session still looks "running" at that moment the reply is rejected and
the agent stays parked forever. Redis round-trips widen that window enough to
hit it most of the time, so this test replies with zero delay, repeatedly.

Uses a stub graph (no Gemini or Tavily quota needed) but the real WebSocket
endpoint and the real Redis configured in .env.

Run:  python test_race.py
"""
import asyncio
import json
import threading
import uuid
from types import SimpleNamespace

import uvicorn
import websockets
from dotenv import load_dotenv

load_dotenv()

import main  # noqa: E402  (must follow load_dotenv)

PORT = 8077
ROUNDS = 15

_paused: set[str] = set()
_GATE = {
    "gate_id": "test",
    "question": "Dig deeper or flag both?",
    "options": ["Dig deeper", "Flag both"],
}


async def _fake_run_mission(session_id, query, checkpoint=None):
    await asyncio.sleep(0.02)
    _paused.add(session_id)
    return {
        "sources": [], "completed_steps": [], "decisions": [],
        "__interrupt__": [SimpleNamespace(value=dict(_GATE))],
    }


async def _fake_resume_mission(session_id, choice):
    await asyncio.sleep(0.02)
    _paused.discard(session_id)
    return {
        "sources": [], "completed_steps": ["t1"],
        "decisions": [{"gate_id": "test", "action": "a", "label": choice}],
    }


async def _fake_pending(session_id):
    return dict(_GATE) if session_id in _paused else None


async def _fake_has_thread(session_id):
    return session_id in _paused


async def _no_persist(**_kwargs) -> None:
    """This test drives 15 synthetic missions — none belong in real storage."""
    return None


main.run_mission = _fake_run_mission
main.resume_mission = _fake_resume_mission
main.get_pending_interrupt = _fake_pending
main.has_thread = _fake_has_thread
main.supabase_store.save_mission = _no_persist


async def _one_round() -> tuple[bool, list[str]]:
    session_id = f"race-{uuid.uuid4()}"
    errors: list[str] = []

    async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws/research/{session_id}") as ws:
        await ws.send(json.dumps({"type": "START_MISSION", "query": "race test"}))
        while True:
            try:
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            except asyncio.TimeoutError:
                errors.append("TIMEOUT (agent left parked)")
                return False, errors

            if event["type"] == "AWAITING_INPUT":
                # Zero delay — this is what races the bookkeeping.
                await ws.send(json.dumps({
                    "type": "USER_RESPONSE", "choice": event["options"][0],
                }))
            elif event["type"] == "ERROR":
                errors.append(event["message"])
            elif event["type"] == "COMPLETE":
                return True, errors


async def _run() -> None:
    for _ in range(40):
        try:
            async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws/research/warmup"):
                break
        except OSError:
            await asyncio.sleep(0.3)

    passed = 0
    errors: list[str] = []
    for i in range(ROUNDS):
        okay, round_errors = await _one_round()
        passed += okay
        errors.extend(round_errors)
        print(f"  round {i + 1:2}/{ROUNDS}: {'COMPLETE' if okay else 'FAILED'}"
              + (f"   errors={round_errors}" if round_errors else ""))

    print("\n" + "=" * 62)
    print(f"  completed       : {passed}/{ROUNDS}")
    print(f"  spurious ERRORs : {len(errors)}")
    if errors:
        print(f"  messages        : {sorted(set(errors))}")
    print("=" * 62)

    assert passed == ROUNDS, "FAIL: some missions never completed"
    assert not errors, "FAIL: spurious ERROR events"
    print("PASS — no false 'still working' rejections")


if __name__ == "__main__":
    config = uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error")
    threading.Thread(target=uvicorn.Server(config).run, daemon=True).start()
    asyncio.run(_run())
