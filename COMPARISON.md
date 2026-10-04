# Gap analysis: what CNWU16/vedic-astro-skills and VedAstro have that this repo doesn't

*A read of both codebases (file trees, engines, changelogs, licences) against `jyotish-agent`, with a measured engine check and a prioritised adoption plan. Written 2026-10-04.*

---

## Part 1 — What the two repos actually are

### 🧩 CNWU16/vedic-astro-skills — 930★ · AGPL-3.0 (+ commercial restriction on prompts) · Python

Created Apr 2026, ~270 files. It is **not** an app — it is an **AI-agent skills suite** in the Claude Skill / Codex format: eight `SKILL.md` prompt packages (68 KB `vedic-core`, 71 KB `vedic-reader`, 56 KB `vedic-rectifier`…) shipped alongside a real calculation engine (81 Python files, 53 KB `engine.py`).

| Skill | What it adds over a plain astrology prompt |
|---|---|
| `vedic-calculator` | Full chart from birth details → canonical `structured_data.md` |
| `vedic-reader` | **16-rule validation system** + data-contract normalisation, plus PDF/screenshot import of JHora charts |
| `vedic-core` | P1–P12 planet audit, PAC synthesis, 12-house + 10-life-area analysis, staged auditable artifacts |
| `vedic-career` / `vedic-love` | Topic workflows using D1/D9/D10 + dasha timing |
| `vedic-rectifier` | **Birth-time rectification**: 5+ life events, minute-by-minute scans, D1/D9/D10 transitions |
| `vedic-synastry` | Two-chart work in 4 explicit frames (romantic/business/friendship/family), Ashtakoota as a screening layer |
| `vedic-prashna` | **Horary** — separate question-time chart with an auditable rule ledger (Shatpanchasika standard; KP 1-249 & Tajika optional, off by default) |

Engine depth beyond ours: **Shadbala + Ishta/Kashta Phala + 9 targeted corrections**, **Chara Karaka (7K primary + 8K reference)**, **Arudha Lagna (AL) & Upapada Lagna (UL)**, Compound Dignity, divisional-boundary sensitivity, the complete **9 MD / 81 AD / 729 PD** timeline, plus bundled `.se1` ephemeris files (True Chitrapaksha, mean node).

Process discipline worth copying:
- **Published regression numbers**: BAV 84/84 sub-items, SAV 12/12 signs, 27/27 dasha boundaries within 2 days, Shadbala total error 0.52 rupa (down from 3.75 in raw PyJHora).
- **Fail-fast** error handling: "missing dependencies and critical failures stop instead of using known-bad fallbacks".
- A **CHANGELOG that documents fixed numerical bugs** — including an ephemeris-flag mismatch that put one chart on two different ephemeris baselines (0–60″ drift), and a Vimshottari year-length global leaking between charts.
- **Minute-by-minute Lagna stability audit** across the birth-time uncertainty range, labelled *stable / boundary-sensitive / unaudited* — it refuses to invent precision.
- Context engineering: `dasha_query.py` retrieves only the relevant PD windows instead of dumping 729 rows into the model.
- Multi-platform sync: canonical `skills/` + generated `claude-code/` + `codex/` trees with a parity checker.

### 🌐 VedAstro/VedAstro — 656★ · MIT · C#/.NET · 927 MB · 3,760 files · since 2021

A **full platform** (non-profit, vedastro.org), not a library: engine + REST API + website + mobile + desktop + console.

- **200+ REST API endpoints** (OpenAPI), an **API Builder**, **MCP server** (plug into Claude/Cursor/VS Code), NuGet package, **PyPI package (`pip install VedAstro`)**, Docker image, WordPress plugin, mobile apps.
- Consumer tools: AI astrologer chat, **Life Predictor** (event prediction), Horoscope (100+ predictions), **Match Checker (10 classical Kuta methods)**, Match Finder, **Horary/Prashna**, **Numerology**, **Birth Time Finder**, Dream Interpreter, Panchang, **Journal** (log life events, mapped against the chart), experimental Earthquake Predictor.
- Engine modules: Ashtakavarga, **Muhurtha**, **PanchaPakshi**, Vargas, VimshottariDasa, **KP**, Core — plus an enormous **`EventName` catalogue (27 KB enum)** and `HoroscopeName` (100+ prediction definitions), under their philosophy *"event prediction = (data + logic) × time"*.
- **Datasets & ML**: 15,000 famous-people birth-data and marriage/divorce datasets on HuggingFace, `MatchMLPipeline` (nearest-centroid classifier), NLP tools, `DocToEmbeddings` (their RAG ingestion), Azure caching.
- Honesty note: some README claims ("Perfect Predictions") are marketing with self-selected examples; the earthquake predictor is labelled experimental. Judge the engine by `Library/Logic/Calculate/`, which is genuinely good, MIT-licensed reference code.

