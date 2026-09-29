const micButton = document.getElementById("micButton");
const waveform = document.getElementById("waveform");
const messages = document.getElementById("messages");

const stateIndicator = document.querySelector(".state-indicator");
const stateText = stateIndicator ? stateIndicator.childNodes[2] : null;

const clearButton = document.querySelector(".clear-button");
const promptChips = document.querySelectorAll(".prompt-chip");

const backendSocket = new WebSocket(
    `ws://${window.location.host}/ws`
);

backendSocket.addEventListener("open", () => {
    console.log("Connected to Auralyn backend.")

    backendSocket.send(
        JSON.stringify({
            type: "browser.ready"
        })
    );
});

backendSocket.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);

    console.log("Backend event:", data);

    if (data.type === "connection") {
        console.log(data.message);
    }

    else if (data.type === "transcript.user") {
        addUserMessage(data.text);
    }

    else if (data.type === "transcript.agent") {
        addAssistantMessage(data.text);
    }

    else if (data.type === "state") {
        setAssistantState(data.state);
    }

    else if (data.type === "tool.call") {
        let toolName = data.name || "tool";

        if (toolName === "get_weather") {
            toolName = "Weather";
        }

        if (toolName === "get_current_time") {
            toolName = "World Time";
        }

        if (toolName === "get_latest_news") {
            toolName = "Live News";
        }

        let details = "";

        if (data.arguments) {
            details = JSON.stringify(data.arguments);
        }

        const toolCard = addToolActivity(
            toolName,
            details
        );

        toolCard.dataset.toolName = data.name;
    }

       

    else if (data.type === "tool_result") {
        const result = data.result;

        const matchingToolCards = document.querySelectorAll(
        `.tool-activity[data-tool-name="${data.name}"]`
    );

    if (matchingToolCards.length > 0) {
        const latestToolCard =
            matchingToolCards[matchingToolCards.length - 1];

        const badge =
            latestToolCard.querySelector(".tool-badge");

        if (badge) {
            badge.textContent = "DONE";
        }

        if (data.source === "voice") {
            return;
        }
    }

        if (
            data.name === "get_weather" &&
            result &&
            result.success
        ) {
            const weatherText =
                `It is currently ${result.temperature_c}°C in ${result.city}, ` +
                `feels like ${result.feels_like_c}°C, ` +
                `with ${result.humidity_percent}% humidity and ` +
                `wind around ${result.wind_speed_kmh} km/h.`;

            addAssistantMessage(weatherText);

            setAssistantState("Listening");
        }

        if (
            data.name === "get_current_time" &&
            result &&
            result.success
        ) {
            const timePart =
                result.current_time.split("T")[1];

            const [hours, minutes] =
                timePart.split(":");

            let hour =
                parseInt(hours, 10);

            const period =
                hour >= 12 ? "PM" : "AM";

            hour = hour % 12;

            hour =
                hour === 0 ? 12 : hour;

            const formattedTime =
                `${hour}:${minutes} ${period}`;

            const timeText =
                `The current time in ${result.city} is ${formattedTime} ` +
                `(${result.timezone}).`;

            addAssistantMessage(timeText);

            setAssistantState("Listening");
        }

        if (
            data.name === "get_latest_news" &&
            result &&
            result.success
        ) {
            addAssistantMessage(
                `Here are the latest ${result.topic} headlines I found.`
            );

            if (
                Array.isArray(result.headlines)
            ) {
                result.headlines.forEach(
                    (item) => {

                        let publishedText = "";

                        if (item.published) {
                            const publishedDate = new Date(item.published);

                            publishedText = publishedDate.toLocaleString("en-IN", {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                                hour: "numeric",
                                minute: "2-digit",
                                hour12: true
                            });
                        }

                        addSourceCard(
                            item.source || "Unknown source",
                            item.title || "Untitled headline",
                            item.link || "#",
                            publishedText
                        );
                    }
                );
            }

            setAssistantState("Listening");
        }
    }
});

backendSocket.addEventListener("close", () => {
    console.log("Disconnected from Auralyn backend.");
});

backendSocket.addEventListener("error", (error) => {
    console.error(
        "WebSocket error:",
        error
    );
});

let micMuted = false;



if (micButton) {
    micButton.addEventListener("click", () => {
        micMuted = !micMuted;

        if (micMuted) {
            micButton.classList.add("muted");

            if (stateIndicator) {
                stateIndicator.innerHTML = `
                    <span class="state-dot"></span>
                    Microphone muted
                `;
            }

            if (waveform) {
                waveform.style.opacity = "0.25";
                waveform.style.animationPlayState = "paused";
            }

            const micText = document.querySelector(".mic-area p");

            if (micText) {
                micText.textContent = "Tap to activate microphone";
            }
        } else {
            micButton.classList.remove("muted");

            setAssistantState("Listening");

            if (waveform) {
                waveform.style.opacity = "1";
            }

            const micText = document.querySelector(".mic-area p");

            if (micText) {
                micText.textContent = "Tap to mute microphone";
            }
        }
    });
}


