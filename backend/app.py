from flask import Flask, request, jsonify, render_template, Response, stream_with_context
import sqlite3
import requests
import json
import uuid
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from docx import Document
import os

app = Flask(__name__)

# ---------------- CONFIG ----------------
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3:8b"
DB_PATH = "chat.db"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------- GENERATE CHAT TITLE ----------
def generate_title(user_message):
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "user", "content": f"Generate a short chat title (max 5 words): {user_message}"}
                ]
            },
            timeout=15
        )
        return r.json().get("message", {}).get("content", "")[:40]
    except:
        return user_message[:40]
    

# ---------- SUMMARIZE DOCUMENT ----------
def summarize_document(text):
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": "Summarize this document clearly for later Q&A."},
                    {"role": "user", "content": text[:6000]}
                ]
            },
            timeout=60
        )
        return r.json().get("message", {}).get("content", "")
    except:
        return ""

# ---------- NEW CHAT ----------
@app.route("/new_chat", methods=["POST"])
def new_chat():
    return jsonify({"chat_id": str(uuid.uuid4())})

# ---------- SIDEBAR CHAT LIST ----------
@app.route("/chats", methods=["GET"])
def list_chats():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT chat_id,
               COALESCE(MAX(title), MIN(content)) AS preview
        FROM messages
        WHERE role='user'
        GROUP BY chat_id
        ORDER BY MIN(id) DESC
    """)

    data = [{"chat_id": r[0], "preview": r[1]} for r in cur.fetchall()]
    db.close()
    return jsonify(data)

# ---------- LOAD CHAT (LAST 30) ----------
@app.route("/chat/<chat_id>", methods=["GET"])
def load_chat(chat_id):
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT role, content
        FROM messages
        WHERE chat_id=?
        ORDER BY id DESC
        LIMIT 30
    """, (chat_id,))

    rows = cur.fetchall()[::-1]
    db.close()

    return jsonify([{"role": r, "content": c} for r, c in rows])

# ---------- DELETE CHAT ----------
@app.route("/chat/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    db.commit()
    db.close()
    return jsonify({"status": "deleted"})

# ---------- MAIN CHAT ----------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message")
    chat_id = data.get("chat_id")

    if not message or not chat_id:
        return jsonify({"error": "Missing data"}), 400

    db = get_db()
    cur = db.cursor()

    # First message?
    cur.execute("SELECT COUNT(*) FROM messages WHERE chat_id=?", (chat_id,))
    is_first = cur.fetchone()[0] == 0

    title = generate_title(message) if is_first else None

    # Save user message
    cur.execute(
        "INSERT INTO messages (chat_id, role, content, title) VALUES (?, ?, ?, ?)",
        (chat_id, "user", message, title)
    )
    db.commit()

    # ---- Load recent messages (sliding window) ----
    cur.execute("""
        SELECT role, content
        FROM messages
        WHERE chat_id=?
        ORDER BY id DESC
        LIMIT 6
    """, (chat_id,))
    history = cur.fetchall()[::-1]

    # ---- Load document summaries ----
    cur.execute("SELECT content FROM documents WHERE chat_id=? ORDER BY id DESC", (chat_id,))
    docs = cur.fetchall()
    db.close()

    doc_context = "\n\n".join(d[0] for d in docs) if docs else ""

    messages = []

    if doc_context:
        messages.append({
            "role": "system",
            "content": (
                 "You are a document assistant.\n"
        "- If the user asks to summarize, rewrite the document summary clearly.\n"
        "- If the user asks a question, answer ONLY from the document summary.\n"
        "- If information is not present, say you don't know.\n\n"
           f"DOCUMENT SUMMARY:\n{doc_context[:1200]}"
            )
        })

    messages.extend({"role": r, "content": c} for r, c in history)

    # ---- STREAM RESPONSE ----
    def generate():
        yield ""  # flush early

        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": True
            },
            stream=True,
            timeout=120
        )

        full_reply = ""

        for line in r.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line.decode())
                token = chunk.get("message", {}).get("content")
                if token:
                    full_reply += token
                    yield token
            except:
                continue

        # Save assistant reply safely
        db2 = get_db()
        cur2 = db2.cursor()
        cur2.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, "assistant", full_reply)
        )
        db2.commit()
        db2.close()

    return Response(stream_with_context(generate()), mimetype="text/plain")

# ---------- FILE UPLOAD ----------
@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    chat_id = request.form.get("chat_id")

    if not file or not chat_id:
        return jsonify({"error": "Missing file or chat_id"}), 400

    filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    text = ""

    try:
        if filename.lower().endswith(".pdf"):
            reader = PdfReader(path)
            for p in reader.pages:
                extracted = p.extract_text()
                if extracted:
                    text += extracted + "\n"

            if not text.strip():
                text = "This document contains limited readable text."

        elif filename.lower().endswith(".docx"):
            doc = Document(path)
            for para in doc.paragraphs:
                text += para.text + "\n"

        else:
            return jsonify({"error": "Unsupported file type"}), 400

    except Exception as e:
        print("FILE READ ERROR:", e)
        text = "Error reading document."

    summary = summarize_document(text)

    if not summary.strip():
        summary = "Document uploaded successfully, but summary could not be generated."

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO documents (chat_id, filename, content) VALUES (?, ?, ?)",
        (chat_id, filename, summary)
    )
    db.commit()
    db.close()

    return jsonify({"status": "uploaded", "filename": filename})


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