---

## Part 2 — Capability matrix

| Capability | jyotish-agent | vedic-astro-skills | VedAstro |
|---|---|---|---|
| Swiss Ephemeris chart + bhavas | ✅ | ✅ | ✅ |
| 16 divisional charts | ✅ | ✅ (15 audited) | ✅ |
| Ashtakavarga (BAV/SAV) | ✅ validated to 337 | ✅ w/ regression numbers | ✅ |
| **Shadbala + Ishta/Kashta Phala** | ❌ | ✅ (+9 corrections) | ✅ (full six-fold, from API sample) |
| **Chara Karaka (Jaimini)** | ❌ | ✅ 7K + 8K | partial |
| **Arudha Lagna / Upapada Lagna** | ❌ | ✅ | partial |
| Vimshottari MD/AD/PD | ✅ (3 levels) | ✅ 9/81/729 complete | ✅ (to Sukshma/Prana) |
| **Other dasha systems (Chara, Ashtottari, KP)** | ❌ | ✅ Chara | ✅ |
| **Prashna (horary)** | ❌ | ✅ full ledger | ✅ |
| **Birth-time rectification** | ❌ | ✅ rigorous | ✅ |
| **Ashtakoota / synastry** | ❌ | ✅ + 4 frames | ✅ 10 Kuta methods |
| **Muhurta (electional)** | ❌ | partial | ✅ |
| **PanchaPakshi / Numerology** | ❌ | ❌ | ✅ |
| **Event/prediction catalogue** | ❌ (LLM narrates instead) | partial | ✅ 100+ named predictions |
| Transits + Sade Sati graded by bindus | ✅ | ✅ + double transits | ✅ |
| **16-rule data validation** | partial (81 tests) | ✅ explicit rule set | ✅ (test project) |
| **Answer self-check vs chart data** | ✅ **unique** | ❌ | ❌ |
| Topic-routed reading checklists | ✅ | ✅ (per-skill) | ❌ (event-based instead) |
| **Fully local/offline LLM** | ✅ **Ollama-first** | ❌ (Claude/Codex cloud) | ❌ (Azure API) |
| Local classical-text RAG | ✅ | ✅ (rules files) | ✅ (DocToEmbeddings) |
| Public REST API | ❌ | ❌ | ✅ 200+ endpoints |
| **MCP server** | ❌ | ❌ | ✅ |
| Packaging (pip / docker / mobile) | ❌ | ❌ | ✅ |
| Multi-language UI + reports | mirror-only | ✅ zh/en/ja + HTML reports | ✅ |
| Bundled ephemeris `.se1` files | ❌ | ✅ | ✅ |
| Datasets for backtesting | ❌ | ❌ | ✅ 15k people |
| Tests + CI | ✅ 81 checks + GitHub Actions | ✅ regression suite | ✅ test project |

---

## Part 3 — The gaps that actually matter (ranked)

### A. Engine precision — ✅ FIXED 2026-10-04

> **Status: both items implemented.** `jyotish.position_mode: true` now uses
> `FLG_TRUEPOS|NONUT|NOGDEFL` (JHora-parity) and the official Astrodienst `.se1` files ship in
> `data/ephe/`. The engine reports which ephemeris actually served each calculation, the convention
> is printed in every chart for the model and the user, and a golden-chart test pins eight
> longitudes + the ascendant to 1e-6° so this can't silently drift again. A `_dms()` rounding bug
> in the same class their changelog documented (illegal `12°60'` values) was found and fixed.
> Original analysis below, kept for the record.

