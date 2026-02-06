# core/language_manager.py  (or config/i18n.py — wherever you keep it)
from __future__ import annotations

import datetime
import streamlit as st

TRANSLATIONS = {
    # ==========================================================
    # ENGLISH
    # ==========================================================
    "en": {
        # --- Greetings / time ---
        "morning": "Good Morning",
        "afternoon": "Good Afternoon",
        "evening": "Good Evening",

        # --- Navigation / pages ---
        "overview": "Overview",
        "transactions": "Transactions",
        "budget": "Budget",
        "analytics": "Analytics",
        "ai_advisor": "AI Advisor",
        "settings": "Settings",
        "accounts": "Accounts",
        "categories": "Categories",
        "data": "Data",
        "loan_calculator": "Loan Calculator",
        "notifications": "Notifications",
        "admin_panel": "Admin Panel",

        # --- Common UI ---
        "select": "Select...",
        "more": "More",
        "welcome_back": "Welcome back, {name}",
        "strategy_view_for": "Strategy view for {name}",
        "recent_insights": "Recent Insights",
        "budget_health": "Budget Health",
        "net_worth": "Net worth",

        # --- KPI / dashboard cards ---
        "monthly_income": "Monthly Income",
        "monthly_expenses": "Monthly Expenses",
        "savings_rate": "Savings rate",
        "six_month_liquidity_forecast": "6-Month Liquidity Forecast",
        "budget_limits_exceeded": "Budget limits exceeded",

        # --- Budget / alerts ---
        "budget_vs_actual": "Budget vs Actual",
        "budget_limit": "Budget limit",
        "actual_spend": "Actual spend",
        "remaining": "Remaining",
        "over_budget": "Over budget",
        "under_budget": "Under budget",

        # --- Transactions ---
        "new_transaction": "New Transaction",
        "amount": "Amount",
        "date": "Date",
        "type": "Type",
        "category": "Category",
        "account": "Account",
        "income": "Income",
        "expense": "Expense",
        "note": "Note",
        "save": "Save",
        "cancel": "Cancel",

        # --- Accounts ---
        "current_balance": "Current balance",
        "opening_balance": "Opening balance",
        "account_type": "Account type",

        # --- AI ---
        "ai_smart_entry": "AI Smart Entry",
        "ask_ai": "Ask AI",
        "ai_ready": "AI is ready",

        # --- Months ---
        "month_january": "January",
        "month_february": "February",
        "month_march": "March",
        "month_april": "April",
        "month_may": "May",
        "month_june": "June",
        "month_july": "July",
        "month_august": "August",
        "month_september": "September",
        "month_october": "October",
        "month_november": "November",
        "month_december": "December",

        # --- Short months (optional) ---
        "month_jan": "Jan",
        "month_feb": "Feb",
        "month_mar": "Mar",
        "month_apr": "Apr",
        "month_may_short": "May",
        "month_jun": "Jun",
        "month_jul": "Jul",
        "month_aug": "Aug",
        "month_sep": "Sep",
        "month_oct": "Oct",
        "month_nov": "Nov",
        "month_dec": "Dec",
    },

    # ==========================================================
    # NORWEGIAN (BOKMÅL)
    # ==========================================================
    "no": {
        "morning": "God morgen",
        "afternoon": "God ettermiddag",
        "evening": "God kveld",

        "overview": "Oversikt",
        "transactions": "Transaksjoner",
        "budget": "Budsjett",
        "analytics": "Analyse",
        "ai_advisor": "AI-rådgiver",
        "settings": "Innstillinger",
        "accounts": "Kontoer",
        "categories": "Kategorier",
        "data": "Data",
        "loan_calculator": "Lånekalkulator",
        "notifications": "Varsler",
        "admin_panel": "Admin-panel",

        "select": "Velg...",
        "more": "Mer",
        "welcome_back": "Velkommen tilbake, {name}",
        "strategy_view_for": "Strategivisning for {name}",
        "recent_insights": "Nylige innsikter",
        "budget_health": "Budsjettstatus",
        "net_worth": "Nettoformue",

        "monthly_income": "Månedlig inntekt",
        "monthly_expenses": "Månedlige utgifter",
        "savings_rate": "Sparerate",
        "six_month_liquidity_forecast": "Likviditetsprognose (6 mnd)",
        "budget_limits_exceeded": "Budsjettgrenser overskredet",

        "budget_vs_actual": "Budsjett vs faktisk",
        "budget_limit": "Budsjettgrense",
        "actual_spend": "Faktisk forbruk",
        "remaining": "Gjenstående",
        "over_budget": "Over budsjett",
        "under_budget": "Under budsjett",

        "new_transaction": "Ny transaksjon",
        "amount": "Beløp",
        "date": "Dato",
        "type": "Type",
        "category": "Kategori",
        "account": "Konto",
        "income": "Inntekt",
        "expense": "Utgift",
        "note": "Notat",
        "save": "Lagre",
        "cancel": "Avbryt",

        "current_balance": "Saldo",
        "opening_balance": "Startsaldo",
        "account_type": "Kontotype",

        "ai_smart_entry": "AI Smart Entry",
        "ask_ai": "Spør AI",
        "ai_ready": "AI er klar",

        "month_january": "Januar",
        "month_february": "Februar",
        "month_march": "Mars",
        "month_april": "April",
        "month_may": "Mai",
        "month_june": "Juni",
        "month_july": "Juli",
        "month_august": "August",
        "month_september": "September",
        "month_october": "Oktober",
        "month_november": "November",
        "month_december": "Desember",

        "month_jan": "Jan",
        "month_feb": "Feb",
        "month_mar": "Mar",
        "month_apr": "Apr",
        "month_may_short": "Mai",
        "month_jun": "Jun",
        "month_jul": "Jul",
        "month_aug": "Aug",
        "month_sep": "Sep",
        "month_oct": "Okt",
        "month_nov": "Nov",
        "month_dec": "Des",
    },

    # ==========================================================
    # SWEDISH (simple coverage)
    # ==========================================================
    "sv": {
        "morning": "God morgon",
        "afternoon": "God eftermiddag",
        "evening": "God kväll",

        "overview": "Översikt",
        "transactions": "Transaktioner",
        "budget": "Budget",
        "analytics": "Analys",
        "ai_advisor": "AI-rådgivare",
        "settings": "Inställningar",
        "accounts": "Konton",
        "categories": "Kategorier",
        "data": "Data",
        "loan_calculator": "Lånekalkyl",
        "notifications": "Aviseringar",
        "admin_panel": "Adminpanel",

        "select": "Välj...",
        "more": "Mer",
        "welcome_back": "Välkommen tillbaka, {name}",
        "strategy_view_for": "Strategivy för {name}",
        "recent_insights": "Senaste insikter",
        "budget_health": "Budgethälsa",
        "net_worth": "Nettoförmögenhet",

        "monthly_income": "Månadsinkomst",
        "monthly_expenses": "Månadsutgifter",
        "savings_rate": "Spargrad",
        "six_month_liquidity_forecast": "Likviditetsprognos (6 mån)",
        "budget_limits_exceeded": "Budgetgränser överskridna",

        "month_january": "Januari",
        "month_february": "Februari",
        "month_march": "Mars",
        "month_april": "April",
        "month_may": "Maj",
        "month_june": "Juni",
        "month_july": "Juli",
        "month_august": "Augusti",
        "month_september": "September",
        "month_october": "Oktober",
        "month_november": "November",
        "month_december": "December",
    },

    # ==========================================================
    # DANISH (simple coverage)
    # ==========================================================
    "da": {
        "morning": "Godmorgen",
        "afternoon": "God eftermiddag",
        "evening": "Godaften",

        "overview": "Oversigt",
        "transactions": "Transaktioner",
        "budget": "Budget",
        "analytics": "Analyse",
        "ai_advisor": "AI-rådgiver",
        "settings": "Indstillinger",
        "accounts": "Konti",
        "categories": "Kategorier",
        "data": "Data",
        "loan_calculator": "Låneberegner",
        "notifications": "Notifikationer",
        "admin_panel": "Adminpanel",

        "welcome_back": "Velkommen tilbage, {name}",
        "net_worth": "Nettoformue",
        "monthly_income": "Månedlig indkomst",
        "monthly_expenses": "Månedlige udgifter",
        "savings_rate": "Opsparingsrate",
        "six_month_liquidity_forecast": "Likviditetsprognose (6 mdr)",
        "budget_limits_exceeded": "Budgetgrænser overskredet",

        "month_january": "Januar",
        "month_february": "Februar",
        "month_march": "Marts",
        "month_april": "April",
        "month_may": "Maj",
        "month_june": "Juni",
        "month_july": "Juli",
        "month_august": "August",
        "month_september": "September",
        "month_october": "Oktober",
        "month_november": "November",
        "month_december": "December",
    },

    # ==========================================================
    # GERMAN / DUTCH / FRENCH / SPANISH (core coverage)
    # ==========================================================
    "de": {
        "morning": "Guten Morgen",
        "afternoon": "Guten Tag",
        "evening": "Guten Abend",
        "overview": "Übersicht",
        "transactions": "Transaktionen",
        "budget": "Budget",
        "analytics": "Analysen",
        "ai_advisor": "KI-Berater",
        "settings": "Einstellungen",
        "accounts": "Konten",
        "categories": "Kategorien",
        "data": "Daten",
        "loan_calculator": "Darlehensrechner",
        "notifications": "Benachrichtigungen",
        "admin_panel": "Admin-Bereich",
        "welcome_back": "Willkommen zurück, {name}",
        "net_worth": "Nettovermögen",
        "monthly_income": "Monatliches Einkommen",
        "monthly_expenses": "Monatliche Ausgaben",
        "savings_rate": "Sparquote",
        "six_month_liquidity_forecast": "Liquiditätsprognose (6 Monate)",
        "budget_limits_exceeded": "Budgetgrenzen überschritten",
        "month_january": "Januar", "month_february": "Februar", "month_march": "März", "month_april": "April",
        "month_may": "Mai", "month_june": "Juni", "month_july": "Juli", "month_august": "August",
        "month_september": "September", "month_october": "Oktober", "month_november": "November", "month_december": "Dezember",
    },
    "nl": {
        "morning": "Goedemorgen",
        "afternoon": "Goedemiddag",
        "evening": "Goedenavond",
        "overview": "Overzicht",
        "transactions": "Transacties",
        "budget": "Budget",
        "analytics": "Analyse",
        "ai_advisor": "AI-adviseur",
        "settings": "Instellingen",
        "accounts": "Rekeningen",
        "categories": "Categorieën",
        "data": "Data",
        "loan_calculator": "Leningen-calculator",
        "notifications": "Meldingen",
        "admin_panel": "Beheerderspaneel",
        "welcome_back": "Welkom terug, {name}",
        "net_worth": "Nettovermogen",
        "monthly_income": "Maandinkomen",
        "monthly_expenses": "Maandelijkse uitgaven",
        "savings_rate": "Spaarpercentage",
        "six_month_liquidity_forecast": "Liquiditeitsprognose (6 maanden)",
        "budget_limits_exceeded": "Budgetlimieten overschreden",
        "month_january": "Januari", "month_february": "Februari", "month_march": "Maart", "month_april": "April",
        "month_may": "Mei", "month_june": "Juni", "month_july": "Juli", "month_august": "Augustus",
        "month_september": "September", "month_october": "Oktober", "month_november": "November", "month_december": "December",
    },
    "fr": {
        "morning": "Bonjour",
        "afternoon": "Bon après-midi",
        "evening": "Bonsoir",
        "overview": "Aperçu",
        "transactions": "Transactions",
        "budget": "Budget",
        "analytics": "Analyses",
        "ai_advisor": "Conseiller IA",
        "settings": "Paramètres",
        "accounts": "Comptes",
        "categories": "Catégories",
        "data": "Données",
        "loan_calculator": "Calculateur de prêt",
        "notifications": "Notifications",
        "admin_panel": "Panneau d'administration",
        "welcome_back": "Bon retour, {name}",
        "net_worth": "Valeur nette",
        "monthly_income": "Revenu mensuel",
        "monthly_expenses": "Dépenses mensuelles",
        "savings_rate": "Taux d’épargne",
        "six_month_liquidity_forecast": "Prévision de liquidité (6 mois)",
        "budget_limits_exceeded": "Limites de budget dépassées",
        "month_january": "Janvier", "month_february": "Février", "month_march": "Mars", "month_april": "Avril",
        "month_may": "Mai", "month_june": "Juin", "month_july": "Juillet", "month_august": "Août",
        "month_september": "Septembre", "month_october": "Octobre", "month_november": "Novembre", "month_december": "Décembre",
    },
    "es": {
        "morning": "Buenos días",
        "afternoon": "Buenas tardes",
        "evening": "Buenas noches",
        "overview": "Resumen",
        "transactions": "Transacciones",
        "budget": "Presupuesto",
        "analytics": "Análisis",
        "ai_advisor": "Asesor IA",
        "settings": "Configuración",
        "accounts": "Cuentas",
        "categories": "Categorías",
        "data": "Datos",
        "loan_calculator": "Calculadora de préstamos",
        "notifications": "Notificaciones",
        "admin_panel": "Panel de administración",
        "welcome_back": "Bienvenido de nuevo, {name}",
        "net_worth": "Patrimonio neto",
        "monthly_income": "Ingresos mensuales",
        "monthly_expenses": "Gastos mensuales",
        "savings_rate": "Tasa de ahorro",
        "six_month_liquidity_forecast": "Pronóstico de liquidez (6 meses)",
        "budget_limits_exceeded": "Límites de presupuesto superados",
        "month_january": "Enero", "month_february": "Febrero", "month_march": "Marzo", "month_april": "Abril",
        "month_may": "Mayo", "month_june": "Junio", "month_july": "Julio", "month_august": "Agosto",
        "month_september": "Septiembre", "month_october": "Octubre", "month_november": "Noviembre", "month_december": "Diciembre",
    },
}

