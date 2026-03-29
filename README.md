# Reverse Code Engineering Agent (CodeLens)

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