The measured finding that drove the fix:
Their changelog records converging on **`FLG_TRUEPOS`** (true positions: no nutation, no aberration, no deflection) after measuring a **0–60″ discrepancy** between two ephemeris baselines on the same chart, reaching ≤1″ parity with desktop JHora.

I measured it on our engine at 1990-01-01 12:00 IST, New Delhi:

| Planet | our engine (apparent) | `FLG_TRUEPOS` | delta |
|---|---|---|---|
| Sun | 256.859918 | 256.865708 | **+20.8″** |
| Mars | 226.118117 | 226.127502 | **+33.8″** |
| Saturn | 261.909715 | 261.917206 | **+27.0″** |
| Jupiter | 71.458852 | 71.455609 | −11.7″ |
| Mercury | 272.014416 | 272.013295 | −4.0″ |
| Moon / Venus | — | — | <1″ |

**Worst case 0.56 arcmin.** That is exactly the class of difference that makes AstroSage/JHora and your chart disagree in the minutes column, and it can flip a pada or varga boundary in edge cases. Neither convention is "wrong" — but if your goal is parity with the software Indian astrologers actually use, this needs a config flag (`jyotish.true_positions: true|false`) and a documented default, not a silent choice.

Also: our `pyswisseph` install ships **zero `.se1` files**, so planetary positions fall back to the built-in **Moshier** ephemeris. Fine for the nine grahas, but it is not the same computation other software runs — and it blocks ever adding Chiron/asteroids. Bundling `sepl/semo/seas_18.se1` (~2 MB) buys exact parity and future scope.

### B. Astrological breadth — the biggest content gap
Both repos have, and ours lacks: **Shadbala + Ishta/Kashta Phala**, **Chara Karaka**, **AL/UL**, **Prashna**, **rectification**, **Ashtakoota/synastry**, **muhurta**, **alternate dasha systems**, KP, PanchaPakshi, numerology. For a *reading* tool, the highest-value three are Shadbala (planet ranking → sharper judgement), Ashtakoota (the most-requested Indian feature), and rectification (turns "time unknown" users into full-chart users).

### C. Validation & regression discipline
We have 81 unit checks. They have a **16-rule cross-validation system** run on every generated chart (Ra-Ke opposition, SAV/BAV constants, planetary war, karaka ordering, MD/AD/PD continuity, D9 formula, divisional-node rules) plus **published regression numbers** and a changelog of fixed numerical bugs. Reading their changelog is a free education in the exact places Jyotish engines silently go wrong — dasha year-length globals, degree-string rounding to `12°60'`, ephemeris baseline mixing. Our fixed `365.2425` dasha year is already configurable (`jyotish.dasha_year_days`), which is the right shape; theirs went further and cross-corrected per-level. Worth a golden-chart regression test pinned in CI.

### D. Delivery & access — where both beat us comprehensively
VedAstro ships API + MCP + Docker + mobile + WP plugin; skills ships Claude/Codex packages with parity checks and HTML reports. We ship a local Streamlit app. The single highest-leverage item here is an **MCP server**: ~150 lines of Python makes your local agent callable from Claude Desktop, Cursor and VS Code — which is exactly your "local PC agent" use case, and nobody else offers a *local-LLM* MCP astrology server.

### E. Data
VedAstro's **15,000 famous-people birth-data + marriage datasets** are the raw material for backtesting ("does my marriage-timing module actually work?"). Check the dataset licence on HuggingFace before use — and note it is observational data, not ground truth about astrological claims.

---

## Part 4 — What we have that they don't

Being fair about the reverse direction, because it shapes strategy:

1. **Fully local, private operation.** Ollama-first with optional cloud fallback; charts, questions and classical texts never leave the machine. VedAstro is a cloud/Azure API; the skills suite needs Claude/Codex. This is our actual differentiator, not a small one.
2. **Answer-level verification.** `core/verify.py` checks the *model's claims* against the computed chart and offers corrective regeneration. Both others validate **data** rigorously but not the **LLM's prose about the data** — nobody in this space does that, and it is why a 7B model can be trusted here.
3. **Topic-routed reading method** (checklist per question class) as a single coherent agent rather than eight separate skill packages.
4. **Size and comprehensibility:** 2,400 readable Python lines, one commit history, AGPL-3.0 clean — versus 927 MB / 3,760 files (VedAstro) or a 270-file multi-platform sync (skills).

