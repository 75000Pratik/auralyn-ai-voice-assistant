import os
import asyncio
import base64
import json
import socket
import glob
import traceback
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

import pyaudio
import websockets
from dotenv import load_dotenv
from datetime import datetime


load_dotenv()

API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
URL = "wss://agents.assemblyai.com/v1/ws"

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 24000
CHUNK = 1200
INPUT_DEVICE_INDEX = 1

conversation_history = []

agent_speaking = False

last_user_text = ""

ui_socket = None

SESSION_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

SESSION_FILE = (
    f"conversations/conversation_{SESSION_TIMESTAMP}.json"
)


async def send_microphone_audio(websocket, ready_event):
    await ready_event.wait()

    audio = pyaudio.PyAudio()

    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=INPUT_DEVICE_INDEX,
        frames_per_buffer=CHUNK
    )

    print("Microphone started. Speak now...")

    try:
        while True:
            data = await asyncio.to_thread(
                stream.read,
                CHUNK,
                False
            )
            if agent_speaking:
                await asyncio.sleep(0.05)
                continue

            encoded_audio = base64.b64encode(data).decode("utf-8")

            message = {
                "type": "input.audio",
                "audio": encoded_audio
            }

            await websocket.send(
                json.dumps(message)
            )

    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


def get_weather(city):
    try:
        city_encoded = urllib.parse.quote(city)

        geocode_url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={city_encoded}&count=1&language=en&format=json"
        )

        with urllib.request.urlopen(geocode_url, timeout=10) as response:
            geocode_data = json.loads(response.read().decode())

        results = geocode_data.get("results")

        if not results:
            return {
                "success": False,
                "message": f"Could not find the city {city}."
            }

        location = results[0]

        latitude = location["latitude"]
        longitude = location["longitude"]
        city_name = location["name"]
        country = location.get("country", "")

        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&current=temperature_2m,apparent_temperature,"
            "relative_humidity_2m,wind_speed_10m"
        )

        with urllib.request.urlopen(weather_url, timeout=10) as response:
            weather_data = json.loads(response.read().decode())

        current = weather_data["current"]

        return {
            "success": True,
            "city": city_name,
            "country": country,
            "temperature_c": current["temperature_2m"],
            "feels_like_c": current["apparent_temperature"],
            "humidity_percent": current["relative_humidity_2m"],
            "wind_speed_kmh": current["wind_speed_10m"]
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


def get_current_time(city):
    try:
        city_encoded = urllib.parse.quote(city)

        geocode_url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={city_encoded}&count=1&language=en&format=json"
        )

        with urllib.request.urlopen(geocode_url, timeout=10) as response:
            geocode_data = json.loads(response.read().decode())

        results = geocode_data.get("results")

        if not results:
            return {
                "success": False,
                "message": f"Could not find the city {city}."
            }

        location = results[0]

        latitude = location["latitude"]
        longitude = location["longitude"]
        city_name = location["name"]
        country = location.get("country", "")

        time_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&current=temperature_2m"
            "&timezone=auto"
        )

        with urllib.request.urlopen(time_url, timeout=10) as response:
            time_data = json.loads(response.read().decode())

        current_time = time_data["current"]["time"]
        timezone_name = time_data.get("timezone", "")

        return {
            "success": True,
            "city": city_name,
            "country": country,
            "current_time": current_time,
            "timezone": timezone_name
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


def get_latest_news(topic):
    try:
        topic_encoded = urllib.parse.quote(topic)

        news_url = (
            "https://news.google.com/rss/search"
            f"?q={topic_encoded}"
            "&hl=en-IN"
            "&gl=IN"
            "&ceid=IN:en"
        )

        with urllib.request.urlopen(news_url, timeout=10) as response:
            rss_data = response.read()

        root = ET.fromstring(rss_data)

        items = root.findall(".//item")

        if not items:
            return {
                "success": False,
                "message": f"No recent news found for {topic}."
            }

        headlines = []

        for item in items[:5]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            published = item.findtext("pubDate", "").strip()
            source = item.findtext("source", "").strip()

            headlines.append(
                {
                    "title": title,
                    "source": source if source else "Unknown source",
                    "published": published,
                    "link": link
                }
            )

        return {
            "success": True,
            "topic": topic,
            "instruction": (
                "When summarizing these headlines, mention the publisher"
                "for each important story."
            ),
            "headlines": headlines
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


async def connect_ui_bridge():
    global ui_socket

    ui_socket = await websockets.connect(
        "ws://127.0.0.1:8000/agent"
    )

    print("Connected to Auralyn UI bridge.")


async def send_ui_event(event):
    if ui_socket is None:
        return

    try:
        await ui_socket.send(
            json.dumps(event)
        )

    except Exception as e:
        print("UI bridge send error:", e)


async def receive_messages(websocket, ready_event):
    global agent_speaking, last_user_text

    pending_tools = []

    audio = pyaudio.PyAudio()

    output_stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=24000,
        output=True
    )

    try:
        async for raw_message in websocket:
            event = json.loads(raw_message)
            event_type = event.get("type")

            if event_type == "session.ready":
                print("Session ready!")
                print("Session ID:", event.get("session_id"))

            elif event_type == "input.speech.started":
                print("\nListening...")

            elif event_type == "input.speech.stopped":
                print("Processing...")

                await send_ui_event(
                    {
                        "type": "state",
                        "state": "Thinking"
                    }
                )

            elif event_type == "transcript.user":
                text = event.get("text", "").strip()

                if text and text == last_user_text:
                    print(
                        "Duplicate user transcript ignored:",
                        text
                    )
                    continue

                print("You:", text)

                if text:
                    last_user_text = text

                    conversation_history.append(
                        {
                            "role": "user",
                            "text": text
                        }
                    )

                    save_conversation()

                    await send_ui_event(
                        {
                            "type": "transcript.user",
                            "text": text
                        }
                    )

            elif event_type == "tool.call":
                tool_name = event.get("name")
                arguments = event.get("arguments", {})

                print("Tool requested:", tool_name)
                print("Tool arguments:", arguments)

                await send_ui_event(
                    {
                        "type": "tool.call",
                        "name": tool_name,
                        "arguments": arguments
                    }
                )

                if tool_name == "get_weather":
                    city = arguments.get("city", "")

                    result = await asyncio.to_thread(
                        get_weather,
                        city
                    )

                elif tool_name == "get_current_time":
                    city = arguments.get("city", "")

                    result = await asyncio.to_thread(
                        get_current_time,
                        city
                    )

                elif tool_name == "get_latest_news":
                    topic = arguments.get("topic", "")

                    result = await asyncio.to_thread(
                        get_latest_news,
                        topic
                    )

                else:
                    result = {
                        "success": False,
                        "message": f"Unknown tool: {tool_name}"
                    }

                pending_tools.append(
                    {
                        "call_id": event["call_id"],
                        "result": result
                    }
                )

            elif event_type == "transcript.agent":
                text = event.get("text", "").strip()

                print("Auralyn:", text)

                if text:
                    conversation_history.append(
                        {
                            "role": "assistant",
                            "text": text
                        }
                    )

                    save_conversation()

                    await send_ui_event(
                        {
                            "type": "transcript.agent",
                            "text": text
                        }
                    )

            elif event_type == "reply.started":
                agent_speaking = True

                print("Auralyn is responding...")

                await send_ui_event(
                    {
                        "type": "state",
                        "state": "Speaking"
                    }
                )

            elif event_type == "reply.audio":
                audio_bytes = base64.b64decode(
                    event["data"]
                )

                await asyncio.to_thread(
                    output_stream.write,
                    audio_bytes
                )

            elif event_type == "reply.done":
                agent_speaking = False

                await send_ui_event(
                    {
                        "type": "state",
                        "state": "Listening"
                    }
                )

                print("Auralyn finished speaking.")

                if not ready_event.is_set():
                    ready_event.set()

                if event.get("status") == "interrupted":
                    pending_tools.clear()

                elif pending_tools:
                    for tool in pending_tools:

                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "tool.result",
                                    "call_id": tool["call_id"],
                                    "result": json.dumps(
                                        tool["result"]
                                    )
                                }
                            )
                        )

                        print(
                            "Tool result sent:",
                            tool["result"]
                        )

                    pending_tools.clear()

            elif event_type == "session.error":
                print("ERROR:", event)

    finally:
        output_stream.stop_stream()
        output_stream.close()
        audio.terminate()


