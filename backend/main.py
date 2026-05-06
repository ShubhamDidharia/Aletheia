from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import asyncio
import json
from datetime import datetime
from schemas.messages import (
    StatusUpdateMessage,
    LogMessage,
    SourceFoundMessage,
    AwaitingInputMessage,
    CompleteMessage,
    UserChoiceMessage,
)

load_dotenv()

app = FastAPI(title="Aletheia API")

# CORS middleware - explicitly allow localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)


manager = ConnectionManager()


async def fake_log_simulator(session_id: str):
    """Simulates a research workflow with logs, sources, and human input."""
    try:
        # Phase 1: Planning
        await manager.send(
            session_id,
            StatusUpdateMessage(
                type="STATUS_UPDATE",
                phase="planning",
                description="Breaking query into tasks...",
            ).model_dump(),
        )

        await asyncio.sleep(1.5)

        # Phase 2: Search
        await manager.send(
            session_id,
            LogMessage(
                type="LOG",
                message="Searching for Apple ESG 2026...",
                icon="search",
            ).model_dump(),
        )

        await asyncio.sleep(1)

        # Phase 3: Source found
        await manager.send(
            session_id,
            SourceFoundMessage(
                type="SOURCE_FOUND",
                title="Apple Sustainability Report 2025",
                url="https://apple.com/esg",
                source_type="pdf",
            ).model_dump(),
        )

        await asyncio.sleep(1)

        # Phase 4: Analyzing
        await manager.send(
            session_id,
            LogMessage(
                type="LOG",
                message="Analyzing carbon credit data...",
                icon="compare",
            ).model_dump(),
        )

        await asyncio.sleep(1)

        # Phase 5: Awaiting input
        await manager.send(
            session_id,
            AwaitingInputMessage(
                type="AWAITING_INPUT",
                question="I found 12 sources older than 3 years. Include for historical context?",
                options=["Yes, include them", "No, recent only"],
            ).model_dump(),
        )

        # Wait for user choice (will be handled in the WebSocket handler)
        # This is a placeholder - the actual wait happens in the connection handler

    except Exception as e:
        print(f"Error in fake_log_simulator: {e}")


async def handle_user_choice(session_id: str, choice: str):
    """Handles user choice and continues the workflow."""
    try:
        await asyncio.sleep(1)

        # Send confirmation
        await manager.send(
            session_id,
            LogMessage(
                type="LOG",
                message=f"Understood. Proceeding with: {choice}",
                icon="read",
            ).model_dump(),
        )

        await asyncio.sleep(2)

        # Send completion
        await manager.send(
            session_id,
            CompleteMessage(
                type="COMPLETE",
                ui="table",
                data={
                    "company": "Apple Inc.",
                    "year": 2026,
                    "carbon_neutral": True,
                    "renewable_energy_percent": 87,
                    "waste_recycled_tons": 78500,
                    "water_usage_reduction": "42%",
                },
                narrative="Apple has achieved carbon neutrality in their operations with 87% renewable energy usage and significant waste reduction initiatives.",
            ).model_dump(),
        )

    except Exception as e:
        print(f"Error in handle_user_choice: {e}")


@app.get("/")
async def root():
    return {"status": "ok", "message": "Aletheia backend running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/research/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    simulator_task = None

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "START_MISSION":
                # Start the fake log simulator
                if simulator_task is None or simulator_task.done():
                    simulator_task = asyncio.create_task(fake_log_simulator(session_id))

            elif message.get("type") == "USER_CHOICE":
                # Handle user choice
                choice = message.get("choice", "")
                await handle_user_choice(session_id, choice)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        if simulator_task and not simulator_task.done():
            simulator_task.cancel()
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(session_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
