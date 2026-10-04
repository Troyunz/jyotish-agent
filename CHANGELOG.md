# Changelog

Notable changes to the Jyotish Agent. Version numbers follow the module changes that alter
computed output — anything under **numerical change** means previously generated charts will
differ, so re-check any reading you keep.

---

## 2026-10-04 — namakshar (naming syllables) + Chandra gati (Moon speed) + boundary fix

**⚙️ Small numerical change at nakshatra/pada boundaries only** (see the fix at the end). Birth
syllables, Moon-speed profile and a sharper birth-time sensitivity figure are now computed, shown in
the UI and given to the model.

### `core/namakshar.py` (new)
The 27 × 4 = 108 pada syllables in Devanagari with roman transliteration, plus the edition notes
where traditions differ (Krittika अ/इ/उ/ए vs आ/ई/ऊ/ए; Rohini वू vs वु). Functions: `syllables_for(lon)`
→ nakshatra, pada, syllable, roman, all four padas; `lookup(name)` → reverse lookup for a soft name
cross-check; `table_text()` for the CLI/report; `render(chart)` for the chart text.
Syllables repeat across nakshatras, so `lookup()` returns a *list* and is never presented as an error
in the native's name — the classical direction is Moon → syllable, and many families don't follow the
naming tradition at all.

### `core/chart.py` — `moon_gati()`
The Moon's daily speed varies ~11.8 to ~15.3 °/day (measured from the bundled ephemeris: apogee
2026-11-14, perigee 2026-12-24, a 1.30× ratio), so a nakshatra takes **20.9–27.1 h** to cross and a
sign ~47–62 h. The engine now reports speed, ratio to the mean (13.176 °/day), a five-band
classification (ati-sheeghra / sheeghra / sama / manda / ati-manda) and — the practically useful part
— **birth-time sensitivity**: 1 minute of clock error shifts the Vimshottari timeline by
`speed/1440 × 120/360 × 365.2425` ≈ **1.14 dasha-days** for the test chart. Quoted in the chart text
and the UI whenever the birth time is uncertain.

### Fixes
- **Float-boundary bug (behaviour change):** `40.0 // (360/27)` evaluates to `2.0` in binary floating
  point, so a Moon at *exactly* 40°000′00″ was assigned to **Krittika instead of Rohini** — one
  nakshatra (and one dasha lord) out. `10.0 // (360/108)` made Ashwini pada 4 read as **pada 3**.
  All three modules (`chart.nakshatra_of`, `namakshar.syllables_for`, `dasha.vimshottari`) now apply a
  single 1e-9° (0.0000036″) epsilon up front, so nakshatra, pada and the starting dasha lord can never
  disagree at a cusp. Verified at all 27 nakshatra and 108 pada cusps. Real cases with birth data to
  arcsecond precision are essentially never exactly on a cusp, so no existing reading changes — but a
  cusp-exact chart now falls on the correct side.
- Devanagari name matching uses the first base character, not `[0]`: 'गे' is *two* code points (ग +
  vowel sign े), so `'गे'[0]` is only ग and a name like गौतम matched nothing. Now both reduce to ग.
  Roman names match on their first syllable ("Gautam" → the Ga/Gi/Gu/Ge family).
- Roman transliteration cannot distinguish श from ष; the Devanagari path is stricter and returns
  nothing for श, which is honest — श is not one of the 108 syllables.

### Knowledge base
`vedic_foundations.md` gains **Namakarana** (the naming rite, the Moon→syllable direction, why the
table is regionally variable) and **Chandra gati** (speed bands, what a fast/slow Moon means for the
mind, the 21–27 h nakshatra crossing, the birth-time arithmetic). `remedies.md` gains a section
separating **yogic kriyas from Jyotisha techniques** (Tratak, pranayama/shatkarmas, asana/yama/niyama)
with contraindications — they are upaya, not astrology. Index: 118 → 130 chunks.

### Tests: 120 → 166 checks
Table shape and Devanagari content, six published syllable values, a 21,600-point sweep (every
longitude yields a valid syllable, pada always 1–4), all 27/108 cusp-agreement checks between the
three modules, reverse lookup in both scripts (including the shared-syllable and unknown-syllable
cases), the float-boundary cases, gati band thresholds, the 20.9–27.1 h crossing range and the
dasha-shift formula.

---

## 2026-10-04 — knowledge base: Ashtakavarga notes + stale-index detection

**No numerical change to charts.** Affects retrieval quality.

### New knowledge file: `data/knowledge/ashtakavarga.md`
The engine computes BAV/SAV and grades every transit with it, but the corpus only mentioned
Ashtakavarga in passing (5 mentions across 3 files). The model was being handed "SAV 30/56 = strong
support" with almost no grounding to explain what that means. The new file adds: how the points are
generated, the classical totals (48/49/39/54/56/52/39 = 337) as a correctness check, the grading
bands (matching `core/ashtakavarga.py` exactly), how to read a planet's own BAV *against* the SAV,
the dasha → transit → Ashtakavarga order of judgement, kakshya subdivisions, sodhya pinda, use in
vargas, and the honest limits. Index grows 102 → 118 chunks, 6 → 7 files.

### Stale-index detection
Previously, editing a book or adding a new one left the agent silently serving the old content — the
user would reasonably conclude the agent ignored their text. Now:
- `build()` records a sha1 + size per knowledge file in the index metadata.
- `KnowledgeBase.staleness()` reports added / edited / removed files.
- `status()` appends `⚠ STALE (...) - rebuild: python build_index.py`.
- `python build_index.py --check` lists exactly what changed and what to do.
- The Streamlit Knowledge base tab shows a warning naming the changed files.
- Indexes built by older versions (no signatures) are handled via filename comparison.

