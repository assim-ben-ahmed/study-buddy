"""FastAPI app: serves the web page and the chat / quiz / flashcard API. The Mistral key never leaves the server."""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

from . import prompts
from .config import ROOT, Settings, get_settings
from .llm import DemoLLM, LLMError, MistralLLM

WEB = ROOT / "web"
Level = Literal["middle", "high", "university"]


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatIn(BaseModel):
    messages: list[Message] = Field(min_length=1)
    mode: Literal["explain", "homework", "summarize", "plan"] = "explain"
    level: Level = "high"


class GenerateIn(BaseModel):
    topic: str = Field(min_length=2, max_length=6000)
    count: int = Field(default=5, ge=3, le=10)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    level: Level = "high"
    language: str = Field(default="en", max_length=12)  # browser language, used when the topic is too short


class Question(BaseModel):
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    answer: int = Field(ge=0, le=3)
    explanation: str = ""


class Quiz(BaseModel):
    topic: str
    questions: list[Question] = Field(min_length=1)


class Card(BaseModel):
    front: str
    back: str


class Deck(BaseModel):
    title: str
    cards: list[Card] = Field(min_length=1)

    @field_validator("cards")
    @classmethod
    def no_empty(cls, cards: list[Card]) -> list[Card]:
        return [c for c in cards if c.front.strip() and c.back.strip()]


class RateLimiter:
    """Sliding one-minute window per client IP."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        window = self.hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            raise HTTPException(429, "Too many requests: take a short break and try again in a minute.")
        window.append(now)


def create_app(settings: Settings | None = None, llm=None) -> FastAPI:
    settings = settings or get_settings()
    llm = llm or (DemoLLM() if settings.demo else MistralLLM(settings.api_key, settings.model, settings.fallback_model))
    limiter = RateLimiter(settings.requests_per_minute)
    app = FastAPI(title="AI Study Buddy", version="1.0.0")
    if settings.allowed_origins:  # only needed when the page is hosted elsewhere (e.g. GitHub Pages)
        app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["*"],
                           allow_headers=["*"])
    app.mount("/static", StaticFiles(directory=WEB), name="static")

    def limited(request: Request) -> None:
        forwarded = request.headers.get("x-forwarded-for", "")
        limiter.check(forwarded.split(",")[0].strip() or (request.client.host if request.client else "local"))

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(WEB / "index.html")

    @app.get("/api/health")
    def health():
        return {"ok": True, "demo": settings.demo, "model": None if settings.demo else settings.model}

    @app.post("/api/chat", dependencies=[Depends(limited)])
    def chat(body: ChatIn):
        history = body.messages[-settings.max_history:]
        if len(history[-1].content) > settings.max_message_chars:
            raise HTTPException(413, f"Message too long (max {settings.max_message_chars} characters).")
        messages = [{"role": "system", "content": prompts.chat_system(body.mode, body.level)}]
        messages += [m.model_dump() for m in history]

        def events():
            try:
                for chunk in llm.stream(messages):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
            except LLMError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    def generate(system: str, topic: str, schema: type[BaseModel]):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": topic}]
        for attempt in range(2):  # one retry if the JSON does not match the schema
            try:
                return schema.model_validate(llm.json(messages))
            except (ValidationError, LLMError) as exc:
                if attempt == 1 or (isinstance(exc, LLMError) and "unavailable" in str(exc)):
                    raise HTTPException(502, f"Could not generate it this time: {exc}") from exc
        raise HTTPException(502, "Could not generate it this time.")

    @app.post("/api/quiz", dependencies=[Depends(limited)])
    def quiz(body: GenerateIn) -> Quiz:
        system = prompts.QUIZ.format(level=prompts.LEVELS[body.level], n=body.count, difficulty=body.difficulty,
                                     language=prompts.language_name(body.language))
        result = generate(system, body.topic, Quiz)
        result.questions = result.questions[: body.count]
        return result

    @app.post("/api/flashcards", dependencies=[Depends(limited)])
    def flashcards(body: GenerateIn) -> Deck:
        system = prompts.FLASHCARDS.format(level=prompts.LEVELS[body.level], n=body.count + 3,
                                           language=prompts.language_name(body.language))
        return generate(system, body.topic, Deck)

    return app


app = create_app()
