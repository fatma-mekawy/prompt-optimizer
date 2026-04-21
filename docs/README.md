# AI Prompt Analyzer

Analyzes and optimizes user prompts to improve LLM responses. Supports text and voice input.

## 🛠 Tech Stack

- **LLM**: [Groq API](https://console.groq.com) running `llama-3.1-8b-instant` (requires free API key)
- **Voice**: `faster-whisper` with `small` model (~465 MB, CPU only)
- **Backend**: FastAPI + Pydantic
- **Frontend**: Plain HTML/JS served directly by FastAPI at `/`

## 📦 Prerequisites

1. Python 3.10+
2. A free [Groq API key](https://console.groq.com)

## 🚀 Setup

### 1. Clone and install

```bash
git clone <repo>
cd ai-prompt-analyzer
pip install -r requirements.txt
```

### 2. Set your Groq API key

```bash
export GROQ_API_KEY=your_groq_api_key_here
```

> 💡 Get a free API key at [console.groq.com](https://console.groq.com). No credit card required.

### 3. Start the backend

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open the app

Navigate to **http://localhost:8000** — the frontend is served automatically by FastAPI.

### 5. Run tests

```bash
pytest
```

## 📡 API Endpoints

| Method   | Path                  | Description                |
| -------- | --------------------- | -------------------------- |
| GET      | `/`                   | Serves the frontend UI     |
| POST     | `/analyze`            | Analyze text prompt        |
| POST     | `/analyze/voice`      | Analyze voice prompt       |
| GET      | `/history/{user_id}`  | Get conversation history   |
| DELETE   | `/history/{user_id}`  | Clear history              |

Interactive docs: http://localhost:8000/docs

## 🔒 Guardrails

The analyzer includes built-in safety layers:

- **Input validation** — enforces prompt length limits (2–3000 chars)
- **Injection detection** — flags common prompt injection and jailbreak patterns
- **Output filtering** — redacts accidental leakage of system internals

## 🧠 How It Works

1. Your prompt is validated and checked for injection attempts.
2. Conversation history (last 10 messages) is retrieved for context.
3. A Chain-of-Thought prompt is sent to the Groq LLM.
4. The structured JSON response is parsed into issues, suggestions, and an improved prompt.
5. Results are cached (up to 100 entries) and saved to per-user memory (up to 20 messages).

## 🎙 Voice Input

Upload an audio file (`wav`, `mp3`, `m4a`, `ogg`, `webm`) to `/analyze/voice`. The `faster-whisper` `small` model transcribes it locally on CPU, then the transcribed text goes through the same analysis pipeline.

> **Note:** The Whisper model is loaded lazily on first use (~465 MB download).