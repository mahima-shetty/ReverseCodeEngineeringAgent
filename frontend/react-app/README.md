# CodeLens React UI

Vite + React + TypeScript port of `code-reviewer-agent.html`.

## Run

```bash
cd frontend/react-app
npm install
npm run dev
```

Open the URL Vite prints (usually `http://127.0.0.1:5173`). API calls go to `/api/analyze`, proxied to `http://127.0.0.1:8000` (start the FastAPI backend separately).

Override API origin when not using the dev proxy:

```bash
# .env.local (optional)
VITE_API_BASE=http://127.0.0.1:8000
```

## Build

```bash
npm run build
npm run preview
```

The legacy single-file UI remains at `frontend/code-reviewer-agent.html` if you need it without Node.
