# Setting up the Jyotish Agent on your Windows PC
### Written for your machine: Ryzen 5 4600H · 16 GB RAM · GTX 1650 (4 GB VRAM) · Windows

This is the complete, step-by-step path from zero to a working Vedic astrology agent on your own PC. Budget about **45–60 minutes**, most of it downloads.

What you are building:

```
   your questions
        │
        ▼
 ┌────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
 │  Streamlit web UI  │ ──► │  Python agent (core/)    │ ──► │  Brain (choose):     │
 │  localhost:8501    │     │  • Swiss Ephemeris chart │     │  • Ollama local GPU  │
 └────────────────────┘     │  • Vimshottari dasha     │     │  • Gemini free tier  │
                            │  • classical-text RAG    │     │  • OpenAI / Claude   │
                            └──────────────────────────┘     └─────────────────────┘
                                        ▲
                                        │ data/knowledge/*.md  (classical texts, notes)
```

Everything except the optional cloud brain runs **offline on your PC**. Birth data never leaves the machine unless you switch to a cloud model — and even then only the chart summary you send is transmitted.

---

## Step 1 — Install Python 3.11 (important: not 3.12 or 3.13)

The astrology engine (`pyswisseph`, a Python binding to the professional Swiss Ephemeris) ships **prebuilt Windows wheels only up to Python 3.11**. On 3.12/3.13, pip would try to compile it from C source and you would need Visual Studio Build Tools — avoid that entirely.

1. Go to **https://www.python.org/downloads/release/python-3119/** (or any 3.11.x).
2. Download **Windows installer (64-bit)**.
3. Run it. On the first screen, **tick “Add python.exe to PATH”**, then *Install Now*.
4. Verify in a new PowerShell window:
   ```powershell
   py -3.11 --version        # should print: Python 3.11.9
   ```

> If `py -3.11` is not found, re-run the installer and choose "Modify" → ensure the launcher is installed.

---

## Step 2 — Confirm your GPU

In PowerShell:
```powershell
nvidia-smi
```
You should see `NVIDIA GeForce GTX 1650` and about **4096 MiB** of memory. If the command is missing, install/update the NVIDIA driver from nvidia.com — Ollama uses CUDA through the driver.

Your GPUs role: the 4 GB card will hold a small model entirely, and a 7B model partially (the rest runs from your 16 GB of RAM). That is fine — expect roughly 5–8 tokens/sec on a 7B model, 15–25 tokens/sec on a 3B model.

---

## Step 3 — Install Ollama and pull the models

1. Download from **https://ollama.com/download** (Windows installer) and install it. Ollama runs in the background and listens on `localhost:11434`.
2. In PowerShell, pull the three models:
   ```powershell
   ollama pull qwen2.5:7b-instruct-q4_K_M   # main brain, ~4.7 GB - best quality that fits
   ollama pull llama3.2:3b                  # fast brain, ~2 GB - fully on the 1650
   ollama pull nomic-embed-text             # embeddings for the classical-text search, ~275 MB
   ```
3. Test it:
   ```powershell
   ollama run llama3.2:3b "Namaste, reply in one line."
   ```
4. (Recommended) keep models warm so answers start fast, and cap memory:
   ```powershell
   setx OLLAMA_KEEP_ALIVE 30m
   ```
   Close and reopen the terminal afterwards.

> **4 GB VRAM guidance** — in `config.yaml` you will find:
> ```yaml
> local:
>   model: qwen2.5:7b-instruct-q4_K_M
>   num_gpu: 24        # how many layers go to the GPU. Lower it (16, 12) if you get CUDA errors,
>                      # raise it (28) if you see spare VRAM in nvidia-smi while it answers.
>   num_ctx: 8192      # context window. 8192 is a good balance; 4096 is faster.
> ```
> A 3B model with `num_gpu: 99` runs entirely on the GPU and feels instant. Start there if you want speed, then move up to the 7B once everything works.

---

