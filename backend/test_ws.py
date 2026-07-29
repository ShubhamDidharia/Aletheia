"""
Integration test: drives a real mission over the WebSocket, answers every
human-in-the-loop gate, and asserts the protocol behaves.

It also simulates a page refresh at the first decision gate to verify that the
thought stream replays and the pending question is re-asked on the new socket.

Run the backend first:  uvicorn main:app --reload
Then:                   python test_ws.py ["your research query"]
"""
import asyncio
import json
import sys
import time
import uuid
from collections import Counter

import websockets

# Agent output carries curly quotes and em-dashes; the default Windows console
# codepage (cp1252) raises UnicodeEncodeError on them and kills the client.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND = "ws://localhost:8000/ws/research"
DEFAULT_QUERY = "Compare Tesla and BYD 2026 solid-state battery roadmaps"


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def show(event: dict) -> None:
    kind = event.get("type", "?")
    detail = event.get("message") or event.get("description") or event.get("title") or ""
    print(f"[{stamp()}] {kind:<14} {detail[:78]}")


async def pump(ws, counts: Counter, urls: list, gates: list) -> bool:
    """Consume events, answering any decision gate. Returns True on COMPLETE."""
    while True:
        try:
            event = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
        except asyncio.TimeoutError:
            print(f"[{stamp()}] TIMEOUT — no message for 120s")
            return False

        kind = event.get("type", "?")
        counts[kind] += 1

        if kind == "SOURCE_FOUND":
            urls.append(event["url"])
            show(event)
        elif kind == "AWAITING_INPUT":
            gates.append(event.get("gate_id", "?"))
            print(f"\n[{stamp()}] === DECISION GATE ({event.get('gate_id')}) ===")
            print(f"   Q: {event['question']}")
            print(f"   Options: {event['options']}")
            choice = event["options"][0]
            print(f"   -> answering: {choice}\n")
            await ws.send(json.dumps({"type": "USER_RESPONSE", "choice": choice}))
        elif kind == "COMPLETE":
            print(f"\n[{stamp()}] COMPLETE: {event['narrative']}")
            return True
        elif kind == "ERROR":
            print(f"[{stamp()}] ERROR: {event['message']}")
            if not event.get("recoverable"):
                return False
        else:
            show(event)


async def wait_for_gate(ws, counts: Counter, urls: list) -> dict | None:
    """Run until the first AWAITING_INPUT (or COMPLETE)."""
    while True:
        try:
            event = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
        except asyncio.TimeoutError:
            print(f"[{stamp()}] TIMEOUT waiting for first gate")
            return None

        kind = event.get("type", "?")
        counts[kind] += 1

        if kind == "SOURCE_FOUND":
            urls.append(event["url"])
            show(event)
        elif kind == "AWAITING_INPUT":
            print(f"\n[{stamp()}] === DECISION GATE ({event.get('gate_id')}) ===")
            print(f"   Q: {event['question']}")
            print(f"   Options: {event['options']}")
            return event
        elif kind in ("COMPLETE", "ERROR"):
            show(event)
            return None
        else:
            show(event)


async def run(session_id: str, query: str) -> None:
    uri = f"{BACKEND}/{session_id}"
    counts: Counter = Counter()
    urls: list = []
    gates: list = []
    completed = False
    refresh_verified = False

    async with websockets.connect(uri, max_size=None) as ws:
        await ws.send(json.dumps({"type": "START_MISSION", "query": query}))
        print(f"[{stamp()}] START_MISSION: {query}\n")
        gate = await wait_for_gate(ws, counts, urls)

    if gate is None:
        print("\n(no decision gate fired for this query)")
        completed = counts["COMPLETE"] > 0
    else:
        gates.append(gate.get("gate_id", "?"))

        # ── Simulate a browser refresh while the agent is paused ──────────
        print(f"\n[{stamp()}] --- simulating page refresh (socket closed) ---")
        async with websockets.connect(uri, max_size=None) as ws2:
            replay: Counter = Counter()
            re_asked = None
            try:
                while True:
                    msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=8))
                    replay[msg["type"]] += 1
                    if msg["type"] == "AWAITING_INPUT":
                        re_asked = msg
            except asyncio.TimeoutError:
                pass

            print(f"[{stamp()}] replayed on reconnect: {dict(replay)}")
            assert re_asked, "FAIL: pending gate was not re-asked after reconnect"
            assert re_asked["question"] == gate["question"], "FAIL: wrong gate re-asked"
            assert replay["SOURCE_FOUND"] == len(urls), (
                f"FAIL: replay had {replay['SOURCE_FOUND']} sources, expected {len(urls)}"
            )
            refresh_verified = True
            print(f"[{stamp()}] PASS: full history replayed and gate re-asked\n")

            choice = gate["options"][0]
            print(f"   -> answering on the reconnected socket: {choice}\n")
            await ws2.send(json.dumps({"type": "USER_RESPONSE", "choice": choice}))
            completed = await pump(ws2, counts, urls, gates)

    print("\n" + "=" * 76)
    print(f"  events              : {dict(counts)}")
    print(f"  gates hit           : {gates}")
    print(f"  SOURCE_FOUND        : {len(urls)}   unique urls: {len(set(urls))}")
    dupes = len(urls) - len(set(urls))
    print(f"  duplicate sources   : {dupes}  {'<-- BUG' if dupes else '<-- OK'}")
    print(f"  refresh/reattach    : {'verified' if refresh_verified else 'not exercised'}")
    print(f"  completed           : {completed}")
    print("=" * 76)

    assert completed, "FAIL: mission never reached COMPLETE"
    assert dupes == 0, "FAIL: duplicate SOURCE_FOUND events (node re-execution)"
    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    asyncio.run(run(str(uuid.uuid4()), sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY))
