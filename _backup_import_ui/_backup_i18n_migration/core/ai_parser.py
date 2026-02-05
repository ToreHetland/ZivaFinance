# core/ai_parser.py
from __future__ import annotations
import json
import re
import datetime
import streamlit as st
from google import genai  # Modern SDK
from google.genai import types
from config.i18n import t
lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

def parse_transaction_with_gemini(user_input: str, categories_list: list[str] = None) -> dict | None:
    """
    Sends natural language text to Gemini using the modern google-genai SDK
    to extract transaction details into a structured JSON format.
    """
    api_key = st.secrets.get("GEMINI_API_KEY")
    # Using gemini-2.0-flash as the primary high-performance model
    target_model = st.secrets.get("GEMINI_MODEL", "gemini-2.0-flash")

    if not api_key:
        st.error("⚠️ GEMINI_API_KEY is missing in .streamlit/secrets.toml")
        return None

    try:
        # Initialize the modern Gemini client
        client = genai.Client(api_key=api_key)
        
        today = datetime.date.today().isoformat()
        
        # Format categories from your imported categories_migration.csv list
        # Examples: Mat, Household, Bil, etc.
        cat_str = ", ".join(categories_list) if categories_list else "Food, Transport, Housing, Salary, Entertainment"
        
        prompt = f"""
        You are a financial data parser. Extract transaction details from the user input.
        
        CONTEXT:
        - Current Date: {today} (Use this year/month if not specified).
        - ALLOWED CATEGORIES: [{cat_str}]
        
        INSTRUCTIONS:
        1. Extract the Payee, Amount, and Date.
        2. Pick the BEST MATCH from the "ALLOWED CATEGORIES" list above. 
           - For payees like {cat_str}, find the logical fit.
           - If no category matches well, use 'Unknown' or 'Diverse'.
        
        RETURN ONLY RAW JSON (no markdown):
        {{
            "date": "YYYY-MM-DD",
            "amount": float,
            "type": "Expense" or "Income",
            "payee": "string",
            "category": "string",
            "description": "string"
        }}

        Input: "{user_input}"
        """

        # Modern syntax for Gemini 2.0 Flash
        response = client.models.generate_content(
            model=target_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1 
            )
        )
        
        # Accessing content via .text as per the new SDK
        text = response.text.strip()
        
        # Remove potential markdown formatting if AI includes it
        if text.startswith("```"):
            text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE)
            
        return json.loads(text)

    except Exception as e:
        if "400" in str(e) or "API_KEY_INVALID" in str(e):
             st.error("🚨 API Key Invalid. Please check .streamlit/secrets.toml")
        else:
             st.error(f"AI Error: {e}")
        return None