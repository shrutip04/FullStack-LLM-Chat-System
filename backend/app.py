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
ALLOWED_EXTENSIONS = {"pdf", "docx"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- STREAM LOCK ----------
active_streams = set()

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ✅ AUTO DB + TABLE CREATION (ONLY NEW FEATURE)
def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        role TEXT,
        content TEXT,
        title TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        filename TEXT,
        content TEXT
    )
    """)

    db.commit()
    db.close()

# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------- FILE UTILS ----------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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
                    {"role": "user", "content": text[:6000] if len(text) > 100 else "Summarize this document."}
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

# ---------- LOAD CHAT ----------
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

    active_streams.discard(chat_id)
    active_streams.add(chat_id)

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) FROM messages WHERE chat_id=?", (chat_id,))
    is_first = cur.fetchone()[0] == 0

    title = generate_title(message) if is_first else None

    cur.execute(
        "INSERT INTO messages (chat_id, role, content, title) VALUES (?, ?, ?, ?)",
        (chat_id, "user", message, title)
    )
    db.commit()

    cur.execute("""
        SELECT role, content
        FROM messages
        WHERE chat_id=?
        ORDER BY id DESC
        LIMIT 6
    """, (chat_id,))
    history = cur.fetchall()[::-1]

    cur.execute(
        "SELECT content FROM documents WHERE chat_id=? ORDER BY id DESC LIMIT 1",
        (chat_id,)
    )
    row = cur.fetchone()
    db.close()

    doc_context = row[0] if row else ""

    messages = [{
        "role": "system",
        "content": "Answer clearly and concisely. Keep responses under 150 words."
    }]

    if doc_context:
        messages.append({
            "role": "system",
            "content": (
                "You are a document assistant.\n"
                "- Answer ONLY from the document summary.\n"
                "- If information is missing, say you don't know.\n\n"
                f"DOCUMENT SUMMARY:\n{doc_context[:1200]}"
            )
        })

    messages.extend({"role": r, "content": c} for r, c in history)

    def generate():
        full_reply = ""
        r = None

        try:
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

            for chunk in r.iter_lines():
                if chat_id not in active_streams:
                    break

                if not chunk:
                    continue

                try:
                    data = json.loads(chunk.decode())
                    token = data.get("message", {}).get("content")
                    if token:
                        full_reply += token
                        yield token
                except:
                    continue

            db2 = get_db()
            cur2 = db2.cursor()
            cur2.execute(
                "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, "assistant", full_reply)
            )
            db2.commit()
            db2.close()

        finally:
            active_streams.discard(chat_id)
            if r:
                r.close()

    return Response(stream_with_context(generate()), mimetype="text/plain")

# ---------- STOP STREAM ----------
@app.route("/stop/<chat_id>", methods=["POST"])
def stop_stream(chat_id):
    active_streams.discard(chat_id)
    return jsonify({"status": "stopped"})

# ---------- FILE UPLOAD ----------
@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    chat_id = request.form.get("chat_id")

    if not file:
        return jsonify({"error": "No file received"}), 400

    if not chat_id:
        return jsonify({"error": "Missing chat_id"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
    path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(path)
    except Exception as e:
        return jsonify({"error": f"File save failed: {str(e)}"}), 500

    text = ""

    try:
        if filename.lower().endswith(".pdf"):
            reader = PdfReader(path)
            for p in reader.pages:
                try:
                    t = p.extract_text()
                    if t:
                        text += t + "\n"
                except:
                    continue

        elif filename.lower().endswith(".docx"):
            doc = Document(path)
            for para in doc.paragraphs:
                text += para.text + "\n"

    except Exception as e:
        return jsonify({"error": f"Document read failed: {str(e)}"}), 500

    if not text.strip() or len(text.strip()) < 50:
        return jsonify({"error": "Could not extract readable text"}), 400

    summary = summarize_document(text)
    if not summary.strip():
        summary = "Document uploaded but summary unavailable."

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
    init_db()   # ✅ ONLY NEW LINE ADDED
    app.run(debug=True)
