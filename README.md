# 🔯 Jyotish Agent — a private, local Vedic astrology expert

An astrology agent that runs on your own PC. It computes real charts with the **Swiss Ephemeris** (the engine professional astrology software uses), reasons in the **Parashari tradition**, grounds its readings in **classical texts stored on your disk**, and talks to you in a web chat UI — using a **local LLM on your GPU** with an optional cloud fallback.

Built and tested for: Windows 11 · Ryzen 5 4600H · 16 GB RAM · GTX 1650 4 GB → see **[SETUP_WINDOWS.md](SETUP_WINDOWS.md)** for your exact machine.

---

## What it does

| Capability | Detail |
|---|---|
| **Real chart calculation** | Sidereal (nirayana) positions for all nine grahas, Lahiri/Raman/KP ayanamsa, true/mean nodes, Lagna, whole-sign bhavas with lords, nakshatra + pada, dignities, combustion, retrogradation |
| **Divisional charts** | All 16 vargas computed with standard Parashari rules — D1, D2, D3, D4, D7, **D9**, **D10**, D12, D16, D20, D24, D27, D30, D40, D45, D60 |
| **Yoga detection** | 25+ classical configurations incl. Pancha Mahapurusha, Gajakesari, Budha-Aditya, Chandra-Mangala, Sunapha/Anapha/Durudhura/Kemadruma, Adhi, Amala, Vipareeta (Harsha/Sarala/Vimala), Raja & Dhana yogas, Parivartana, Shakata, Vargottama, Neecha-bhanga, **Mangal dosha with its classical cancellations**, Kaal Sarpa (flagged as non-classical) |
| **Vimshottari dasha** | Mahadasha → Antardasha → Pratyantardasha with exact dates, current period, upcoming changes, balance-at-birth |
| **Gochara (transits)** | Current Jupiter/Saturn/Rahu positions counted from the natal Moon, **Sade Sati** phase detection, Ashtama/Ardha-Ashtama Shani |
| **Ashtakavarga** | BAV + **SAV bindu strength** per sign and bhava (validated against the classical 337 total) — grades every transit by the ground it lands on |
| **Answer self-check** | Every chart claim in an answer is verified against the computed data; contradictions are shown with a one-click corrective regeneration |
| **JHora-parity positions** | `position_mode: true` uses the true-position flag set verified against desktop Jagannatha Hora (≤1″), reported in every chart; switchable to apparent positions |
| **Bundled ephemeris** | Official Astrodienst `.se1` data files ship with the repo — no silent Moshier fallback, and the engine reports which ephemeris actually served the calculation |
| **Topic-routed analysis** | Questions are classified (marriage / career / wealth / children / health / education / transit / spirituality) and each gets the tradition's own checklist for that subject |
| **Panchanga** | Tithi, nitya yoga, karana, vara, Moon phase, sunrise/sunset for the birth location |
| **Classical RAG** | Hybrid BM25 + embedding search over classical texts and notes in `data/knowledge/`, cited in the answers (BPHS, Phaladeepika, Saravali, Brihat Jataka, Jataka Parijata, Uttara Kalamrita study notes included) |
| **Three brains** | Ollama (local, offline, GPU) · Gemini free tier · OpenAI/Claude — with automatic fallback |
| **Ethical guardrails** | Refuses death/lifespan predictions, no medical/legal/financial instructions, states dosha cancellations before difficulties, never claims scientific proof |
| **Offline geo lookup** | 290+ cities with fuzzy matching + offline timezone resolution + manual lat/lon/timezone override |

---

## Quick start

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

ollama pull qwen2.5:7b-instruct-q4_K_M     # or llama3.2:3b for speed
ollama pull nomic-embed-text