def get_language() -> str:
    return (st.session_state.get("language", "en") or "en").lower()

def t(key: str, **kwargs) -> str:
    """
    Translate a key using current session language.
    - Fallback order: selected language -> English -> key
    - Supports placeholders: t("welcome_back", name="Tore")
    """
    lang = get_language()
    text = TRANSLATIONS.get(lang, {}).get(key)
    if text is None:
        text = TRANSLATIONS["en"].get(key, key)
    try:
        return text.format(**kwargs)
    except Exception:
        return text

def get_time_greeting_key(now: datetime.datetime | None = None) -> str:
    # Oslo time if available
    if now is None:
        try:
            from zoneinfo import ZoneInfo
            now = datetime.datetime.now(ZoneInfo("Europe/Oslo"))
        except Exception:
            now = datetime.datetime.now()

    if now.hour < 12:
        return "morning"
    if now.hour < 18:
        return "afternoon"
    return "evening"

def get_time_greeting(now: datetime.datetime | None = None) -> str:
    return t(get_time_greeting_key(now))

def month_name(month: int, short: bool = False) -> str:
    """
    month: 1..12
    short: True for Jan/Feb etc.
    """
    keys_long = [
        "month_january", "month_february", "month_march", "month_april", "month_may", "month_june",
        "month_july", "month_august", "month_september", "month_october", "month_november", "month_december",
    ]
    keys_short = [
        "month_jan", "month_feb", "month_mar", "month_apr", "month_may_short", "month_jun",
        "month_jul", "month_aug", "month_sep", "month_oct", "month_nov", "month_dec",
    ]
    idx = max(1, min(12, int(month))) - 1
    return t(keys_short[idx] if short else keys_long[idx])
