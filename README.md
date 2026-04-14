# CodeLens

CodeLens provides an intelligent Code Review and Reverse Engineering layer on top of **LTM Blueverse Foundry models**. It supports multi-language review (SQL, Groovy, OIC, Shell Scripts) with feature-rich analysis including interactive diff viewing, actionable Jira tickets, micro-tracked architecture metrics, and coding standard evaluations powered by a local FAISS RAG index.

---

## 🚀 Getting Started

You will need to run both the **Backend API** and the **Vite React Frontend** simultaneously to use the application.

### 1️⃣ Backend Setup (Terminal 1)

1. **Navigate to the backend directory and set up a Python Virtual Environment**:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt

3. **Configure Environment Variables**:
   Copy the example environment into a production `.env` file:
   ```powershell
   cp .env.example .env
   ```
   Open `.env` and fill out your specific configuration variables:
   - `BLUEVERSE_BEARER_TOKEN`: Your valid authorization bearer token.
   - `ORACLE_LINKS`: Comma-separated documentation links like `https://example.com/oracle-docs1`. The FAISS index builds a vector-store memory bank off of these rules.
4. **Boot up the server**:
   ```powershell
   uvicorn main:app --reload --port 8000
   ```
   *(The backend server will run on `http://localhost:8000` and immediately process the FAISS documentation vectors)*

---

### 2️⃣ Frontend Setup (Terminal 2)

1. **Navigate to the frontend React app**:
   ```powershell
   cd frontend/react-app
   ```
2. **Install Node libraries**:
   ```powershell
   npm install
   ```
3. **Start the Vite Dev Server**:
   ```powershell
   npm run dev
   ```
4. **Launch Application**:
   Open the URL provided in your terminal (usually `http://localhost:5173`) in your web browser. Follow on-screen setup properties to provide your API endpoints and run!

---

## ✨ Features Highlight

- **RAG Architecture**: Enforces organizational rules locally. Contextual documentation is embedded via `sentence-transformers` and intelligently appended based on code intent.
- **Diff Mode Analysis**: Upload unified `.patch` or Git diff chunks natively and CodeLens maps logical differences scoring architectural *Risk Deltas*.
- **Confidence & Evidence Scoring**: LLM insights are scored securely. Confidence percentages and specific line-code rule `Evidence` are extracted and highlighted directly throughout the UI.
- **Jira Automation**: Findings are immediately compiled into actionable tickets labeled with `Types` and weighted via `Story Points`. Access them globally from the new **Jira Tasks** workspace tab.

## RAG Modes

CodeLens supports two retrieval paths:

- **Vertex AI RAG** for managed corpus retrieval when your GCP quota is available
- **Local semantic RAG** using Sentence Transformers + FAISS for quota-free retrieval on cached Oracle documentation

The backend merges local keyword retrieval, local semantic retrieval, and Vertex retrieval. The analysis output includes `rag_diagnostics`, including `local_hits`, `semantic_hits`, and `vertex_hits`, so you can verify which path returned evidence for a query.

Configuration:

```powershell
LOCAL_SEMANTIC_RAG_ENABLED=true
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

## LLM Integration Notes

- Primary provider: BlueVerse
- Fallback chain: BlueVerse -> Claude -> OpenAI -> Gemini
- Token/cost usage logs: `backend/logs/llm_usage.jsonl`
- Provider/session/prompt strategy details: [ProjectDocs/LLM_INTEGRATION.md](ProjectDocs/LLM_INTEGRATION.md)

## Promptfoo

This repo now includes a basic Promptfoo setup for evaluating the local CodeLens backend.

Quick start:

```powershell
npm install
npm run promptfoo:eval
```

To open the Promptfoo UI:

```powershell
npm run promptfoo:view
```

Files:
- `promptfooconfig.yaml`
- `promptfoo/providers/codelens-api.mjs`
- `promptfoo/tests/codelens-evals.yaml`

The Promptfoo provider calls the local backend at `http://127.0.0.1:8000/api/analyze` by default and reads tokens from `backend/.env`.

## Docker

You can run the backend and frontend together with Docker Compose.

1. Create `backend/.env` from `backend/.env.example` and fill in your runtime secrets.
2. If you use Vertex AI RAG, put your GCP service account key at `backend/secrets/gcp-sa.json`.
   In Docker, the backend is forced to use `/app/secrets/gcp-sa.json` as `GOOGLE_APPLICATION_CREDENTIALS`.
3. From the project root, start the stack:
   ```powershell
   docker compose up --build
   ```
4. Open:
   - Frontend: `http://localhost:5173`
   - Backend health: `http://localhost:8000/health`

Notes:
- The frontend proxies `/api/*` to the backend container, so no extra frontend API env var is required.
- `backend/logs` and `backend/evidence` are mounted as volumes so generated artifacts persist across restarts.
