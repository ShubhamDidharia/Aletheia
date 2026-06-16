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


# Old mocked functions removed for production.

@app.get("/")
async def root():
    return {"status": "ok", "message": "Aletheia backend running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/research/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "START_MISSION":
                query = message.get("query", "Default research query")
                
                async def emit(event: dict):
                    await websocket.send_json(event)
                
                # Send immediate status
                await emit(
                    StatusUpdateMessage(
                        type="STATUS_UPDATE",
                        phase="planning",
                        description="Mission started, initializing agents...",
                    ).model_dump()
                )
                
                # Run actual graph
                try:
                    final_state = await run_mission(query, emit)
                    
                    # Convert Pydantic models to dicts for COMPLETE message
                    sources_data = [s.model_dump(mode="json") for s in final_state.get("sources", [])]
                    
                    await emit(
                        CompleteMessage(
                            type="COMPLETE",
                            ui="table",
                            data={"sources": sources_data},
                            narrative=f"Research complete for: {query}"
                        ).model_dump()
                    )
                except Exception as e:
                    print(f"Mission error: {e}")
                    await emit({"type": "ERROR", "message": str(e)})

            elif message.get("type") == "USER_CHOICE":
                # Fallback handler, as we removed the mock choice handler
                pass

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(session_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