def save_conversation():
    if not conversation_history:
        return

    os.makedirs(
        "conversations",
        exist_ok=True
    )

    with open(
        SESSION_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            conversation_history,
            file,
            indent=4,
            ensure_ascii=False
        )


def load_latest_conversation():
    files = glob.glob(
        "conversations/conversation_*.json"
    )

    if not files:
        return []

    latest_file = max(
        files,
        key=os.path.getmtime
    )

    try:
        with open(
            latest_file,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except (
        json.JSONDecodeError,
        OSError
    ):
        print(
            "Could not load previous conversation."
        )
        return []


def build_history_text():
    previous_history = (
        load_latest_conversation()
    )

    if not previous_history:
        return ""

    recent_messages = (
        previous_history[-6:]
    )

    history_text = (
        "\nRecent conversation history:\n"
    )

    for item in recent_messages:
        role = item.get(
            "role",
            "unknown"
        )

        text = item.get(
            "text",
            ""
        )

        history_text += (
            f"{role}: {text}\n"
        )

    return history_text


async def receive_ui_commands(assembly_ws):
    global ui_socket

    if ui_socket is None:
        return

    while True:
        try:
            message = await ui_socket.recv()
            data = json.loads(message)

            if data.get("type") != "quick_action":
                continue

            action = data.get("action")

            print("UI quick action received:", action)

            if action == "weather":
                city = data.get("city", "Mumbai")

                result = await asyncio.to_thread(
                    get_weather,
                    city
                )

                await send_ui_event(
                    {
                        "type": "tool.call",
                        "name": "get_weather",
                        "arguments": {
                            "city": city
                        }
                    }
                )

                await send_ui_event(
                    {
                        "type": "tool_result",
                        "name": "get_weather",
                        "result": result
                    }
                )

            elif action == "world_time":
                city = data.get("city", "London")

                result = await asyncio.to_thread(
                    get_current_time,
                    city
                )

                print("World time result:", result)

                await send_ui_event(
                    {
                        "type": "tool.call",
                        "name": "get_current_time",
                        "arguments": {
                            "city": city
                        }
                    }
                )

                await send_ui_event(
                    {
                        "type": "tool_result",
                        "name": "get_current_time",
                        "result": result
                    }
                )

            elif action == "latest_news":
                topic = data.get("topic", "OpenAI")

                result = await asyncio.to_thread(
                    get_latest_news,
                    topic
                )

                print("Latest news result:", result)

                await send_ui_event(
                    {
                        "type": "tool.call",
                        "name": "get_latest_news",
                        "arguments": {
                            "topic": topic
                        }
                    }
                )

                await send_ui_event(
                    {
                        "type": "tool_result",
                        "name": "get_latest_news",
                        "result": result
                    }
                )

        except Exception as e:
            print("UI command error:", e)
            break


async def main():
    await connect_ui_bridge()
    if not API_KEY:
        print(
            "AssemblyAI API key not found."
        )
        return

    headers = {
        "Authorization":
        f"Bearer {API_KEY}"
    }

    history_text = build_history_text()

    async with websockets.connect(
        URL,
        additional_headers=headers,
        family=socket.AF_INET
    ) as websocket:

        print(
            "Connected to AssemblyAI."
        )

        session_config = {
            "type": "session.update",
            "session": {

                "system_prompt": (
                    "You are Auralyn, a helpful real-time AI voice assistant. "
                    "Respond in clear natural English. "
                    "Answer general questions accurately and conversationally. "
                    "You can explain concepts, help with learning, answer technical questions, "
                    "brainstorm ideas, assist with everyday tasks, and hold natural conversations. "
                    "Keep spoken responses concise unless the user asks for more detail. "
                    "Do not interrupt the user while they are thinking or speaking. "
                    "Ask follow-up questions only when genuinely useful. "
                    "If you are uncertain, say so instead of making something up. "
                    "When answering from the news tool, mention the publisher or source for important headlines when available. "
                    "Do not present a news claim as certain if the headline itself is tentative or uses words like reportedly, may, or alleged. "
                    "Be friendly, professional, and conversational. "
                    "Use recent conversation history only when relevant."
                    "Wait patiently for the user to finish speaking. "
                    "Do not treat short pauses as the end of the user's thought. "
                    "For normal voice questions, keep answers to about 2 to 4 sentences. "
                    "Give longer explanations only when the user explicitly asks for the detail. "
                    + history_text
                ),
                "greeting": (
                    "Hello! I'm Auralyn, "
                    "your AI voice assistant. "
                    "What can I help you with today?"
                ),

                "tools": [
                    {
                        "type": "function",
                        "name": "get_weather",
                        "description": "Get the current weather for a city.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                    "description": "The city whose current weather is requested."
                                }
                            },
                            "required": ["city"]
                        }

                    },

                    {
                        "type": "function",
                        "name": "get_current_time",
                        "description": "Get the current local date and time for a city.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                    "description": "The city whose current local date and time is requested."
                                }
                            },
                            "required": ["city"]
                        }
                    },

                    {
                        "type": "function",
                        "name": "get_latest_news",
                        "description": "Get recent news headlines about a topic.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "topic": {
                                    "type": "string",
                                    "description": "The news topic for."
                                }
                            },
                            "required": ["topic"]
                        }
                    }

                ],

                "input": {
                    "turn_detection": {
                        "vad_threshold": 0.6,
                        "interrupt_response": False
                    }
                },

                "output": {
                    "voice": "anna"
                }
            }
        }

        await websocket.send(
            json.dumps(session_config)
        )

        print(
            "Session configuration sent."
        )

        ready_event = asyncio.Event()

        await asyncio.gather(
            send_microphone_audio(
                websocket,
                ready_event
            ),
            receive_messages(
                websocket,
                ready_event
            ),
            receive_ui_commands(websocket)
        )


try:
    asyncio.run(main())

except KeyboardInterrupt:
    print(
        "\nAuralyn stopped."
    )


except Exception as e:
    print("\nUnexpected error:")
    traceback.print_exc()

finally:
    save_conversation()

    if conversation_history:
        print(f"Conversation saved to: {SESSION_FILE}")
