"""Configuration loading: config.yaml + .env environment overrides."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent

try:  # python-dotenv is optional at import time
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:  # pragma: no cover
    pass

# Every provider below speaks the OpenAI chat-completions protocol,
# which lets us use ONE client library for local and cloud brains.
PROVIDERS: dict[str, dict[str, Any]] = {
    "local": {
        "base_url": None,  # filled from local.host at runtime
        "key_env": None,
        "default_model": "qwen2.5:7b-instruct-q4_K_M",
        "label": "Ollama (local)",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
        "label": "Google Gemini",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "label": "OpenAI",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1/",
        "key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-5",
        "label": "Anthropic Claude",
    },
}


class Config:
    """Loaded once, passed around. All accessors are safe with missing keys."""

    def __init__(self, path: str | Path | None = None):
        self.root = ROOT
        self.path = Path(path) if path else ROOT / "config.yaml"
        self.raw: dict[str, Any] = {}
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as fh:
                self.raw = yaml.safe_load(fh) or {}

    # ------------------------------------------------------------------ utils
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def path_of(self, dotted: str, default: str) -> Path:
        p = Path(self.get(dotted, default))
        return p if p.is_absolute() else (self.root / p)

    # -------------------------------------------------------------------- LLM
    @property
    def backend(self) -> str:
        b = str(self.get("backend", "local")).lower()
        return b if b in PROVIDERS else "local"

    @property
    def auto_fallback(self) -> bool:
        return bool(self.get("auto_fallback", True))

    @property
    def fallback_backend(self) -> str:
        b = str(self.get("fallback_backend", "gemini")).lower()
        return b if b in PROVIDERS and b != self.backend else "gemini"

    def has_key(self, provider: str) -> bool:
        env = PROVIDERS.get(provider, {}).get("key_env")
        if not env:  # local needs no key
            return provider == "local"
        return bool(os.getenv(env, "").strip())

    def provider_settings(self, provider: str | None = None) -> dict[str, Any]:
        """Return everything the LLM client needs for one provider."""
        name = (provider or self.backend).lower()
        if name not in PROVIDERS:
            name = "local"
        meta = PROVIDERS[name]

        if name == "local":
            host = (os.getenv("OLLAMA_HOST") or self.get("local.host", "http://localhost:11434")).rstrip("/")
            return {
                "name": name,
                "label": meta["label"],
                "base_url": host + "/v1",
                "host": host,
                "api_key": "ollama",
                "model": self.get("local.model", meta["default_model"]),
                "num_gpu": self.get("local.num_gpu"),
                "num_ctx": self.get("local.num_ctx", 8192),
                "is_local": True,
            }
        return {
            "name": name,
            "label": meta["label"],
            "base_url": meta["base_url"],
            "api_key": os.getenv(meta["key_env"], "").strip(),
            "model": self.get(f"api.{name}.model", meta["default_model"]),
            "is_local": False,
        }

    # --------------------------------------------------------------- Jyotish
    @property
    def ayanamsa(self) -> str:
        return str(self.get("jyotish.ayanamsa", "lahiri")).lower()

    @property
    def node_type(self) -> str:
        return str(self.get("jyotish.node", "true")).lower()

    @property
    def house_system(self) -> str:
        return str(self.get("jyotish.house_system", "whole")).lower()

    @property
    def dasha_year_days(self) -> float:
        return float(self.get("jyotish.dasha_year_days", 365.2425))

    @property
    def position_mode(self) -> str:
        """'true' (JHora-parity true positions) or 'apparent' (Swiss Ephemeris default)."""
        m = str(self.get("jyotish.position_mode", "true")).lower()
        return m if m in ("true", "apparent") else "true"

    @property
    def ephe_path(self) -> Path:
        """Directory holding the bundled Swiss Ephemeris .se1 data files."""
        return self.path_of("jyotish.ephe_path", "data/ephe")

    # -------------------------------------------------------------------- RAG
    @property
    def rag_enabled(self) -> bool:
        return bool(self.get("rag.enabled", True))

    @property
    def rag_top_k(self) -> int:
        return int(self.get("rag.top_k", 5))

    @property
    def embed_provider(self) -> str:
        return str(self.get("rag.embed_provider", "auto")).lower()

    @property
    def embed_model(self) -> str:
        return str(self.get("rag.embed_model", "nomic-embed-text"))

    @property
    def knowledge_dir(self) -> Path:
        return self.path_of("rag.knowledge_dir", "data/knowledge")

    @property
    def index_path(self) -> Path:
        return self.path_of("rag.index_path", "data/knowledge_index.json")

    # ------------------------------------------------------------ generation
    @property
    def temperature(self) -> float:
        return float(self.get("generation.temperature", 0.4))

    @property
    def max_tokens(self) -> int:
        return int(self.get("generation.max_tokens", 1600))
