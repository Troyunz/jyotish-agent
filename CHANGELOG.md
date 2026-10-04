# Changelog

Notable changes to the Jyotish Agent. Version numbers follow the module changes that alter
computed output — anything under **numerical change** means previously generated charts will
differ, so re-check any reading you keep.

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
