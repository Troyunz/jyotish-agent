# Improving the Jyotish Agent — a prioritized roadmap

Improvement here means two different things, and mixing them up wastes effort:

1. **Astrological accuracy** — does the engine compute what the tradition actually computes? (Ashtakavarga, Shadbala, Ashtakoota, dasha systems.) This is deterministic: you can test it, and it either matches the classical rules or it doesn't.
2. **Interpretive quality** — does the agent *read* the chart like a competent astrologer? (Order of reasoning, depth, tone, timing windows, honesty about exceptions.) This is a language-model problem, and the biggest wins are prompt design, exemplars and knowledge quality — **not** a bigger model.

The rule that saves the most wasted effort: **measure before you tune.** `test_agent.py` (now 80 checks) covers accuracy. For interpretive quality, build the evaluation harness in Tier 2 *before* you change prompts or models, or you will be guessing forever.

Legend: ✅ = implemented in this session · 🔜 = recommended next · 💡 = optional / depends on your taste

---

## Tier 1 — Done today (verify it works, then build on it)

### 1.1 ✅ Ashtakavarga — bindu strength (`core/ashtakavarga.py`)
**Why it's the highest-value accuracy addition:** without it the agent can only say *"Jupiter transits your 7th house"*. With it, it says *"Jupiter transits your 7th with 30 SAV bindus — strong support"* or warns that the same transit lands on a 19-bindu (weak) sign. Classical transit judgement is meaningless without this: the same Saturn transit that destroys one person's year is manageable for another, and bindus are the standard reason why.

