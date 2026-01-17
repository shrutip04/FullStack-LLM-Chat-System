# Persistent LLM Chat System – ChatGPT-like Conversational AI Backend

A full-stack **ChatGPT-style conversational AI system** built from scratch with a strong focus on **backend architecture**, **persistent memory**, and **real-time streaming responses**.  
This project goes beyond a basic chatbot by implementing session-based conversations, context window management, and document-augmented interactions using a local LLM.

---

## 🚀 Demo

Screenshots and demo media are available in the `/assets` folder.

- ChatGPT-like chat interface with streaming responses  
- Multiple chat sessions with persistent history  
- Smooth UX with typing indicators and blinking cursor  

---

## ✨ Key Features

- 🧠 **Persistent Chat Memory**
  - Session-based conversations stored in SQLite
  - Users can switch between chats and resume context seamlessly

- 🔁 **Sliding Context Window**
  - Efficient context handling to balance performance and response quality
  - Prevents token overflow while maintaining conversational relevance

- ⚡ **Streaming LLM Responses**
  - Token-by-token response streaming for a ChatGPT-like experience
  - Real-time typing indicator on the frontend

- 📁 **Document Upload & RAG (One-time Summarization)**
  - Supports PDF and DOCX uploads
  - Documents are summarized once and injected into chat context when required

- 🧩 **Multiple Chat Sessions**
  - Sidebar-based chat management
  - Each session maintains independent memory

- 📤 **Conversation Export**
  - Export chat history for later reference

- 🎨 **Clean & Responsive UI**
  - Modern ChatGPT-inspired interface
  - Optimized rendering and smooth interactions

---

## 🔍 Skills & Keywords Demonstrated

- Backend Development
- REST API Design
- Large Language Models (LLMs)
- Conversational AI Systems
- ChatGPT-like Architecture
- Session-based State Management
- Persistent Storage (SQLite)
- Streaming API Responses
- Context Window Management
- Retrieval-Augmented Generation (RAG)
- Full-Stack Web Development
- System Design & Architecture
- Performance Optimization
- Local LLM Inference

---

## 🛠️ Tech Stack

### Backend
- Python
- Flask
- SQLite
- REST APIs with streaming responses

### Frontend
- HTML
- CSS
- JavaScript

### LLM & AI
- Ollama
- llama3:8b (local inference)

---

## 🧱 System Architecture (High Level)

1. Frontend sends user messages to the Flask API  
2. Backend retrieves session-specific chat history from SQLite  
3. A sliding context window is applied to optimize inference  
4. Document summaries (if present) are injected into the prompt  
5. The LLM generates responses via Ollama  
6. Tokens are streamed back to the frontend in real time  
7. Conversations are persisted for future sessions  

---

## 🧠 Engineering Focus

This project focuses on solving real backend challenges such as:
- Maintaining conversational state across sessions
- Efficient context handling for LLM inference
- Streaming responses for real-time UX
- Designing scalable and persistent chat memory

The goal was to replicate **core architectural concepts behind ChatGPT-style systems**, not to build a simple rule-based chatbot.

---

## ▶️ How to Run Locally

### Prerequisites
- Python 3.9+
- Ollama installed and running
- llama3:8b model pulled

### Setup

```bash
git clone https://github.com/shrutip04/Persistent-LLM-Chat-System.git
cd Persistent-LLM-Chat-System
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
````

### Run the Application

```bash
python app.py
```

Open your browser at:

```
http://127.0.0.1:5000
```

---

## 🔒 Security Notes

* `.env` files are excluded from version control
* API keys and sensitive data are not committed
* Local LLM inference avoids third-party API exposure

---

## 📈 Future Improvements

* User authentication and accounts
* Vector database integration for advanced RAG
* Dockerization and cloud deployment
* Role-based memory handling
* Hybrid C++ backend using `pybind11`

---

## 📌 Why This Project Matters

This project demonstrates practical experience in:

* Designing backend systems for conversational AI
* Managing persistent state and memory
* Implementing real-time streaming architectures
* Integrating LLMs beyond tutorial-level usage

It is intended as a **portfolio-grade project** for software engineering, backend, and AI internships.

---

## 👩‍💻 Author

**Shruti Pawar**
Computer Engineering Student

