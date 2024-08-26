from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
import uvicorn
import logging

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store room information and clients
rooms = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str, room_code: str):
        for client in rooms.get(room_code, []):
            await client.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{room_code}/{username}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, username: str):
    await manager.connect(websocket)
    
    # Log when a user joins
    logger.info(f"User {username} connected to room {room_code}")

    if room_code not in rooms:
        rooms[room_code] = []

    rooms[room_code].append(websocket)
    await manager.broadcast(f"{username} joined the room", room_code)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{username}: {data}", room_code)
            # Log when a user sends a message
            logger.info(f"Message from {username} in room {room_code}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        rooms[room_code].remove(websocket)
        await manager.broadcast(f"{username} left the room", room_code)
        
        # Log when a user disconnects
        logger.info(f"User {username} disconnected from room {room_code}")

        if not rooms[room_code]:
            del rooms[room_code]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
