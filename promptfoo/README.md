# Promptfoo

This project includes a basic Promptfoo harness for evaluating the local CodeLens backend.

## Prerequisites

- Backend running locally or via Docker at `http://127.0.0.1:8000`
- `backend/.env` populated with valid BlueVerse tokens, especially `BLUEVERSE_JUDGE_BEARER_TOKEN`
- Node.js installed on the host machine

## Install

From the project root:

```powershell
npm install
```

## Run evaluations

```powershell
npm run promptfoo:eval
```

This uses [promptfooconfig.yaml](../../promptfooconfig.yaml) and writes results to `promptfoo/output/latest-results.json`.

## Open the Promptfoo UI

```powershell
npm run promptfoo:view
```

## Notes

- The custom provider calls `POST /api/analyze` on the local backend.
- By default it reads tokens from `backend/.env`.
- You can override the backend URL with `CODELENS_API_BASE`, for example:
  ```powershell
  $env:CODELENS_API_BASE='http://127.0.0.1:8000'
  npm run promptfoo:eval
  ```
