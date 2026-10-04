"""Core package for the Jyotish Agent (chart math, dasha, RAG, LLM, agent loop)."""

__version__ = "1.0.0"

# Bumped whenever a *long-running* process (the Streamlit server) must be restarted to
# pick up new core APIs. Python caches imported modules in memory: after a `git pull`,
# Streamlit re-runs app.py, but `from core.config import Config` returns the module
# object already in sys.modules - i.e. the OLD code. app.py compares this number and
# tells the user to restart instead of failing with an AttributeError.
#
#   1 - initial public release
#   2 - position_mode / ephe_path settings (JHora-parity positions, bundled ephemeris)
API_LEVEL = 2

