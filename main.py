from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
from pydantic import BaseModel
import json

app = FastAPI()

# Dictionary to store room information and clients
rooms: Dict[str, List[Dict[str, str]]] = {}

class JoinRoom(BaseModel):
    roomCode: str
    username: str

class LeaveRoom(BaseModel):
    roomCode: str
    username: str

class Transcription(BaseModel):
    roomCode: str
    username: str
    transcription: str

@app.websocket("/ws/{room_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str):
    await websocket.accept()
    username = None

    # Check if the room exists or create a new one
    if room_code not in rooms:
        rooms[room_code] = []

    try:
        # Receive and handle messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if 'join' in message:
                username = message['join']['username']
                if not any(client['username'] == username for client in rooms[room_code]):
                    rooms[room_code].append({"socket": websocket, "username": username})
                    await websocket.send_text(json.dumps({'event': 'userJoined', 'username': username}))
                    for client in rooms[room_code]:
                        if client["username"] != username:
                            await client["socket"].send_text(json.dumps({'event': 'userJoined', 'username': username}))
            
            elif 'leave' in message:
                username = message['leave']['username']
                rooms[room_code] = [client for client in rooms[room_code] if client['username'] != username]
                await websocket.send_text(json.dumps({'event': 'userLeft', 'username': username}))
                for client in rooms[room_code]:
                    await client["socket"].send_text(json.dumps({'event': 'userLeft', 'username': username}))
                if not rooms[room_code]:
                    del rooms[room_code]

            elif 'transcription' in message:
                username = message['transcription']['username']
                transcription = message['transcription']['transcription']
                for client in rooms[room_code]:
                    await client["socket"].send_text(json.dumps({'event': 'transcription', 'username': username, 'transcription': transcription}))
    
    except WebSocketDisconnect:
        # Handle disconnection
        if username:
            rooms[room_code] = [client for client in rooms[room_code] if client['username'] != username]
            for client in rooms[room_code]:
                await client["socket"].send_text(json.dumps({'event': 'userLeft', 'username': username}))
            if not rooms[room_code]:
                del rooms[room_code]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
