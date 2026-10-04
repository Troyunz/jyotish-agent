"""Answer verification - catches the model contradicting the calculated chart.

Small local models (and occasionally big ones) drift: they say "Jupiter in the
5th house" when the ground truth says house 4, or invent a dasha year. This module
extracts verifiable claims from an answer with careful regexes and checks them
against the computed chart, returning precise corrections.

It is a heuristic, not a proof: it only checks the claim types it knows
(planet-house, planet-sign, house-lord, dignity flags, dasha-year) and deliberately
skips hedged or transit sentences to avoid false alarms. Anything it reports is
worth fixing; silence is not a guarantee.
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------ vocabularies

PLANETS: dict[str, list[str]] = {
    "Sun": ["sun", "surya", "ravi", "aditya"],
    "Moon": ["moon", "chandra", "soma"],
    "Mars": ["mars", "mangal", "mangala", "kuja", "angaraka"],
    "Mercury": ["mercury", "budha", "budh"],
    "Jupiter": ["jupiter", "guru", "brihaspati"],
    "Venus": ["venus", "shukra", "sukra"],
    "Saturn": ["saturn", "shani", "sani"],
    "Rahu": ["rahu"],
    "Ketu": ["ketu"],
}
ASC_ALIASES = ["lagna", "ascendant", "ascendent", "rising sign"]

SIGNS: dict[int, list[str]] = {
    1: ["aries", "mesha"], 2: ["taurus", "vrishabha"], 3: ["gemini", "mithuna"],
    4: ["cancer", "karka"], 5: ["leo", "simha"], 6: ["virgo", "kanya"],
    7: ["libra", "tula", "thula"], 8: ["scorpio", "vrishchika", "vrischika"],
    9: ["sagittarius", "dhanu"], 10: ["capricorn", "makara"],
    11: ["aquarius", "kumbha"], 12: ["pisces", "meena"],
}

ORDINALS = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5, "sixth": 6, "6th": 6, "seventh": 7, "7th": 7, "eighth": 8, "8th": 8,
    "ninth": 9, "9th": 9, "tenth": 10, "10th": 10, "eleventh": 11, "11th": 11,
    "twelfth": 12, "12th": 12,
}

HOUSE_VERBS = (r"(?:is\s+(?:placed|posited|located|sitting)?|occupies|sits\s+in|placed\s+in|"
               r"posited\s+in|resides\s+in|falls\s+in|lies\s+in|in)")
FLAG_WORDS = {"retrograde": "retrograde", "vakri": "retrograde",
              "exalted": "exalted", "uccha": "exalted",
              "debilitated": "debilitated", "neecha": "debilitated",
              "combust": "combust", "asta": "combust"}

# sentences about transits, hypotheticals or general theory must NOT be checked
SKIP_MARKERS = [
    "transit", "transiting", "gochara", "passing through", "will enter", "entering",
    "currently in", "these days", "right now", "now in", "moving through", "over the next",
    "would ", "if ", "hypothetical", "in general", "generally", "for example", "e.g.",
    "represents", "symbolises", "symbolizes", "classical", "texts say", "for instance",
    "from the moon", "from the lagna", "from natal", "aspect", "aspecting",
]
CHART_CONTEXT = ["your", "chart", "horoscope", "native", "you ", "birth", "kundli", "janma"]

# a flag claim ("Saturn is retrograde") is only checked when it is chart-specific:
# either the sentence carries chart context, or it avoids generic/theory vocabulary
GENERIC_MARKERS = ["usually", "often", "generally", "people", "tends to", "period",
                   "when ", "those with", "person born", "means for", "good time to",
                   "best to", "advises", "advise", "recommend", "every year", "each year"]


def _planet_pattern() -> str:
    names = sorted({n for v in PLANETS.values() for n in v}, key=len, reverse=True)
    return r"\b(" + "|".join(re.escape(n) for n in names) + r")\b"


def _sign_pattern() -> str:
    names = sorted({n for v in SIGNS.values() for n in v}, key=len, reverse=True)
    return r"\b(" + "|".join(re.escape(n) for n in names) + r")\b"


def _canon_planet(token: str) -> str | None:
    t = token.lower().strip()
    for canon, aliases in PLANETS.items():
        if t in aliases:
            return canon
    return None


def _canon_sign(token: str) -> int | None:
    t = token.lower().strip()
    for num, aliases in SIGNS.items():
        if t in aliases:
            return num
    return None


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [p.strip(" -•*") for p in parts if p and p.strip()]


def _skip(sentence: str) -> bool:
    low = sentence.lower()
    return any(m in low for m in SKIP_MARKERS)


def _has_context(sentence: str) -> bool:
    low = " " + sentence.lower() + " "
    return any(c in low for c in CHART_CONTEXT)


def _is_generic(sentence: str) -> bool:
    """Theory/pop-astrology sentences that must not be checked as chart claims."""
    low = " " + sentence.lower() + " "
    return any(m in low for m in GENERIC_MARKERS)


# ------------------------------------------------------------------ the checker

def verify_answer(answer: str, chart: dict[str, Any]) -> list[dict[str, str]]:
    """Return a list of contradictions: {kind, claim, data, fix}."""
    if not answer or not chart:
        return []

    planets = chart.get("planets", {})
    houses = chart.get("houses", {})
    asc = chart.get("ascendant", {})
    issues: list[dict[str, str]] = []

    p_pat, s_pat = _planet_pattern(), _sign_pattern()
    house_claims = re.compile(
        p_pat + r"[^.\n;]{0,45}?" + HOUSE_VERBS + r"[^.\n;]{0,20}?\b(" +
        "|".join(ORDINALS) + r")\b\s*(?:house|bhava)", re.IGNORECASE)
    sign_claims = re.compile(
        p_pat + r"[^.\n;]{0,30}?(?:is\s+in|in\s+the\s+sign\s+of|in|occupies|placed\s+in)\s*"
        + s_pat, re.IGNORECASE)
    lord_claims = re.compile(
        r"\b(" + "|".join(ORDINALS) + r")\b\s*(?:house|bhava)?\s*(?:lord|ruler|adhipati)\b"
        r"[^.\n;]{0,25}?\b" + p_pat, re.IGNORECASE)
    flag_claims = re.compile(
        p_pat + r"[^.\n;]{0,25}?\b(?:is|was|remains|stays)?\s*"
        r"(retrograde|vakri|exalted|uccha|debilitated|neecha|combust|asta)\b", re.IGNORECASE)
    dasha_claims = re.compile(
        p_pat + r"[^.\n;]{0,20}?\b(mahadasha|mahadasa|antardasha|antardasa|bhukti|dasha|period)\b"
        r"[^.\n;]{0,60}?\b(1[89]\d\d|20\d\d)\b", re.IGNORECASE)

    # pre-flatten dasha periods by level for the year checks
    md_periods: dict[str, list[tuple[str, str]]] = {}
    ad_periods: dict[str, list[tuple[str, str]]] = {}
    for md in chart.get("dashas", []):
        md_periods.setdefault(md["lord"], []).append((md["start"], md["end"]))
        for ad in md.get("sub", []):
            ad_periods.setdefault(ad["lord"], []).append((ad["start"], ad["end"]))

    def in_periods(lord: str, year: int, table: dict[str, list[tuple[str, str]]]) -> bool:
        for start, end in table.get(lord, []):
            if start[:4] <= str(year) <= end[:4]:
                return True
        return False

    for sentence in _sentences(answer):
        if _skip(sentence):
            continue

        # 1. "X is in the Nth house"
        for m in house_claims.finditer(sentence):
            planet = _canon_planet(m.group(1))
            n = ORDINALS.get(m.group(2).lower())
            if not planet or not n or planet not in planets:
                continue
            actual = planets[planet]["house"]
            if actual != n:
                issues.append({
                    "kind": "planet-house",
                    "claim": f"{planet} in house {n}",
                    "data": f"{planet} is in house {actual} ({planets[planet]['sign_name']})",
                    "fix": f"say house {actual}",
                })

        # 2. "X is in <Sign>" (chart context required) + ascendant sign claims
        if _has_context(sentence):
            for m in sign_claims.finditer(sentence):
                planet = _canon_planet(m.group(1))
                sign = _canon_sign(m.group(2))
                if not planet or not sign or planet not in planets:
                    continue
                actual = planets[planet]["sign"]
                if actual != sign:
                    issues.append({
                        "kind": "planet-sign",
                        "claim": f"{planet} in {m.group(2)}",
                        "data": f"{planet} is in {planets[planet]['sign_name']} "
                                f"(house {planets[planet]['house']})",
                        "fix": f"say {planets[planet]['sign_name']}",
                    })
            low = sentence.lower()
            for alias in ASC_ALIASES:
                if alias in low:
                    for num, aliases in SIGNS.items():
                        if any(sn in low for sn in aliases):
                            if num != asc["sign"]:
                                issues.append({
                                    "kind": "ascendant-sign",
                                    "claim": f"{alias} in {aliases[0]}",
                                    "data": f"Lagna is {asc['sign_name']}",
                                    "fix": f"say {asc['sign_name']}",
                                })
                            break
                    break

        # 3. dignity / retrograde flags (chart context OR a non-generic assertion)
        if _has_context(sentence) or not _is_generic(sentence):
            for m in flag_claims.finditer(sentence):
                planet = _canon_planet(m.group(1))
                if not planet or planet not in planets:
                    continue
                flag = FLAG_WORDS.get(m.group(2).lower())
                if not flag:
                    continue
                p = planets[planet]
                truth = {
                    "retrograde": p["retrograde"],
                    "combust": p["combust"],
                    "exalted": p["dignity"].startswith("exalt"),
                    "debilitated": p["dignity"].startswith("debil"),
                }[flag]
                if not truth:
                    issues.append({
                        "kind": f"flag-{flag}",
                        "claim": f"{planet} {flag}",
                        "data": f"{planet} is {'retrograde' if p['retrograde'] else 'direct'}; "
                                f"dignity {p['dignity']}; combust {p['combust']}",
                        "fix": f"correct the {flag} statement",
                    })

        # 4. "Nth house lord is X"
        for m in lord_claims.finditer(sentence):
            n = ORDINALS.get(m.group(1).lower())
            planet = _canon_planet(m.group(2))
            if not n or not planet:
                continue
            H = houses.get(n) or houses.get(str(n))
            if not H or H["lord"] == planet:
                continue
            issues.append({
                "kind": "house-lord",
                "claim": f"house {n} lord is {planet}",
                "data": f"house {n} lord is {H['lord']}",
                "fix": f"say {H['lord']}",
            })

        # 5. dasha year claims
        for m in dasha_claims.finditer(sentence):
            planet = _canon_planet(m.group(1))
            level_word = m.group(2).lower()
            year = int(m.group(3))
            if not planet:
                continue
            level = "antar" if level_word in ("antardasha", "antardasa", "bhukti") else "maha"
            table = ad_periods if level == "antar" else md_periods
            if planet in table and not in_periods(planet, year, table):
                periods = ", ".join(f"{a}→{b}" for a, b in table[planet][:3])
                issues.append({
                    "kind": "dasha-year",
                    "claim": f"{planet} {level_word} in {year}",
                    "data": f"{planet} {level_word} periods: {periods}",
                    "fix": "use the calculated period dates",
                })

    # de-duplicate
    seen, unique = set(), []
    for i in issues:
        key = (i["kind"], i["claim"])
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return unique


def correction_prompt(issues: list[dict[str, str]]) -> str:
    """Instruction block used for the corrective generation pass."""
    lines = [
        "Your previous answer contains statements that CONTRADICT the calculated chart data.",
        "The chart data is ground truth. Correct exactly these items and keep everything else intact:",
    ]
    for i in issues:
        lines.append(f'- You wrote: "{i["claim"]}". Computed data: {i["data"]}. Therefore: {i["fix"]}.')
    lines.append(
        "Rewrite the full answer now, with the same structure and tone, with those claims fixed. "
        "Do not mention this correction or add any note about verification."
    )
    return "\n".join(lines)