### Tests: 111 → 120 checks
Staleness behaviour is tested against a temporary knowledge folder: empty index is stale, a fresh
build is not, editing/adding/removing a file is each detected, and rebuilding clears the flag.

---

## 2026-10-04 — precision: true positions, bundled ephemeris, golden chart

**⚙️ Numerical change.** Charts computed before this date used apparent planetary positions on the
Moshier fallback ephemeris. Both are now fixed and documented.

### Position convention (`jyotish.position_mode`, default `true`)
- New setting selecting the Swiss Ephemeris flag set:
  - `true` → `SEFLG_TRUEPOS | SEFLG_NONUT | SEFLG_NOGDEFL` — the combination verified against
    desktop Jagannatha Hora (delta ≤ 1″) by the vedic-astro-skills project, which measured a
    0–60″ discrepancy between the two baselines.
  - `apparent` → plain Swiss Ephemeris apparent positions (previous behaviour).
- Measured difference at 1990-01-01 12:00 IST, New Delhi: **Mars +33.8″, Saturn +27.0″, Sun +20.8″,
  Jupiter −11.7″, Mercury −4.0″, Moon +0.7″, Venus −0.8″**. Sub-arcminute, but visible in the
  arcminute column and able to flip a pada or varga boundary in edge cases — hence a setting rather
  than a silent choice.
- The convention and the ephemeris actually used are now recorded in `chart["settings"]`, printed in
  the chart text handed to the model, and shown in the UI (sidebar + Chart tab).

### Bundled Swiss Ephemeris data files (`jyotish.ephe_path`, default `data/ephe`)
- Adds the official Astrodienst data files `sepl_18.se1`, `semo_18.se1`, `seas_18.se1` (~2 MB,
  planets/Moon/asteroids, 1800–2400).
- Before this, `pyswisseph` silently fell back to the **Moshier** built-in ephemeris — a different
  computation from what other Jyotish software runs. Measured difference: up to **0.45″**
  (Venus); Mercury 0.07″, Moon 0.13″.
- The engine now reports which ephemeris served the calculation by reading the flags returned by
  `swe.calc_ut`, so a missing or unreadable file set is visible rather than silent.
- Bundling the files also unblocks asteroid/Chiron work later.

### Degrees-minutes-seconds formatting
- `_dms()` rewritten to round once in arcseconds and clamp at the sign boundary. It can no longer
  emit illegal values such as `12°60'00"` or `30°00'00"` — a rounding bug class documented in a
  sibling project. A 42,857-value invariant sweep is now part of the test suite.

### Tests: 81 → 107 checks
- **Golden chart**: eight planet longitudes plus the ascendant pinned to 1e-6°, so any future engine
  change that shifts positions is caught immediately instead of silently.
- Ephemeris assertions: bundled files present, Swiss Ephemeris genuinely in use (not Moshier).
- Flag assertions: `true` sets the three true-position flags, `apparent` does not.
- Documented-magnitude assertions: Mars ≈34″, Sun ≈21″, Moon <2″ between the two modes.

---

## 2026-10-04 — fresh-install failure: undeclared `httpx`

**Fix (no numerical change).** `openai` 3.x switched its HTTP dependency to `httpx2` (a renamed
fork), so a fresh install had no `httpx` — which `core/llm.py` and `core/rag.py` import directly for
the Ollama API. The agent failed at import on any clean machine. `pandas` had the same problem,
available only transitively through Streamlit.

- `requirements.txt` now declares `httpx>=0.27,<1` and `pandas>=2.0` explicitly, and pins
  `openai>=1.40,<3` to the tested chat-completions API surface.
- New regression guard in the test suite parses every module's imports and asserts each
  third-party import is declared in `requirements.txt`.

---

## 2026-10-04 — reliability and interpretation features

- **Ashtakavarga** (`core/ashtakavarga.py`): BAV + SAV bindu strength per sign and bhava, validated
  against the classical totals (48/49/39/54/56/52/39 = 337). Every transit line now carries
  own-BAV/8 and SAV/56 with a grade. The proposed tables were wrong for the Moon and the total test
  caught it before release.
- **Answer self-check** (`core/verify.py`): verifiable claims in each answer (planet-house,
  planet-sign, house-lord, retrograde/dignity/combust, dasha-years) are checked against the computed
  chart, surfaced in the UI, with one-click corrective regeneration. Deliberately ignores transits,
  hypotheticals and theory to avoid false alarms.
- **Topic-routed analysis checklists** (`core/prompts.py`): questions are classified (marriage,
  career, wealth, children, health, education, transit, spirituality, general) and each class
  receives the tradition's own analysis order, plus topic vocabulary for retrieval.
- **AGPL-3.0 licence** and a CI workflow (self-tests + knowledge index + UI smoke test on every push).

---

## 2026-10-04 — first public commit

Initial public state: Swiss Ephemeris chart engine (Lahiri/Raman/KP, true/mean nodes, whole-sign
bhavas, 16 vargas), Vimshottari dasha to Pratyantardasha, 25+ yoga detections, panchanga, gochara
transits with Sade Sati, classical-text RAG, Ollama/Gemini/OpenAI/Claude brains, Streamlit UI and
CLI.
