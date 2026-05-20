# MACE AI Academy Intelligent RAG Chatbot

Production-ready Retrieval-Augmented Generation (RAG) chatbot for **MACE AI Academy** — course counseling, syllabus details, fees, and placement FAQs grounded in your document knowledge base.

## Quick start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- [Groq API key](https://console.groq.com/)

### 1. Environment

From the project root:

```bash
copy .env.example .env
```

Set `GROQ_API_KEY` in `.env`. Default LLM: `llama-3.3-70b-versatile` (Groq decommissioned `llama3-70b-8192`).

### 2. Backend

```bash
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
pip install email-validator
python -m backend.ingest
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

### 4. Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Project structure

```text
mace-ai-chatbot/
├── backend/
│   ├── app.py           # FastAPI routes
│   ├── ingest.py        # Document loading & ChromaDB indexing
│   ├── rag_pipeline.py  # Retrieval + Groq generation
│   ├── chatbot.py       # SQLite sessions & orchestration
│   ├── config.py        # Settings (project-root paths)
│   ├── prompts.py       # RAG prompt templates
│   └── utils.py         # JWT, bcrypt, logging
├── frontend/            # React + Vite + Tailwind
├── data/                # Course TXT/PDF/DOCX/CSV sources
├── chroma_db/           # Vector store (generated)
├── docker-compose.yml
└── .env.example
```

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health + vector store status |
| POST | `/auth/register` | No | Create account |
| POST | `/auth/login` | No | JWT login |
| POST | `/chat` | Yes | RAG chat |
| POST | `/upload` | Yes | Upload & re-index document |
| POST | `/reingest` | Yes | Rebuild ChromaDB from `data/` |
| POST | `/leads` | No | Callback form |

## Test with curl

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Student\",\"email\":\"you@example.com\",\"password\":\"secure123\"}"

curl -X POST http://127.0.0.1:8000/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"you@example.com\",\"password\":\"secure123\"}"
```

Use the returned `access_token` as `Authorization: Bearer <token>` for `/chat`, `/conversations`, etc.
