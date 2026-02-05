# config/ai_config.py
from __future__ import annotations

import os
from typing import Dict, Any
import streamlit as st
from core.i18n import t

def get_ai_config() -> Dict[str, Any]:
    """
    Single source of truth for AI configuration.
    Priority:
      1) Streamlit session_state
      2) Streamlit secrets (Cloud)
      3) Environment variables (local/server)
    """

    # Key
    api_key = (
        st.session_state.get("GEMINI_API_KEY")
        or st.session_state.get("gemini_api_key")
        or st.secrets.get("GEMINI_API_KEY", None)
        or st.secrets.get("gemini_api_key", None)
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("gemini_api_key")
    )

    # Model
    model = (
        st.session_state.get("GEMINI_MODEL")
        or st.session_state.get("gemini_model")
        or st.secrets.get("GEMINI_MODEL", None)
        or st.secrets.get("gemini_model", None)
        or os.environ.get("GEMINI_MODEL")
        or os.environ.get("gemini_model")
        or "gemini-1.5-flash"
    )

    # Optional: if you still want your diagnostic override, do it HERE (not required)
    # model = "gemini-pro-latest"

    key_source = "none"
    if api_key:
        if st.session_state.get("GEMINI_API_KEY") or st.session_state.get("gemini_api_key"):
            key_source = "session_state"
        elif st.secrets.get("GEMINI_API_KEY", None) or st.secrets.get("gemini_api_key", None):
            key_source = "secrets"
        else:
            key_source = "env"

    return {
        "gemini_api_key": api_key,
        "gemini_model": model,
        "enable_advanced_ai": bool(api_key),
        "enable_ai_chat": bool(api_key),
        "key_source": key_source,
    }
