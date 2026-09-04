"""Mock target FastAPI app — a local vulnerable AI application for testing the tester."""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from mock_target.engine import handle_chat, set_profile
except ModuleNotFoundError:
    from engine import handle_chat, set_profile

app = FastAPI(title="Mock Vulnerable AI Target", docs_url="/docs", openapi_url="/openapi.json")

PROFILES = [
    "secure",
    "prompt_leak",
    "partial_leak",
    "rag_vulnerable",
    "tool_vulnerable",
    "ambiguous",
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation: list[dict[str, Any]] | None = None


class ChatResponse(BaseModel):
    answer: str
    latency_ms: int = 0


class ProfileRequest(BaseModel):
    profile: str


@app.get("/")
@app.get("/chat")
async def chat_info():
    return {
        "status": "online",
        "message": "Mock Vulnerable AI Target is active. Send POST requests to /chat with JSON body: {'message': 'your prompt'}",
        "docs": "/docs",
        "profile_endpoint": "/profile",
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    start = time.perf_counter()
    answer = handle_chat(req.model_dump())
    latency = int((time.perf_counter() - start) * 1000)
    if isinstance(answer, dict) and answer.get("_error"):
        raise HTTPException(status_code=400, detail=answer)
    return ChatResponse(answer=answer["answer"], latency_ms=latency)


@app.post("/profile")
async def set_mode(req: ProfileRequest):
    if req.profile not in PROFILES:
        raise HTTPException(status_code=400, detail=f"unknown profile: {req.profile}")
    set_profile(req.profile)
    return {"ok": True, "profile": req.profile, "profiles": PROFILES}


@app.get("/profile")
async def get_mode():
    try:
        from mock_target.engine import engine
    except ModuleNotFoundError:
        from engine import engine

    return {"profile": engine.profile}


@app.get("/health")
async def health():
    return {"status": "ok"}