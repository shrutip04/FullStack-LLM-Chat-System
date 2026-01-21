let chatId = null;
let recognition = null;
let isStreaming = false;
let currentReader = null;
let stopRequested = false;


// --------------------
// START NEW CHAT
// --------------------
async function startNewChat() {
    try {
        const res = await fetch("/new_chat", { method: "POST" });
        const data = await res.json();

        chatId = data.chat_id;

        document.getElementById("chat-box").innerHTML = "";
        document.getElementById("empty-state").style.display = "none";

        await loadChatHistory();
    } catch (err) {
        console.error("Failed to start new chat", err);
        alert("Failed to start new chat");
    }
}

// --------------------
// LOAD CHAT HISTORY (SIDEBAR)
// --------------------
async function loadChatHistory() {
    const res = await fetch("/chats");
    const chats = await res.json();

    const list = document.getElementById("chat-list");
    if (!list) return;

    list.innerHTML = "";

    chats.forEach(chat => {
        const item = document.createElement("div");
        item.className = "chat-item";

        const title = document.createElement("span");
        title.innerText = chat.preview || "New Chat";
        title.onclick = () => openChat(chat.chat_id);

        const del = document.createElement("span");
        del.innerText = " 🗑";
        del.className = "delete-btn";
        del.onclick = (e) => {
            e.stopPropagation();
            deleteChat(chat.chat_id);
        };

        item.appendChild(title);
        item.appendChild(del);
        list.appendChild(item);
    });
}

// --------------------
// OPEN EXISTING CHAT
// --------------------
async function openChat(id) {
    chatId = id;
    isStreaming = false;
    currentReader = null;

    document.getElementById("empty-state").style.display = "none";

    const res = await fetch(`/chat/${id}`);
    const messages = await res.json();

    const box = document.getElementById("chat-box");
    box.innerHTML = "";

    messages.forEach(msg => {
        addMessage(msg.content, msg.role);
    });

    box.scrollTop = box.scrollHeight;
}

// --------------------
// DELETE CHAT
// --------------------
async function deleteChat(id) {
    if (!confirm("Delete this chat?")) return;

    await fetch(`/chat/${id}`, { method: "DELETE" });

    if (chatId === id) {
        chatId = null;
        document.getElementById("chat-box").innerHTML = "";
        document.getElementById("empty-state").style.display = "flex";
    }

    loadChatHistory();
}

// --------------------
// SEND MESSAGE (STREAMING)
// --------------------
async function sendMessage() {
    if (isStreaming) return;

    const input = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");
    const stopBtn = document.getElementById("stop-btn");

    const message = input.value.trim();
    if (!message) return;

    if (!chatId) {
        await startNewChat();
    }

    isStreaming = true;
    input.disabled = true;
    sendBtn.disabled = true;

    sendBtn.style.display = "none";
    stopBtn.style.display = "inline-block";

    document.getElementById("empty-state").style.display = "none";

    addMessage(message, "user");
    input.value = "";

    const box = document.getElementById("chat-box");

    const aiMsg = document.createElement("div");
    aiMsg.className = "assistant";
    aiMsg.innerHTML = '<em class="thinking">Thinking</em>';

    box.appendChild(aiMsg);
    box.scrollTop = box.scrollHeight;

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                chat_id: chatId
            })
        });

        if (!res.ok || !res.body) {
            aiMsg.innerText = "⚠️ Server error";
            resetInput();
            return;
        }

        currentReader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let buffer = "";

        while (!stopRequested) {
            const { value, done } = await currentReader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            aiMsg.innerHTML = `${buffer}<span class="cursor">▍</span>`;
            box.scrollTop = box.scrollHeight;
        }

        aiMsg.innerHTML = marked.parse(buffer);

        const speakBtn = document.createElement("span");
        speakBtn.innerText = " 🔊";
        speakBtn.style.cursor = "pointer";
        speakBtn.title = "Read aloud";
        speakBtn.onclick = () => speak(buffer);
        aiMsg.appendChild(speakBtn);

    } catch (err) {
        console.error(err);
        aiMsg.innerText = "⚠️ Connection error";
    } finally {
        resetInput();
    }

    stopRequested = false;
}

// --------------------
// STOP GENERATING
// --------------------
async function stopStreaming() {
    stopRequested = true;

    if (currentReader) {
        try { currentReader.cancel(); } catch {}
        currentReader = null;
    }

    if (chatId) {
        fetch(`/stop/${chatId}`, { method: "POST" });
    }

    resetInput();
}

// --------------------
// RESET INPUT STATE
// --------------------
function resetInput() {
    const input = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");
    const stopBtn = document.getElementById("stop-btn");

    isStreaming = false;
    input.disabled = false;
    sendBtn.disabled = false;

    sendBtn.style.display = "inline-block";
    stopBtn.style.display = "none";

    input.focus();
}

// --------------------
// ADD MESSAGE TO UI
// --------------------
function addMessage(text, role, forcePlain = false) {
    const box = document.getElementById("chat-box");
    const msg = document.createElement("div");

    msg.className = role === "assistant" ? "assistant" : "user";

    if (role === "assistant" && !forcePlain) {
        msg.innerHTML = marked.parse(text);
    } else {
        msg.innerText = text;
    }

    box.appendChild(msg);
    box.scrollTop = box.scrollHeight;
}

// --------------------
// ENTER KEY SUPPORT
// --------------------
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("user-input");

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

// --------------------
// VOICE INPUT 🎙️
// --------------------
function startVoice() {
    if (isStreaming) return;

    if (!("webkitSpeechRecognition" in window)) {
        alert("Voice input not supported");
        return;
    }

    recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (event) => {
        document.getElementById("user-input").value =
            event.results[0][0].transcript;
    };

    recognition.start();
}

// --------------------
// VOICE OUTPUT 🔊
// --------------------
function speak(text) {
    if (!window.speechSynthesis) return;

    speechSynthesis.cancel();
    speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

// --------------------
// FILE UPLOAD (🔥 FIXED)
// --------------------
document.getElementById("file-upload").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file || isStreaming) return;

    if (!chatId) {
        await startNewChat();
    }

    addMessage(`📄 Uploading: ${file.name}`, "assistant", true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("chat_id", chatId);

    try {
        const res = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        let data;
        try {
            data = await res.json();
        } catch {
            addMessage("⚠️ Server returned invalid response", "assistant", true);
            return;
        }

        if (!res.ok) {
            addMessage(`⚠️ Upload failed: ${data.error || "Unknown error"}`, "assistant", true);
            return;
        }

        addMessage(
            `✅ File uploaded: ${file.name}\nYou can now ask questions about this document.`,
            "assistant",
            true
        );

        // 🔥 THIS IS THE KEY LINE
        await openChat(chatId);

    } catch (err) {
        console.error(err);
        addMessage("⚠️ Upload error", "assistant", true);
    }

    e.target.value = "";
});
