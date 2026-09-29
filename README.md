# Auralyn AI — Real-Time Voice Assistant

Auralyn AI is a real-time conversational voice assistant built for the **AssemblyAI Voice Agent Hackathon**.

It supports natural voice conversations, live transcripts, persistent conversation memory, and real-time tools for weather, world time, and news through a modern web interface.

---

## Features

- Real-time microphone audio streaming
- Live speech recognition
- AI-generated spoken responses
- Listening / Thinking / Speaking UI states
- Persistent JSON conversation history
- Weather tool
- World Time tool
- Live News with clickable sources
- Quick-action buttons
- FastAPI WebSocket bridge
- Echo suppression while Auralyn is speaking

---

## Architecture

```text
Browser UI
   ↓ WebSocket /ws
FastAPI Server
   ↓ WebSocket /agent
Auralyn Backend
   ↓
AssemblyAI Voice Agent + Live Tools
```

The browser UI and Python voice assistant communicate through a FastAPI WebSocket bridge.

---

## Tech Stack

### Backend
- Python 3.12
- FastAPI
- Uvicorn
- WebSockets
- PyAudio
- python-dotenv

### Voice AI
- AssemblyAI Voice Agent API

### Frontend
- HTML
- CSS
- JavaScript
- Browser WebSocket API

### Live Data
- Open-Meteo Weather API
- Open-Meteo Geocoding API
- Google News RSS

### Storage
- JSON conversation history

---

## Project Structure

```text
auralyn-ai-voice-assistant/
│
├── main.py
├── server.py
├── README.md
├── requirements.txt
├── .gitignore
│
├── conversations/
│   └── conversation_*.json
│
└── ui/
    ├── index.html
    ├── style.css
    └── script.js
```

---

## Setup

### 1. Create a virtual environment

```powershell
py -3.12 -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Configure the API key

Create a `.env` file in the project root:

```env
ASSEMBLYAI_API_KEY=your_api_key_here
```

Do not commit `.env` to GitHub.

---

## Run

Auralyn currently uses two local processes.

### Terminal 1 — Web Server

```powershell
python -m uvicorn server:app
```

Open:

```text
http://127.0.0.1:8000
```

### Terminal 2 — Voice Assistant

```powershell
python main.py
```

---

## Example Requests

- “What’s the weather in Mumbai?”
- “What time is it in London?”
- “What are the latest OpenAI news headlines?”
- “Explain machine learning in simple terms.”

---

## Live Tools

### Weather
Provides live temperature, feels-like temperature, humidity, and wind speed.

### World Time
Provides the current local time and timezone for a city.

### Live News
Displays recent headlines with publisher, publication time, and clickable source links.

---

## Current Limitations

- Microphone and speaker playback currently run through the local Python process
- Quick-action examples use predefined city/topic values
- FastAPI and the voice assistant run as separate processes
- English-first experience
- Speech quality depends on microphone and background noise

---

## Author

**Pratik Pratibha Tekade**

Built for the **AssemblyAI Voice Agent Hackathon**.