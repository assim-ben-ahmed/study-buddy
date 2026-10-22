"""Mistral chat API client (streaming and JSON), with retries on rate limits and a fallback model.

A DemoLLM with the same interface answers when no API key is configured, so the app and its tests run anywhere.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator

import httpx

API_URL = "https://api.mistral.ai/v1/chat/completions"


class LLMError(RuntimeError):
    pass


class MistralLLM:
    def __init__(self, api_key: str, model: str, fallback_model: str | None = None, timeout: float = 60):
        self.api_key = api_key
        self.models = [m for m in (model, fallback_model) if m]
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _post(self, payload: dict, stream: bool = False):
        """Try each model; on 429 wait and retry once before moving to the fallback model."""
        last = None
        for model in self.models:
            for attempt in range(2):
                body = {**payload, "model": model, "stream": stream}
                client = httpx.Client(timeout=self.timeout)
                request = client.build_request("POST", API_URL, headers=self._headers(), json=body)
                response = client.send(request, stream=stream)
                if response.status_code == 200:
                    return model, client, response
                detail = response.read().decode("utf-8", "replace")[:200]
                response.close()
                client.close()
                last = f"{model}: HTTP {response.status_code} {detail}"
                if response.status_code == 429 and attempt == 0:
                    time.sleep(1.5)
                    continue
                if response.status_code in (401, 403) and "tier" not in detail:
                    raise LLMError("The Mistral API key was refused.")
                break
        raise LLMError(f"Mistral is unavailable right now ({last}).")

    def stream(self, messages: list[dict], temperature: float = 0.4, max_tokens: int = 900) -> Iterator[str]:
        model, client, response = self._post(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}, stream=True
        )
        try:
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0]["delta"].get("content")
                if delta:
                    yield delta
        finally:
            response.close()
            client.close()

    def json(self, messages: list[dict], temperature: float = 0.5, max_tokens: int = 1800) -> dict:
        model, client, response = self._post(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens,
             "response_format": {"type": "json_object"}}
        )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        finally:
            client.close()
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("The model did not return valid JSON.") from exc


class DemoLLM:
    """Offline stand-in: fixed, clearly labelled sample answers (no API key needed)."""

    NOTICE = "*(Demo mode: add a MISTRAL_API_KEY to get real answers.)*\n\n"

    def stream(self, messages: list[dict], **_) -> Iterator[str]:
        question = messages[-1]["content"]
        text = (self.NOTICE + f"You asked: **{question[:120]}**\n\n"
                "In the full version, Mistral explains the idea step by step, gives an example, "
                "then checks your understanding with a question.\n\n"
                "1. **Define** the concept in one sentence\n2. **Example** you can picture\n"
                "3. **Check**: can you explain it back in your own words?")
        for word in text.split(" "):
            yield word + " "

    def json(self, messages: list[dict], **_) -> dict:
        if "flashcards" in messages[0]["content"]:
            return {"title": "Photosynthesis (demo)", "cards": [
                {"front": "What do plants need for photosynthesis?", "back": "Light, water and carbon dioxide."},
                {"front": "What does photosynthesis produce?", "back": "Glucose (sugar) and oxygen."},
                {"front": "Where does it happen?", "back": "In the chloroplasts, mostly in leaves."},
            ]}
        return {"topic": "Photosynthesis (demo)", "questions": [
            {"question": "Which gas do plants absorb for photosynthesis?",
             "options": ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"], "answer": 1,
             "explanation": "Plants take in CO₂ from the air and release oxygen."},
            {"question": "Where in the cell does photosynthesis happen?",
             "options": ["Nucleus", "Mitochondria", "Chloroplasts", "Ribosomes"], "answer": 2,
             "explanation": "Chloroplasts contain chlorophyll, which captures light."},
        ]}
