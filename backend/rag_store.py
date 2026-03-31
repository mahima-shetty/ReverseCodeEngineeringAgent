"""
RAG store using Vertex AI RAG Engine (Option A — fully managed).

Setup:
  1. Set GCP_PROJECT_ID, GCP_LOCATION, GCS_BUCKET_URI in backend/.env
  2. Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path
  3. Leave RAG_CORPUS_ID empty on first run — the corpus will be created
     automatically and the resource name will be printed + saved to
     backend/rag_corpus.txt. Copy it into RAG_CORPUS_ID in .env.

Subsequent runs with RAG_CORPUS_ID set will skip corpus creation and
query directly — fast startup, no re-import.

If GCP credentials / config are missing the module degrades gracefully
and get_rag_context() returns "" so main.py continues to work as before.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

# .env is loaded by main.py before this module is imported at request time,
# but we read env vars lazily inside functions so they are always fresh.

CORPUS_NAME_FILE = Path(__file__).parent / "rag_corpus.txt"

_rag_corpus_name: str | None = None   # resolved full resource name
_rag_ready       = False
_init_attempted  = False              # prevent repeated failed init attempts


# ── Helpers ───────────────────────────────────────────────────────────────────
def _cfg(key: str, default: str = "") -> str:
    """Read env var (always fresh — called inside functions, not at module level)."""
    return (os.getenv(key) or default).strip()


def _import_vertexai() -> bool:
    try:
        import vertexai  # noqa: F401
        from vertexai.preview import rag  # noqa: F401
        return True
    except ImportError:
        print(
            "[rag_store] google-cloud-aiplatform[preview] not installed. "
            "Run: pip install google-cloud-aiplatform[preview]"
        )
        return False


def _resolve_corpus_name(corpus_id: str, project: str, location: str) -> str:
    """Return a fully-qualified corpus resource name if only an ID was given."""
    if corpus_id.startswith("projects/"):
        return corpus_id
    return f"projects/{project}/locations/{location}/ragCorpora/{corpus_id}"


def _save_corpus_name(name: str) -> None:
    try:
        CORPUS_NAME_FILE.write_text(name, encoding="utf-8")
        print(f"[rag_store] Corpus name saved to {str(CORPUS_NAME_FILE)}")
    except OSError as e:
        print(f"[rag_store] Could not save corpus name to file: {e}")


def _load_corpus_name_from_file() -> str:
    try:
        if CORPUS_NAME_FILE.exists():
            return CORPUS_NAME_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _poll_import_operation(operation, timeout_s: int = 300, poll_interval_s: int = 10) -> None:
    """Wait for a long-running GCP operation to complete."""
    if hasattr(operation, "result"):
        try:
            operation.result(timeout=timeout_s)
        except Exception as e:
            print(f"[rag_store] Operation polling warning: {e}")
        return
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if getattr(operation, "done", lambda: True)():
            return
        time.sleep(poll_interval_s)


# ── Initialise RAG corpus ─────────────────────────────────────────────────────
def init_rag_store() -> None:
    global _rag_corpus_name, _rag_ready, _init_attempted

    if _rag_ready or _init_attempted:
        return
    _init_attempted = True

    # Read config fresh (dotenv already loaded by main.py's load_dotenv())
    project    = _cfg("GCP_PROJECT_ID")
    location   = _cfg("GCP_LOCATION", "us-central1")
    gcs_uri    = _cfg("GCS_BUCKET_URI")
    corpus_id  = _cfg("RAG_CORPUS_ID")

    if not project:
        print("[rag_store] GCP_PROJECT_ID not set — RAG disabled.")
        return

    if not _import_vertexai():
        return

    import vertexai
    from vertexai.preview import rag

    # Build explicit credentials from the service account key in .env.
    # This overrides any system-level GOOGLE_APPLICATION_CREDENTIALS / ADC
    # (which may be an expired gcloud user credential).
    credentials = None
    creds_path = _cfg("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and os.path.exists(creds_path):
        try:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            print(f"[rag_store] Using service account credentials: {creds_path}")
        except Exception as e:
            print(f"[rag_store] Could not load service account credentials: {e}")
    else:
        if creds_path:
            print(f"[rag_store] WARNING: credentials file not found at {creds_path!r}")
        print("[rag_store] Falling back to Application Default Credentials (ADC)")

    try:
        vertexai.init(project=project, location=location, credentials=credentials)
        print(f"[rag_store] Vertex AI initialised (project={project}, location={location})")
    except Exception as e:
        print(f"[rag_store] vertexai.init failed: {e}")
        return

    # ── 1. Resolve corpus name from env or saved file ────────────────────────
    corpus_name = (
        _resolve_corpus_name(corpus_id, project, location) if corpus_id else ""
    ) or _load_corpus_name_from_file()

    if corpus_name:
        try:
            rag.get_corpus(name=corpus_name)
            _rag_corpus_name = corpus_name
            _rag_ready = True
            print(f"[rag_store] [OK] Using existing RAG corpus: {corpus_name}")
            return
        except Exception as e:
            print(f"[rag_store] Corpus not found ({e}), will create a new one.")
            corpus_name = ""

    # ── 2. Create new corpus ──────────────────────────────────────────────────
    if not gcs_uri:
        print("[rag_store] GCS_BUCKET_URI not set — cannot create corpus. RAG disabled.")
        return

    print("[rag_store] Creating new Vertex AI RAG corpus 'codelens-rag' ...")
    try:
        corpus = rag.create_corpus(
            display_name="codelens-rag",
            description="CodeLens org coding standards",
        )
        corpus_name = corpus.name
        print(f"[rag_store] Corpus created: {corpus_name}")
    except Exception as e:
        print(f"[rag_store] Failed to create corpus: {e}")
        return

    # ── 3. Import PDFs from GCS ───────────────────────────────────────────────
    uri = gcs_uri.rstrip("/") + "/"
    print(f"[rag_store] Importing PDFs from {uri} — this may take a few minutes ...")
    try:
        op = rag.import_files(
            corpus_name,
            paths=[uri],
            chunk_size=1024,
            chunk_overlap=200,
        )
        _poll_import_operation(op)
        print("[rag_store] [OK] PDF import complete.")
    except Exception as e:
        print(f"[rag_store] PDF import failed: {e} — corpus exists but may have no docs.")

    _rag_corpus_name = corpus_name
    _rag_ready = True
    _save_corpus_name(corpus_name)

    print(
        f"\n[rag_store] [OK] RAG corpus ready.\n"
        f"  -> Add this line to backend/.env to skip re-import on next start:\n"
        f"  RAG_CORPUS_ID={corpus_name}\n"
    )


# ── Public API ────────────────────────────────────────────────────────────────
def get_rag_context(query: str, k: int = 3) -> str:
    """
    Retrieve top-k relevant chunks from the RAG corpus for `query`.
    Returns a formatted string to inject into the LLM prompt.
    Returns "" gracefully if RAG is unavailable.
    """
    prompt_chunks, _ = _retrieve_chunks(query, k)
    return "\n\n".join(prompt_chunks)


def get_rag_citations(query: str, k: int = 3) -> list[dict]:
    """
    Return structured citation objects for the UI:
    [{"source": "gs://bucket/file.pdf", "excerpt": "...text snippet..."}, ...]
    """
    _, citations = _retrieve_chunks(query, k)
    return citations


def _retrieve_chunks(query: str, k: int = 3):
    """
    Core retrieval: returns (prompt_chunks, citation_dicts).
    prompt_chunks: list of strings for LLM injection
    citation_dicts: list of {"source": ..., "excerpt": ...}
    """
    global _rag_corpus_name, _rag_ready

    if not _rag_ready:
        init_rag_store()

    if not _rag_ready or not _rag_corpus_name:
        return [], []

    if not _import_vertexai():
        return [], []

    from vertexai.preview import rag

    try:
        response = rag.retrieval_query(
            rag_resources=[rag.RagResource(rag_corpus=_rag_corpus_name)],
            text=query,
            similarity_top_k=k,
        )
    except Exception as e:
        print(f"[rag_store] retrieval_query failed: {e}")
        return [], []

    prompt_chunks: list[str] = []
    citations: list[dict] = []
    try:
        for ctx in response.contexts.contexts:
            source = (
                getattr(ctx, "source_uri", "")
                or getattr(ctx, "source_display_name", "GCS")
            )
            text = getattr(ctx, "text", "")
            if text.strip():
                prompt_chunks.append(f"Source ({source}):\n{text.strip()}")
                citations.append({"source": source, "excerpt": text.strip()[:500]})
    except Exception as e:
        print(f"[rag_store] Response parsing error: {e}")
        return [], []

    return prompt_chunks, citations


