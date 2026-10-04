"""Self-checks for the chart engine, dasha, geo lookup and retrieval.

Run:  python test_agent.py        (no network, no LLM needed)
"""
from __future__ import annotations

import re
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

    print("\nposition convention & ephemeris (precision):")
    from core.chart import EPHE_FILES, ephemeris_status, position_flags, _dms

    check("default position mode is 'true' (JHora parity)", cfg.position_mode == "true", cfg.position_mode)
    check("config reports ephe_path", cfg.ephe_path.name == "ephe", str(cfg.ephe_path))

    st = ephemeris_status()
    check("bundled .se1 ephemeris files present",
          all(f in st["files"] for f in EPHE_FILES), str(st["files"]))
    check("Swiss Ephemeris files are actually in use (not Moshier fallback)",
          "Swiss Ephemeris" in st["in_use"], st["in_use"])
    check("chart records the ephemeris it used",
          "Swiss Ephemeris" in chart["settings"]["ephemeris"], chart["settings"]["ephemeris"])
    check("chart records the position convention",
          chart["settings"]["positions"] == "true" and "Jagannatha Hora parity" in chart["settings"]["positions_label"])

    # flags: 'true' adds TRUEPOS|NONUT|NOGDEFL, 'apparent' does not
    ft, fa = position_flags("true"), position_flags("apparent")
    check("true mode sets TRUEPOS|NONUT|NOGDEFL",
          all(ft & f for f in (swe.FLG_TRUEPOS, swe.FLG_NONUT, swe.FLG_NOGDEFL)))
    check("apparent mode leaves them off",
          not any(fa & f for f in (swe.FLG_TRUEPOS, swe.FLG_NONUT, swe.FLG_NOGDEFL)))
    check("both modes use SWIEPH + sidereal + speed",
          all(m & swe.FLG_SWIEPH and m & swe.FLG_SIDEREAL and m & swe.FLG_SPEED for m in (ft, fa)))

    # measured impact: apparent vs true must match the documented magnitudes
    jd_g = swe.julday(1990, 1, 1, 6.5)
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    deltas = {}
    for name, pid in (("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS), ("Saturn", swe.SATURN)):
        a_lon = swe.calc_ut(jd_g, pid, fa)[0][0]
        t_lon = swe.calc_ut(jd_g, pid, ft)[0][0]
        deltas[name] = abs(t_lon - a_lon) * 3600
    check("Mars differs by ~34\" between modes (documented)", 25 < deltas["Mars"] < 45, f"{deltas['Mars']:.1f}\"")
    check("Sun differs by ~21\" between modes", 10 < deltas["Sun"] < 30, f"{deltas['Sun']:.1f}\"")
    check("Moon differs by <2\" (true positions barely affect it)", deltas["Moon"] < 2, f"{deltas['Moon']:.1f}\"")

    # golden chart: pinned longitudes catch any silent engine change in future
    GOLDEN = {"Sun": 256.865713, "Moon": 306.465455, "Mars": 226.127500, "Mercury": 272.013316,
              "Jupiter": 71.455677, "Venus": 282.529793, "Saturn": 261.917182, "Rahu": 294.726414}
    for g, expected in GOLDEN.items():
        got = chart["planets"][g]["lon"]
        check(f"golden longitude {g} = {expected}", abs(got - expected) < 1e-6, f"got {got:.6f}")
    check("golden ascendant = 343.922640", abs(chart["ascendant"]["lon"] - 343.922640) < 1e-6,
          f"{chart['ascendant']['lon']:.6f}")

    # dms formatting can never emit an illegal value
    check("dms clamps at sign end (29.99999 never becomes 30° or 60')",
          _dms(29.99999) == "29°59'59\"", _dms(29.99999))
    check("dms rounds up legally inside a sign (12.999999 -> 13°)",
          _dms(12.999999) == "13°00'00\"", _dms(12.999999))
    check("dms normal case", _dms(15.5) == "15°30'00\"", _dms(15.5))
    check("dms zero", _dms(0.0) == "00°00'00\"", _dms(0.0))
    bad = [x / 1000 for x in range(0, 300000, 7) if (
        "°60'" in _dms(x / 1000) or "'60\"" in _dms(x / 1000) or _dms(x / 1000).startswith("30°"))]
    check("invariant sweep: 42,857 longitudes produce no illegal dms strings", not bad,
          f"offenders: {bad[:5]}")

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

    print("\nashtakavarga (validated against classical totals):")
    from core import ashtakavarga as av

    avd = chart["ashtakavarga"]
    check("BAV totals are 48/49/39/54/56/52/39",
          all(avd["totals"][p] == v for p, v in av.EXPECTED_TOTALS.items()),
          str(avd["totals"]))
    check("SAV total is 337", avd["sav_total"] == 337, str(avd["sav_total"]))
    check("every sign has 0-8 bindus per planet",
          all(0 <= v <= 8 for g in avd["bav"].values() for v in g.values()))
    check("SAV by house sums to 337", sum(avd["by_house"].values()) == 337)
    check("bindus_by_sign matches (house 1 = lagna sign)",
          avd["by_house"][1] == avd["sav"][chart["ascendant"]["sign"]])
    probe = av.bindu_of(chart, "Saturn", chart["planets"]["Moon"]["sign"])
    check("transit bindu lookup works", probe is not None and 0 <= probe["bav"] <= 8, str(probe))
    check("grade() buckets correctly", av.grade(29) == "strong support" and av.grade(23) == "average"
          and av.grade(18) == "weak / friction")

    print("\nanswer verification (self-check):")
    from core.verify import correction_prompt, verify_answer

    # correct statements must pass clean
    good = ("Your Lagna is Pisces. Jupiter sits in the 4th house. Saturn is in the 10th house. "
            "The 7th house lord Mercury is in the 11th house.")
    check("correct claims produce no issues", verify_answer(good, chart) == [], str(verify_answer(good, chart)))

    # wrong house, wrong sign, wrong lord must be caught
    bad = ("Jupiter is in the 5th house. In your chart Mercury is in Aries. "
           "The 7th house lord is Jupiter. Saturn is retrograde.")
    issues = verify_answer(bad, chart)
    kinds = {i["kind"] for i in issues}
    check("wrong planet-house caught", "planet-house" in kinds, str(kinds))
    check("wrong planet-sign caught", "planet-sign" in kinds, str(kinds))
    check("wrong house-lord caught", "house-lord" in kinds, str(kinds))
    check("wrong retrograde flag caught", "flag-retrograde" in kinds, str(kinds))
    check("issue carries the computed data", all(i.get("data") for i in issues))

    # must NOT flag transits, theory or hypotheticals (false-positive guard)
    harmless = ("Saturn transiting the 4th house brings pressure. Jupiter is transiting your 10th house. "
                "If Jupiter were in the 5th house it would aspect the 9th. "
                "The 7th house represents marriage and partnership.")
    fp = verify_answer(harmless, chart)
    check("transit/theory sentences are not flagged", fp == [], str(fp))

    # dasha year check
    dasha_bad = "Your Saturn mahadasha runs through 2019 according to the chart."
    check("impossible dasha year caught", any(i["kind"] == "dasha-year" for i in verify_answer(dasha_bad, chart)))
    dasha_ok = "Your Saturn mahadasha runs from 2024 onward."
    check("valid dasha year accepted", not any(i["kind"] == "dasha-year" for i in verify_answer(dasha_ok, chart)))
    check("correction prompt built", "CONTRADICT" in correction_prompt(issues))

    print("\ntopic routing:")
    from core.prompts import detect_topic

    cases = [("When will I get married?", "marriage"), ("Which career suits me?", "career"),
             ("How is my financial situation and property?", "wealth"),
             ("What about children?", "children"), ("Will my health be ok?", "health"),
             ("best course for my education and exams", "education"),
             ("What is happening in my transits this year?", "transit"),
             ("tell me about my sadhana and guru", "spirituality"),
             ("Give me a full reading", "general")]
    for q, expected in cases:
        got = detect_topic(q)[0]
        check(f"'{q[:34]}...' -> {expected}", got == expected, f"got {got}")
    check("checklists are non-empty", all(len(detect_topic(q)[1]) > 100 for q, _ in cases))

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
    check("topic checklist injected", "ANALYSIS CHECKLIST FOR THIS QUESTION" in msgs[0]["content"])
    check("ashtakavarga present in chart text", "ASHTAKAVARGA" in txt and "bindus" in txt)
    check("transits graded with bindus", "bindus: own" in txt)
    msgs2 = agent.build_messages("When will I marry?")
    check("marriage topic detected in agent", agent.last_topic == "marriage", agent.last_topic)
    check("marriage checklist text injected", "D9 (Navamsa)" in msgs2[0]["content"])
    check("user message last", msgs[-1]["role"] == "user")

    print("\ndependency declaration (regression guard):")
    # A fresh install must work. This caught a real bug: openai 3.x switched from
    # "httpx" to "httpx2", so an undeclared `import httpx` broke every new install.
    import ast

    NON_DECLARED_OK = {"core", "app"}          # local modules
    ALIASES = {"swisseph": "pyswisseph", "yaml": "pyyaml", "dotenv": "python-dotenv"}
    req_file = Path(__file__).parent / "requirements.txt"
    declared = set()
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            declared.add(re.split(r"[<>=!~;\[]", line)[0].strip().lower())
    imports: set[str] = set()
    for src in Path(__file__).parent.rglob("*.py"):
        if ".venv" in src.parts or "site-packages" in src.parts:
            continue
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imports.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
    third_party = {i for i in imports
                   if i not in sys.stdlib_module_names and i not in NON_DECLARED_OK}
    missing = {ALIASES.get(i, i).lower() for i in third_party} - declared
    check("every third-party import is declared in requirements.txt", not missing,
          f"undeclared: {sorted(missing)}")

    print("\nnamakshar (naming syllables):")
    from core import namakshar as nk
    from core.chart import NAKSHATRAS, moon_gati, render_chart_text

    check("27 nakshatras with 4 padas each = 108 syllables",
          len(nk.PADA_SYLLABLES) == 27 and all(len(p) == 4 for _, p, _ in nk.PADA_SYLLABLES),
          f"{len(nk.PADA_SYLLABLES)} nakshatras")
    all_syl = [d for _, padas, _ in nk.PADA_SYLLABLES for d, _ in padas]
    all_rom = [r for _, padas, _ in nk.PADA_SYLLABLES for _, r in padas]
    check("108 syllables, all non-empty", len(all_syl) == 108 and all(s.strip() for s in all_syl))
    check("every syllable has a roman form", all(r.strip() for r in all_rom))
    check("syllables are Devanagari", all(any("\u0900" <= c <= "\u097f" for c in s) for s in all_syl))
    check("nakshatra names match the engine's nakshatra list",
          [n for n, _, _ in nk.PADA_SYLLABLES] == [n for n, _ in NAKSHATRAS])

    # known values, verified against published pada tables
    known = [(0.0, "Ashwini", 1, "चु", "Chu"), (13.4, "Bharani", 1, "ली", "Li"),
             (40.0, "Rohini", 1, "ओ", "O"), (120.0, "Magha", 1, "मा", "Ma"),
             (246.0, "Mula", 2, "यो", "Yo"), (252.0, "Mula", 4, "भी", "Bhi"),
             (359.9, "Revati", 4, "ची", "Chi")]
    for lon, exp_nak, exp_pada, exp_dev, exp_rom in known:
        got = nk.syllables_for(lon)
        check(f"lon {lon} -> {exp_nak} pada {exp_pada} = {exp_dev} ({exp_rom})",
              got["nakshatra"] == exp_nak and got["pada"] == exp_pada
              and got["syllable"] == exp_dev and got["syllable_roman"] == exp_rom, str(got))

    # the test chart's Moon: Dhanishta pada 4 -> Ge
    moon_lon = chart["planets"]["Moon"]["lon"]
    got = nk.syllables_for(moon_lon)
    check("test chart Moon lands on Dhanishta pada 4 = Ge",
          got["nakshatra"] == "Dhanishta" and got["pada"] == 4 and got["syllable_roman"] == "Ge", str(got))
    check("chart carries the namakshar block",
          chart["namakshar"]["syllable_roman"] == got["syllable_roman"])
    check("all four padas returned", len(chart["namakshar"]["all_padas"]) == 4)

    # boundary sweep: every longitude yields a valid pada, no gaps
    bad = []
    x = 0.0
    while x < 360.0:
        r = nk.syllables_for(x)
        if not (1 <= r["pada"] <= 4 and r["syllable"]):
            bad.append(x)
        x += 1.0 / 60
    check("21,600-longitude sweep yields valid syllables with no gaps", not bad, f"{bad[:5]}")

    # boundary agreement: chart, namakshar and dasha must never disagree at a cusp
    cusp_nak = [(i * (360 / 27), nakshatra_of(i * (360 / 27))["name"], nk.syllables_for(i * (360 / 27))["nakshatra"])
                for i in range(27)]
    check("nakshatra agrees between chart and namakshar at all 27 cusps",
          all(c == d == NAKSHATRAS[i][0] for i, (_lon, c, d) in enumerate(cusp_nak)),
          str([t for t in cusp_nak if not (t[1] == t[2])]))
    cusp_pada = [(i * (360 / 108), nakshatra_of(i * (360 / 108))["pada"], nk.syllables_for(i * (360 / 108))["pada"])
                 for i in range(108)]
    check("pada agrees between chart and namakshar at all 108 cusps",
          all(c == d for _lon, c, d in cusp_pada) and all(1 <= c <= 4 for _l, c, _d in cusp_pada),
          str([t for t in cusp_pada if t[1] != t[2]]))
    check("10.000000 deg is Ashwini pada 4 (the float-boundary case)",
          nakshatra_of(10.0)["name"] == "Ashwini" and nakshatra_of(10.0)["pada"] == 4
          and nk.syllables_for(10.0)["syllable_roman"] == "La",
          f"{nakshatra_of(10.0)['name']} pada {nakshatra_of(10.0)['pada']}")
    check("40.000000 deg is Rohini pada 1 (the float-boundary case)",
          nakshatra_of(40.0)["name"] == "Rohini" and nakshatra_of(40.0)["pada"] == 1,
          f"{nakshatra_of(40.0)['name']} pada {nakshatra_of(40.0)['pada']}")
    # the dasha engine must start from the same nakshatra as the other two
    d_cusp = dasha_mod.vimshottari(40.0, datetime(2000, 1, 1))
    check("dasha at exactly 40.0 deg starts with Moon (Rohini's lord), not Mars (Krittika's)",
          d_cusp[0]["lord"] == "Moon", f"{d_cusp[0]['lord']} first")
    check("pada is never outside 1-4 across a 21,600-point sweep",
          all(1 <= nakshatra_of(i / 60.0)["pada"] <= 4 for i in range(21600)))

    # reverse lookup
    check("reverse: 'Ge' -> Dhanishta pada 4",
          any(h["nakshatra"] == "Dhanishta" and h["pada"] == 4 for h in nk.lookup("Ge")))
    check("reverse: Devanagari 'गे' works too",
          any(h["nakshatra"] == "Dhanishta" for h in nk.lookup("गे")))
    check("reverse: shared syllable returns several nakshatras", len(nk.lookup("Ta")) > 1,
          f"{len(nk.lookup('Ta'))} matches")
    check("reverse: a roman name matches on its first syllable ('Gautam' -> Ga family)",
          any(h["nakshatra"] == "Dhanishta" and h["pada"] == 1 for h in nk.lookup("Gautam")),
          str(nk.lookup("Gautam")))
    check("reverse: a Devanagari name matches on its first base character ('गौतम' -> ग)",
          any(h["syllable_roman"].startswith("Ga") for h in nk.lookup("गौतम")), str(nk.lookup("गौतम")))
    # श is genuinely not one of the 108 (the list has the retroflex ष); roman "Sharma"
    # matches only because English transliteration collapses श and ष onto "Sh".
    check("reverse: Devanagari 'शर्मा' honestly returns empty (श is not a pada syllable)",
          nk.lookup("शर्मा") == [], str(nk.lookup("शर्मा")))
    check("reverse: Devanagari 'ष' (the retroflex, which IS in the list) resolves",
          len(nk.lookup("ष")) > 0, str(nk.lookup("ष")))
    check("reverse: single letters stay a short, readable list (<20 hits)",
          all(len(nk.lookup(s)) < 20 for s in "RTA'SG"), str([(s, len(nk.lookup(s))) for s in "RTASG"]))
    check("reverse: unknown syllable returns empty, not an error", nk.lookup("Zz") == [])
    check("reverse: empty input is safe", nk.lookup("") == [])

    print("\nchandra gati (Moon's speed):")
    fast = moon_gati(14.0)
    slow = moon_gati(11.9)
    avg = moon_gati(13.2)
    check("15 deg/day (near the real maximum) is 'very fast'",
          moon_gati(15.0)["gati"].startswith("very fast"), moon_gati(15.0)["gati"])
    check("fast Moon classified fast", fast["gati"].startswith("fast"), fast["gati"])
    check("slow Moon classified slow", slow["gati"].startswith("slow"), slow["gati"])
    check("average Moon classified average", avg["gati"].startswith("average"), avg["gati"])
    check("very slow Moon classified ati-manda", moon_gati(11.0)["gati"].startswith("very slow"))
    # the documented claim: a nakshatra takes 20.9h (perigee) to 27.1h (apogee)
    perigee, apogee = moon_gati(15.31), moon_gati(11.79)
    check("nakshatra crossing spans ~20.9h (fastest) to ~27.1h (slowest)",
          20.7 < perigee["nakshatra_hours"] < 21.1 and 26.9 < apogee["nakshatra_hours"] < 27.3,
          f"perigee={perigee['nakshatra_hours']}h apogee={apogee['nakshatra_hours']}h")
    check("sign crossing spans ~47h to ~61h",
          46.5 < perigee["sign_hours"] < 47.5 and 60.5 < apogee["sign_hours"] < 61.5,
          f"perigee={perigee['sign_hours']}h apogee={apogee['sign_hours']}h")
    check("dasha sensitivity ~1.1 days per minute at mean speed",
          abs(avg["dasha_days_per_minute"] - 1.11) < 0.05, str(avg["dasha_days_per_minute"]))
    check("fast Moon shifts the dasha timeline more than a slow one",
          fast["dasha_days_per_minute"] > slow["dasha_days_per_minute"])
    check("chart carries the moon_profile block with all fields",
          all(k in chart["moon_profile"] for k in
              ("speed", "gati", "note", "nakshatra_hours", "sign_hours", "dasha_days_per_minute")))
    rendered = render_chart_text(chart)
    check("chandra gati rendered into the chart text", "CHANDRA GATI" in rendered)
    check("namakshar rendered into the chart text", "NAMAKSHAR" in rendered)
    check("chart text states the dasha sensitivity in human terms",
          "Birth-time sensitivity" in rendered and "dasha timeline" in rendered)
    check("table_text() lists all 27 nakshatras", nk.table_text().count(":") >= 27)

    print("\nknowledge index freshness:")
    import shutil
    import tempfile

    from core.config import Config as _Cfg
    from core.rag import KnowledgeBase as _KB

    tmp = Path(tempfile.mkdtemp(prefix="kbtest_"))
    try:
        (tmp / "knowledge").mkdir()
        (tmp / "knowledge" / "a.md").write_text("# Test A\nJupiter transit rules for marriage timing.", encoding="utf-8")
        cfg2 = _Cfg()
        cfg2.raw.setdefault("rag", {})["knowledge_dir"] = str(tmp / "knowledge")
        cfg2.raw["rag"]["index_path"] = str(tmp / "index.json")

        kb2 = _KB(cfg2)
        check("empty index reports as stale", kb2.staleness()["stale"] is True)

        res = kb2.build(embed=False)
        check("temp index builds", res["ok"] and res["chunks"] == 1, str(res.get("message")))
        check("freshly built index is NOT stale", kb2.staleness()["stale"] is False, str(kb2.staleness()))
        check("signatures recorded in meta", bool(kb2.meta.get("files_detail", {}).get("a.md", {}).get("sha1")))

        (tmp / "knowledge" / "a.md").write_text("# Test A\nEdited: Saturn transit rules.", encoding="utf-8")
        after_edit = kb2.staleness()
        check("editing a file is detected", after_edit["stale"] and after_edit["changed"] == ["a.md"],
              str(after_edit))

        (tmp / "knowledge" / "b.md").write_text("# Test B\nNew chapter.", encoding="utf-8")
        check("adding a file is detected", kb2.staleness()["added"] == ["b.md"], str(kb2.staleness()))

        (tmp / "knowledge" / "a.md").unlink()
        check("removing a file is detected", kb2.staleness()["removed"] == ["a.md"], str(kb2.staleness()))

        kb2.build(embed=False)
        check("rebuild clears the stale flag", kb2.staleness()["stale"] is False, str(kb2.staleness()))
        check("status() surfaces staleness in text", "STALE" in _KB(cfg2).status()
              or "chunks" in _KB(cfg2).status())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nproject consistency guards:")
    # app.py declares the core API level it needs; a mismatch must be caught here, not
    # by a user hitting a cryptic AttributeError after a git pull on a running server.
    import core as _core

    app_src = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
    m = re.search(r"REQUIRED_API_LEVEL\s*=\s*(\d+)", app_src)
    check("app.py declares REQUIRED_API_LEVEL", m is not None)
    if m:
        required = int(m.group(1))
        check(f"core API level satisfies app requirement ({_core.API_LEVEL} >= {required})",
              _core.API_LEVEL >= required, f"core={_core.API_LEVEL} app={required}")
    check("stale-process guard present in app.py", "Restart needed" in app_src)
    # the guard must not be able to pass on a module object that lacks new APIs
    check("guard uses a numeric level, not a version string",
          "getattr(_core, \"API_LEVEL\", 0)" in app_src)

    print(f"\n{'-' * 46}\n{PASS} passed, {FAIL} failed\n{'-' * 46}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
