"""Namakshar (nama-akshara) - the 108 naming syllables of the nakshatra padas.

At namakarana (naming ceremony) the child's name traditionally begins with the
syllable assigned to the pada (quarter) of the nakshatra the Moon occupied at birth.
27 nakshatras x 4 padas = 108 syllables.

The table below was checked against a published 108-pada list (onlinejyotish.com,
Feb 2026) and cross-checked on individual nakshatras against bhrigupandit.com. Where
editions differ in a syllable (a few do, e.g. Ashwini chu/che vs chuu), the more
widely used form is given and the alternates are noted.

Direction of the mapping matters: the Moon's position determines the syllable. The
reverse (name -> pada) is provided only as a soft cross-check, because every pada
syllable is shared by several nakshatras and many families do not follow the
tradition.
"""
from __future__ import annotations

from typing import Any

# (nakshatra, [(devanagari, roman), ...4 padas], note)
PADA_SYLLABLES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Ashwini",            [("चु", "Chu"), ("चे", "Che"), ("चो", "Cho"), ("ला", "La")], "also written चू / Chuu"),
    ("Bharani",            [("ली", "Li"), ("लू", "Lu"), ("ले", "Le"), ("लो", "Lo")], ""),
    ("Krittika",           [("आ", "A"), ("ई", "I"), ("ऊ", "U"), ("ए", "E")], "some editions give अ/इ/उ"),
    ("Rohini",             [("ओ", "O"), ("वा", "Va"), ("वी", "Vi"), ("वु", "Vu")], ""),
    ("Mrigashira",         [("वे", "Ve"), ("वो", "Vo"), ("का", "Ka"), ("की", "Ki")], ""),
    ("Ardra",              [("कु", "Ku"), ("घ", "Gha"), ("ङ", "Nga"), ("छ", "Chha")], ""),
    ("Punarvasu",          [("के", "Ke"), ("को", "Ko"), ("हा", "Ha"), ("ही", "Hi")], ""),
    ("Pushya",             [("हु", "Hu"), ("हे", "He"), ("हो", "Ho"), ("डा", "Da")], ""),
    ("Ashlesha",           [("डी", "Di"), ("डू", "Du"), ("डे", "De"), ("डो", "Do")], ""),
    ("Magha",              [("मा", "Ma"), ("मी", "Mi"), ("मू", "Mu"), ("मे", "Me")], ""),
    ("Purva Phalguni",     [("मो", "Mo"), ("टा", "Ta"), ("टी", "Ti"), ("टू", "Tu")], ""),
    ("Uttara Phalguni",    [("टे", "Te"), ("टो", "To"), ("पा", "Pa"), ("पी", "Pi")], ""),
    ("Hasta",              [("पू", "Pu"), ("ष", "Sha"), ("ण", "Na"), ("ठ", "Tha")], ""),
    ("Chitra",             [("पे", "Pe"), ("पो", "Po"), ("रा", "Ra"), ("री", "Ri")], ""),
    ("Swati",              [("रू", "Ru"), ("रे", "Re"), ("रो", "Ro"), ("ता", "Ta")], ""),
    ("Vishakha",           [("ती", "Ti"), ("तू", "Tu"), ("ते", "Te"), ("तो", "To")], ""),
    ("Anuradha",           [("ना", "Na"), ("नी", "Ni"), ("नू", "Nu"), ("ने", "Ne")], ""),
    ("Jyeshtha",           [("नो", "No"), ("या", "Ya"), ("यी", "Yi"), ("यू", "Yu")], ""),
    ("Mula",               [("ये", "Ye"), ("यो", "Yo"), ("भा", "Bha"), ("भी", "Bhi")], ""),
    ("Purva Ashadha",      [("भू", "Bhu"), ("धा", "Dha"), ("फा", "Pha"), ("ढा", "Dha")], ""),
    ("Uttara Ashadha",     [("भे", "Bhe"), ("भो", "Bho"), ("जा", "Ja"), ("जी", "Ji")], ""),
    ("Shravana",           [("खी", "Khi"), ("खू", "Khu"), ("खे", "Khe"), ("खो", "Kho")], ""),
    ("Dhanishta",          [("गा", "Ga"), ("गी", "Gi"), ("गू", "Gu"), ("गे", "Ge")], ""),
    ("Shatabhisha",        [("गो", "Go"), ("सा", "Sa"), ("सी", "Si"), ("सू", "Su")], ""),
    ("Purva Bhadrapada",   [("से", "Se"), ("सो", "So"), ("दा", "Da"), ("दी", "Di")], ""),
    ("Uttara Bhadrapada",  [("दू", "Du"), ("थ", "Tha"), ("झ", "Jha"), ("ञ", "Nya")], "some editions give ण"),
    ("Revati",             [("दे", "De"), ("दो", "Do"), ("चा", "Cha"), ("ची", "Chi")], ""),
]

NAK_SPAN = 360.0 / 27.0   # 13°20'
PADA_SPAN = NAK_SPAN / 4  # 3°20'

# transliteration variants accepted by the reverse lookup
VARIANTS = {
    "ch": "ch", "chh": "chha", "nga": "nga", "nya": "nya", "gna": "nya",
    "sha": "sha", "sa": "sa", "w": "v", "v": "v",
}