## Step 4 — Put the project on your PC

Copy the whole **`jyotish-agent`** folder (download it from this workspace — the file tree is listed in `README.md`) to somewhere simple, for example:

```
C:\Users\<YourName>\jyotish-agent
```

Recommended: open this folder in **VS Code** — you get a file browser and a built-in terminal, which makes the next steps easier.

---

## Step 5 — Create the Python environment and install dependencies

In VS Code, open a terminal in the project folder (Terminal → New Terminal), then:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell refuses to run `activate` ("running scripts is disabled"), either run this once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
or simply use `cmd` instead of PowerShell for the activate step (`.venv\Scripts\activate.bat`).

Installation takes a few minutes. `pyswisseph` will install as a ready-made wheel — no compiler needed, because you are on Python 3.11.

---

## Step 6 — Configure

1. **API keys (optional but recommended).** Copy `.env.example` to `.env` in the same folder. For the free cloud fallback:
   - Go to **https://aistudio.google.com/apikey** → *Create API key* (free, no credit card).
   - Paste it into `.env`:
     ```
     GEMINI_API_KEY=your-key-here
     ```
   With `auto_fallback: true` in `config.yaml`, the agent answers with your local model and automatically retries with Gemini if the local one is unreachable or over-weighted. You can also switch providers any time from the sidebar.

2. **Astrology settings** (`config.yaml`) — defaults are the classical Indian standard:
   ```yaml
   jyotish:
     ayanamsa: lahiri      # lahiri | raman | krishnamurti | yukteshwar | true_chitra
     node: true            # true | mean Rahu/Ketu
     house_system: whole   # whole-sign (classical Parashari)
   ```

---

## Step 7 — Verify the installation (no AI needed)

```powershell
python test_agent.py
```
You should see **48 passed, 0 failed**. This checks the ephemeris, the nakshatra maths, dasha sequencing, city lookup, and the knowledge index — a good sign that the astronomy is correct.

Then build the classical-text index with embeddings:
```powershell
python build_index.py
```
Expected output mentions `Embeddings: ollama:nomic-embed-text`. If Ollama is not running you will get `none (BM25 keyword search)` — still fully functional, just keyword-based.

---

## Step 8 — Run it

**Option A — web UI (recommended):**
```powershell
streamlit run app.py
```
A browser tab opens at **http://localhost:8501**. Or just double-click **`run.bat`**.

In the sidebar: enter your name, date of birth, **exact time of birth** (local clock time, 24-hour), and birth city (a built-in list of 290+ cities, with fuzzy matching, plus manual latitude/longitude for anywhere else). Press **Calculate chart**, then ask anything in the Chat tab. The Chart, Dashas and Knowledge-base tabs let you inspect the ground truth the model is reasoning from.

**Option B — command line:**
```powershell
python cli.py --name "Your Name" --dob 1990-01-01 --tob 12:00 --city "New Delhi"
```

**Option C — one-off question:**
```powershell
python cli.py --dob 1990-01-01 --tob 12:00 --city Delhi --ask "What do my dashas say about career change in 2027?"
```

To use it from your phone on the same Wi-Fi, open `http://<your-PC-IP>:8501` (the `.streamlit/config.toml` already binds to 0.0.0.0 for this).

---

## Step 9 — Add your own classical books (this is where it gets good)

The `data/knowledge/` folder already contains study notes that the agent cites. To deepen it, drop in more `.md`, `.txt`, or `.pdf` files — your own notes, translations you own, or public-domain texts (e.g. from archive.org) — then rebuild:

```powershell
python build_index.py
```

Suggested additions: a full translation of BPHS, Phaladeepika, Saravali, Sarvartha Chintamani, Uttara Kalamrita, your own guru's teaching notes, or your own course material. The agent will quote and apply them with the source name attached.

⚠️ Use only texts you have the right to use. Do not add pirated copyrighted books. Everything stays on your own disk.

---

## Step 10 — What to verify with your own astrology software

