"""Jyotish Agent - Streamlit web interface.

Run:  streamlit run app.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from core import dasha as dasha_mod
from core.agent import BirthDetails, JyotishAgent
from core.config import Config
from core.rag import Embedder, KnowledgeBase

st.set_page_config(page_title="Jyotish Agent", page_icon="🔯", layout="wide")

BACKENDS = {"local": "Ollama - local (free, offline)", "gemini": "Gemini - free tier",
            "openai": "OpenAI", "anthropic": "Claude"}


# --------------------------------------------------------------------- state
@st.cache_resource
def get_agent(backend: str) -> JyotishAgent:
    cfg = Config()
    agent = JyotishAgent(cfg)
    agent.set_backend(backend)
    agent._cfg_cache = cfg  # keep a handle for the UI
    return agent


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("backend", Config().backend)
    ss.setdefault("messages", [])          # [{"role": "user"|"assistant", "content": str, "meta": {...}}]
    ss.setdefault("birth_set", False)
    ss.setdefault("birth_summary", "")
    ss.setdefault("last_sources", [])
    ss.setdefault("warnings", [])


init_state()
cfg = Config()
agent = get_agent(st.session_state.backend)


# --------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("🔯 Jyotish Agent")
    st.caption("Parashari Vedic astrology - Swiss Ephemeris calculations + classical sources, running on your PC.")

    st.subheader("Brain")
    labels = list(BACKENDS.keys())
    backend = st.selectbox("Model provider", labels,
                           index=labels.index(st.session_state.backend),
                           format_func=lambda k: BACKENDS[k])
    if backend != st.session_state.backend:
        st.session_state.backend = backend
        agent.set_backend(backend)
        st.rerun()

    with st.expander("Status / connection check"):
        if st.button("Check now", use_container_width=True):
            st.session_state["status"] = agent.brain.status()
        status = st.session_state.get("status")
        if status:
            if status.get("ollama_up"):
                st.success(f"Ollama is running. {len(status.get('ollama_models', []))} model(s) installed.")
                ps = cfg.provider_settings("local")
                st.caption(f"local model: `{ps['model']}` | GPU layers: {ps.get('num_gpu')} | ctx: {ps.get('num_ctx')}")
                if not status.get("ollama_model_present"):
                    st.warning(f"Model `{ps['model']}` not found - run:  ollama pull {ps['model']}")
            else:
                st.error("Ollama is not reachable. Start the Ollama app (or `ollama serve`).")
            st.caption("API keys: " + ", ".join(f"{p}: {'set' if status.get(f'{p}_key') else 'missing'}"
                                                for p in ("gemini", "openai", "anthropic")))
            st.caption(f"auto-fallback: {status.get('auto_fallback')} -> {cfg.fallback_backend}")

    st.divider()
    st.subheader("Birth details")
    with st.form("birth"):
        name = st.text_input("Name", value=st.session_state.get("form_name", "Native"))
        c1, c2 = st.columns(2)
        dob = c1.date_input("Date of birth", value=None, min_value=datetime(1800, 1, 1), max_value=datetime(2100, 12, 31))
        tob = c2.time_input("Time of birth (local clock)", value=None, step=60)
        city = st.text_input("Birth city", value=st.session_state.get("form_city", ""),
                             placeholder="e.g. Bengaluru, or Delhi, or Dubai")
        unknown_time = st.checkbox("Birth time unknown (use 12:00 noon - Lagna will be approximate)")
        with st.expander("Manual coordinates (optional, overrides city lookup)"):
            lat = st.text_input("Latitude", placeholder="12.9716")
            lon = st.text_input("Longitude", placeholder="77.5946")
            tz = st.text_input("Timezone (IANA)", placeholder="Asia/Kolkata")
        submitted = st.form_submit_button("Calculate chart", use_container_width=True, type="primary")

    if submitted:
        details = BirthDetails(
            name=name.strip() or "Native",
            dob=dob.strftime("%Y-%m-%d") if dob else "",
            tob=tob.strftime("%H:%M") if tob else "",
            city=city.strip(),
            lat=float(lat) if lat.strip() else None,
            lon=float(lon) if lon.strip() else None,
            tz=tz.strip() or None,
            time_unknown=unknown_time,
        )
        try:
            agent.set_birth(details)
            st.session_state.birth_set = True
            st.session_state.warnings = agent.warnings
            b = agent.birth
            st.session_state.birth_summary = f"{b['name']} | {b['local_dt']:%d %b %Y %H:%M} | {b['place']}"
            st.session_state.messages = []
            st.session_state.form_name, st.session_state.form_city = name, city
            st.success("Chart calculated.")
        except Exception as exc:
            st.error(str(exc))

    if st.session_state.birth_set and agent.has_chart():
        st.info(st.session_state.birth_summary)
        for w in st.session_state.warnings:
            st.warning(w)
        if st.button("Clear conversation", use_container_width=True):
            agent.reset_conversation()
            st.session_state.messages = []
            st.rerun()

    st.divider()
    st.caption(f"Settings: {cfg.ayanamsa} ayanamsa | {cfg.node_type} nodes | {cfg.house_system} houses")
    st.caption(f"Knowledge base: {agent.kb.status() if agent.kb else 'disabled'}")


# --------------------------------------------------------------------- tabs
tab_chat, tab_chart, tab_dasha, tab_kb, tab_export = st.tabs(
    ["💬 Chat", "🧭 Chart", "⏳ Dashas", "📚 Knowledge base", "💾 Export"])

# ---------------------------- chat
with tab_chat:
    if not agent.has_chart():
        st.info("Enter birth details in the sidebar and press **Calculate chart**. "
                "You can still ask general questions about Jyotisha without a chart.")
    else:
        asc = agent.chart["ascendant"]
        p = agent.chart["planets"]
        cur = agent.chart["dasha_current"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Lagna", asc["sign_name"].split(" (")[0], asc["deg_str"])
        m2.metric("Chandra (Moon)", p["Moon"]["sign_name"].split(" (")[0], p["Moon"]["nakshatra"])
        m3.metric("Surya (Sun)", p["Sun"]["sign_name"].split(" (")[0], p["Sun"]["deg_str"])
        m4.metric("Dasha now", cur.get("maha", {}).get("lord", "-"),
                  cur.get("antar", {}).get("lord", "") and f"AD {cur['antar']['lord']}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🕉️" if msg["role"] == "assistant" else "🙏"):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("meta"):
                meta = msg["meta"]
                if meta.get("sources"):
                    with st.expander(f"📚 Classical sources used ({len(meta['sources'])})"):
                        for s in meta["sources"]:
                            st.markdown(f"- **{s['title']}** {('- ' + s['heading']) if s.get('heading') else ''} "
                                        f"<span style='color:#888'>(score {s['score']})</span>", unsafe_allow_html=True)
                if meta.get("backend"):
                    st.caption(f"answered by: {meta['backend']}")

    prompts = [
        "Give me a full reading of my chart - start with Lagna, Moon and the strongest yogas.",
        "What does my chart say about marriage and when is the likely window?",
        "Which career fields suit me, and what does the current dasha favour?",
        "What are my current transits and what do they mean for this year?",
    ]
    if agent.has_chart() and not st.session_state.messages:
        st.caption("Try one of these:")
        cols = st.columns(2)
        for i, q in enumerate(prompts):
            if cols[i % 2].button(q, use_container_width=True, key=f"p{i}"):
                st.session_state["queued"] = q
                st.rerun()

    question = st.chat_input("Ask Jyotishi anything about your chart, dashas, or Jyotisha in general...")
    if not question:
        question = st.session_state.pop("queued", None)

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user", avatar="🙏"):
            st.markdown(question)
        with st.chat_message("assistant", avatar="🕉️"):
            placeholder = st.empty()
            text = ""
            meta: dict = {}
            try:
                for ev in agent.stream_answer(question):
                    if ev["type"] == "token":
                        text += ev["text"]
                        placeholder.markdown(text + " ▌")
                    elif ev["type"] == "done":
                        meta = {"backend": ev.get("backend"), "sources": ev.get("sources", [])}
                    elif ev["type"] == "error":
                        text = f"⚠️ {ev['message']}\n\nCheck the sidebar status, or switch the provider " \
                               f"(local needs Ollama running; cloud needs a key in `.env`)."
                placeholder.markdown(text)
            except Exception as exc:
                text = f"⚠️ Something went wrong: {exc}"
                placeholder.markdown(text)
        st.session_state.messages.append({"role": "assistant", "content": text, "meta": meta})
        if meta.get("sources"):
            st.session_state.last_sources = meta["sources"]
        st.rerun()

# ---------------------------- chart
with tab_chart:
    if not agent.has_chart():
        st.info("Calculate a chart first (sidebar).")
    else:
        c = agent.chart
        b = c["birth"]
        st.subheader(f"Chart of {b['name']}")
        st.caption(f"{b['local_datetime']} local ({b['tz']}, UTC{b['utc_offset']}) = {b['utc_datetime']} UT | "
                   f"{b['place']} | JD {b['julian_day_ut']} | ayanamsa {c['ayanamsa_value']}°")

        asc = c["ascendant"]
        st.markdown(f"**Lagna:** {asc['sign_name']} {asc['deg_str']} - nakshatra "
                    f"{asc['nakshatra']['name']} pada {asc['nakshatra']['pada']} (lord {asc['nakshatra']['lord']})")

        st.markdown("#### Grahas (sidereal positions)")
        rows = []
        for g in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"):
            p = c["planets"][g]
            flags = ", ".join([f for f in ["retrograde" if p["retrograde"] else "", "combust" if p["combust"] else ""] if f])
            rows.append({"Graha": g, "Sign": p["sign_name"], "Degree": p["deg_str"], "House": p["house"],
                         "Nakshatra": p["nakshatra"], "Nak lord": p["nak_lord"], "Dignity": p["dignity"], "Flags": flags})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("#### Bhavas (whole-sign houses)")
        hrows = []
        for h in range(1, 13):
            H = c["houses"][str(h)] if str(h) in c["houses"] else c["houses"][h]
            hrows.append({"House": h, "Sign": H["sign"], "Lord": H["lord"],
                          "Lord placed in": f"house {H['lord_house']} ({H['lord_sign']}, {H['lord_dignity']})",
                          "Occupants": ", ".join(H["occupants"]) or "-",
                          "Aspected by": ", ".join(H["aspecting"]) or "-",
                          "Signifies": H["significations"]})
        st.dataframe(pd.DataFrame(hrows), use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Panchanga at birth")
            for k, v in c["panchanga"].items():
                st.markdown(f"- **{k.replace('_', ' ').title()}:** {v}")
        with col2:
            st.markdown("#### Yogas & notable configurations")
            if c["yogas"]:
                for y in c["yogas"]:
                    st.markdown(f"- {y}")
            else:
                st.caption("No classical yoga patterns flagged for this chart.")

        with st.expander("Divisional charts (vargas) - signs"):
            vrows = []
            keys = list(c["planets"]["Sun"]["vargas"].keys())
            vrows.append({"Body": "Lagna", **{k: c["ascendant"]["vargas"][k] for k in keys}})
            for g in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"):
                vrows.append({"Body": g, **c["planets"][g]["vargas"]})
            st.dataframe(pd.DataFrame(vrows), use_container_width=True, hide_index=True)

        with st.expander("Full chart text (what the model receives as ground truth)"):
            st.code(agent.chart_text(), language="text")

# ---------------------------- dasha
with tab_dasha:
    if not agent.has_chart():
        st.info("Calculate a chart first (sidebar).")
    else:
        c = agent.chart
        cur = c["dasha_current"]
        c1, c2, c3 = st.columns(3)
        for col, key, label in ((c1, "maha", "Mahadasha"), (c2, "antar", "Antardasha"), (c3, "pratyantar", "Pratyantardasha")):
            if key in cur:
                col.metric(label, cur[key]["lord"], f"{cur[key]['start']} → {cur[key]['end']}")
        st.markdown("#### Upcoming changes")
        for e in c["dasha_upcoming"]:
            st.markdown(f"- **{e['level']} {e['lord']}**: {e['starts']} → {e['ends']}")

        st.markdown("#### Full Vimshottari sequence")
        level = st.radio("Detail level", ["Mahadasha", "Mahadasha + Antardasha", "Antardasha + Pratyantardasha"],
                         horizontal=True)
        if level.startswith("Antardasha"):
            rows = dasha_mod.flatten(c["dashas"], level="ad")
        else:
            rows = dasha_mod.flatten(c["dashas"], level="md")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=420)

# ---------------------------- knowledge base
with tab_kb:
    st.subheader("Local knowledge base")
    st.caption("Classical Jyotisha texts and notes live in `data/knowledge/`. Everything is indexed and searched "
               "on your machine. Drop in more .md / .txt / .pdf files (only use texts you have the right to use) "
               "and rebuild the index.")
    if agent.kb:
        st.markdown(f"**Status:** {agent.kb.status()}")
        if agent.kb.meta.get("files"):
            st.markdown("**Files indexed:** " + ", ".join(f"`{f}`" for f in agent.kb.meta["files"]))
        emb = Embedder(cfg)
        st.markdown(f"**Embedding provider available now:** {emb.provider or 'none - BM25 keyword search will be used'}"
                    + (f" (`{emb.model}`)" if emb.provider else ""))

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("🔨 Rebuild index (with embeddings if available)", use_container_width=True):
                with st.spinner("Indexing..."):
                    res = agent.kb.build(embed=True)
                    agent.kb = KnowledgeBase(cfg)  # reload
                st.success(res["message"])
                st.rerun()
        with c2:
            if st.button("⚡ Rebuild without embeddings (fastest)", use_container_width=True):
                with st.spinner("Indexing..."):
                    res = agent.kb.build(embed=False)
                    agent.kb = KnowledgeBase(cfg)
                st.success(res["message"])
                st.rerun()

        st.divider()
        st.markdown("#### Test retrieval")
        q = st.text_input("Search the classical notes", value="jupiter transit marriage")
        if q:
            hits = agent.kb.search(q, k=4)
            if not hits:
                st.info("No matches. Try different words, or rebuild the index.")
            for h in hits:
                with st.expander(f"{h['title']} - {h.get('heading', '')} (score {h['score']})"):
                    st.markdown(h["text"])
    else:
        st.warning("RAG is disabled in config.yaml (`rag.enabled: false`).")

# ---------------------------- export
with tab_export:
    st.subheader("Export")
    if not agent.has_chart():
        st.info("Calculate a chart first (sidebar).")
    else:
        st.markdown("Download a JSON file with the birth data, the full calculated chart, the dasha tree "
                    "and your conversation. Useful as a record, or to keep a reading for later.")
        if st.button("📄 Prepare transcript", use_container_width=False):
            path = agent.save_transcript("transcript_export.json")
            st.session_state["export_path"] = str(path)
        path = st.session_state.get("export_path")
        if path and Path(path).exists():
            st.download_button("⬇️ Download transcript_export.json", Path(path).read_text(encoding="utf-8"),
                               file_name="jyotish_transcript.json", mime="application/json")
        if st.session_state.messages:
            md = "\n\n".join(f"**{'You' if m['role'] == 'user' else 'Jyotishi'}:** {m['content']}"
                             for m in st.session_state.messages)
            st.download_button("⬇️ Download conversation (Markdown)", md,
                               file_name="jyotish_conversation.md", mime="text/markdown")
