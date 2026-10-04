"""Local knowledge base (RAG) over classical Jyotisha texts.

The knowledge base lives in data/knowledge/*.md (plain text or markdown, PDFs optional).
Retrieval is hybrid:
  * BM25 keyword scoring - always available, no extra downloads
  * dense embeddings via Ollama (nomic-embed-text) or the OpenAI API - used when reachable
Everything stays on your machine; no index is uploaded anywhere.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

import httpx

from .config import Config

WORD_RE = re.compile(r"[\w'’-]+", re.UNICODE)
CHUNK_CHARS = 1100
CHUNK_OVERLAP = 150
INDEXABLE = (".md", ".txt", ".pdf")


def _knowledge_files(kdir: Path) -> list[Path]:
    return sorted(p for p in kdir.rglob("*") if p.suffix.lower() in INDEXABLE)


def _file_signatures(kdir: Path) -> dict[str, dict[str, Any]]:
    """sha1 + size per knowledge file, used to detect a stale index."""
    sig: dict[str, dict[str, Any]] = {}
    for p in _knowledge_files(kdir):
        try:
            data = p.read_bytes()
        except OSError:
            continue
        sig[p.name] = {"sha1": hashlib.sha1(data).hexdigest(), "size": len(data)}
    return sig


# ------------------------------------------------------------------ text utils

def _tokens(text: str) -> list[str]:
    return [t.lower() for t in WORD_RE.findall(text)]


def _split_into_chunks(text: str, source: str) -> list[dict[str, Any]]:
    """Split on headings/blank lines, then pack into ~CHUNK_CHARS windows."""
    blocks: list[tuple[str, str]] = []  # (heading, body)
    heading = ""
    buf: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            if buf:
                blocks.append((heading, "\n".join(buf).strip()))
                buf = []
            heading = line.lstrip("# ").strip()
        elif not line.strip():
            if buf:
                blocks.append((heading, "\n".join(buf).strip()))
                buf = []
        else:
            buf.append(line)
    if buf:
        blocks.append((heading, "\n".join(buf).strip()))

    chunks: list[dict[str, Any]] = []
    carry = ""
    for head, body in blocks:
        piece = (carry + "\n" + body).strip() if carry else body
        carry = ""
        if len(piece) <= CHUNK_CHARS:
            if piece:
                chunks.append({"source": source, "heading": head, "text": piece})
            continue
        sentences = re.split(r"(?<=[.!?;])\s+", piece)
        cur = ""
        for s in sentences:
            if len(cur) + len(s) + 1 > CHUNK_CHARS and cur:
                chunks.append({"source": source, "heading": head, "text": cur.strip()})
                cur = cur[-CHUNK_OVERLAP:] + " " + s
            else:
                cur = (cur + " " + s).strip()
        if cur.strip():
            chunks.append({"source": source, "heading": head, "text": cur.strip()})
    return chunks


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # pragma: no cover
        print(f"  ! could not read PDF {path.name}: {exc}")
        return ""


# ------------------------------------------------------------------ embeddings

class Embedder:
    """Tries Ollama first (free, local), then OpenAI. Falls back to None (BM25-only)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.provider: str | None = None
        self.model = cfg.embed_model
        self.host = cfg.provider_settings("local")["host"]
        pref = cfg.embed_provider
        if pref == "auto":
            if self._ollama_ok():
                self.provider = "ollama"
            elif cfg.has_key("openai"):
                self.provider = "openai"
        elif pref == "ollama" and self._ollama_ok():
            self.provider = "ollama"
        elif pref == "openai" and cfg.has_key("openai"):
            self.provider = "openai"
            self.model = "text-embedding-3-small"
        elif pref == "bm25":
            self.provider = None

    def _ollama_ok(self) -> bool:
        try:
            with httpx.Client(timeout=4.0) as c:
                r = c.get(f"{self.host}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
                return any(m == self.model or m.startswith(self.model.split(":")[0]) for m in models)
        except Exception:
            return False

    def embed(self, texts: list[str], progress: Callable[[int, int], None] | None = None) -> list[list[float]] | None:
        if not self.provider:
            return None
        out: list[list[float]] = []
        if self.provider == "ollama":
            try:
                with httpx.Client(timeout=120.0) as c:
                    for i, t in enumerate(texts):
                        r = c.post(f"{self.host}/api/embeddings", json={"model": self.model, "prompt": t})
                        r.raise_for_status()
                        out.append(r.json()["embedding"])
                        if progress and i % 10 == 0:
                            progress(i + 1, len(texts))
                return out
            except Exception as exc:
                print(f"  ! Ollama embeddings failed ({exc}); falling back")
                if not self.cfg.has_key("openai"):
                    self.provider = None
                    return None
                self.provider, self.model = "openai", "text-embedding-3-small"
        if self.provider == "openai":
            try:
                from openai import OpenAI

                client = OpenAI()
                for i in range(0, len(texts), 96):
                    batch = texts[i:i + 96]
                    res = client.embeddings.create(model=self.model, input=batch)
                    out.extend([d.embedding for d in res.data])
                    if progress:
                        progress(min(i + 96, len(texts)), len(texts))
                return out
            except Exception as exc:
                print(f"  ! OpenAI embeddings failed ({exc}); BM25 only")
                self.provider = None
        return None


# ------------------------------------------------------------------ the index

class KnowledgeBase:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.index_path: Path = cfg.index_path
        self.chunks: list[dict[str, Any]] = []
        self.vectors: list[list[float]] | None = None
        self.doc_freq: Counter = Counter()
        self.avg_len = 1.0
        self.meta: dict[str, Any] = {}
        self.load()

    # -------------------------------------------------------------- persistence
    def load(self) -> bool:
        if not self.index_path.exists():
            return False
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.chunks = data.get("chunks", [])
            self.vectors = data.get("embeddings")
            self.meta = data.get("meta", {})
            self._prepare_stats()
            return bool(self.chunks)
        except Exception as exc:
            print(f"  ! index unreadable ({exc}); rebuild with: python build_index.py")
            return False

    def save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": self.meta,
            "chunks": self.chunks,
            "embeddings": self.vectors,
        }
        self.index_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _prepare_stats(self) -> None:
        self.doc_freq = Counter()
        total = 0
        for ch in self.chunks:
            toks = set(_tokens(ch["text"]))
            ch["_len"] = len(_tokens(ch["text"]))
            total += ch["_len"]
            for t in toks:
                self.doc_freq[t] += 1
        self.avg_len = max(1.0, total / max(1, len(self.chunks)))

    # -------------------------------------------------------------- build
    def build(self, force: bool = False, embed: bool = True) -> dict[str, Any]:
        kdir = self.cfg.knowledge_dir
        files = _knowledge_files(kdir)
        if not files:
            return {"ok": False, "message": f"No .md/.txt/.pdf files found in {kdir}. Add classical text summaries there."}

        chunks: list[dict[str, Any]] = []
        for p in files:
            text = _read_pdf(p) if p.suffix.lower() == ".pdf" else p.read_text(encoding="utf-8", errors="ignore")
            src = p.stem
            for ch in _split_into_chunks(text, src):
                ch["title"] = self._title_of(src)
                chunks.append(ch)
                ch["id"] = len(chunks) - 1

        self.chunks = chunks
        self._prepare_stats()
        self.vectors = None
        provider = None
        if embed and self.vectors is None:
            emb = Embedder(self.cfg)
            vectors = emb.embed([c["text"] for c in chunks])
            if vectors:
                self.vectors = vectors
                provider = f"{emb.provider}:{emb.model}"
        self.meta = {
            "files": [p.name for p in files],
            "files_detail": _file_signatures(kdir),   # sha1 per file - used for staleness checks
            "chunks": len(chunks),
            "embedding_provider": provider or "bm25-only",
            "built": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        self.save()
        return {"ok": True, "message": f"Indexed {len(chunks)} chunks from {len(files)} file(s). "
                                        f"Embeddings: {provider or 'none (BM25 keyword search)'}", **self.meta}

    @staticmethod
    def _title_of(stem: str) -> str:
        pretty = {
            "bphs_summary": "Brihat Parashara Hora Shastra (Parashara)",
            "phaladeepika_summary": "Phaladeepika (Mantreswara)",
            "saravali_summary": "Saravali (Kalyana Varma)",
            "jataka_parijata_summary": "Jataka Parijata (Vaidyanatha Dikshita)",
            "brihat_jataka_summary": "Brihat Jataka (Varahamihira)",
            "uttara_kalamrita_summary": "Uttara Kalamrita (Kalidasa)",
            "vedic_foundations": "Jyotisha foundations (compiled)",
            "classical_yogas": "Classical yogas & doshas (compiled)",
            "dasha_interpretation": "Vimshottari dasha interpretation (compiled)",
            "transit_gochara": "Gochara - planetary transits (compiled)",
            "remedies": "Traditional remedies (compiled)",
            "western_planets": "Western astrology - planets (compiled)",
            "western_aspects": "Western astrology - aspects & orbs (compiled)",
        }
        return pretty.get(stem, stem.replace("_", " ").title())

    # -------------------------------------------------------------- search
    def _bm25(self, query_tokens: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
        n = len(self.chunks)
        scores = [0.0] * n
        q = Counter(query_tokens)
        for term, qf in q.items():
            if term not in self.doc_freq:
                continue
            df = self.doc_freq[term]
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for i, ch in enumerate(self.chunks):
                toks = ch.get("_tokens")
                if toks is None:
                    toks = Counter(_tokens(ch["text"]))
                    ch["_tokens"] = toks
                tf = toks.get(term, 0)
                if tf:
                    dl = ch.get("_len", 1)
                    scores[i] += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / self.avg_len))
        return scores

    def _cosine(self, qvec: list[float]) -> list[float]:
        import numpy as np

        if not self.vectors:
            return []
        M = np.array(self.vectors, dtype="float32")
        q = np.array(qvec, dtype="float32")
        denom = (np.linalg.norm(M, axis=1) * (np.linalg.norm(q) + 1e-9))
        return (M @ q / (denom + 1e-9)).tolist()

    def search(self, query: str, k: int | None = None) -> list[dict[str, Any]]:
        if not self.chunks:
            return []
        k = k or self.cfg.rag_top_k
        q_tokens = _tokens(query)
        if not q_tokens:
            return []
        bm = self._bm25(q_tokens)

        dense: list[float] = []
        if self.vectors:
            emb = Embedder(self.cfg)
            if emb.provider:
                vec = emb.embed([query])
                if vec:
                    dense = self._cosine(vec[0])

        if dense and len(dense) == len(bm):
            def norm(xs: list[float]) -> list[float]:
                lo, hi = min(xs), max(xs)
                return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]
            bmn, dn = norm(bm), norm(dense)
            scores = [0.45 * bm + 0.55 * d for bm, d in zip(bmn, dn)]
        else:
            scores = bm

        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for i in order:
            if scores[i] <= 0:
                continue
            ch = self.chunks[i]
            results.append({
                "score": round(float(scores[i]), 4),
                "source": ch["source"],
                "title": ch.get("title", ch["source"]),
                "heading": ch.get("heading", ""),
                "text": ch["text"],
            })
        return results

    @staticmethod
    def context_block(results: Iterable[dict[str, Any]]) -> str:
        out = []
        for i, r in enumerate(results, 1):
            head = f"[{i}] {r['title']}" + (f" - {r['heading']}" if r.get("heading") else "")
            out.append(f"{head}\n{r['text']}")
        return "\n\n".join(out)

    # -------------------------------------------------------------- status
    def staleness(self) -> dict[str, Any]:
        """Has the knowledge folder changed since the index was built?

        Without this, editing a book or adding a new one silently keeps serving the
        old content - the user assumes the agent ignored their text.
        """
        current = _file_signatures(self.cfg.knowledge_dir)
        indexed = self.meta.get("files_detail") or {}
        if not self.chunks:
            return {"known": False, "stale": True, "reason": "no index built yet",
                    "added": sorted(current), "removed": [], "changed": []}
        if not indexed:
            # index built by an older version that did not record signatures
            old = set(self.meta.get("files", []))
            added, removed = sorted(set(current) - old), sorted(old - set(current))
            return {"known": False, "stale": bool(added or removed), "reason": "index predates signature tracking",
                    "added": added, "removed": removed, "changed": []}
        added = sorted(set(current) - set(indexed))
        removed = sorted(set(indexed) - set(current))
        changed = sorted(n for n in (set(current) & set(indexed))
                         if current[n]["sha1"] != indexed[n]["sha1"])
        return {"known": True, "stale": bool(added or removed or changed), "reason": "",
                "added": added, "removed": removed, "changed": changed}

    def status(self) -> str:
        if not self.chunks:
            return "empty - run: python build_index.py"
        emb = self.meta.get("embedding_provider", "?")
        base = f"{len(self.chunks)} chunks from {len(self.meta.get('files', []))} file(s); embeddings: {emb}"
        st = self.staleness()
        if st["stale"]:
            parts = []
            if st["added"]:
                parts.append(f"{len(st['added'])} new")
            if st["changed"]:
                parts.append(f"{len(st['changed'])} edited")
            if st["removed"]:
                parts.append(f"{len(st['removed'])} removed")
            base += f" | ⚠ STALE ({', '.join(parts)}) - rebuild: python build_index.py"
        return base
