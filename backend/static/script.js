let chatId = null;
let recognition = null;

// --------------------
// START NEW CHAT
// --------------------
async function startNewChat() {
    try {
        const res = await fetch("/new_chat", { method: "POST" });
        const data = await res.json();

        chatId = data.chat_id;
        document.getElementById("chat-box").innerHTML = "";

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
    }

    loadChatHistory();
}

// --------------------
// SEND MESSAGE (STREAMING)
// --------------------
async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message || !chatId) return;

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
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Text + blinking cursor (ChatGPT-style)
            aiMsg.innerHTML = `${buffer}<span class="cursor">▍</span>`;
            box.scrollTop = box.scrollHeight;
        }

        // AFTER streaming finishes → render markdown ONCE
        aiMsg.innerHTML = marked.parse(buffer);

        // 🔊 Speaker button (ChatGPT-style)
        const speakBtn = document.createElement("span");
        speakBtn.innerText = " 🔊";
        speakBtn.style.cursor = "pointer";
        speakBtn.title = "Read aloud";
        speakBtn.onclick = () => speak(buffer);

        aiMsg.appendChild(speakBtn);


    } catch (err) {
        console.error(err);
        aiMsg.innerText = "⚠️ Connection error";
    }
}

// --------------------
// ADD MESSAGE TO UI
// --------------------
function addMessage(text, role) {
    const box = document.getElementById("chat-box");
    const msg = document.createElement("div");

    msg.className = role === "assistant" ? "assistant" : "user";

    if (role === "assistant") {
        msg.innerHTML = marked.parse(text);
    } else {
        msg.innerText = text;
    }

    box.appendChild(msg);
    box.scrollTop = box.scrollHeight;
}

function trimMessages(max = 120) {
    const box = document.getElementById("chat-box");
    while (box.children.length > max) {
        box.removeChild(box.firstChild);
    }
}


// --------------------
// ENTER KEY SUPPORT
// --------------------
document.addEventListener("DOMContentLoaded", () => {
    startNewChat();

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
    if (!("webkitSpeechRecognition" in window)) {
        alert("Voice input not supported in this browser");
        return;
    }

    recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
        console.log("🎙️ Listening...");
    };

    recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;
        document.getElementById("user-input").value = text;
    };

    recognition.onerror = (event) => {
        console.error("Voice error:", event.error);
    };

    recognition.start();
}

// --------------------
// VOICE OUTPUT 🔊
// --------------------
function speak(text) {
    if (!window.speechSynthesis) return;

    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 1;
    utterance.pitch = 1;

    speechSynthesis.speak(utterance);
}

// --------------------
// FILE UPLOAD (PDF / DOCX)
// --------------------
document.getElementById("file-upload").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file || !chatId) return;

    addMessage(`📄 Uploading: ${file.name}`, "assistant");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("chat_id", chatId);

    try {
        const res = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (!res.ok) {
            addMessage(`⚠️ Upload failed: ${data.error}`, "assistant");
            return;
        }

        addMessage(
            `✅ File uploaded: ${file.name}\nYou can now ask questions about this document.`,
            "assistant"
        );

    } catch (err) {
        console.error(err);
        addMessage("⚠️ Upload error", "assistant");
    }

    e.target.value = ""; // reset input
});


