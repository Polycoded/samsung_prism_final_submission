"""Local WebSocket delivery; session data is discarded on disconnect."""
from __future__ import annotations

import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, ConfigDict, field_validator

from .runtime import LiveRuntime
from .upload import parse_upload
from .benchmark import run_benchmark

ROOT = Path(__file__).parent


class TranscriptMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=100)
    turn_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=4000)
    timestamp_ms: float = Field(ge=0, allow_inf_nan=False)
    is_final: bool = False
    revision_of: str | None = Field(default=None, max_length=100)
    target_intent_key: str | None = Field(default=None, max_length=500)
    sequence: int | None = Field(default=None, ge=0)

    @field_validator("text")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("text cannot be blank")
        return value


@asynccontextmanager
async def lifespan(app):
    app.state.runtime = await asyncio.to_thread(LiveRuntime)
    app.state.sessions = {}
    yield
    app.state.sessions.clear()


app = FastAPI(title="CiteFrontier Live", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/health")
def health():
    runtime = app.state.runtime
    return {"status": "ok", "backend": runtime.backend, "corpus_chunks": len(runtime.chunks),
            "generation": "verified exact extraction", "official_validation": "pending",
            "parser": runtime.decomposer.method, "corpus_hash": runtime.corpus_hash}


@app.get("/corpus")
def corpus():
    return [asdict(c) for c in app.state.runtime.chunks]


@app.get("/demo-scenarios")
def demo_scenarios():
    """Presentation fixtures only; the retrieval engine never reads this file."""
    if os.environ.get("CITEFRONTIER_DEMO", "0") != "1":
        return {}
    path = ROOT / "demo" / "scenarios.json"
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


@app.get("/session/{session_id}/telemetry")
def telemetry(session_id: str, authorization: str | None = Header(default=None)):
    connection = app.state.sessions.get(session_id)
    if connection is None:
        raise HTTPException(404, "Session closed or unknown")
    if not secrets.compare_digest(authorization or "", f"Bearer {connection.token}"):
        raise HTTPException(403, "Session token required")
    return connection.telemetry


@app.get("/session/{session_id}/corpus")
def session_corpus(session_id: str, authorization: str | None = Header(default=None)):
    telemetry(session_id, authorization)
    return [asdict(c) for c in app.state.sessions[session_id].runtime.chunks]


@app.get("/scorecard")
def scorecard():
    path = ROOT / "reports" / "scorecard.json"
    if not path.exists():
        return {"status": "pending", "official_validation": "pending"}
    return json.loads(path.read_text(encoding="utf-8"))


@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    # Local demo: reject cross-site browser sockets, allow CLI clients without Origin.
    origin = ws.headers.get("origin")
    if origin and origin not in {f"http://{ws.headers.get('host')}", f"https://{ws.headers.get('host')}"}:
        await ws.close(code=1008)
        return
    await ws.accept()
    connection = app.state.runtime.connection()
    session_id = connection.session_id
    app.state.sessions[session_id] = connection
    await ws.send_json({"type": "ready", "session_id": session_id, "session_token": connection.token,
                        "backend": app.state.runtime.backend, "parser": app.state.runtime.decomposer.method,
                        "corpus_hash": connection.runtime.corpus_hash})
    pending = set()
    send_lock = asyncio.Lock()

    async def respond(message):
        try:
            result = await connection.handle(message)
        except ValueError as exc:
            result = {"type": "error", "event_id": message.event_id, "detail": str(exc)[:500]}
        except Exception:
            result = {"type": "error", "event_id": message.event_id, "detail": "Processing failed; no answer was committed. Start a new session."}
        async with send_lock:
            await ws.send_json(result)
    try:
        for _ in range(500):
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=900)
                if len(raw.encode('utf-8')) > 1_000_000:
                    raise ValueError("Upload exceeds the 1 MB limit")
                envelope = json.loads(raw)
                if isinstance(envelope, dict) and envelope.get('type') == 'corpus_upload':
                    if pending:
                        await asyncio.gather(*pending)
                        pending.clear()
                    chunks = parse_upload(envelope.get('files'))
                    runtime = await asyncio.to_thread(LiveRuntime, chunks=chunks,
                        backend=app.state.runtime.backend, parser='spacy')
                    await connection.close()
                    app.state.sessions.pop(session_id, None)
                    connection = runtime.connection()
                    session_id = connection.session_id
                    app.state.sessions[session_id] = connection
                    await ws.send_json({'type':'corpus_loaded','session_id':session_id,'session_token':connection.token,
                        'corpus_hash':runtime.corpus_hash,'chunks':len(chunks),'documents':len({c.doc_id for c in chunks}),
                        'backend':runtime.backend,'parser':runtime.decomposer.method})
                    continue
                if isinstance(envelope, dict) and envelope.get('type') == 'benchmark_run':
                    if pending:
                        await asyncio.gather(*pending)
                        pending.clear()
                    result = await run_benchmark(connection.runtime, envelope.get('cases'))
                    async with send_lock:
                        await ws.send_json(result)
                    continue
                if len(raw) > 16000:
                    raise ValueError("Message exceeds size limit")
                message = TranscriptMessage.model_validate_json(raw)
                if len(pending) >= 8:
                    raise ValueError("Too many pending events; wait for a response")
                task = asyncio.create_task(respond(message))
                pending.add(task)
                task.add_done_callback(pending.discard)
            except (ValidationError, ValueError) as exc:
                async with send_lock:
                    await ws.send_json({"type": "error", "detail": str(exc)[:500]})
        await ws.close(code=1000, reason="Session event limit reached")
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        await connection.close()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        app.state.sessions.pop(session_id, None)