python test_agent.py        # expect: 107 passed, 0 failed
python build_index.py       # builds the classical-text index
streamlit run app.py        # open http://localhost:8501
```

Copy `.env.example` → `.env` and add `GEMINI_API_KEY=...` if you want the free cloud fallback.

---

## File tree

```
jyotish-agent/
├── app.py                    Streamlit web UI (Chat · Chart · Dashas · Knowledge base · Export)
├── cli.py                    Terminal chat with commands (/chart /dashas /sources /backend /export)
├── build_index.py            Rebuilds the classical-text index
├── test_agent.py             107 self-checks (ephemeris, golden chart, dasha, geo, RAG, verifier)
├── config.yaml               Brain, model, ayanamsa, positions, ephemeris, RAG settings
├── CHANGELOG.md              Numerical changes and fixes worth knowing about
├── .env.example              API keys (copy to .env — never commit)
├── requirements.txt
├── run.bat                   Windows double-click launcher
├── core/
│   ├── chart.py              Swiss Ephemeris + bhavas, vargas, yogas, panchanga, transits, prompt renderer
│   ├── dasha.py              Vimshottari dasha engine (MD/AD/PD, current period, transitions)
│   ├── geo.py                Offline city lookup + timezone resolution
│   ├── rag.py                Hybrid retrieval (BM25 + embeddings), index build/load/search
│   ├── llm.py                One client for Ollama / Gemini / OpenAI / Claude + fallback
│   ├── prompts.py            The Jyotishi persona, reading method and ground rules
│   └── agent.py              Orchestration: birth details → chart → retrieval → prompt → streamed answer
├── data/
│   ├── cities.csv            292 cities with coordinates (India + major world cities)
│   ├── ephe/                 Official Swiss Ephemeris .se1 files (planets, Moon, asteroids)
│   ├── knowledge/            Classical study notes (RAG corpus) — add your own books here
│   └── knowledge_index.json  Generated index
└── .streamlit/config.toml    UI theme + server binding
```

---

## Position convention and ephemeris (accuracy)

Two settings determine the exact numbers in your chart. Both are visible in the chart output and in
the UI, so nothing is hidden:

- **`position_mode: true`** (default) uses `SEFLG_TRUEPOS | NONUT | NOGDEFL` — true geometric
  positions. This is the flag set verified against desktop **Jagannatha Hora** (agreement within
  1″) by the `vedic-astro-skills` project, after they measured a 0–60″ discrepancy between the two
  baselines. Measured difference versus apparent positions: **Mars 33.8″, Saturn 27.0″, Sun 20.8″**,
  Moon under 1″. Set `apparent` to match software that uses apparent positions.
- **`ephe_path: data/ephe`** loads the official Astrodienst `.se1` files shipped in this repo. Without
  them, `pyswisseph` silently falls back to the built-in **Moshier** ephemeris — a different
  computation (measured difference up to 0.45″). The engine reads the flags returned by the Swiss
  Ephemeris to report which one actually served the calculation; check the `EPHEMERIS:` line in the
  Chart tab, or run `python -c "from core.chart import ephemeris_status; print(ephemeris_status())"`.

`test_agent.py` pins eight planet longitudes and the ascendant to 1e-6° as a **golden chart**, so any
future change to the flag set, ayanamsa handling or ephemeris path fails the tests loudly instead of
silently shifting every reading. See `CHANGELOG.md` for the measured numbers behind these choices.

---

## How the pipeline works

```
birth details ──► geo.find_city / tz_for ──► chart.calc_chart(jd, lat, lon)
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
              grahas + bhavas            vargas (D1..D60)            dasha + gochara
                    │                           │                           │
                    └──────────────► render_chart_text() ◄──────────────────┘
                                             │
   your question ──► rag.search() ──► classical passages ──► system prompt (persona + ground truth + refs)
                                             │
                                        llm.stream()  ──►  streamed answer with source list
```

Two design decisions matter most:

1. **The model never computes astrology.** All positions, houses, vargas, dashas and transits are calculated in Python and injected into the prompt as read-only ground truth ("never contradict, recompute or invent these values"). This is why a small 7B local model can give a reliable reading — it only has to interpret, not calculate.
2. **Retrieval keeps it classical.** The classical texts on your disk are retrieved per question and cited by name, which anchors style and content to the tradition instead of to the model's general training data about astrology (much of which is pop-horoscope mush).

---

## Configuration (`config.yaml`)

```yaml
backend: local              # local | gemini | openai | anthropic
auto_fallback: true         # retry with fallback_backend if the primary brain fails
local:
  model: qwen2.5:7b-instruct-q4_K_M
  num_gpu: 24               # GPU layers — lower if CUDA OOM, raise if VRAM is spare
  num_ctx: 8192             # context window
