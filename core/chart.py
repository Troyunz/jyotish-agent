"""Chart calculation engine - Swiss Ephemeris + classical Jyotisha analytics.

Everything here is computed from the actual ephemeris (pyswisseph), never guessed:
  * sidereal (nirayana) positions with Lahiri/Raman/KP ayanamsa
  * Lagna, whole-sign bhavas, house lords and tenants
  * nakshatra + pada for every graha, dignity (exaltation/own/friend/enemy), combustion
  * 16 divisional charts (D1..D60) with the standard Parashari varga rules
  * Panchanga (tithi, nakshatra, yoga, karana, vara, sunrise/sunset)
  * classical yoga / dosha detection, Vimshottari dasha, gochara transits
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import swisseph as swe

from . import ashtakavarga as av_mod
from . import dasha as dasha_mod
from . import namakshar as namakshar_mod

# --------------------------------------------------------------------- constants

RASHIS = [
    ("Mesha", "Aries"), ("Vrishabha", "Taurus"), ("Mithuna", "Gemini"), ("Karka", "Cancer"),
    ("Simha", "Leo"), ("Kanya", "Virgo"), ("Tula", "Libra"), ("Vrishchika", "Scorpio"),
    ("Dhanu", "Sagittarius"), ("Makara", "Capricorn"), ("Kumbha", "Aquarius"), ("Meena", "Pisces"),
]

NAKSHATRAS = [
    ("Ashwini", "Ketu"), ("Bharani", "Venus"), ("Krittika", "Sun"), ("Rohini", "Moon"),
    ("Mrigashira", "Mars"), ("Ardra", "Rahu"), ("Punarvasu", "Jupiter"), ("Pushya", "Saturn"),
    ("Ashlesha", "Mercury"), ("Magha", "Ketu"), ("Purva Phalguni", "Venus"), ("Uttara Phalguni", "Sun"),
    ("Hasta", "Moon"), ("Chitra", "Mars"), ("Swati", "Rahu"), ("Vishakha", "Jupiter"),
    ("Anuradha", "Saturn"), ("Jyeshtha", "Mercury"), ("Mula", "Ketu"), ("Purva Ashadha", "Venus"),
    ("Uttara Ashadha", "Sun"), ("Shravana", "Moon"), ("Dhanishta", "Mars"), ("Shatabhisha", "Rahu"),
    ("Purva Bhadrapada", "Jupiter"), ("Uttara Bhadrapada", "Saturn"), ("Revati", "Mercury"),
]

BHAVA_NAMES = [
    "Tanu (self, body, vitality)", "Dhana (wealth, family, speech)", "Sahaja (siblings, courage, communication)",
    "Sukha (mother, home, property)", "Putra (children, intellect, romance)", "Ari (enemies, disease, service)",
    "Kalatra (spouse, partnership)", "Randhra (longevity, transformation, occult)", "Dharma (fortune, father, guru)",
    "Karma (career, status, karma)", "Labha (gains, income, network)", "Vyaya (loss, foreign, moksha)",
]

GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
SWE_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
}
SANSKRIT = {
    "Sun": "Surya", "Moon": "Chandra", "Mars": "Mangala", "Mercury": "Budha", "Jupiter": "Guru",
    "Venus": "Shukra", "Saturn": "Shani", "Rahu": "Rahu", "Ketu": "Ketu",
}
EXALT = {"Sun": (1, 10.0), "Moon": (2, 3.0), "Mars": (10, 28.0), "Mercury": (6, 15.0),
         "Jupiter": (4, 5.0), "Venus": (12, 27.0), "Saturn": (7, 20.0)}
OWN = {"Sun": [5], "Moon": [4], "Mars": [1, 8], "Mercury": [3, 6], "Jupiter": [9, 12],
       "Venus": [2, 7], "Saturn": [10, 11]}
MOOLTRIKONA = {"Sun": (5, 0, 20), "Moon": (2, 3, 30), "Mars": (1, 0, 12), "Mercury": (6, 15, 20),
               "Jupiter": (9, 0, 10), "Venus": (7, 0, 15), "Saturn": (11, 0, 20)}
FRIENDS = {
    "Sun": {"f": ["Moon", "Mars", "Jupiter"], "e": ["Venus", "Saturn"]},
    "Moon": {"f": ["Sun", "Mercury"], "e": []},
    "Mars": {"f": ["Sun", "Moon", "Jupiter"], "e": ["Mercury"]},
    "Mercury": {"f": ["Sun", "Venus"], "e": ["Moon"]},
    "Jupiter": {"f": ["Sun", "Moon", "Mars"], "e": ["Mercury", "Venus"]},
    "Venus": {"f": ["Mercury", "Saturn"], "e": ["Sun", "Moon"]},
    "Saturn": {"f": ["Mercury", "Venus"], "e": ["Sun", "Moon", "Mars"]},
}
COMBUST_ORB = {"Moon": 12.0, "Mars": 17.0, "Mercury": 14.0, "Jupiter": 11.0, "Venus": 10.0, "Saturn": 15.0}

AYANAMSA = {
    "lahiri": swe.SIDM_LAHIRI, "raman": swe.SIDM_RAMAN, "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "yukteshwar": swe.SIDM_YUKTESHWAR, "fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
    "true_chitra": swe.SIDM_TRUE_CITRA,
}
HOUSE_SYSTEM = {"whole": b"W", "placidus": b"P", "equal": b"E", "porphyry": b"O", "sripati": b"B"}

VARGA_NAMES = {
    1: "Rashi", 2: "Hora", 3: "Drekkana", 4: "Chaturthamsa", 7: "Saptamsa", 9: "Navamsa",
    10: "Dashamsa", 12: "Dwadashamsa", 16: "Shodashamsa", 20: "Vimsamsa", 24: "Siddhamsa (Chaturvimsamsa)",
    27: "Bhamsa (Nakshatramsa)", 30: "Trimsamsa", 40: "Khavedamsa", 45: "Akshavedamsa", 60: "Shashtiamsa",
}

TITHI_NAMES = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami",
               "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi",
               "Purnima/Amavasya"]
NITYA_YOGA = ["Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma", "Dhriti",
              "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata",
              "Variyana", "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"]
KARANA_MOVABLE = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]
KARANA_FIXED = ["Shakuni", "Chatushpada", "Naga", "Kimstughna"]
VARA = ["Monday (Somavara)", "Tuesday (Mangalavara)", "Wednesday (Budhavara)", "Thursday (Guruvara)",
        "Friday (Shukravara)", "Saturday (Shanivara)", "Sunday (Ravivara)"]


# ------------------------------------------------------------------ helpers

def _ord(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ------------------------------------------------------- ephemeris & positions

_EPHE_PATH: str | None = None
EPHE_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")

POSITION_MODES = {
    "true": "true positions (TRUEPOS|NONUT|NOGDEFL - Jagannatha Hora parity)",
    "apparent": "apparent positions (Swiss Ephemeris default)",
}


def position_flags(mode: str = "true") -> int:
    """Swiss Ephemeris flags for the configured position convention.

    "true" is the combination verified against desktop Jagannatha Hora (delta <= 1")
    by the vedic-astro-skills project after they measured a 0-60" discrepancy between
    the two baselines. "apparent" is the plain Swiss Ephemeris default that this
    engine used before. The difference reaches ~34" (Mars) and is visible in the
    arcminute column, so it is a documented setting rather than a silent choice.
    """
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    if str(mode).lower() in ("true", "jhora", "jhora_parity"):
        flags |= swe.FLG_TRUEPOS | swe.FLG_NONUT | swe.FLG_NOGDEFL
    return flags


def ensure_ephe_path(path: str | Path | None) -> tuple[str, list[str]]:
    """Point Swiss Ephemeris at the bundled .se1 data files (once per process).

    Without .se1 files pyswisseph silently falls back to the built-in Moshier
    ephemeris. That still works, but it is a different computation from what other
    Jyotish software runs, so we load the official Astrodienst files and report
    which one is actually in use.
    """
    global _EPHE_PATH
    if path:
        p = Path(path)
        if p.is_dir():
            files = sorted(f.name for f in p.glob("*.se1"))
            if files and str(p) != _EPHE_PATH:
                swe.set_ephe_path(str(p))
                _EPHE_PATH = str(p)
            return _EPHE_PATH or str(p), files
    return _EPHE_PATH or "", []


def ephemeris_in_use(jd: float, mode: str = "true") -> str:
    """Which ephemeris actually served the last calculation - read from the returned flags."""
    try:
        _, retflag = swe.calc_ut(jd, swe.SUN, position_flags(mode))
    except Exception:
        return "unavailable"
    if retflag < 0:
        return "error"
    if retflag & swe.FLG_JPLEPH:
        return "JPL ephemeris"
    if retflag & swe.FLG_SWIEPH:
        return "Swiss Ephemeris (bundled .se1 files)"
    if retflag & swe.FLG_MOSEPH:
        return "Moshier built-in fallback (no .se1 files found)"
    return "unknown"


def ephemeris_status(jd: float | None = None, mode: str = "true") -> dict[str, Any]:
    """Status block for the UI and the test suite."""
    jd = jd if jd is not None else swe.julday(2000, 1, 1, 12.0)
    path, files = ensure_ephe_path(_EPHE_PATH or None)
    return {
        "path": path or "(not set - using pyswisseph default search)",
        "files": files,
        "expected_files": list(EPHE_FILES),
        "in_use": ephemeris_in_use(jd, mode),
        "mode": mode,
        "mode_label": POSITION_MODES.get(mode, mode),
    }


def _dms(lon: float) -> str:
    """Degrees / minutes / seconds inside a sign.

    Rounded once in arcseconds so it can never emit an illegal value like
    12°60'00" or 30°00'00" at the end of a sign (a rounding bug class documented
    in other Jyotish engines).
    """
    total = int(round((lon % 30.0) * 3600))
    total = min(total, 30 * 3600 - 1)  # clamp 29°59'59.5"+ to 29°59'59", never 30°00'00"
    d, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{d:02d}°{m:02d}'{s:02d}\""


def sign_of(lon: float) -> int:
    """1-12 (Aries=1)."""
    return int(lon // 30.0) % 12 + 1


def sign_name(s: int) -> str:
    n, e = RASHIS[(s - 1) % 12]
    return f"{n} ({e})"


def nakshatra_of(lon: float) -> dict[str, Any]:
    # +1e-9 deg (0.0000036 arcsec) makes exact boundaries land in the division that
    # begins there: 40.000000 deg is the start of Rohini, but 40.0 // (360/27) = 2.0 in
    # binary floating point, and 10.000000 deg is the start of Ashwini pada 4, but
    # 10.0 // (360/108) = 2.999... which would otherwise report pada 3. The epsilon is
    # applied once, up front, so nakshatra and pada can never disagree.
    span = 360.0 / 27.0
    x = (lon + 1e-9) % 360.0
    idx = int(x // span) % 27
    within = x % span
    pada = int(within // (span / 4)) + 1
    name, lord = NAKSHATRAS[idx]
    return {"name": name, "pada": pada, "lord": lord, "index": idx + 1}


def varga_sign(lon: float, d: int) -> int:
    """Return the sign (1-12) a longitude maps to in divisional chart D`d`."""
    s = sign_of(lon)
    deg = lon % 30.0
    if d == 1:
        return s
    if d == 2:
        leo = (s % 2 == 1 and deg < 15) or (s % 2 == 0 and deg >= 15)
        return 5 if leo else 4
    if d == 3:
        return ((s - 1 + 4 * int(deg // 10)) % 12) + 1
    if d == 4:
        return ((s - 1 + 3 * int(deg // 7.5)) % 12) + 1
    if d == 7:
        start = s if s % 2 == 1 else s + 6
        return ((start - 1 + int(deg // (30 / 7))) % 12) + 1
    if d == 9:
        start = {1: 1, 2: 10, 0: 7}[s % 3]
        return ((start - 1 + int(deg // (10 / 3))) % 12) + 1
    if d == 10:
        start = s if s % 2 == 1 else s + 8
        return ((start - 1 + int(deg // 3)) % 12) + 1
    if d == 12:
        return ((s - 1 + int(deg // 2.5)) % 12) + 1
    if d == 16:
        start = {1: 1, 2: 5, 0: 9}[s % 3]
        return ((start - 1 + int(deg // 1.875)) % 12) + 1
    if d == 20:
        start = {1: 1, 2: 9, 0: 5}[s % 3]
        return ((start - 1 + int(deg // 1.5)) % 12) + 1
    if d == 24:
        start = 5 if s % 2 == 1 else 4
        return ((start - 1 + int(deg // 1.25)) % 12) + 1
    if d == 27:
        start = {1: 1, 2: 4, 0: 7}[s % 3]
        return ((start - 1 + int(deg * 27 // 30)) % 12) + 1
    if d == 30:
        if s % 2 == 1:
            spans = [(5, 1), (5, 11), (8, 9), (7, 3), (5, 7)]  # Mars, Saturn, Jupiter, Mercury, Venus
        else:
            spans = [(5, 7), (7, 3), (8, 9), (5, 11), (5, 1)]
        acc = 0.0
        for span, sign in spans:
            if deg < acc + span:
                return sign
            acc += span
        return spans[-1][1]
    if d == 40:
        start = 1 if s % 2 == 1 else 11
        return ((start - 1 + int(deg // 0.75)) % 12) + 1
    if d == 45:
        start = {1: 1, 2: 5, 0: 9}[s % 3]
        return ((start - 1 + int(deg * 45 // 30)) % 12) + 1
    if d == 60:
        return ((s - 1 + int(deg * 2)) % 12) + 1
    raise ValueError(f"Unsupported varga D{d}")


def _aspects_house(planet_house: int, target_house: int, planet: str) -> bool:
    """Graha drishti in whole-sign houses (all planets aspect the 7th)."""
    diff = (target_house - planet_house) % 12 + 1  # 1 = same house
    if diff in (1, 7):
        return True
    if planet == "Mars" and diff in (4, 8):
        return True
    if planet == "Jupiter" and diff in (5, 9):
        return True
    if planet == "Saturn" and diff in (3, 10):
        return True
    if planet in ("Rahu", "Ketu"):
        # common convention: nodes aspect 5th, 7th, 9th (varies by school)
        return diff in (5, 9)
    return False


def _dignity(planet: str, sign: int, deg: float) -> str:
    if planet in ("Rahu", "Ketu"):
        return "n/a (node)"
    if planet in EXALT:
        ex_sign, ex_deg = EXALT[planet]
        if sign == ex_sign:
            return "exalted (uccha)"
        if sign == (ex_sign + 6 - 1) % 12 + 1:
            return "debilitated (neecha)"
    if planet in MOOLTRIKONA:
        ms, lo, hi = MOOLTRIKONA[planet]
        if sign == ms and lo <= deg <= hi:
            return "moolatrikona"
    if sign in OWN.get(planet, []):
        return "own sign (swakshetra)"
    lord_of_sign = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars",
                    "Jupiter", "Saturn", "Saturn", "Jupiter"][sign - 1]
    if lord_of_sign == planet:
        return "own sign"
    rel = "neutral"
    if lord_of_sign in FRIENDS.get(planet, {}).get("f", []):
        rel = "friendly sign (mitra)"
    elif lord_of_sign in FRIENDS.get(planet, {}).get("e", []):
        rel = "enemy sign (shatru)"
    return rel


# ------------------------------------------------------------------ core calc

def _ayanamsa_mode(name: str) -> int:
    return AYANAMSA.get(name.lower(), swe.SIDM_LAHIRI)


def calc_positions(jd_ut: float, ayanamsa: str = "lahiri", node: str = "true",
                   position_mode: str = "true") -> dict[str, dict[str, Any]]:
    swe.set_sid_mode(_ayanamsa_mode(ayanamsa), 0, 0)
    flags = position_flags(position_mode)
    out: dict[str, dict[str, Any]] = {}
    for name in GRAHAS:
        if name == "Ketu":
            rahu = out["Rahu"]["lon"]
            lon, speed = (rahu + 180.0) % 360.0, out["Rahu"]["speed"]
        else:
            pid = swe.MEAN_NODE if (name == "Rahu" and node == "mean") else SWE_IDS[name]
            xx, _ = swe.calc_ut(jd_ut, pid, flags)
            lon, speed = xx[0] % 360.0, xx[3]
        sign = sign_of(lon)
        nak = nakshatra_of(lon)
        out[name] = {
            "lon": round(lon, 6), "sign": sign, "sign_name": sign_name(sign),
            "deg_str": _dms(lon), "deg_in_sign": round(lon % 30, 4),
            "house": None, "nakshatra": f"{nak['name']} pada {nak['pada']}",
            "nak_lord": nak["lord"], "nak_index": nak["index"],
            "dignity": _dignity(name, sign, lon % 30),
            "retrograde": bool(speed < 0 and name not in ("Sun", "Moon")),
            "speed": round(speed, 5), "combust": False,
        }
    sun = out["Sun"]["lon"]
    for name, orb in COMBUST_ORB.items():
        sep = abs((out[name]["lon"] - sun + 180) % 360 - 180)
        out[name]["combust"] = sep < orb
    return out


def sunrise_sunset(d: date, lat: float, lon: float) -> tuple[str | None, str | None]:
    try:
        jd0 = swe.julday(d.year, d.month, d.day, 0.0)
        geopos = (lon, lat, 0.0)
        rise, _ = swe.rise_trans(jd0, swe.SUN, swe.CALC_RISE | swe.BIT_DISC_CENTER, geopos, 0, 0)
        sett, _ = swe.rise_trans(jd0, swe.SUN, swe.CALC_SET | swe.BIT_DISC_CENTER, geopos, 0, 0)

        def to_ist_utc(jd: float) -> str:
            y, m, dd, hh = swe.revjul(jd)
            h = int(hh)
            mi = int(round((hh - h) * 60))
            if mi == 60:
                h, mi = h + 1, 0
            return f"{y:04d}-{m:02d}-{dd:02d} {h:02d}:{mi:02d} UTC"

        return to_ist_utc(rise), to_ist_utc(sett)
    except Exception:
        return None, None


def panchanga(jd_ut: float, sun_lon: float, moon_lon: float, local_date: date) -> dict[str, Any]:
    diff = (moon_lon - sun_lon) % 360.0
    tithi_num = int(diff // 12.0) + 1
    paksha = "Shukla (waxing)" if tithi_num <= 15 else "Krishna (waning)"
    tname = TITHI_NAMES[(tithi_num - 1) % 15]
    if tithi_num == 15:
        tname = "Purnima"
    elif tithi_num == 30:
        tname = "Amavasya"
    nitya_idx = int(((sun_lon + moon_lon) % 360.0) // (360.0 / 27.0)) % 27
    k_idx = int(diff // 6.0)  # 0..59
    if k_idx == 0:
        karana = KARANA_FIXED[3]
    elif k_idx >= 57:
        karana = KARANA_FIXED[(k_idx - 57) % 4]
    else:
        karana = KARANA_MOVABLE[(k_idx - 1) % 7]
    return {
        "tithi": f"{paksha} {tname} (#{tithi_num})",
        "nitya_yoga": NITYA_YOGA[nitya_idx],
        "karana": karana,
        "vara": VARA[local_date.weekday()],
        "moon_phase_pct": round(diff / 3.6, 1),  # 100 = full moon
    }


MOON_MEAN_SPEED = 13.176  # degrees per day; the Moon's average daily motion


def moon_gati(speed: float, year_days: float = 365.2425) -> dict[str, Any]:
    """Chandra gati - the Moon's daily speed and what it means.

    The Moon's speed varies ~11.8 to ~15.3 deg/day because its orbit is elliptical, so
    the same nakshatra can take 21 or 27 hours to cross. Classical use: a fast Moon
    (sheeghra gati) indicates a quick, agile, hasty mind; a slow Moon (manda gati) a
    steady, deliberate, emotionally heavier one. It is also the single best guide to
    how much a birth-time error moves the dasha timeline, which is why the days-per-
    minute figure is computed here.
    """
    ratio = speed / MOON_MEAN_SPEED
    if ratio >= 1.10:
        label, note = "very fast (ati-sheeghra)", "an unusually quick, restless mind - quick to act and to change course"
    elif ratio >= 1.03:
        label, note = "fast (sheeghra)", "a quick, agile mind - grasps quickly, moves on quickly"
    elif ratio > 0.97:
        label, note = "average (sama)", "steady mental pace, neither hasty nor slow"
    elif ratio > 0.90:
        label, note = "slow (manda)", "a deliberate, steady mind - slower to decide, firm once decided"
    else:
        label, note = "very slow (ati-manda)", "an unusually slow, deeply rooted mind - needs time, resists haste"
    # how far a birth-time error moves the dasha timeline:
    # 1 minute of clock time moves the Moon by speed/1440 degrees, and 360 deg = 120 years
    days_per_minute = (speed / 1440.0) * (120.0 / 360.0) * year_days
    return {
        "speed": round(speed, 4),
        "mean_speed": MOON_MEAN_SPEED,
        "ratio": round(ratio, 3),
        "gati": label,
        "note": note,
        "nakshatra_hours": round(namakshar_mod.NAK_SPAN / speed * 24.0, 2) if speed else None,
        "sign_hours": round(30.0 / speed * 24.0, 2) if speed else None,
        "dasha_days_per_minute": round(days_per_minute, 2),
    }


def detect_yogas(planets: dict[str, dict[str, Any]], asc_sign: int) -> list[str]:
    """Chart-configuration based yogas/doshas. Reports what IS, with classical nuance."""
    y: list[str] = []
    houses: dict[int, list[str]] = {}
    for name, p in planets.items():
        houses.setdefault(p["house"], []).append(name)

    def lord_of(sign: int) -> str:
        return ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars",
                "Jupiter", "Saturn", "Saturn", "Jupiter"][sign - 1]

    moon_sign = planets["Moon"]["sign"]
    jup = planets["Jupiter"]
    mars = planets["Mars"]

    # Pancha Mahapurusha
    for planet, yoga in [("Mars", "Ruchaka"), ("Mercury", "Bhadra"), ("Jupiter", "Hamsa"),
                         ("Venus", "Malavya"), ("Saturn", "Sasa")]:
        dg = planets[planet]["dignity"]
        if dg.startswith(("exalt", "own", "moolatrikona")) and planets[planet]["house"] in (1, 4, 7, 10):
            y.append(f"{yoga} yoga: {planet} in {dg} placed in a kendra (house {planets[planet]['house']}).")

    # Gajakesari
    kendra_from_moon = (jup["sign"] - moon_sign) % 12 + 1
    if kendra_from_moon in (1, 4, 7, 10):
        y.append(f"Gajakesari yoga: Jupiter is in the {kendra_from_moon}th from the Moon "
                 f"(house {jup['house']}) - classical mark of wisdom, reputation and protection.")

    # Budha-Aditya
    if planets["Mercury"]["house"] == planets["Sun"]["house"]:
        y.append("Budha-Aditya yoga: Sun and Mercury together (house "
                 f"{planets['Sun']['house']}) - sharp intellect, articulate communication.")
    # Chandra-Mangala
    if mars["house"] == planets["Moon"]["house"]:
        y.append("Chandra-Mangala yoga: Moon and Mars together - enterprise and wealth through effort; "
                 "can also give restlessness.")
    # Sunapha / Anapha / Durudhura / Kemadruma (from Moon)
    second = [n for n in houses.get((planets["Moon"]["house"] % 12) + 1, []) if n != "Sun"]
    twelfth_house = ((planets["Moon"]["house"] - 2) % 12) + 1
    twelfth = [n for n in houses.get(twelfth_house, []) if n != "Sun"]
    if second and twelfth:
        y.append(f"Durudhura yoga: planets flank the Moon ({', '.join(second + twelfth)}) - well-supported mind, resources.")
    elif second:
        y.append(f"Sunapha yoga: planet(s) in the 2nd from Moon ({', '.join(second)}) - self-earned resources.")
    elif twelfth:
        y.append(f"Anapha yoga: planet(s) in the 12th from Moon ({', '.join(twelfth)}) - renunciant streak, inner life.")
    else:
        kendra_planets = [n for n, p in planets.items() if n not in ("Moon", "Sun", "Rahu", "Ketu")
                          and p["house"] in (1, 4, 7, 10)]
        note = " (cancelled/relieved by planets in kendras)" if kendra_planets else ""
        y.append(f"Kemadruma yoga: no planets beside the Moon{note} - a solitary mind that finds its own path.")
    # Amala
    for ref_house in (planets["Moon"]["house"], 1):
        tenth = (ref_house + 9 - 1) % 12 + 1
        ben = [n for n in houses.get(tenth, []) if n in ("Jupiter", "Venus", "Mercury", "Moon")]
        if ben:
            y.append(f"Amala yoga: benefic {', '.join(ben)} in the 10th from {'Moon' if ref_house != 1 else 'Lagna'} "
                     "- lasting good name in work.")
            break
    # Adhi
    adhi = [n for n in ("Jupiter", "Venus", "Mercury") if (planets[n]["sign"] - moon_sign) % 12 + 1 in (6, 7, 8)]
    if len(adhi) >= 2:
        y.append(f"Adhi yoga: {', '.join(adhi)} occupy the 6th-8th from the Moon - leadership, comfort, protection.")
    # Vipareeta Raja
    for hno, label, lord_house in ((6, "Harsha", None), (8, "Sarala", None), (12, "Vimala", None)):
        lord = lord_of(((asc_sign + hno - 2) % 12) + 1)
        if planets[lord]["house"] in (6, 8, 12):
            y.append(f"{label} (Vipareeta Raja) yoga: {hno}th lord {lord} sits in house {planets[lord]['house']} "
                     "- adversity converts into advantage.")
    # Kendra-Trikona raja yoga (conjunction of a kendra lord with a trikona lord)
    kendra_lords = {lord_of(((asc_sign + h - 2) % 12) + 1) for h in (1, 4, 7, 10)}
    trikona_lords = {lord_of(((asc_sign + h - 2) % 12) + 1) for h in (1, 5, 9)}
    pairs = []
    for k in kendra_lords:
        for t in trikona_lords:
            if k != t and planets[k]["house"] == planets[t]["house"]:
                pairs.append(f"{k} + {t} in house {planets[k]['house']}")
    if pairs:
        y.append("Raja yoga (kendra-trikona conjunction): " + "; ".join(sorted(set(pairs))) +
                 " - status and rise through responsibility.")
    # Exchanges (parivartana)
    for h in range(1, 13):
        s = ((asc_sign + h - 2) % 12) + 1
        l1 = lord_of(s)
        other = planets[l1]["house"]
        if other != h:
            l2 = lord_of(((asc_sign + other - 2) % 12) + 1)
            if l2 != l1 and planets[l2]["house"] == h:
                y.append(f"Parivartana (exchange) yoga: house {h} lord {l1} and house {other} lord {l2} "
                         "exchange signs - those life areas are strongly linked.")
    # Shakata
    md = (planets["Moon"]["sign"] - jup["sign"]) % 12 + 1
    if md in (6, 8):
        y.append("Shakata yoga: Moon and Jupiter in 6/8 from each other - fortunes rise and dip; "
                 "steady effort and Jupiter remedies are emphasised.")
    # Grahana
    for lum in ("Sun", "Moon"):
        for nd in ("Rahu", "Ketu"):
            if planets[lum]["house"] == planets[nd]["house"]:
                y.append(f"Grahana-type conjunction: {lum} with {nd} in house {planets[lum]['house']} "
                         "- eclipses the significations of that luminary; spiritual practices help.")
    # Mangal dosha with classical exceptions
    kuja_houses = [h for h in (1, 2, 4, 7, 8, 12) if mars["house"] == h]
    moon_ref = (mars["sign"] - moon_sign) % 12 + 1
    from_moon = moon_ref in (1, 2, 4, 7, 8, 12)
    venus_sign = planets["Venus"]["sign"]
    from_venus = ((mars["sign"] - venus_sign) % 12 + 1) in (1, 2, 4, 7, 8, 12)
    if kuja_houses or from_moon or from_venus:
        where = []
        if kuja_houses:
            where.append(f"from Lagna: house {mars['house']}")
        if from_moon:
            where.append(f"from Moon: {moon_ref}th")
        if from_venus:
            where.append("from Venus")
        cancels = []
        if mars["dignity"].startswith(("exalt", "own", "moolatrikona")):
            cancels.append(f"Mars is in its {mars['dignity']}")
        if mars["sign"] in (4, 1):  # Cancer / Aries
            cancels.append(f"Mars in {sign_name(mars['sign'])} (a classical cancellation)")
        jup_aspect = _aspects_house(jup["house"], mars["house"], "Jupiter")
        if jup_aspect:
            cancels.append("Jupiter aspects Mars")
        note = (" Classical cancellations present: " + "; ".join(cancels) + ".") if cancels else ""
        y.append(f"Mangal (Kuja) dosha present - {', '.join(where)}.{note} "
                 "Traditionally checked before matching charts; with cancellations this is often mild.")
    # Kaal Sarpa (a modern, non-classical label - flagged as such)
    longitudes = [(planets[g]["lon"] - planets["Rahu"]["lon"]) % 360 for g in
                  ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")]
    if all(l < 180 for l in longitudes) or all(l > 180 for l in longitudes):
        y.append("Kaal Sarpa-type configuration: all seven grahas lie on one side of the Rahu-Ketu axis. "
                 "Note: this is a modern label, not found in the classical texts; treat it as a symbolic pattern, not a curse.")
    # Vargottama
    for name, p in planets.items():
        if name in ("Rahu", "Ketu"):
            continue
        if varga_sign(p["lon"], 9) == p["sign"]:
            y.append(f"Vargottama: {name} is in the same sign in Rashi and Navamsa ({p['sign_name']}) "
                     "- a sign of strength and consistency.")
    # Debilitation + cancellation
    for name, p in planets.items():
        if p["dignity"].startswith("debil"):
            dispositor = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars",
                          "Jupiter", "Saturn", "Saturn", "Jupiter"][p["sign"] - 1]
            disp = planets[dispositor]
            cancels = []
            if disp["house"] in (1, 4, 7, 10) or (disp["sign"] - moon_sign) % 12 + 1 in (1, 4, 7, 10):
                cancels.append(f"its dispositor {dispositor} is in a kendra")
            if planets[dispositor]["dignity"].startswith(("exalt", "own")):
                cancels.append(f"dispositor {dispositor} is {planets[dispositor]['dignity']}")
            note = (" Neecha-bhanga (cancellation) indicated: " + "; ".join(cancels) + ".") if cancels else ""
            y.append(f"{name} is debilitated in {sign_name(p['sign'])} (house {p['house']})." + note)
    return y


# ------------------------------------------------------------------ main API

def calc_chart(birth: dict[str, Any]) -> dict[str, Any]:
    """birth = {name, local_dt (aware), utc_dt (aware), lat, lon, tz, ayanamsa, node, house_system}"""
    utc: datetime = birth["utc_dt"]
    jd = swe.julday(utc.year, utc.month, utc.day,
                    utc.hour + utc.minute / 60 + utc.second / 3600)
    ayan = birth.get("ayanamsa", "lahiri")
    node = birth.get("node", "true")
    hsys_name = birth.get("house_system", "whole")
    pos_mode = str(birth.get("position_mode", "true")).lower()
    if pos_mode not in POSITION_MODES:
        pos_mode = "true"
    ensure_ephe_path(birth.get("ephe_path"))
    lat, lon = float(birth["lat"]), float(birth["lon"])

    swe.set_sid_mode(_ayanamsa_mode(ayan), 0, 0)
    planets = calc_positions(jd, ayan, node, pos_mode)

    # Ascendant + cusps
    hsys = HOUSE_SYSTEM.get(hsys_name, b"W")
    try:
        cusps, ascmc = swe.houses_ex(jd, lat, lon, hsys, swe.FLG_SIDEREAL)
        asc_lon = ascmc[0] % 360.0
        mc_lon = ascmc[1] % 360.0
        cusp_list = [c % 360.0 for c in cusps]
    except Exception:
        asc_lon = 0.0
        mc_lon = None
        cusp_list = []

    asc_sign = sign_of(asc_lon)
    # whole-sign houses; if another system requested, use cusp-based house for the asc only
    for name, p in planets.items():
        p["house"] = (p["sign"] - asc_sign) % 12 + 1

    # vargas
    for name, p in planets.items():
        p["vargas"] = {f"D{d}": sign_name(varga_sign(p["lon"], d)) for d in VARGA_NAMES}
    asc_vargas = {f"D{d}": sign_name(varga_sign(asc_lon, d)) for d in VARGA_NAMES}

    # house lords + tenants
    def lord_of(sign: int) -> str:
        return ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars",
                "Jupiter", "Saturn", "Saturn", "Jupiter"][sign - 1]

    houses: dict[int, dict[str, Any]] = {}
    for h in range(1, 13):
        s = ((asc_sign + h - 2) % 12) + 1
        lord = lord_of(s)
        houses[h] = {
            "sign": sign_name(s),
            "lord": lord,
            "lord_house": planets[lord]["house"],
            "lord_sign": planets[lord]["sign_name"],
            "lord_dignity": planets[lord]["dignity"],
            "occupants": [n for n, p in planets.items() if p["house"] == h],
            "aspecting": [n for n, p in planets.items()
                          if p["house"] != h and _aspects_house(p["house"], h, n)],
            "significations": BHAVA_NAMES[h - 1],
        }

    panch = panchanga(jd, planets["Sun"]["lon"], planets["Moon"]["lon"], birth["local_dt"].date())
    rise, sett = sunrise_sunset(birth["local_dt"].date(), lat, lon)

    dashas = dasha_mod.vimshottari(planets["Moon"]["lon"], birth["local_dt"],
                                   birth.get("dasha_year_days", 365.2425), depth=3)

    chart: dict[str, Any] = {
        "birth": {
            "name": birth.get("name") or "Native",
            "local_datetime": birth["local_dt"].strftime("%Y-%m-%d %H:%M:%S"),
            "utc_datetime": utc.strftime("%Y-%m-%d %H:%M:%S"),
            "tz": birth.get("tz", "UTC"),
            "utc_offset": birth["local_dt"].strftime("%z"),
            "lat": lat, "lon": lon,
            "place": birth.get("place", ""),
            "julian_day_ut": round(jd, 6),
        },
        "settings": {"ayanamsa": ayan, "nodes": node, "house_system": "whole-sign (Parashari)"
                     if hsys_name == "whole" else hsys_name,
                     "positions": pos_mode, "positions_label": POSITION_MODES.get(pos_mode, pos_mode),
                     "ephemeris": ephemeris_in_use(jd, pos_mode)},
        "ayanamsa_value": round(swe.get_ayanamsa_ut(jd), 6),
        "ascendant": {
            "lon": round(asc_lon, 6), "sign": asc_sign, "sign_name": sign_name(asc_sign),
            "deg_str": _dms(asc_lon), "nakshatra": nakshatra_of(asc_lon),
            "mc": None if mc_lon is None else {"lon": round(mc_lon, 6), "sign_name": sign_name(sign_of(mc_lon)), "deg_str": _dms(mc_lon)},
            "vargas": asc_vargas,
        },
        "planets": planets,
        "houses": houses,
        "panchanga": {**panch, "sunrise_utc": rise, "sunset_utc": sett},
        "yogas": detect_yogas(planets, asc_sign),
        "dashas": dashas,
        "ashtakavarga": av_mod.compute({"planets": planets, "ascendant": {"sign": asc_sign}}),
        "namakshar": namakshar_mod.syllables_for(planets["Moon"]["lon"]),
        "moon_profile": moon_gati(planets["Moon"]["speed"], birth.get("dasha_year_days", 365.2425)),
        "dasha_current": dasha_mod.current_periods(dashas),
        "dasha_upcoming": dasha_mod.upcoming_changes(dashas, n=4),
    }
    return chart


# ------------------------------------------------------------------ transits

def transit_summary(chart: dict[str, Any], when: datetime | None = None) -> str:
    """Gochara: transits counted from the natal Moon (plus Sade Sati status)."""
    when = when or datetime.now(timezone.utc)
    jd = swe.julday(when.year, when.month, when.day, when.hour + when.minute / 60)
    ayan = chart["settings"]["ayanamsa"]
    planets = calc_positions(jd, ayan, chart["settings"]["nodes"],
                             chart["settings"].get("positions", "true"))
    moon_sign = chart["planets"]["Moon"]["sign"]
    lines = []
    for g in ("Sun", "Jupiter", "Saturn", "Rahu", "Ketu"):
        t = planets[g]
        from_moon = (t["sign"] - moon_sign) % 12 + 1
        bindu = av_mod.bindu_of(chart, g, t["sign"])
        strength = ""
        if bindu:
            strength = (f" [bindus: own {bindu['bav']}/8, SAV {bindu['sav']}/56"
                        f" = {av_mod.grade(bindu['sav'])}]")
        lines.append(f"  {g}: transiting {t['sign_name']} ({t['deg_str']}) = {_ord(from_moon)} from natal Moon"
                     + (" [retrograde]" if t["retrograde"] else "") + strength)
    # Sade Sati
    sat = planets["Saturn"]
    rel = (sat["sign"] - moon_sign) % 12 + 1
    if rel in (12, 1, 2):
        phase = {12: "first phase (12th from Moon)", 1: "peak phase (over the Moon)", 2: "final phase (2nd from Moon)"}[rel]
        sade = f"SATURN TRANSIT: Sade Sati is running - {phase}."
    elif rel in (4, 8):
        sade = "SATURN TRANSIT: Ardha-Ashtama/Ashtama Shani (Saturn in 4th/8th from Moon) - a maturing, pressure-testing phase."
    else:
        sade = "SATURN TRANSIT: no Sade Sati currently; Saturn is in an ordinary position from the Moon."
    return "GOCHARA (transits as of " + when.strftime("%Y-%m-%d") + ", sidereal):\n" + "\n".join(lines) + "\n  " + sade


# ------------------------------------------------------------------ rendering

def render_chart_text(chart: dict[str, Any], when: datetime | None = None, include_vargas: bool = True,
                      include_ashtakavarga: bool = True) -> str:
    """Compact but complete text block handed to the LLM as ground truth."""
    b = chart["birth"]
    L: list[str] = []
    L.append(f"BIRTH DATA: {b['name']} | {b['local_datetime']} local ({b['tz']}, UTC{b['utc_offset']}) "
             f"= {b['utc_datetime']} UT | {b['place']} | lat {b['lat']:.4f} lon {b['lon']:.4f} | JD {b['julian_day_ut']}")
    L.append(f"SETTINGS: {chart['settings']['ayanamsa']} ayanamsa ({chart['ayanamsa_value']}°), "
             f"{chart['settings']['nodes']} nodes, {chart['settings']['house_system']} houses, "
             f"{chart['settings'].get('positions_label', chart['settings'].get('positions', 'true'))}")
    L.append(f"EPHEMERIS: {chart['settings'].get('ephemeris', 'unknown')}")

    asc = chart["ascendant"]
    nak = asc["nakshatra"]
    L.append(f"\nLAGNA: {asc['sign_name']} {asc['deg_str']} | Nakshatra: {nak['name']} pada {nak['pada']} (lord {nak['lord']})")
    if asc.get("mc"):
        L.append(f"10th-house cusp (MC): {asc['mc']['sign_name']} {asc['mc']['deg_str']}")

    L.append("\nGRAHA POSITIONS (sidereal):")
    L.append("  Planet  | Sign            | Degree    | House | Nakshatra (pada, lord)     | Dignity              | Flags")
    for g in GRAHAS:
        p = chart["planets"][g]
        flags = []
        if p["retrograde"]:
            flags.append("retro")
        if p["combust"]:
            flags.append("combust")
        L.append(f"  {g:7s} | {p['sign_name']:15s} | {p['deg_str']:9s} | {p['house']:^5d} | "
                 f"{p['nakshatra']:26s} | {p['dignity']:20s} | {','.join(flags)}")

    L.append("\nBHAVAS (whole-sign from Lagna):")
    for h in range(1, 13):
        H = chart["houses"][h]
        occ = ", ".join(H["occupants"]) or "-"
        asp = ", ".join(H["aspecting"]) or "-"
        L.append(f"  {h:2d}. {H['sign']:15s} lord {H['lord']:7s} (placed in {H['lord_house']}, {H['lord_sign']}, {H['lord_dignity']}) "
                 f"| in-house: {occ:28s} | aspecting: {asp} | {H['significations']}")

    pan = chart["panchanga"]
    L.append(f"\nPANCHANGA (birth day): {pan['vara']} | Tithi: {pan['tithi']} | Nitya yoga: {pan['nitya_yoga']} | "
             f"Karana: {pan['karana']} | Moon phase {pan['moon_phase_pct']}%")

    if chart.get("moon_profile"):
        mp = chart["moon_profile"]
        L.append(f"\nCHANDRA GATI (Moon's daily speed): {mp['speed']} deg/day = {mp['gati']} "
                 f"(mean {mp['mean_speed']}, ratio {mp['ratio']})")
        L.append(f"  Meaning: {mp['note']}")
        L.append(f"  Nakshatra crossing time: {mp['nakshatra_hours']}h | sign crossing: {mp['sign_hours']}h")
        L.append(f"  Birth-time sensitivity: 1 minute of clock error shifts the dasha timeline by "
                 f"~{mp['dasha_days_per_minute']} days - use this when the birth time is uncertain.")

    if chart.get("namakshar"):
        L.append("\n" + namakshar_mod.render(chart))

    if include_vargas:
        keys = ["D3", "D7", "D9", "D10", "D12", "D24", "D30", "D60"]
        L.append("\nKEY DIVISIONAL CHARTS (planet -> sign):")
        L.append("  Ascendant: " + ", ".join(f"{k}={chart['ascendant']['vargas'][k]}" for k in keys))
        for g in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
            L.append(f"  {g:7s}: " + ", ".join(f"{k}={chart['planets'][g]['vargas'][k]}" for k in keys))

    L.append("\nYOGAS / NOTABLE CONFIGURATIONS:")
    L.extend("  - " + y for y in chart["yogas"])

    if include_ashtakavarga and chart.get("ashtakavarga"):
        L.append("\n" + av_mod.render(chart))

    dc = chart["dasha_current"]
    L.append(f"\nVIMSHOTTARI DASHA (as of {dc['as_of']}):")
    if "maha" in dc:
        L.append(f"  Mahadasha: {dc['maha']['lord']} ({dc['maha']['start']} to {dc['maha']['end']})")
    if "antar" in dc:
        L.append(f"  Antardasha: {dc['antar']['lord']} ({dc['antar']['start']} to {dc['antar']['end']})")
    if "pratyantar" in dc:
        L.append(f"  Pratyantardasha: {dc['pratyantar']['lord']} ({dc['pratyantar']['start']} to {dc['pratyantar']['end']})")
    L.append("  Upcoming changes:")
    for e in chart["dasha_upcoming"]:
        L.append(f"    {e['level']} {e['lord']}: {e['starts']} -> {e['ends']}")

    L.append("\nDASHA SEQUENCE FROM BIRTH (Mahadasha level):")
    for md in chart["dashas"]:
        bal = f" (balance at birth {md['balance_at_birth']}y)" if md.get("balance_at_birth") else ""
        L.append(f"  {md['lord']:8s} {md['start']} -> {md['end']}{bal}")

    if when is not None:
        L.append("\n" + transit_summary(chart, when))
    return "\n".join(L)
