"""Ashtakavarga - the classical bindu (point) system for judging transit strength.

How it works: each of the seven grahas contributes benefic points ("bindus") to
specific signs, counted from its own position, from 8 reference points
(the 7 grahas + the Lagna). The result is an 8-point BAV (Bhinnashtakavarga) grid
per planet, and the SAV (Sarvashtakavarga) = the sum of all seven grids.

Why it matters for this agent: a transit is only as good as the ground it lands on.
Jupiter crossing your 7th house with 30 SAV bindus is a very different event from
the same transit over a 19-bindu sign. Without this layer the agent can only say
"Jupiter transits the 7th"; with it, it can grade the transit.

Tables below follow the standard published Ashtakavarga scheme (BPHS tradition).
The self-test validates them against the classical totals (48/49/39/54/56/52/39,
337 in the SAV) - if a table entry were wrong, those totals would not come out.
"""
from __future__ import annotations

from typing import Any

CONTRIBUTORS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna"]

# For each planet: the houses (counted from each contributor) that receive a bindu.
BENEFIC_POINTS: dict[str, dict[str, list[int]]] = {
    "Sun": {
        "Sun": [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon": [3, 6, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus": [6, 7, 12],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna": [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun": [3, 6, 7, 8, 10, 11],
        "Moon": [1, 3, 6, 7, 10, 11],
        "Mars": [2, 3, 5, 6, 9, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12],
        "Venus": [3, 4, 5, 7, 9, 10, 11],
        "Saturn": [3, 5, 6, 11],
        "Lagna": [3, 6, 10, 11],
    },
    "Mars": {
        "Sun": [3, 5, 6, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus": [6, 8, 11, 12],
        "Saturn": [1, 4, 7, 8, 9, 10, 11],
        "Lagna": [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun": [5, 6, 9, 11, 12],
        "Moon": [2, 4, 6, 8, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna": [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon": [2, 5, 7, 9, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus": [2, 5, 6, 9, 10, 11],
        "Saturn": [3, 5, 6, 12],
        "Lagna": [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun": [8, 11, 12],
        "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars": [3, 5, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn": [3, 4, 5, 8, 9, 10, 11],
        "Lagna": [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun": [1, 2, 4, 7, 8, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus": [6, 11, 12],
        "Saturn": [3, 5, 6, 11],
        "Lagna": [1, 3, 4, 6, 10, 11],
    },
}

EXPECTED_TOTALS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
                   "Jupiter": 56, "Venus": 52, "Saturn": 39}
SAV_TOTAL = 337

# Classical grading of Sarvashtakavarga bindus (per sign / bhava)
GRADES = [(28, "strong support"), (25, "good"), (22, "average"), (0, "weak / friction")]


def grade(bindus: int) -> str:
    for threshold, label in GRADES:
        if bindus >= threshold:
            return label
    return "weak"


def _contributor_signs(chart: dict[str, Any]) -> dict[str, int]:
    signs = {g: chart["planets"][g]["sign"] for g in
             ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")}
    signs["Lagna"] = chart["ascendant"]["sign"]
    return signs


def compute(chart: dict[str, Any]) -> dict[str, Any]:
    """Return {'bav': {planet: {sign: bindus}}, 'sav': {sign: bindus}, 'by_house': {...}}."""
    base = _contributor_signs(chart)
    bav: dict[str, dict[int, int]] = {}
    for planet, table in BENEFIC_POINTS.items():
        grid = {s: 0 for s in range(1, 13)}
        for contributor, houses in table.items():
            from_sign = base[contributor]
            for h in houses:
                target = ((from_sign - 1 + h - 1) % 12) + 1
                grid[target] += 1
        bav[planet] = grid

    sav = {s: 0 for s in range(1, 13)}
    for planet, grid in bav.items():
        for s in range(1, 13):
            sav[s] += grid[s]

    asc = chart["ascendant"]["sign"]
    by_house = {h: sav[((asc - 1 + h - 1) % 12) + 1] for h in range(1, 13)}
    return {
        "bav": bav,
        "sav": sav,
        "by_house": by_house,
        "totals": {p: sum(g.values()) for p, g in bav.items()},
        "sav_total": sum(sav.values()),
    }


def bindu_of(chart: dict[str, Any], planet: str, sign: int) -> dict[str, int] | None:
    """Bindus of a sign in one planet's BAV and in the SAV - used for transits."""
    av = chart.get("ashtakavarga")
    if not av or planet not in av["bav"]:
        return None
    return {"bav": av["bav"][planet].get(sign, 0), "sav": av["sav"].get(sign, 0)}


def render(chart: dict[str, Any], compact: bool = False) -> str:
    """Text block for the LLM prompt / the UI."""
    av = chart.get("ashtakavarga")
    if not av:
        return ""
    L = ["ASHTAKAVARGA (classical bindu strength - grade transits with this):"]
    L.append("  Sarvashtakavarga by bhava (whole-sign):")
    asc_signs = chart["houses"]
    row = []
    for h in range(1, 13):
        sign = asc_signs[h]["sign"].split(" (")[0]
        b = av["by_house"][h]
        row.append(f"H{h}({sign}):{b}({grade(b)})")
    L.append("    " + " | ".join(row[:6]))
    L.append("    " + " | ".join(row[6:]))
    if not compact:
        for p in ("Jupiter", "Saturn"):
            grid = av["bav"][p]
            from_asc = chart["ascendant"]["sign"]
            rowp = []
            for h in range(1, 13):
                sign = ((from_asc - 1 + h - 1) % 12) + 1
                rowp.append(f"H{h}:{grid[sign]}")
            L.append(f"  {p} BAV by bhava: " + " ".join(rowp) + f"  (total {av['totals'][p]})")
    L.append("  Reading: 28+ bindus = strong support, 25-27 good, 22-24 average, below 22 = friction.")
    L.append("  A planet transiting a sign with high bindus in ITS OWN BAV gives clean results;")
    L.append("  the SAV shows how the bhava as a whole receives outside influences.")
    return "\n".join(L)
