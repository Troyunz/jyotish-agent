"""Vimshottari Dasha engine - the 120-year cycle based on the Moon's nakshatra.

All dates are returned as ISO strings so the whole result is JSON-safe.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}
TOTAL_YEARS = 120.0
NAK_SPAN = 360.0 / 27.0  # 13 deg 20 arcmin


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _jump(dt: datetime, years: float, year_days: float) -> datetime:
    return dt + timedelta(days=years * year_days)


def _subdivide(lord: str, start: datetime, years: float, year_days: float, depth: int) -> list[dict[str, Any]]:
    """Split a period of `lord` into its 9 sub-periods (antardasha), recursing."""
    if depth <= 0:
        return []
    base = ORDER.index(lord)
    out: list[dict[str, Any]] = []
    cursor = start
    for j in range(9):
        sub_lord = ORDER[(base + j) % 9]
        sub_years = years * YEARS[sub_lord] / TOTAL_YEARS
        end = _jump(cursor, sub_years, year_days)
        item: dict[str, Any] = {
            "lord": sub_lord,
            "start": _iso(cursor),
            "end": _iso(end),
            "years": round(sub_years, 4),
        }
        if depth > 1:
            item["sub"] = _subdivide(sub_lord, cursor, sub_years, year_days, depth - 1)
        out.append(item)
        cursor = end
    return out


def vimshottari(moon_lon: float, birth_dt: datetime, year_days: float = 365.2425,
                depth: int = 3) -> list[dict[str, Any]]:
    """Build the dasha tree from birth.

    moon_lon : sidereal longitude of the Moon (0-360)
    depth    : 1 = Mahadasha only, 2 = +Antardasha, 3 = +Pratyantardasha
    """
    idx = int(moon_lon // NAK_SPAN) % 27
    frac = (moon_lon % NAK_SPAN) / NAK_SPAN
    start_i = idx % 9
    birth_lord = ORDER[start_i]
    balance_years = YEARS[birth_lord] * (1.0 - frac)

    # nominal start of the birth mahadasha (may be before birth)
    nominal_start = _jump(birth_dt, -(YEARS[birth_lord] - balance_years), year_days)

    periods: list[dict[str, Any]] = []
    cursor = nominal_start
    for i in range(9):
        lord = ORDER[(start_i + i) % 9]
        years = YEARS[lord] if i > 0 else YEARS[lord]
        end = _jump(cursor, years, year_days)

        # clip the first (partial) period to the moment of birth
        visible_start = max(cursor, birth_dt)
        item: dict[str, Any] = {
            "lord": lord,
            "start": _iso(visible_start),
            "end": _iso(end),
            "years": round((end - visible_start).days / year_days, 4),
            "balance_at_birth": (round(balance_years, 4) if i == 0 else None),
        }
        subs = _subdivide(lord, cursor, years, year_days, depth - 1 if depth > 1 else 0)
        if subs:
            # clip sub-periods to birth as well
            clipped = []
            for s in subs:
                if s["end"] >= _iso(birth_dt):
                    if s["start"] < _iso(birth_dt):
                        s["start"] = _iso(birth_dt)
                    clipped.append(s)
            item["sub"] = clipped
        periods.append(item)
        cursor = end
    return periods


# --------------------------------------------------------------------- queries

def _contains(period: dict[str, Any], when: str) -> bool:
    return period["start"] <= when < period["end"]


def current_periods(dasha: list[dict[str, Any]], when: datetime | None = None,
                    depth: int = 3) -> dict[str, Any]:
    """Which Mahadasha / Antardasha / Pratyantardasha is running on `when`."""
    when = when or datetime.now()
    w = _iso(when)
    result: dict[str, Any] = {"as_of": w}
    for md in dasha:
        if _contains(md, w):
            result["maha"] = {"lord": md["lord"], "start": md["start"], "end": md["end"]}
            if depth >= 2:
                for ad in md.get("sub", []):
                    if _contains(ad, w):
                        result["antar"] = {"lord": ad["lord"], "start": ad["start"], "end": ad["end"]}
                        if depth >= 3:
                            for pd in ad.get("sub", []):
                                if _contains(pd, w):
                                    result["pratyantar"] = {"lord": pd["lord"], "start": pd["start"], "end": pd["end"]}
                                    break
                        break
            break
    return result


def upcoming_changes(dasha: list[dict[str, Any]], when: datetime | None = None, n: int = 3) -> list[dict[str, str]]:
    """Next antardasha / mahadasha transitions after `when`."""
    when = when or datetime.now()
    w = _iso(when)
    events: list[dict[str, str]] = []
    for md in dasha:
        if md["end"] > w:
            events.append({"level": "Mahadasha", "lord": md["lord"], "starts": md["start"], "ends": md["end"]})
        for ad in md.get("sub", []):
            if ad["end"] > w:
                events.append({"level": f"Antardasha ({md['lord']})", "lord": ad["lord"],
                               "starts": ad["start"], "ends": ad["end"]})
    events.sort(key=lambda e: e["starts"])
    return events[:n]


def flatten(dasha: list[dict[str, Any]], level: str = "md") -> list[dict[str, str]]:
    """Flat rows for a UI table."""
    rows: list[dict[str, str]] = []
    for md in dasha:
        if level == "md":
            rows.append({"Level": "Mahadasha", "Lord": md["lord"], "Start": md["start"], "End": md["end"]})
        if level in ("md", "ad"):
            for ad in md.get("sub", []):
                if level == "ad" or level == "md":
                    rows.append({"Level": f"  AD ({md['lord']})", "Lord": ad["lord"], "Start": ad["start"], "End": ad["end"]})
                if level == "ad":
                    for pd in ad.get("sub", []):
                        rows.append({"Level": f"    PD ({ad['lord']})", "Lord": pd["lord"],
                                     "Start": pd["start"], "End": pd["end"]})
    return rows
