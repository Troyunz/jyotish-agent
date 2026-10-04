"""The agent: birth details -> chart -> retrieval -> prompt -> streamed answer."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from . import chart as chart_mod
from . import geo
from .config import Config
from .llm import Brain, LLMError
from .prompts import build_system_prompt, detect_topic
from .rag import KnowledgeBase
from .verify import correction_prompt, verify_answer

HISTORY_LIMIT = 16  # messages kept (8 exchanges)


@dataclass
class BirthDetails:
    name: str = "Native"
    dob: str = ""            # YYYY-MM-DD
    tob: str = ""            # HH:MM (24h, local clock time)
    city: str = ""           # free text, resolved against data/cities.csv
    lat: float | None = None
    lon: float | None = None
    tz: str | None = None
    time_unknown: bool = False

    def validation_error(self) -> str | None:
        if not self.dob:
            return "Date of birth is required (YYYY-MM-DD)."
        if not self.city and (self.lat is None or self.lon is None):
            return "Birth city is required (or enter latitude/longitude manually)."
        if not self.tob and not self.time_unknown:
            return "Time of birth is required, or tick 'birth time unknown'."
        return None

    def resolve(self, cfg: Config) -> dict[str, Any]:
        """Turn human input into a fully-specified birth record."""
        err = self.validation_error()
        if err:
            raise ValueError(err)

        city_row = geo.find_city(self.city) if self.city else None
        lat = self.lat if self.lat is not None else (city_row["lat"] if city_row else None)
        lon = self.lon if self.lon is not None else (city_row["lon"] if city_row else None)
        if lat is None or lon is None:
            raise ValueError(f"Could not resolve '{self.city}'. Try a nearby larger city, or type "
                             f"latitude/longitude manually (e.g. 12.9716, 77.5946).")

        tz = self.tz or geo.tz_for(lat, lon)
        d = datetime.strptime(self.dob, "%Y-%m-%d").date()
        warnings: list[str] = []
        if self.time_unknown:
            t = time(12, 0)
            warnings.append("Birth time is unknown - 12:00 (local clock) was assumed. The Lagna, houses, "
                            "dasha start dates and Moon nakshatra pada are approximate; Sun sign, Moon sign "
                            "(usually), nakshatra and most yogas are still reliable.")
        else:
            try:
                t = datetime.strptime(self.tob, "%H:%M").time()
            except ValueError:
                t = datetime.strptime(self.tob, "%H:%M:%S").time()

        if not city_row and not warnings:
            pass
        elif city_row is None and self.city:
            warnings.append(f"Used manual coordinates; town '{self.city}' was not in the built-in city list.")

        local_dt = datetime.combine(d, t, tzinfo=ZoneInfo(tz))
        utc_dt = local_dt.astimezone(timezone.utc)
        place = geo.describe(city_row, lat, lon, tz)
        return {
            "name": self.name or "Native",
            "local_dt": local_dt, "utc_dt": utc_dt, "lat": lat, "lon": lon, "tz": tz, "place": place,
            "ayanamsa": cfg.ayanamsa, "node": cfg.node_type,
            "house_system": cfg.house_system, "dasha_year_days": cfg.dasha_year_days,
            "warnings": warnings,
        }


class JyotishAgent:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.brain = Brain(self.cfg)
        self.kb = KnowledgeBase(self.cfg) if self.cfg.rag_enabled else None
        self.chart: dict[str, Any] | None = None
        self.birth: dict[str, Any] | None = None
        self.history: list[dict[str, str]] = []
        self.last_sources: list[dict[str, Any]] = []
        self.last_checks: list[dict[str, str]] = []
        self.last_topic: str = ""
        self.warnings: list[str] = []

    # ------------------------------------------------------------------ setup
    def set_birth(self, details: BirthDetails) -> dict[str, Any]:
        self.birth = details.resolve(self.cfg)
        self.warnings = self.birth.get("warnings", [])
        self.chart = chart_mod.calc_chart(self.birth)
        self.history = []
        return self.chart

    def set_backend(self, backend: str) -> None:
        self.brain = Brain(self.cfg, backend=backend)

    def has_chart(self) -> bool:
        return self.chart is not None

    def chart_text(self, when: datetime | None = None) -> str:
        if not self.chart:
            return ""
        return chart_mod.render_chart_text(
            self.chart, when=when or datetime.now(timezone.utc),
            include_vargas=bool(self.cfg.get("jyotish.include_vargas", True)),
            include_ashtakavarga=bool(self.cfg.get("jyotish.include_ashtakavarga", True)),
        )

    # ------------------------------------------------------------------ prompting
    def _retrieve(self, query: str, topic_keywords: list[str] | None = None) -> str:
        self.last_sources = []
        if not self.kb or not self.kb.chunks:
            return ""
        # blend the question with the chart's core facts and the topic's own vocabulary
        extra = ""
        if self.chart:
            extra = (f" lagna {self.chart['ascendant']['sign_name']} "
                     f"moon sign {self.chart['planets']['Moon']['sign_name']}")
        if topic_keywords:
            extra += " " + " ".join(topic_keywords[:6])
        results = self.kb.search(query + extra, k=self.cfg.rag_top_k)
        self.last_sources = results
        return self.kb.context_block(results) if results else ""

    def build_messages(self, query: str) -> list[dict[str, str]]:
        now = datetime.now(timezone.utc)
        topic, checklist, topic_kw = detect_topic(query)
        self.last_topic = topic
        chart_ctx = self.chart_text(when=now) if self.chart else None
        refs = self._retrieve(query, topic_kw)
        system = build_system_prompt(
            chart_context=chart_ctx,
            reference_context=refs,
            today=now.strftime("%A, %d %B %Y (%H:%M UTC)"),
            rag_enabled=bool(self.cfg.rag_enabled),
            topic_checklist=checklist if self.chart else None,
        )
        msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
        msgs.extend(self.history[-HISTORY_LIMIT:])
        msgs.append({"role": "user", "content": query})
        return msgs

    # ------------------------------------------------------------------ ask
    def stream_answer(self, query: str) -> Iterator[dict[str, Any]]:
        """Yield {"type": "token"|"done"|"error", ...} events."""
        messages = self.build_messages(query)
        collected: list[str] = []
        try:
            for piece in self.brain.stream(messages):
                collected.append(piece)
                yield {"type": "token", "text": piece}
        except LLMError as exc:
            yield {"type": "error", "message": str(exc)}
            return
        answer = "".join(collected)
        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": answer})

        # ---- self-check against the calculated chart ----
        self.last_checks = []
        if self.chart and bool(self.cfg.get("generation.self_check", True)):
            self.last_checks = verify_answer(answer, self.chart)

        yield {
            "type": "done",
            "text": answer,
            "backend": self.brain.last_used or self.cfg.backend,
            "topic": self.last_topic,
            "checks": self.last_checks,
            "sources": [
                {"title": s["title"], "heading": s.get("heading", ""), "score": s["score"]}
                for s in self.last_sources
            ],
        }

    def corrective_pass(self, query: str, answer: str,
                        issues: list[dict[str, str]] | None = None) -> Iterator[dict[str, Any]]:
        """Regenerate an answer with the contradicting claims explicitly corrected."""
        issues = issues if issues is not None else self.last_checks
        if not issues:
            yield {"type": "done", "text": answer, "backend": self.brain.last_used or self.cfg.backend,
                   "checks": [], "sources": [], "corrected": False}
            return
        messages = self.build_messages(query)
        # drop the system prompt rebuild's history tail duplication: keep system + this exchange
        messages = [messages[0], {"role": "user", "content": query},
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": correction_prompt(issues)}]
        collected: list[str] = []
        try:
            for piece in self.brain.stream(messages, temperature=0.2):
                collected.append(piece)
                yield {"type": "token", "text": piece}
        except LLMError as exc:
            yield {"type": "error", "message": str(exc)}
            return
        fixed = "".join(collected)
        if self.history and self.history[-1]["role"] == "assistant":
            self.history[-1]["content"] = fixed
        remaining = verify_answer(fixed, self.chart) if self.chart else []
        self.last_checks = remaining
        yield {
            "type": "done", "text": fixed, "corrected": True, "checks": remaining,
            "backend": self.brain.last_used or self.cfg.backend,
            "sources": [{"title": s["title"], "heading": s.get("heading", ""), "score": s["score"]}
                        for s in self.last_sources],
        }

    def ask(self, query: str) -> dict[str, Any]:
        """Non-streaming convenience wrapper (used by the CLI/tests)."""
        answer, meta = "", {}
        for ev in self.stream_answer(query):
            if ev["type"] == "token":
                answer += ev["text"]
            elif ev["type"] == "done":
                meta = ev
            elif ev["type"] == "error":
                raise LLMError(ev["message"])
        return {"answer": answer, **meta}

    # ------------------------------------------------------------------ misc
    def reset_conversation(self) -> None:
        self.history = []

    def save_transcript(self, path: str | Path) -> Path:
        p = Path(path)
        payload = {
            "birth": {k: (v.isoformat() if isinstance(v, datetime) else v)
                      for k, v in (self.birth or {}).items()},
            "chart": self.chart,
            "conversation": self.history,
        }
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return p