Cross-check one chart against AstroSage / Jagannatha Hora / Parashara's Light (same Lahiri ayanamsa, whole-sign houses). Planetary longitudes should match to the arc-second, since this project uses the same Swiss Ephemeris engine. Dasha dates should match to within a day (the difference, if any, comes from the year-length convention in `config.yaml` → `dasha_year_days`).

---

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| `pip install pyswisseph` starts compiling / errors with MSVC | You are not on Python 3.11. Delete `.venv`, install Python 3.11, recreate it (`py -3.11 -m venv .venv`). |
| `streamlit : command not found` | Virtual environment not activated. Run `.venv\Scripts\activate` in the project folder. |
| UI says "Ollama is not reachable" | The Ollama app is not running. Launch it from the Start menu, or run `ollama serve`. |
| `CUDA error: out of memory` | Lower `local.num_gpu` in config.yaml (24 → 16 → 12), or switch to `llama3.2:3b`. Check the split with `ollama ps`. |
| Answers take very long | Switch to the 3B model, set `num_ctx: 4096`, close games/GPU apps. First answer after a cold start is always slower (model loading). |
| Answer quality is weak / it misreads the chart | Use the 7B model, or switch the sidebar provider to Gemini for that question. Small local models are best at summarising the chart data they are given — the chart itself is computed, not guessed, so the numbers are always right. |
| The model invents quotes | Rebuild the knowledge index (`python build_index.py`) so real references are retrieved, and ask it directly: "cite only from the references provided". |
| Wrong timezone / DST | Use the sidebar's *Manual coordinates* section and type the IANA timezone (e.g. `America/New_York`, `Asia/Kolkata`). |
| Output mixes in Chinese characters | A quirk of some Qwen builds. Use `llama3.2:3b`, `gemma3:4b`, or the Gemini fallback. |
| `ModuleNotFoundError: No module named 'httpx'` (or `pandas`) | Your install predates a dependency fix — `openai` 3.x now pulls `httpx2` instead of `httpx`. Re-run `pip install -r requirements.txt`, or `pip install "httpx>=0.27,<1" "pandas>=2.0"`. |

---

## Hardware reality check

- **GTX 1650 (4 GB + FP16-friendly)** comfortably runs 3B models; 7B models run with partial CPU offload. That is enough for a genuinely useful astrology agent, because the *hard* part (positions, dashas, vargas) is computed by the ephemeris, not by the model. The model's job is interpretation and conversation.
- Your **16 GB RAM** is the real limiter for 7B models — leave a couple of GB free for Windows and Streamlit.
- If you later upgrade to a 12 GB+ GPU, `qwen2.5:14b-instruct` or `gemma2:9b`/`gemma3:12b` become the sweet spot — just change `local.model` in `config.yaml`.
- Keep the **Gemini free tier** configured as a fallback: for deep readings (full chart analysis, long dasha reasoning) a 100B+ cloud model is noticeably more coherent than a 7B at home.

---

## Privacy, cost, and licensing

- **Cost:** ₹0 to run locally. Cloud APIs are optional; Gemini has a free tier, OpenAI/Claude are pay-per-use.
- **Privacy:** birth data, charts and conversations stay on your disk. The only outbound traffic is to whatever brain you choose (and only if you choose a cloud one).
- **Secrets:** keep API keys in `.env` only — it is already in `.gitignore`.
- **Licensing:** `pyswisseph` wraps the Swiss Ephemeris, which is dual-licensed **AGPL-3.0 / commercial** (Astrodienst). Personal, local use is fine; if you ever distribute or host this publicly, either open-source your code under AGPL or buy a Swiss Ephemeris commercial licence. The bundled knowledge notes are original study summaries written for this project.
- **Ethics:** the agent is deliberately built not to predict death, diagnose illness, or give financial/legal instructions, and to state both the classical view and the exceptions before flagging any dosha. Astrology here is a guidance tradition, not a verdict.
