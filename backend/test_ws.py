import asyncio
import websockets
import json
import uuid

async def test_ws():
    session_id = str(uuid.uuid4())
    uri = f"ws://localhost:8000/ws/research/{session_id}"
    print(f"Connecting to {uri}")
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({
            "type": "START_MISSION",
            "query": "What is the capital of France?"
        }))
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                print(f"Received: {data['type']}")
                if data["type"] in ["COMPLETE", "ERROR"]:
                    break
            except Exception as e:
                print(f"Error: {e}")
                break

if __name__ == "__main__":
    asyncio.run(test_ws())
