from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory="ui"),
    name="static"
)

connected_browsers = []

agent_socket = None


@app.get("/")
async def home():
    return FileResponse("ui/index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    connected_browsers.append(websocket)

    print("Browser connected.")

    try:
        while True:
            message = await websocket.receive_text()

            print("Browser message:", message)

            try:
                data = json.loads(message)

                if data.get("type") == "quick_action":
                    if agent_socket is not None:
                        await agent_socket.send_json(data)
                        print("Quick action sent to Auralyn:", data)

            except json.JSONDecodeError:
                pass

            await websocket.send_json(
                {
                    "type": "connection",
                    "status": "connected",
                    "message": "Auralyn backend connected."
                }
            )

    except WebSocketDisconnect:
        print("Browser disconnected.")

        if websocket in connected_browsers:
            connected_browsers.remove(websocket)


async def broadcast_to_browsers(event):
    disconnected = []

    for browser in connected_browsers:

        try:
            await browser.send_json(event)

        except Exception:
            disconnected.append(browser)

    for browser in disconnected:
        if browser in connected_browsers:
            connected_browsers.remove(browser)


@app.websocket("/agent")
async def agent_websocket(websocket: WebSocket):

    global agent_socket

    await websocket.accept()

    agent_socket = websocket

    print("Auralyn agent connected.")

    try:

        while True:
            message = await websocket.receive_text()

            try:
                event = json.loads(message)

            except json.JSONDecodeError:
                print("Invalid agent message:", message)
                continue

            print(
                "Agent event:",
                event.get("type")
            )

            await broadcast_to_browsers(event)

    except WebSocketDisconnect:
        print("Auralyn agent disconnected.")