- BAV for all seven grahas + SAV, by sign and by bhava, rendered into the prompt.
- Every transit line now carries `own BAV /8` and `SAV /56` with a grade.
- Tables are validated against the **classical totals 48/49/39/54/56/52/39 = 337** in the test suite — if an entry were mistyped, the totals would not come out. (This test caught a real error during development: the Moon's table had one bindu too many.)
- Visible in the UI: **Chart tab → Ashtakavarga** expander.

**Next on this line:** Kakshya (the 8 sub-divisions of each sign) for finer wedding/election timing, and Sodhya Pinda for strength ranking.

### 1.2 ✅ Answer self-check + one-click correction (`core/verify.py`)
**Why:** an LLM reading a chart will occasionally say "Jupiter in the 5th" when the data says house 4 — small models more often, big models less, none never. Until now you had to catch that yourself. Now:

- Every answer is scanned for verifiable claims (planet-house, planet-sign, house-lord, retrograde/exalted/debilitated/combust, dasha-years) and each is checked against the computed chart.
- Contradictions appear in the UI with the *exact* computed data and a **🔁 Regenerate, corrected** button that re-generates with those items fixed (and re-checks the result).
- Careful false-positive guards: transit sentences, hypotheticals, theory statements and generic pop-astrology are deliberately **not** flagged.
- Tests prove it catches injected errors *and* stays silent on correct answers, transits and theory sentences.

**Why this matters more than it looks:** it converts the model's biggest failure mode from "silent wrongness" into "visible, fixable". It also lets you run a smaller/faster model with confidence, since drifts get caught.

### 1.3 ✅ Topic-routed analysis checklists (`core/prompts.py`)
**Why:** a general prompt makes a model free-associate. The tradition itself prescribes an order for each subject, so each question type now injects its own checklist — marriage (7th house → 7th lord → Venus/Jupiter → Upapada → delay indicators → D9 → dasha windows), career (10th house/lord → Sun/Saturn/Mercury → 6th & 11th → D10 → Raja/Dhana yogas → timing), and so on for wealth, children, health, education, transits, spirituality and full readings. Retrieval also gets the topic's vocabulary, so the right classical passages surface.

**Next on this line:** make checklists **data-aware** — instead of a static text, generate the checklist with the actual chart values pre-filled ("7th lord Mercury placed in the 11th, dignity neutral → check 11th-house themes in marriage") so the model has less room to wander.

---

## Tier 2 — Next highest impact (do these in this order)

### 2.1 🔜 Evaluation harness — build this *before* anything else
**Why first:** you cannot improve what you cannot measure. Without it, every change (new model, new prompt, new retrieval setting) is a vibe.
- **`eval_cases.yaml`** — 25-40 questions across topics, each with: the question, the chart it refers to, and the *expected chart factors* the answer must contain (e.g. "must mention 7th lord Mercury in the 11th", "must give a dasha window in 2027-2028").
- **Deterministic scoring** — reuse `verify.py` for chart-claim accuracy; check required factors with keyword checks; measure latency, tokens, corrections needed.
- **Rubric scoring** — for interpretation quality, have a strong model (Gemini) score each answer 1-5 on: uses the real chart factors, classical order followed, timing windows given, tone humane, guardrails respected. Store scores per run.
- **`eval_agent.py`** — runs all cases, prints a scoreboard, writes `eval_results/<timestamp>.json` so you can diff runs.
- Target metrics to track: chart-fact accuracy (aim 100% after correction), required-factor coverage (aim 90%+), self-check issues per answer (aim trending to 0 on the 7B), median latency.

### 2.2 🔜 Shadbala — six-fold planetary strength (`core/shadbala.py`)
**Why:** dignity (`exalted/own/friend`) is coarse. Shadbala produces a **ranking** — which two planets actually dominate the chart — and classical practice leans on that for "which planet gives its results". It directly sharpens every reading ("your Jupiter outranks your Saturn in strength, so…").
- Implement: Sthana bala (uchcha, saptavargaja, ojhayugma, kendradi, drekkana), Dig bala, Kala bala (natonnata, paksha, tribhaga, varsha-masa-dina-hora, ayana), Cheshta bala, Naisargika bala, Drik bala → total in **rupas** (1 rupa = 60 shashtiamsas).
- ⚠️ Verify against a reference chart from Jagannatha Hora or Parashara's Light before trusting it — the formulas have variant conventions (especially Kala bala and Cheshta bala). Add a test with at least one external benchmark value.
- Add a `planets_by_strength` line to the prompt: "Strongest: Saturn (8.2 rupas), then Mercury (7.9)…" and let the model use it.

### 2.3 🔜 Ashtakoota matching — 36-point chart compatibility (`core/matching.py`)
**Why:** the single most-requested feature in Indian practice, and it is pure rule-based maths — perfect for this architecture, zero hallucination risk.
- Varna (1), Vashya (2), Tara (3), Yoni (4), Graha Maitri (5), Gana (6), Bhakoot (7), Nadi (8) = 36 points; plus the 10 South-Indian *Porutham* if you want the Tamil system.
- Everything needed is already computed: Moon nakshatra, pada, rashi, rashi lords, friendship tables, Mangal dosha.
- **Important:** document the Yoni-scoring convention you adopt (implementations differ slightly), and always present Nadi/Bhakoot doshas **with the classical cancellations** — the same discipline the agent already uses for Mangal dosha.
- UI: a second birth-details form, a score table, and a plain-language summary that the LLM narrates **from the computed scores** (never computes itself).
- Test each kuta against a known pair from a textbook so the tables are provably right.

### 2.4 🔜 Muhurta — auspicious window finder (`core/muhurta.py`)
**Why:** the natural next question after "when will I marry" is "which date should we pick". This is computational astrology at its most useful, and you already have panchanga + ephemeris + Ashtakavarga.
- Score each day for a given purpose (marriage, griha pravesh, vehicle purchase, travel, business opening, naming) using: tithi, nakshatra suitability, vara, nitya yoga, karana (avoid Vishti/Bhadra), lagna of the day's sunrise chart, Jupiter/Venus strength, and the couple's Moon nakshatras (avoid Tara/Janma nakshatra days).
- Output: a ranked list of dates in a range, with the reasons and the classical rule applied. Present it as *"traditionally preferred"*, not as a guarantee.

### 2.5 🔜 Deeper and alternate timing systems
- **Sookshma & Prana dasha levels** — trivial extension of `dasha.py` (one more recursion level); useful for pinning down a month when the user asks narrowly. Better: let the agent *report the level as a range* instead of over-precise dates.
- **Chara dasha (Jaimini)** — the standard alternative for relationship/turning-point timing; the algorithm is sign-count based and well documented.
- **Ashtottari / Yogini dashas** — for variety; each has its own classical applicability conditions (Krishna paksha, Rahu condition), which you should state when using them.
- **KP sub-lords** — the 249 nakshatra subdivisions (each nakshatra's 9 subs, each sub's 9 sub-subs) are pure longitude maths on data you already compute. Add Placidus houses (already available) and the system is complete. Use it **only** when the user follows KP, and keep it separate from Parashari reasoning.

### 2.6 🔜 Bhava chalit and cusp-based views
Whole-sign houses are the classical default (and correct for Parashari), but a cusp-based view shows what changes when a planet sits near a sign boundary. Add `bhava_chalit` (planets mapped to Placidus/Sripati cusps) alongside, so the agent can note "Saturn is in the 4th by sign but slips into the 5th by cusp — this is why the theme blends". This is exactly the nuance a human astrologer adds.

### 2.7 🔜 Individual nakshatra analysis for every planet
The agent currently interprets the Moon's and Lagna's nakshatras. Classical practice also reads **the nakshatra of the dasha lord and of the relevant planet** (their lord, deity, gana, and the resulting temperament). Add the nakshatra lord to the per-planet lines and a short nakshatra table (deity, gana, temperament keyword) to the knowledge base — cheap, and it noticeably improves the specificity of readings.

---

## Tier 3 — Interpretive quality without new astronomy

### 3.1 💡 Exemplars (few-shot) — the single biggest quality jump per hour of work
Paste **2–3 complete, hand-polished readings** (one marriage, one career, one full reading) into the system prompt as gold standards. Local 7B models imitate structure and tone remarkably well when shown; your readings will suddenly follow the exact "direct answer → chart factors → practical meaning → one modest remedy" shape with the right warmth. Cost: a few hundred tokens of context. Do this before considering a bigger model.

### 3.2 💡 Multi-pass reading pipeline for "full reading" requests
For long readings, replace one-shot generation with: **plan** (which houses/yogas/vargas matter for this person) → **analyse per domain** (short focused generations) → **synthesise** (one coherent reading) → **self-check** (already built). This is how you get depth without a 30B model: each small prompt stays inside a 7B's competence. Wire it as a "Deep reading" button in the UI, and consider capping total latency (~3-4 model calls).

### 3.3 💡 Distillation — make the local model behave like the cloud model
1. Use the eval harness cases + your chart data to generate 100–300 high-quality readings with Gemini (the strong brain).
2. Filter: keep only answers that pass `verify.py` with zero issues and score 4+ on the rubric.
3. Fine-tune `qwen2.5:7b` (LoRA) on that dataset — Unsloth on a free Colab T4 is enough; your 1650 can't train but doesn't need to.
4. Export to GGUF, `ollama create jyotishi-7b -f Modelfile`, point `config.yaml` at it.
This is how you get a domain-specialised local astrologer rather than a generalist that has been prompted carefully. Keep the LoRA dataset in the repo (`data/finetune/`) — it also becomes an asset in itself.

### 3.4 💡 Model routing per task
Not every call needs the big model: chart lookups, "what does my Lagna mean", summaries → 3B locally (instant); full readings, dasha reasoning, sensitive questions → 7B or Gemini. Add `generation.routing` to config with per-topic backend overrides and pass a `backend_hint` from the agent. Cuts latency on simple questions by 3-5×.

### 3.5 💡 Retrieval upgrades (in order of payoff)
- **Reranking:** retrieve top-15 with BM25+embeddings, rerank to top-5 with a cross-encoder or with a single cheap LLM call ("which of these passages are most relevant?"). Usually the largest RAG quality gain available.
- **Query expansion:** add Sanskrit/synonym expansion for the user's words (*marriage → vivaha, kalatra, 7th house, upapada*; *career → karma bhava, 10th, amatyakaraka*) before retrieval. Cheap, and works surprisingly well for Jyotisha vocabulary.
- **Better embeddings:** `bge-m3` or `multilingual-e5` handle Devanagari and transliterated Sanskrit far better than `nomic-embed-text`; if you read Hindi/Bengali sources, this matters.
- **Section-aware chunking:** store `source / chapter / topic` metadata per chunk so citations read like "Phaladeepika, chapter on gochara" rather than a bare heading.

### 3.6 💡 Knowledge base growth (highest ceiling of anything on this page)
The agent's depth is capped by what is in `data/knowledge/`. Priorities:
1. Complete translations of **Phaladeepika** and **Sarvartha Chintamani** (chapter by chapter — you can add it incrementally).
2. **Nakshatra** details (deity, gana, yoni, pada-level traits) — needed for 2.7.
3. **Varga interpretation** per divisional chart (what D10 planetary placements mean for specific professions, etc.).
4. **Yoga encyclopaedia** — a systematic list with results and cancellations.
5. Your own guru's/teacher's notes and your own case notes; then the agent becomes *your* astrologer, not a generic one.
6. Optional: **case studies** — "chart → outcome" pairs. Extremely valuable for exemplars and fine-tuning.
⚠️ Use only texts you have the right to use; keep the corpus local.

---

## Tier 4 — Experience and usefulness

- 🔜 **Chart diagrams** — North-Indian (diamond) and South-Indian (square) rashi charts and a D9 chart, drawn as inline SVG in Streamlit. Visual charts make the numbers trustworthy to a human eye and are the fastest way to spot-check the engine against your other software.
- 🔜 **PDF report export** — compile a polished reading into a printable PDF (ReportLab or WeasyPrint): birth data, chart tables, diagrams, the reading text, remedies. This is what makes it feel like a real service and is easy to give to family.
- 🔜 **Multi-person profiles + journal** — SQLite for people, charts, sessions and readings; a "family charts" view; history per person ("show me last year's reading for me"). Then it becomes a tool you use rather than a toy you demo.
- 💡 **Event calendars** — scheduled scans that alert you to: dasha changes (sandhi windows), Sade Sati phase transitions, Jupiter/Saturn sign changes, personal muhurta days, and annual birthday charts (varshaphala). A `--daemon` mode with morning notifications.
- 💡 **Voice** — Whisper (faster-whisper, small model = fine) for questions, Piper or a cloud TTS for answers. A hands-free reading session is a genuinely nicer experience for this domain.
- 💡 **Regional languages** — the persona already mirrors the user's language, but add Hindi/Telugu/Tamil UI labels and a transliteration toggle (Devanagari ↔ IAST) for Sanskrit terms.
- 💡 **Telegram / WhatsApp bot** — wrapping `JyotishAgent` in a bot is ~100 lines; family members can then ask questions on their phones (with the chart stored per user). Keep the ethics guardrails in the persona.
- 💡 **Matching view** — after 2.3, a two-chart comparison page with the kuta table and a narrated summary.

---

## Tier 5 — Engineering, robustness, ops

- **Caching:** cache embeddings per query and per chunk (they never change between builds); enable prompt caching on the cloud providers (chart text is a stable prefix — big latency/cost saver); keep `OLLAMA_KEEP_ALIVE` tuned so the model stays in VRAM.
- **Observability:** log every prompt/answer pair with latency and token counts to `logs/`; a "why did it say that" debug view showing exactly what the model saw. This is what makes debugging prompt problems possible.
- **Guardrail test suite:** extend the tests with adversarial questions (death predictions, medical advice, gemstone sales pressure, "is astrology science?") and assert the guardrail holds in the *prompt* (the rules are present) and in behaviour (spot-check answers manually after model changes).
- **Privacy:** transcripts currently sit in JSON files unencrypted — fine on a personal PC, but add an option to encrypt readings (age/sqlite + a passphrase) and a "delete my data" button. Keep an explicit **offline lock** setting that *prevents* any cloud call (useful if you ever share the machine).
- **Packaging:** a `install.ps1` that checks Python, creates the venv, installs, pulls Ollama models and builds the index in one go; then a desktop shortcut. Removes the only remaining friction for re-installing or moving to another PC.
- **Prompt hygiene:** keep the persona in a *templated* file (`core/prompts/` with `persona.md`, `checklists/*.md`, `exemplars/*.md`) so you can edit the astrologer's voice and rules without touching Python. Version it — small prompt edits change behaviour more than you expect.

---

## What *not* to do (learned from how astrology bots usually go wrong)

1. **Don't let the LLM compute anything.** The moment the model calculates a dasha or a transit, accuracy dies. Extend the Python engine, keep the model as an interpreter. This is the architecture's whole advantage — protect it.
2. **Don't reach for a bigger model first.** For a 4 GB GPU the order of payoff is: eval harness → exemplars → retrieval quality → knowledge base → distillation → model size. A well-prompted, well-fed 7B with a verified engine beats a lazy 14B on a hallucinated chart.
3. **Don't add fear.** Kaal Sarpa, Mangal dosha, Sade Sati sell consultations and destroy trust. The agent already states classical definitions *and* cancellations before difficulty — keep that discipline in every new feature, especially matching (Nadi/Bhakoot) and muhurta.
4. **Don't mix systems silently.** If you add KP sub-lords or Chara dasha, the answer must say which system it is using and why. Blending KP Placidus cusps with Parashari whole-sign houses produces confident nonsense.
5. **Don't skip the external cross-check.** Before trusting any new calculation (Shadbala especially), compare one chart against Jagannatha Hora / Parashara's Light. Two independent implementations agreeing is the only real proof.
6. **Don't add features without a test.** Every module here has tests keeping it honest; Ashtakavarga's test caught a genuine table error within minutes of writing it. Keep that bar — especially for the tables-heavy modules (matching, muhurta, Shadbala).

---

## Suggested order of work (weekend-sized chunks)

| # | Task | Time | Payoff |
|---|---|---|---|
| 1 | Evaluation harness (`eval_agent.py` + cases) | 1 weekend | Turns all future work from guessing into measuring |
| 2 | Exemplars in the prompt (2-3 gold readings) | 2 hours | Biggest visible quality jump for the effort |
| 3 | Chart diagrams + PDF export | 1 weekend | Trust, shareability, real usability |
| 4 | Ashtakoota matching | 1 weekend | The most requested Indian astrology feature |
| 5 | Retrieval reranking + query expansion + bge-m3 | 1 weekend | Deeper, better-cited classical grounding |
| 6 | Shadbala (verify externally!) | 1-2 weekends | Planetary strength ranking → sharper readings |
| 7 | Multi-pass deep-reading pipeline | 1 weekend | Book-quality full readings from a small model |
| 8 | Muhurta finder | 1 weekend | Answers "which date", not just "when" |
| 9 | Distillation → fine-tuned local model | 2-3 weekends | A domain specialist instead of a generalist |
| 10 | Multi-person profiles, journal, PDF, voice, bot | ongoing | From tool → personal practice companion |

---

## Measuring improvement (the scoreboard to keep)

| Metric | How | Target |
|---|---|---|
| Chart-fact accuracy | `verify.py` issues per answer across the eval set | 0 after correction |
| Required-factor coverage | keyword/factor checks per eval case | 90%+ |
| Interpretation quality | rubric score 1-5 by a strong-model judge | 4+ average, no answer below 3 |
| Guardrail compliance | adversarial cases in the eval set | 100% |
| Latency | median seconds to first token / full answer | <2s / <25s local |
| Correction rate | % of answers needing the corrective pass | trending to <10% |
| Classical grounding | % of answers citing retrieved sources | 80%+ on interpretive questions |

Run the harness after **every** change to prompt, model, config or knowledge base, and keep the JSON results. The diff between two scoreboards is your real answer to "did this improve the agent?" — everything else is opinion.