jyotish:
  ayanamsa: lahiri          # lahiri | raman | krishnamurti | yukteshwar | true_chitra
  node: true                # true | mean Rahu/Ketu
  house_system: whole       # whole-sign (classical Parashari)
  dasha_year_days: 365.2425 # year length for dasha dates
  position_mode: true       # true = JHora-parity true positions | apparent = SE default
  ephe_path: data/ephe      # bundled Swiss Ephemeris .se1 files
rag:
  enabled: true
  top_k: 5
  embed_provider: auto      # auto | ollama | openai | bm25
  embed_model: nomic-embed-text
```

Any change is picked up on restart. The provider can also be switched live from the UI sidebar.

---

## Where to take it next

- **Add Ashtakavarga / Shadbala** — `core/chart.py` already exposes planetary longitudes and house data; bindus and six-fold strength are the natural next layer for sharper transit timing.
- **Add your own knowledge** — drop `.md`/`.txt`/`.pdf` files into `data/knowledge/` and run `python build_index.py`. Add a pretty title mapping in `core/rag.py` → `_title_of`.
- **Match two charts** — write a `core/matching.py` (Ashtakoota with the 36 points); all the pieces (nakshatra, gana, nadi, rashi lords, Mangal dosha) are already computed.
- **Prashna (horary)** — compute the chart for the moment of the question instead of a birth date; `chart.calc_chart` takes any datetime.
- **Other front ends** — the agent is just Python: wrap `JyotishAgent.stream_answer()` in FastAPI, a Telegram bot, a WhatsApp bridge, or expose it to Open WebUI as an OpenAI-compatible endpoint.
- **Bigger brains** — with a 12 GB+ GPU, switch to `qwen2.5:14b`, `gemma3:12b`, or `mistral-nemo`. Nothing else changes.

### Other ways to build this on your PC (if you prefer assembling tools)

| Approach | Good for | Trade-off |
|---|---|---|
| **This project** (Python + Streamlit) | Full control, real ephemeris maths, citations | You maintain the code |
| **Open WebUI + a custom model** | Great chat UX, document upload, zero coding | No chart calculation — pure conversation, and it will hallucinate positions |
| **AnythingLLM / LM Studio** | Quick local RAG over your PDFs | No astrology domain logic or guardrails |
| **n8n / Flowise / Langflow** | Visual agent flows, scheduling, integrations | Ephemeris maths still needs a custom node or API call |
| **Continue / Cline in VS Code** | A "development agent" that can edit this codebase with you | Not an end-user chat app |

The honest summary: for a topic where **accuracy of numbers matters**, you want the calculation layer in real code (as here) and the LLM only for language and interpretation. Assembling a chat-only RAG stack gets you something that *sounds* like an astrologer but misplaces planets.

---

## Limitations & responsible use

- An LLM can still misread even correct data. Ask it to "list the chart factors" — it should cite the computed values, and you can check them in the Chart/Dashas tabs.
- The bundled knowledge notes are **original study summaries** of classical principles, not translations of copyrighted works. Nothing is quoted verbatim, so there are no fabricated verse numbers.
- Small local models (3B–7B) write plainer prose and reason less deeply than cloud models. For a full life reading, the Gemini fallback is worth having.
- This is guidance software, not a substitute for a doctor, lawyer, financial adviser, or your own judgement. It is built to say so.
- **Licensing:** this project is released under **AGPL-3.0** (see `LICENSE`), because it links the Swiss Ephemeris through `pyswisseph`, which Astrodienst dual-licenses as **AGPL-3.0 / commercial**. Personal use is unrestricted; publishing, hosting or distributing the code keeps the AGPL terms (share the source, keep the licence). If you ever want to relicense it under different terms, you would need a commercial Swiss Ephemeris licence from Astrodienst.

---

## Licence

**GNU Affero General Public License v3.0** — see [`LICENSE`](LICENSE).

Why AGPL: the astrology calculations use the Swiss Ephemeris (`pyswisseph`), which is dual-licensed by Astrodienst as AGPL-3.0 or commercial. Running this on your own machine is free and unrestricted under either interpretation. If you publish, host it as a service, or ship it to others, the AGPL requires you to make the corresponding source available under the same licence — which is exactly what a public repository does.


---

## Credits

Swiss Ephemeris by Astrodienst (via `pyswisseph`) · Classical system: Parashara's BPHS tradition, with references to Phaladeepika, Saravali, Brihat Jataka, Jataka Parijata and Uttara Kalamrita · Built for local-first operation with Ollama.
