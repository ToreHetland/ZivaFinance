# services/ai_services.py
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any

import pandas as pd
import streamlit as st

# Modern SDK Imports (2026 Standard)
from google import genai
from google.genai import types

# Single source of truth for configuration
from config.ai_config import get_ai_config

# Optional helpers (fallback if missing)
try:
    from utils.ai_helpers import prepare_financial_context, format_context_for_ai
except ImportError:
    def format_context_for_ai(ctx: Dict) -> str:
        fm = ctx.get("financial_metrics", {})
        return (
            f"Monthly Income: {fm.get('monthly_income', 0):,.2f}, "
            f"Expenses: {fm.get('monthly_expenses', 0):,.2f}"
        )

    def prepare_financial_context(df, accounts, loans, budgets):
        inc = df[df["type"] == "Income"]["amount"].sum() if not df.empty else 0
        exp = df[df["type"] == "Expense"]["amount"].sum() if not df.empty else 0
        return {"financial_metrics": {"monthly_income": inc, "monthly_expenses": exp}}

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

@dataclass
class AIConfigResolved:
    gemini_api_key: Optional[str]
    gemini_model: Optional[str]
    key_source: str 

def _resolve_api_key_and_model() -> AIConfigResolved:
    cfg = get_ai_config() or {}
    # Prioritize gemini-2.0-flash for Paid Tier performance
    model = cfg.get("gemini_model") or st.secrets.get("GEMINI_MODEL") or "gemini-2.0-flash"
    key = cfg.get("gemini_api_key")

    if key:
        return AIConfigResolved(key, model, cfg.get("key_source", "config"))

    key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("gemini_api_key")
    if key:
        return AIConfigResolved(key, model, "secrets")

    import os
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("gemini_api_key")
    if key:
        return AIConfigResolved(key, model, "env")

    return AIConfigResolved(None, model, "none")

def _normalize_text(text: Any) -> str:
    if text is None: return ""
    return str(text).strip()

class AdvancedAIService:
    """
    Updated to use the modern Google GenAI SDK.
    """
    def __init__(self):
        self._resolved: AIConfigResolved = AIConfigResolved(None, None, "none")
        self.client = None # Replaced model_instance with client
        self.last_error: Optional[str] = None
        self._configured_signature: Optional[Tuple[str, str]] = None
        self.setup_clients(force=True)

    def setup_clients(self, force: bool = False) -> None:
        resolved = _resolve_api_key_and_model()
        self._resolved = resolved

        key = resolved.gemini_api_key
        model = resolved.gemini_model or "gemini-2.0-flash"

        if not key:
            self.client = None
            self.last_error = "Gemini API key not found."
            self._configured_signature = None
            return

        signature = (key, model)
        if (not force) and (self._configured_signature == signature) and self.client is not None:
            return

        try:
            # Modern Client Initialization
            self.client = genai.Client(api_key=key)
            self._configured_signature = signature
            self.last_error = None
            logger.info("Gemini Client configured (model=%s, source=%s)", model, resolved.key_source)
        except Exception as e:
            self.last_error = f"Failed to configure Gemini Client: {e}"
            self.client = None
            self._configured_signature = None
            logger.error(self.last_error)

    @property
    def gemini_api_key(self) -> Optional[str]:
        return self._resolved.gemini_api_key

    @property
    def gemini_model(self) -> Optional[str]:
        return self._resolved.gemini_model or "gemini-2.0-flash"

    # --- FIX ADDED HERE: Property for key_source ---
    @property
    def key_source(self) -> str:
        return self._resolved.key_source

    def _generate_with_retry(self, prompt: str, system_instruction: str = None, timeout_s: int = 30, retries: int = 2) -> str:
        if not self.client:
            raise RuntimeError(self.last_error or "Gemini client not configured.")

        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                # Modern generate_content call structure
                response = self.client.models.generate_content(
                    model=self.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        http_options=types.HttpOptions(timeout=timeout_s * 1000) # Timeout in ms
                    )
                )
                return _normalize_text(response.text) # Use .text property

            except Exception as e:
                # Basic error mapping for modern SDK
                if "429" in str(e) or "ResourceExhausted" in str(e):
                    last_exc = e
                    if attempt < retries:
                        time.sleep(1.0 * (attempt + 1))
                        continue
                raise e

        raise RuntimeError(f"AI request failed: {last_exc}")

    def get_financial_advice(self, question: str, financial_context: Dict) -> str:
        if not self.client or not self.gemini_api_key:
            return f"❌ **AI Service Error**: {self.last_error or 'Client not configured.'}"

        formatted_context = format_context_for_ai(financial_context)
        system_prompt = (
            "You are an expert personal finance advisor. "
            "Be practical, specific, and concise. "
            "Prefer bullets. Max 5 short bullets or 3-5 sentences."
        )

        full_prompt = f"Context:\n{formatted_context}\n\nUser question:\n{question.strip()}"

        try:
            txt = self._generate_with_retry(full_prompt, system_instruction=system_prompt)
            if not txt:
                return "⚠️ No AI response returned."
            self.last_error = None
            return txt
        except Exception as e:
            self.last_error = str(e)
            return f"❌ **API Error**: {e}"

# Global instance
ai_service = AdvancedAIService()

def generate_advice(
    transactions_df: pd.DataFrame,
    budgets_df: Optional[pd.DataFrame] = None,
    lang: str = "en",
    question: Optional[str] = None,
) -> Tuple[str, Optional[str], Dict]:
    """
    Main entry point for UI. Returns (advice_text, error_code, diagnostics).
    """
    ai_service.setup_clients(force=False)
    
    # Safely handle empty budgets/loans for context
    ctx = prepare_financial_context(transactions_df, accounts=[], loans=[], budgets=budgets_df or [])

    diag = {
        "key_detected": bool(ai_service.gemini_api_key),
        "key_source": ai_service.key_source,  # <--- This line caused the crash, fixed by adding @property
        "model_used": ai_service.gemini_model,
        "last_error": ai_service.last_error,
    }

    if not ai_service.gemini_api_key:
        return ("Please configure your Gemini API key to get AI advice.", "missing_api_key", diag)

    q = question.strip() if question else "Provide a brief financial overview and one key recommendation."
    advice = ai_service.get_financial_advice(q, ctx)

    error_code = "api_error" if ai_service.last_error else None
    diag["last_error"] = ai_service.last_error
    return (advice, error_code, diag)

def test_gemini_connection() -> Tuple[bool, str, Dict]:
    ai_service.setup_clients(force=True)
    diag = {
        "key_detected": bool(ai_service.gemini_api_key),
        "key_source": ai_service.key_source,
        "model_to_test": ai_service.gemini_model,
        "error": None,
    }
    if not ai_service.gemini_api_key:
        return False, "No Gemini API key detected.", diag

    try:
        resp = ai_service._generate_with_retry("Reply with exactly: OK")
        if "OK" in resp:
            return True, f"✅ Gemini API connection successful! (Model: {ai_service.gemini_model})", diag
        return False, f"❌ Test failed: {resp}", diag
    except Exception as e:
        diag["error"] = str(e)
        return False, f"❌ Connection test failed: {e}", diag

def get_ai_chat_response(prompt: str) -> str:
    ai_service.setup_clients(force=False)
    try:
        ctx = {"financial_metrics": {"monthly_income": 0, "monthly_expenses": 0}}
        return ai_service.get_financial_advice(prompt, ctx)
    except Exception as e:
        return f"⚠️ AI Service Error: {e}"