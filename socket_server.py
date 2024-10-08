import io
import base64
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioDataStream, SpeechSynthesisOutputFormat, ResultReason
 
# Create FastAPI app
app = FastAPI()
 
# Add CORS middleware to the FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
# Create a new Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='asgi')
 
# Wrap the Socket.IO server with the ASGI app
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
 
# Initialize rooms dictionary
rooms = {}
 
# Azure Speech Configurations
speech_config = SpeechConfig(subscription="a446630e73514d779093ab5621f15304", region="eastus")
speech_config.set_speech_synthesis_output_format(SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm)
 
# Function to synthesize speech
async def synthesize_speech(text, language="en-US"):
    # Set the language for speech synthesis
    speech_config.speech_synthesis_language = language
 
    synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    result = synthesizer.speak_text_async(text).get()
 
    if result.reason == ResultReason.SynthesizingAudioCompleted:
        # Convert audio data to Base64
        audio_data = result.audio_data
        base64_audio = base64.b64encode(audio_data).decode('utf-8')
        return base64_audio
    else:
        print(f"Speech synthesis failed with reason: {result.reason}")
        return None
 
# Event handler when a new client connects
@sio.event
async def connect(sid, environ):
    print(f'New client connected: {sid}')
 
# Event handler when a client joins a room
@sio.event
async def join(sid, data):
    room_code = data.get('roomCode')
    username = data.get('username')
 
    if not room_code:
        print('Room code is missing')
        return
 
    if room_code not in rooms:
        rooms[room_code] = []
 
    existing_client = next((client for client in rooms[room_code] if client['username'] == username), None)
    if existing_client:
        print(f'User {username} rejoined room {room_code}')
        return
 
    rooms[room_code].append({'sid': sid, 'username': username})
    await sio.enter_room(sid, room_code)
    print(f'User {username} joined room {room_code}')
 
    # Notify other users in the room about the new user
    await sio.emit('userJoined', {'username': username}, room=room_code)
 
# Event handler for receiving transcriptions
@sio.event
async def transcription(sid, data):
    room_code = data.get('roomCode')
    username = data.get('username')
    transcription = data.get('transcription')
    language = data.get('language', 'en-US')  # Default to English if no language is provided
 
    if not room_code:
        print('Room code is missing')
        return
 
    # Synthesize speech and get Base64-encoded audio
    base64_audio = await synthesize_speech(transcription, language)
   
    if base64_audio:
        # Broadcast the synthesized audio to all users in the room
        await sio.emit('synthesizedAudio', {'username': username, 'audio': base64_audio}, room=room_code)
        print(f'Transcription from {username} in room {room_code} has been synthesized and broadcasted.')
 
# Event handler when a client leaves a room
@sio.event
async def leave(sid, data):
    room_code = data.get('roomCode')
    username = data.get('username')
 
    if not room_code:
        print('Room code is missing')
        return
 
    await sio.leave_room(sid, room_code)
    rooms[room_code] = [client for client in rooms[room_code] if client['username'] != username]
 
    # Notify other users in the room about the user leaving
    await sio.emit('userLeft', {'username': username}, room=room_code)
 
    # Cleanup the room if it's empty
    if not rooms[room_code]:
        del rooms[room_code]
        print(f'Room {room_code} is empty and has been deleted.')
 
    print(f'User {username} left room {room_code}')
 
# Event handler when a client disconnects
@sio.event
async def disconnect(sid):
    print(f'Client disconnected: {sid}')
    for room_code, clients in list(rooms.items()):
        rooms[room_code] = [client for client in clients if client['sid'] != sid]
 
        # Notify other users in the room about the user disconnecting
        disconnected_client = next((client for client in clients if client['sid'] == sid), None)
        if disconnected_client:
            await sio.emit('userLeft', {'username': disconnected_client['username']}, room=room_code)
 
        # Cleanup the room if it's empty
        if not rooms[room_code]:
            del rooms[room_code]
            print(f'Room {room_code} is empty and has been deleted.')
#