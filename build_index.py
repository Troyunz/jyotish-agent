"""Build (or rebuild) the local knowledge-base index.

Usage:
    python build_index.py              # incremental-friendly full rebuild
    python build_index.py --no-embed   # keyword-only index (fastest, no embedding model needed)
    python build_index.py --force      # same as default; kept for clarity

Reads every .md / .txt / .pdf in data/knowledge/ (per config.yaml).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import Config
from core.rag import Embedder, KnowledgeBase


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Jyotish knowledge index")
    ap.add_argument("--no-embed", action="store_true", help="skip embeddings, BM25 keyword search only")
    ap.add_argument("--check", action="store_true", help="only report what is available")
    args = ap.parse_args()

    cfg = Config()
    print(f"Knowledge directory : {cfg.knowledge_dir}")
    print(f"Index file          : {cfg.index_path}")

    kb = KnowledgeBase(cfg)
    if args.check:
        emb = Embedder(cfg)
        print(f"Embedding provider  : {emb.provider or 'none (BM25 only)'} {emb.model if emb.provider else ''}")
        print(f"Index status        : {kb.status()}")
        return 0

    files = sorted(p.name for p in cfg.knowledge_dir.rglob("*")
                   if p.suffix.lower() in (".md", ".txt", ".pdf"))
    if not files:
        print(f"\nNo knowledge files found in {cfg.knowledge_dir}.")
        print("Add .md/.txt/.pdf books or notes there, then re-run this script.")
        return 1
    print(f"Found {len(files)} file(s):")
    for f in files:
        print(f"  - {f}")

    print("\nIndexing (chunking + embeddings if available)...")
    result = kb.build(embed=not args.no_embed)
    print("\n" + result["message"])
    if result.get("ok"):
        print(f"Saved to {cfg.index_path}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
