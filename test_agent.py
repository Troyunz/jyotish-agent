"""Self-checks for the chart engine, dasha, geo lookup and retrieval.

Run:  python test_agent.py        (no network, no LLM needed)
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import swisseph as swe

from core import dasha as dasha_mod
from core.agent import BirthDetails
from core.chart import calc_chart, nakshatra_of, sign_name, varga_sign
from core.config import Config
from core import geo

PASS, FAIL = 0, 0


def check(label: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label} {extra}")


def main() -> int:
    cfg = Config()
    print("config:")
    check("config.yaml loads", bool(cfg.raw), str(cfg.path))
    check("backend is a known provider", cfg.backend in ("local", "gemini", "openai", "anthropic"), cfg.backend)

    print("\nswiss ephemeris:")
    jd = swe.julday(1990, 1, 1, 6.5)
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    check("Lahiri ayanamsa 1990-01-01 = 23.7174", abs(swe.get_ayanamsa_ut(jd) - 23.717417) < 1e-4)

    print("\nnakshatra maths:")
    check("0 deg = Ashwini pada 1", nakshatra_of(0.0)["name"] == "Ashwini" and nakshatra_of(0.0)["pada"] == 1)
    check("13.4 deg = Bharani pada 1", nakshatra_of(13.4)["name"] == "Bharani" and nakshatra_of(13.4)["pada"] == 1)
    check("359.9 deg = Revati pada 4", nakshatra_of(359.9)["name"] == "Revati" and nakshatra_of(359.9)["pada"] == 4)
    check("D9 formula: 15 Aries -> Leo navamsa", sign_name(varga_sign(15.0, 9)) == "Simha (Leo)")
    check("D10 formula: 0 Aries -> Aries dashamsa", sign_name(varga_sign(0.5, 10)) == "Mesha (Aries)")

    print("\ngeo / timezone (offline):")
    c = geo.find_city("bangalore")
    check("'bangalore' resolves (alias ok)", bool(c) and c["city"] in ("Bengaluru", "Bangalore"), str(c))
    check("'New Delhi' resolves", (geo.find_city("New Delhi") or {}).get("city") == "New Delhi")
    check("typo 'kolkatta' fuzzy-resolves", (geo.find_city("kolkatta") or {}).get("city") == "Kolkata")
    check("tz for Bengaluru = Asia/Kolkata", geo.tz_for(12.9716, 77.5946) == "Asia/Kolkata")

    print("\nchart for 1990-01-01 12:00 IST, New Delhi:")
    details = BirthDetails(name="Test", dob="1990-01-01", tob="12:00", city="New Delhi")
    birth = details.resolve(cfg)
    chart = calc_chart(birth)
    check("timezone resolved", birth["tz"] == "Asia/Kolkata")
    check("Lagna is Pisces (Meena)", chart["ascendant"]["sign_name"].startswith("Meena"), chart["ascendant"]["sign_name"])
    check("Moon in Aquarius (Kumbha)", chart["planets"]["Moon"]["sign_name"].startswith("Kumbha"))
    check("Moon nakshatra Dhanishta", chart["planets"]["Moon"]["nakshatra"].startswith("Dhanishta"))
    check("Sun in Sagittarius (Dhanu)", chart["planets"]["Sun"]["sign_name"].startswith("Dhanu"))
    check("Mercury flagged retrograde", chart["planets"]["Mercury"]["retrograde"] is True)
    check("Ketu opposite Rahu", abs(((chart["planets"]["Rahu"]["lon"] - chart["planets"]["Ketu"]["lon"]) % 360) - 180) < 1e-6)
    check("all 9 grahas present", len(chart["planets"]) == 9)
    check("12 bhavas built with lords", len(chart["houses"]) == 12 and chart["houses"][1]["lord"] == "Jupiter")
    check("houses filled for every graha", all(p["house"] in range(1, 13) for p in chart["planets"].values()))
    check("16 vargas computed per graha", len(chart["planets"]["Sun"]["vargas"]) == 16)
    check("yogas detected", len(chart["yogas"]) > 0, f"count={len(chart['yogas'])}")
    check("panchanga has tithi", "tithi" in chart["panchanga"] and "Shukla" in chart["panchanga"]["tithi"])
    check("ascendant nakshatra = Uttara Bhadrapada", chart["ascendant"]["nakshatra"]["name"] == "Uttara Bhadrapada")

    print("\nvimshottari dasha:")
    md = chart["dashas"][0]
    check("first mahadasha lord is Mars (Dhanishta lord)", md["lord"] == "Mars", md["lord"])
    check("Mars balance at birth ~0.10 years", abs((md["balance_at_birth"] or 0) - 0.1057) < 0.02,
          str(md["balance_at_birth"]))
    check("second mahadasha is Rahu (1986-2004 style sequence)", chart["dashas"][1]["lord"] == "Rahu")
    check("jupiter mahadasha follows rahu", chart["dashas"][2]["lord"] == "Jupiter")
    check("saturn follows jupiter", chart["dashas"][3]["lord"] == "Saturn")
    cur = dasha_mod.current_periods(chart["dashas"], datetime(2026, 10, 4))
    check("Saturn mahadasha runs in 2026", cur.get("maha", {}).get("lord") == "Saturn", str(cur))
    check("antardasha present for 2026", "antar" in cur, str(cur))
    check("upcoming changes listed", len(chart["dasha_upcoming"]) > 0)

    print("\nbirth-time-unknown handling:")
    d2 = BirthDetails(name="X", dob="1985-03-03", tob="", city="Mumbai", time_unknown=True)
    b2 = d2.resolve(cfg)
    chart2 = calc_chart(b2)
    check("assumes 12:00 local", b2["local_dt"].hour == 12)
    check("warning attached", len(b2["warnings"]) == 1)
    check("chart still computes", chart2["ascendant"]["sign"] in range(1, 13))

    print("\nvalidation and errors:")
    try:
        BirthDetails(dob="", tob="10:00", city="Delhi").resolve(cfg)
        check("missing dob raises", False)
    except ValueError:
        check("missing dob raises", True)
    try:
        BirthDetails(dob="1990-01-01", tob="10:00", city="Atlantis-nowhere").resolve(cfg)
        check("unknown city raises", False)
    except ValueError as exc:
        check("unknown city raises with helpful message", "latitude" in str(exc))

    print("\nknowledge base (BM25 path, no network):")
    from core.rag import KnowledgeBase

    kb = KnowledgeBase(cfg)
    if not kb.chunks:
        res = kb.build(embed=False)
        print(f"  (built index: {res['message']})")
    check("index has chunks", len(kb.chunks) > 20, f"chunks={len(kb.chunks)}")
    hits = kb.search("sade sati saturn transit from the moon", k=4)
    check("search returns hits", len(hits) > 0, f"hits={len(hits)}")
    blob = " ".join(h["text"].lower() for h in hits)
    check("sade sati found in classical notes", "sade sati" in blob)
    hits2 = kb.search("mangal dosha exceptions cancellation", k=4)
    blob2 = " ".join(h["text"].lower() for h in hits2)
    check("mangal dosha cancellations retrievable", "cancel" in blob2 or "exception" in blob2)

    print("\nagent wiring (no LLM call):")
    from core.agent import JyotishAgent

    agent = JyotishAgent(cfg)
    agent.set_birth(BirthDetails(name="Test", dob="1990-01-01", tob="12:00", city="New Delhi"))
    txt = agent.chart_text()
    check("chart text renders long", len(txt) > 3000, f"len={len(txt)}")
    check("chart text has bhavas and dashas", "BHAVAS" in txt and "VIMSHOTTARI" in txt and "GOCHARA" in txt)
    msgs = agent.build_messages("Will I travel abroad?")
    check("system prompt includes chart ground truth", "CALCULATED CHART DATA" in msgs[0]["content"])
    check("retrieval injected classical refs", "CLASSICAL REFERENCES" in msgs[0]["content"])
    check("user message last", msgs[-1]["role"] == "user")

    print(f"\n{'-' * 46}\n{PASS} passed, {FAIL} failed\n{'-' * 46}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