def syllables_for(lon: float) -> dict[str, Any]:
    """Naming syllable from a sidereal longitude (normally the Moon's).

    A tiny epsilon makes exact boundaries deterministic: 40.000000 deg (the start of
    Rohini) would otherwise floor to Krittika because 40.0 // (360/27) = 2.0 in binary
    floating point. 1e-9 deg is 0.0000036 arcsec - far below any real precision, but
    enough to place a boundary longitude in the nakshatra that *begins* there.
    """
    x = (lon + 1e-9) % 360.0
    idx = int(x // NAK_SPAN) % 27
    within = x % NAK_SPAN
    pada = int(within // PADA_SPAN) + 1
    name, padas, note = PADA_SYLLABLES[idx]
    dev, rom = padas[pada - 1]
    return {
        "nakshatra": name,
        "nakshatra_index": idx + 1,
        "pada": pada,
        "syllable": dev,
        "syllable_roman": rom,
        "note": note,
        "all_padas": [{"pada": i + 1, "syllable": d, "roman": r} for i, (d, r) in enumerate(padas)],
    }


def _normalise(text: str) -> str:
    t = text.strip().lower().replace("aa", "a").replace("ee", "i").replace("oo", "u")
    t = t.replace("chh", "chha").replace("sh", "sha").replace("ny", "nya")
    return t


def _devanagari_base(text: str) -> str:
    """First base character of a Devanagari string.

    'गे' is two code points (ग + the vowel sign े), so naive indexing on [0] fails.
    A name is matched on its first base character only, which is the right granularity
    for a soft cross-check: 'गे' and 'गौतम' both reduce to ग, narrowing the search to
    the Ga/Gi/Gu/Ge family instead of guessing the vowel. Independent vowels are kept
    as-is (आनंद -> आ), and combining marks (vowel signs, virama, nukta, anusvara) are
    never returned as a base.
    """
    for c in text.strip():
        if not ("\u0900" <= c <= "\u097f"):
            return ""
        if c == "\u093c" or "\u0900" <= c <= "\u0903":      # nukta, chandrabindu/anusvara/visarga
            continue
        if "\u093e" <= c <= "\u094d" or "\u0951" <= c <= "\u0954":   # vowel signs, virama, accents
            continue
        return c
    return ""


def lookup(syllable: str) -> list[dict[str, Any]]:
    """Reverse lookup: a name's first syllable -> possible (nakshatra, pada).

    Returns a list, because pada syllables are shared across nakshatras. An empty
    list means the syllable is not one of the 108 (the name may simply not follow
    the tradition - which is common and not a problem).
    """
    if not syllable:
        return []
    if any("\u0900" <= c <= "\u097f" for c in syllable):  # Devanagari input
        target = _devanagari_base(syllable)
        matches = []
        for idx, (name, padas, _note) in enumerate(PADA_SYLLABLES):
            for p in range(4):
                if _devanagari_base(padas[p][0]) == target:
                    matches.append({"nakshatra": name, "nakshatra_index": idx + 1, "pada": p + 1,
                                    "syllable": padas[p][0], "syllable_roman": padas[p][1]})
        return matches

    norm = _normalise(syllable)
    matches = []
    for idx, (name, padas, _note) in enumerate(PADA_SYLLABLES):
        for p in range(4):
            rom = _normalise(padas[p][1])
            if norm.startswith(rom) or rom.startswith(norm):
                matches.append({"nakshatra": name, "nakshatra_index": idx + 1, "pada": p + 1,
                                "syllable": padas[p][0], "syllable_roman": padas[p][1]})
    return matches


def table_text() -> str:
    """The full 108-syllable table, for the knowledge base and the UI."""
    lines = ["NAMAKSHAR - 108 naming syllables by nakshatra pada", ""]
    for idx, (name, padas, note) in enumerate(PADA_SYLLABLES, start=1):
        cells = "  ".join(f"{p + 1}:{d} ({r})" for p, (d, r) in enumerate(padas))
        lines.append(f"{idx:2d}. {name:22s} {cells}" + (f"   [{note}]" if note else ""))
    return "\n".join(lines)


def render(chart: dict[str, Any]) -> str:
    """Chart-text block: the birth naming syllable plus the padas of the Moon's nakshatra."""
    info = chart.get("namakshar")
    if not info:
        return ""
    L = [f"NAMAKSHAR (birth naming syllable, from the Moon's pada): "
         f"{info['syllable']} ({info['syllable_roman']})"]
    L.append(f"  Moon nakshatra {info['nakshatra']} (no. {info['nakshatra_index']}), pada {info['pada']}")
    L.append("  All four padas of this nakshatra: "
             + ", ".join(f"pada {p['pada']}={p['syllable']} ({p['roman']})" for p in info["all_padas"]))
    if info.get("note"):
        L.append(f"  Note: {info['note']}")
    L.append("  Traditional use: the name is chosen to begin with this syllable (namakarana), so that "
             "the name carries the vibration of the birth nakshatra. It is also used to open the "
             "nakshatra-specific remedies (the deity of the padas is propitiated by its own syllable).")
    return "\n".join(L)
