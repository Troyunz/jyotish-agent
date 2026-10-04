"""One brain, many providers.

Local (Ollama) is called through its native /api/chat so we can pass options like
num_gpu and num_ctx (the OpenAI-compatible shim does not forward those).
Cloud providers (Gemini / OpenAI / Anthropic) all speak the OpenAI protocol, so one
SDK covers them. Automatic fallback: if the local model fails mid-setup, the cloud
brain takes over for that answer.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

import httpx

from .config import Config

TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0)


class LLMError(RuntimeError):
    pass


class Brain:
    def __init__(self, cfg: Config, backend: str | None = None):
        self.cfg = cfg
        self.backend = (backend or cfg.backend).lower()
        self.last_used: str | None = None
        self.last_error: str | None = None

    # ------------------------------------------------------------------ status
    def status(self) -> dict[str, Any]:
        """What is available right now - used by the UI status panel."""
        s: dict[str, Any] = {"configured": self.backend, "auto_fallback": self.cfg.auto_fallback}
        try:
            with httpx.Client(timeout=4.0) as c:
                host = self.cfg.provider_settings("local")["host"]
                r = c.get(f"{host}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
                s["ollama_up"] = True
                s["ollama_models"] = models
                wanted = self.cfg.provider_settings("local")["model"]
                s["ollama_model_present"] = any(m == wanted or m.startswith(wanted.split(":")[0]) for m in models)
        except Exception as exc:
            s["ollama_up"] = False
            s["ollama_error"] = str(exc)[:200]
        for p in ("gemini", "openai", "anthropic"):
            s[f"{p}_key"] = self.cfg.has_key(p)
        return s

    # ------------------------------------------------------------------ routing
    def _providers_to_try(self) -> list[str]:
        order = [self.backend]
        fb = self.cfg.fallback_backend
        if self.cfg.auto_fallback and fb not in order and self.cfg.has_key(fb):
            order.append(fb)
        return order

    # ------------------------------------------------------------------ local
    def _ollama_stream(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> Iterator[str]:
        ps = self.cfg.provider_settings("local")
        options: dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
        if ps.get("num_ctx"):
            options["num_ctx"] = int(ps["num_ctx"])
        if ps.get("num_gpu") is not None:
            options["num_gpu"] = int(ps["num_gpu"])
        payload = {"model": ps["model"], "messages": messages, "stream": True, "options": options}
        with httpx.Client(timeout=TIMEOUT) as client:
            with client.stream("POST", f"{ps['host']}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    body = r.read().decode("utf-8", "ignore")[:300]
                    raise LLMError(f"Ollama HTTP {r.status_code}: {body}")
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("error"):
                        raise LLMError(f"Ollama error: {data['error']}")
                    piece = (data.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
                    if data.get("done"):
                        break

    # ------------------------------------------------------------------ cloud
    def _openai_stream(self, provider: str, messages: list[dict[str, str]], temperature: float,
                       max_tokens: int) -> Iterator[str]:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError("openai package missing - run: pip install openai") from exc
        ps = self.cfg.provider_settings(provider)
        if not ps["api_key"]:
            raise LLMError(f"No API key configured for {provider}. Add it to .env")
        client = OpenAI(api_key=ps["api_key"], base_url=ps["base_url"], timeout=TIMEOUT)
        try:
            stream = client.chat.completions.create(
                model=ps["model"], messages=messages, temperature=temperature,
                max_tokens=max_tokens, stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            raise LLMError(f"{ps['label']} call failed: {exc}") from exc

    # ------------------------------------------------------------------ public
    def stream(self, messages: list[dict[str, str]], temperature: float | None = None,
               max_tokens: int | None = None) -> Iterator[str]:
        temperature = self.cfg.temperature if temperature is None else temperature
        max_tokens = self.cfg.max_tokens if max_tokens is None else max_tokens
        errors: list[str] = []
        for provider in self._providers_to_try():
            emitted = False
            try:
                gen = (self._ollama_stream(messages, temperature, max_tokens) if provider == "local"
                       else self._openai_stream(provider, messages, temperature, max_tokens))
                for piece in gen:
                    emitted = True
                    yield piece
                self.last_used = provider
                return
            except Exception as exc:
                self.last_error = str(exc)
                errors.append(f"{provider}: {exc}")
                if emitted:
                    # partial answer already shown - don't restart with another model
                    self.last_used = provider
                    return
                continue
        raise LLMError("All brains failed -> " + " | ".join(errors))

    def complete(self, messages: list[dict[str, str]], temperature: float | None = None,
                 max_tokens: int | None = None) -> str:
        return "".join(self.stream(messages, temperature, max_tokens))
