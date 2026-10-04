"""Command-line chat with the Jyotish agent - handy for testing without the web UI.

Examples:
    python cli.py --name "Asha" --dob 1990-01-01 --tob 12:00 --city Delhi
    python cli.py --ask "What does my 7th house say about marriage?" --dob 1995-06-15 --tob 04:30 --city Chennai
    python cli.py                      # interactive: it will ask for birth details

In-chat commands:
    /chart      show the full calculated chart text
    /dashas     show the Vimshottari dasha table
    /sources    show the classical sources used in the last answer
    /backend X  switch brain (local | gemini | openai | anthropic)
    /birth      re-enter birth details
    /reset      clear the conversation (keeps the chart)
    /export F   save transcript+chart to JSON file F
    /quit
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import dasha as dasha_mod
from core.agent import BirthDetails, JyotishAgent
from core.config import Config


def ask_birth(details: BirthDetails) -> BirthDetails:
    print("\n--- Birth details (leave blank to keep current value) ---")
    name = input(f"Name [{details.name}]: ").strip()
    dob = input(f"Date of birth YYYY-MM-DD [{details.dob}]: ").strip()
    tob = input(f"Time of birth HH:MM (24h, local clock) [{details.tob}]: ").strip()
    city = input(f"Birth city [{details.city}]: ").strip()
    unknown = input("Birth time unknown? (y/N): ").strip().lower() == "y"
    return BirthDetails(
        name=name or details.name, dob=dob or details.dob, tob=tob or details.tob,
        city=city or details.city, time_unknown=unknown or details.time_unknown,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Jyotish agent - command line")
    ap.add_argument("--name", default="Native")
    ap.add_argument("--dob", default="", help="YYYY-MM-DD")
    ap.add_argument("--tob", default="", help="HH:MM local")
    ap.add_argument("--city", default="")
    ap.add_argument("--lat", type=float, default=None)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--tz", default=None, help="IANA timezone, e.g. Asia/Kolkata")
    ap.add_argument("--time-unknown", action="store_true")
    ap.add_argument("--backend", default=None, help="local | gemini | openai | anthropic")
    ap.add_argument("--ask", default=None, help="ask one question and exit")
    args = ap.parse_args()

    cfg = Config()
    agent = JyotishAgent(cfg)
    if args.backend:
        agent.set_backend(args.backend)

    details = BirthDetails(name=args.name, dob=args.dob, tob=args.tob, city=args.city,
                           lat=args.lat, lon=args.lon, tz=args.tz, time_unknown=args.time_unknown)
    if details.validation_error():
        details = ask_birth(details)

    try:
        agent.set_birth(details)
    except ValueError as exc:
        print(f"\n! {exc}")
        return 2

    b = agent.birth
    print(f"\nChart calculated: {b['name']} | {b['local_dt']} ({b['tz']}) | {b['place']}")
    for w in agent.warnings:
        print(f"  note: {w}")
    asc = agent.chart["ascendant"]
    print(f"  Lagna: {asc['sign_name']} {asc['deg_str']} | Moon: {agent.chart['planets']['Moon']['sign_name']} "
          f"({agent.chart['planets']['Moon']['nakshatra']}) | Current dasha: {agent.chart['dasha_current'].get('maha', {}).get('lord', '?')}")

    if args.ask:
        print("\n" + "=" * 70)
        for ev in agent.stream_answer(args.ask):
            if ev["type"] == "token":
                print(ev["text"], end="", flush=True)
            elif ev["type"] == "done":
                print(f"\n\n[brain: {ev['backend']}]")
                for s in ev.get("sources", []):
                    print(f"  ref: {s['title']} - {s.get('heading', '')} ({s['score']})")
            elif ev["type"] == "error":
                print(f"\n! {ev['message']}")
        return 0

    print("\nAsk anything. Commands: /chart /dashas /sources /backend /birth /reset /export /quit")
    while True:
        try:
            q = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q in ("/quit", "/exit"):
            break
        if q == "/chart":
            print("\n" + agent.chart_text())
            continue
        if q == "/dashas":
            rows = dasha_mod.flatten(agent.chart["dashas"], level="md")
            for r in rows[:40]:
                print(f"  {r['Level']:16s} {r['Lord']:8s} {r['Start']} -> {r['End']}")
            print("  (showing first 40 Mahadasha/Antardasha rows)")
            continue
        if q == "/sources":
            for s in agent.last_sources:
                print(f"  - {s['title']} | {s.get('heading', '')} | score {s['score']}")
            if not agent.last_sources:
                print("  (no knowledge-base references were retrieved)")
            continue
        if q.startswith("/backend"):
            parts = q.split()
            if len(parts) == 2:
                agent.set_backend(parts[1])
                print(f"  brain -> {parts[1]}")
            else:
                print("  usage: /backend local|gemini|openai|anthropic")
            continue
        if q == "/birth":
            details = ask_birth(details)
            agent.set_birth(details)
            print("  chart recalculated")
            continue
        if q == "/reset":
            agent.reset_conversation()
            print("  conversation cleared (chart kept)")
            continue
        if q.startswith("/export"):
            parts = q.split(maxsplit=1)
            path = parts[1] if len(parts) > 1 else f"transcript_{datetime.now(timezone.utc):%Y%m%d_%H%M}.json"
            p = agent.save_transcript(path)
            print(f"  saved {p}")
            continue

        print()
        try:
            for ev in agent.stream_answer(q):
                if ev["type"] == "token":
                    print(ev["text"], end="", flush=True)
                elif ev["type"] == "done":
                    print(f"\n\n[brain: {ev['backend']}]")
                elif ev["type"] == "error":
                    print(f"\n! {ev['message']}")
        except KeyboardInterrupt:
            print("\n(stopped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