function setAssistantState(state) {
    if (!stateIndicator) return;

    stateIndicator.innerHTML = `
        <span class="state-dot"></span>
        ${state}
    `;

    const orb = document.querySelector(".voice-orb");

    if (!orb) return;

    orb.classList.remove(
        "state-listening",
        "state-thinking",
        "state-speaking"
    );

    if (state === "Listening") {
        orb.classList.add("state-listening");
    }

    if (state === "Thinking") {
        orb.classList.add("state-thinking");
    }

    if (state === "Speaking") {
        orb.classList.add("state-speaking");
    }
}


function addUserMessage(text) {
    const message = document.createElement("div");

    message.className = "message user-message";

    message.innerHTML = `
        <div class="message-content">

            <div class="message-meta user-meta">
                <span>now</span>
                <strong>You</strong>
            </div>

            <div class="message-bubble">
                ${escapeHTML(text)}
            </div>

        </div>

        <div class="message-avatar user-avatar">
            P
        </div>
    `;

    messages.appendChild(message);

    scrollMessagesToBottom();
}



function addAssistantMessage(text) {
    const message = document.createElement("div");

    message.className = "message assistant-message";

    message.innerHTML = `
        <div class="message-avatar">
            A
        </div>

        <div class="message-content">

            <div class="message-meta">
                <strong>Auralyn</strong>
                <span>now</span>
            </div>

            <div class="message-bubble">
                ${escapeHTML(text)}
            </div>

        </div>
    `;

    messages.appendChild(message);

    scrollMessagesToBottom();
}


function addToolActivity(toolName, description) {
    const tool = document.createElement("div");

    tool.className = "tool-activity";
    tool.dataset.toolName = "";

    tool.innerHTML = `
        <div class="tool-icon">
            ✦
        </div>

        <div>
            <strong>${escapeHTML(toolName)}</strong>
            <p>${escapeHTML(description)}</p>
        </div>

        <span class="tool-badge">
            LIVE
        </span>
    `;

    messages.appendChild(tool);

    scrollMessagesToBottom();

    return tool;
}


function addSourceCard(source, headline, link = "#", published = "") {
    const card = document.createElement("a");

    card.className = "source-card";
    card.href = link;
    card.target = "_blank";
    card.rel = "noopener noreferrer";

    card.innerHTML = `
        <div class="source-card-header">

            <div>
                <p class="source-label">
                    SOURCE
                </p>

                <strong>
                    ${escapeHTML(source)}
                </strong>
            </div>

            <span>
                ↗
            </span>

        </div>

        <p>
            ${escapeHTML(headline)}
        </p>

        ${published ? `<small class="source-time">${escapeHTML(published)}</small>` : ""}
    `;

    messages.appendChild(card);

    scrollMessagesToBottom();
}



promptChips.forEach((chip) => {
    chip.addEventListener("click", () => {
        const text = chip.textContent.trim();

        if (text.includes("Weather")) {
            if (backendSocket.readyState === WebSocket.OPEN) {
                addUserMessage("What's the weather in Mumbai?");
                setAssistantState("Thinking");

                backendSocket.send(
                    JSON.stringify({
                        type: "quick_action",
                        action: "weather",
                        city: "Mumbai"
                    })
                );
            }
        }

        if (text.includes("World Time")) {
            if (backendSocket.readyState === WebSocket.OPEN) {
                addUserMessage("What time is it in London?");
                setAssistantState("Thinking");

                backendSocket.send(
                    JSON.stringify({
                        type: "quick_action",
                        action: "world_time",
                        city: "London"
                    })
                );
            }
        }

        if (text.includes("Latest News")) {
            if (backendSocket.readyState === WebSocket.OPEN) {
                addUserMessage("What are the latest OpenAI news headlines?");
                setAssistantState("Thinking");

                backendSocket.send(
                    JSON.stringify({
                        type: "quick_action",
                        action: "latest_news",
                        topic: "OpenAI"
                    })
                );
            }
        }
    });
});


if (clearButton) {
    clearButton.addEventListener("click", () => {
        messages.innerHTML = "";

        addAssistantMessage(
            "Conversation cleared. What can I help you with?"
        );

        setAssistantState("Listening");
    });
}



const newChatButton = document.querySelector(".new-chat-btn");

if (newChatButton) {
    newChatButton.addEventListener("click", () => {
        messages.innerHTML = "";

        addAssistantMessage(
            "Hello! I'm Auralyn, your AI voice assistant. What can I help you with today?"
        );

        setAssistantState("Listening");
    });
}


function scrollMessagesToBottom() {
    messages.scrollTo({
        top: messages.scrollHeight,
        behavior: "smooth"
    });
}


function escapeHTML(value) {
    const div = document.createElement("div");

    div.textContent = value;

    return div.innerHTML;
}


setAssistantState("Listening");