---

## Part 5 — Adoption plan (with licence reality)

| # | Item | Source of truth | Effort | Licence note |
|---|---|---|---|---|
| 1 | ✅ **DONE** `position_mode` flag + JHora-parity default + golden-chart test | their measured finding | S | idea/measurement, no code copied |
| 2 | ✅ **DONE** Bundle `.se1` ephemeris files + report which one is in use | Swiss Ephemeris | S | data files, freely redistributable |
| 3 | **MCP server** exposing chart/dasha/ask tools | VedAstro's pattern | S–M | write our own; MIT code readable for reference |
| 4 | Chara Karaka + AL/UL in `chart.py` | classical (BPHS/Jaimini) | S | public-domain rules |
| 5 | **Ashtakoota matching** module + UI | classical (public knowledge) | M | implement ourselves — do **not** copy skills' `SKILL.md` text |
| 6 | **Shadbala** (+ Ishta/Kashta) | classical; PyJHora as numeric oracle | M–L | PyJHora is **AGPL-3.0** → compatible with our repo, but a heavy dependency; prefer reference-oracle use |
| 7 | **Birth-time rectification** | skills' workflow design | M | design ideas OK; their prompt files are commercial-restricted |
| 8 | **Prashna** (separate pipeline) | classical (Shatpanchasika) | M | — |
| 9 | **Muhurta** finder | VedAstro's `Muhurtha.cs` | M | MIT: may reuse logic with attribution + licence notice |
| 10 | **Validation rules** (16-rule style) + published regression numbers | skills' approach | M | our own implementation |
| 11 | **Cross-check oracle in CI**: compare our longitudes/dashas against VedAstro's free API (and/or PyJHora) on a golden chart | both repos indirectly | S–M | API terms: non-commercial use; keep it optional/nightly |
| 12 | HTML/PDF report builder + person cards | skills' `report_builder.py` | M | our own; they have a ready reference |
| 13 | Backtest against the 15k-people dataset | VedAstro/HuggingFace | L | **check dataset licence first** |

**Do not copy:** their prompt text into anything commercial (skills' `COMMERCIAL_NOTICE` forbids exactly that, even though the repo is AGPL — an interesting dual-licence arrangement), VedAstro's Azure/ML/mobile stack, numerology, dream interpretation, earthquake prediction. Also: don't adopt **PyJHora** wholesale as your engine. It is AGPL (fine for you) but you would be swapping a 2,400-line readable engine for a large black box, and their own changelog shows PyJHora's dasha year-length global is buggy — they had to wrap and correct it. Use it as an *oracle to test against*, not as a foundation.

---

## Part 6 — Bottom line

They are **deeper in astrology** (breadth of techniques + published accuracy discipline) and **far deeper in distribution** (API, MCP, PyPI, Docker, mobile, datasets). You are **deeper in AI trust**: local-first privacy, chart-grounded answer verification, and an agent that reasons in the tradition's own order.

The strategic move is not to catch up on everything — it is:
1. **Fix the precision question** (items 1–2) because it is cheap and it is the foundation of every reading.
2. **Add the three highest-demand techniques** (Shadbala, Ashtakoota, rectification) rather than all twelve.
3. **Wrap it in an MCP server** so it plugs into the AI clients you already use — that is a distribution win nobody else has in local form.
4. **Adopt their validation culture**: golden-chart regressions, published numbers, external cross-check oracle in CI.

Everything else in those two repos is either a different product (VedAstro's consumer suite), a different delivery model (skills' cloud-agent packages), or out of scope (numerology, earthquake prediction).

---

### Sources
- `CNWU16/vedic-astro-skills`: README.en.md, CHANGELOG.md, COMMERCIAL_NOTICE, skills/ + claude-code/ + codex/ trees (commit `HEAD`, 2026-09-04).
- `VedAstro/VedAstro`: README.md, Library/Logic/Calculate/, API/FrontDesk/, HuggingFace/, MatchMLPipeline/ (commit `HEAD`, 2026-08-13).
- Measured locally: pyswisseph 2.10.03, Lahiri, 1990-01-01 12:00 IST New Delhi, flags `FLG_SWIEPH|FLG_SIDEREAL|FLG_SPEED` vs same `+FLG_TRUEPOS`.
