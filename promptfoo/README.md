# Promptfoo For CodeLens

This folder contains a starter Promptfoo evaluation harness for the local CodeLens API.

## What it does

- Calls `POST /api/analyze` on the local backend
- Evaluates the returned `final_output`
- Checks that the UI-facing response is structured
- Verifies that failures do not fabricate fake findings

## Prerequisites

- Backend running on `http://127.0.0.1:8000`
- Valid tokens available either in:
  - `backend/.env` as `BLUEVERSE_BEARER_TOKEN` and `BLUEVERSE_JUDGE_BEARER_TOKEN`
  - or shell environment variables with the same names
- Optional:
  - `CODELENS_API_BASE`
  - `BLUEVERSE_URL`

## Run

```powershell
npx promptfoo@latest eval -c promptfooconfig.yaml
```

## View results

```powershell
npx promptfoo@latest view
```

## Notes

- The provider returns the first item from the CodeLens analysis batch.
- Assertions inspect `final_output`, not the raw primary output.
- The `Failed auth must not fabricate findings` case is intentionally negative and verifies explicit failure behavior.
- By default the provider reuses `backend/.env`, so Promptfoo can run against the same credentials as the local backend.
