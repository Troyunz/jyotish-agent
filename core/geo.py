"""Place resolution and time handling - fully offline.

Given a city name we look it up in data/cities.csv (bundled, ~250 cities),
then use timezonefinder to resolve the IANA timezone from lat/lon.
You can always override with an explicit lat/lon/timezone.
"""
from __future__ import annotations

import csv
import difflib
from datetime import date, datetime, time, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import ROOT

CITIES_CSV = ROOT / "data" / "cities.csv"

_TZ_FINDER = None


@lru_cache(maxsize=1)
def load_cities() -> list[dict[str, Any]]:
    if not CITIES_CSV.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(CITIES_CSV, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                rows.append({
                    "city": row["city"].strip(),
                    "region": (row.get("region") or "").strip(),
                    "country": (row.get("country") or "").strip(),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                })
            except (KeyError, ValueError):
                continue
    return rows


def find_city(query: str) -> dict[str, Any] | None:
    """Fuzzy city lookup. Returns {city, region, country, lat, lon} or None."""
    if not query:
        return None
    q = " ".join(query.lower().replace(",", " ").split())
    cities = load_cities()

    # 1. exact
    for c in cities:
        if c["city"].lower() == q:
            return c
    # 2. prefix ("bengaluru" matches "Bengaluru", "new delhi" -> "New Delhi")
    for c in cities:
        if c["city"].lower().startswith(q) or q.startswith(c["city"].lower()):
            return c
    # 3. token containment ("bangalore karnataka" / "delhi india")
    for c in cities:
        if c["city"].lower() in q:
            return c
    # 4. fuzzy
    names = [c["city"] for c in cities]
    close = difflib.get_close_matches(q, [n.lower() for n in names], n=1, cutoff=0.74)
    if close:
        for c in cities:
            if c["city"].lower() == close[0]:
                return c
    return None


def tz_for(lat: float, lon: float) -> str:
    """IANA timezone from coordinates (offline)."""
    global _TZ_FINDER
    try:
        if _TZ_FINDER is None:
            from timezonefinder import TimezoneFinder

            _TZ_FINDER = TimezoneFinder()
        name = _TZ_FINDER.timezone_at(lat=lat, lng=lon)
        if name:
            return name
    except Exception:
        pass
    # crude fallback: India bounding box
    if 68.0 <= lon <= 98.0 and 6.0 <= lat <= 38.0:
        return "Asia/Kolkata"
    return "UTC"


def local_to_utc(d: date, t: time, tz_name: str) -> datetime:
    """Local wall-clock time in a timezone -> aware UTC datetime."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.combine(d, t, tzinfo=tz).astimezone(timezone.utc)


def describe(city: dict[str, Any] | None, lat: float | None = None, lon: float | None = None,
             tz: str | None = None) -> str:
    """Human-readable place line for prompts / UI."""
    bits = []
    if city:
        place = city["city"]
        if city.get("region"):
            place += f", {city['region']}"
        if city.get("country") and city["country"] != city.get("region", ""):
            place += f", {city['country']}"
        bits.append(place)
        la, lo = city["lat"], city["lon"]
    else:
        la, lo = lat, lon
    if la is not None and lo is not None:
        bits.append(f"lat {la:.4f}, lon {lo:.4f}")
    if tz:
        bits.append(tz)
    return " | ".join(bits) if bits else "unknown place"
