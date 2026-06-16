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
from graph.agent_graph import run_mission
from services import redis_service

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

# Track background mission tasks
running_missions: dict[str, asyncio.Task] = {}

@app.get("/")
async def root():
    return {"status": "ok", "message": "Aletheia backend running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/research/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    subscriber_task = None

    try:
        # Start subscriber loop to forward Redis pub/sub messages to the WebSocket
        async def subscribe_loop():
            try:
                async for event in redis_service.subscribe(session_id):
                    await manager.send(session_id, event)
            except asyncio.CancelledError:
                pass
                
        subscriber_task = asyncio.create_task(subscribe_loop())

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "START_MISSION":
                query = message.get("query", "Default research query")
                
                # Check for existing checkpoint
                checkpoint = await redis_service.load_checkpoint(session_id)
                if checkpoint and checkpoint.get("status") != "completed":
                    await redis_service.publish_event(session_id, {
                        "type": "STATUS_UPDATE",
                        "phase": "planning",
                        "description": "Reattaching to in-progress research..."
                    })
                else:
                    await redis_service.publish_event(session_id, {
                        "type": "STATUS_UPDATE",
                        "phase": "planning",
                        "description": "Mission started, initializing agents..."
                    })
                    checkpoint = None
                
                # Run actual graph in background
                async def run_mission_task():
                    try:
                        final_state = await run_mission(session_id, query, checkpoint)
                        
                        # Convert Pydantic models to dicts for COMPLETE message
                        sources_data = [
                            s.model_dump(mode="json") if hasattr(s, "model_dump") else s 
                            for s in final_state.get("sources", [])
                        ]
                        
                        await redis_service.publish_event(session_id, {
                            "type": "COMPLETE",
                            "ui": "table",
                            "data": {"sources": sources_data},
                            "narrative": f"Research complete for: {query}"
                        })
                        await redis_service.delete_checkpoint(session_id)
                    except Exception as e:
                        print(f"Mission error: {e}")
                        await redis_service.publish_event(session_id, {"type": "ERROR", "message": str(e)})
                    finally:
                        if session_id in running_missions:
                            del running_missions[session_id]
                
                if session_id not in running_missions or running_missions[session_id].done():
                    running_missions[session_id] = asyncio.create_task(run_mission_task())

            elif message.get("type") == "USER_CHOICE":
                # Minimal hook for Commit 6
                # e.g., writing the choice to Redis so the graph can pick it up
                client = redis_service.get_redis()
                await client.rpush(f"resume:{session_id}", json.dumps(message))

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(session_id)
    finally:
        if subscriber_task:
            subscriber_task.cancel()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
