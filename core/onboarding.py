# core/onboarding.py
from __future__ import annotations

from datetime import date
import streamlit as st

from core.db_operations import (
    load_data_db,
    add_record_db,
    execute_query_db,
    ensure_category_exists,
)


# -----------------------------
# Language + currency inference
# -----------------------------
def infer_currency_from_language(lang: str) -> str:
    lang = (lang or "").lower().strip()

    # 🇳🇴 Hard default
    if not lang or lang == "no":
        return "NOK"

    if lang == "sv":
        return "SEK"
    if lang == "da":
        return "DKK"
    if lang in ("de", "fr", "nl", "it", "es"):
        return "EUR"
    if lang == "uk":
        return "UAH"

    return "NOK"




def default_account_name(lang: str) -> str:
    lang = (lang or "en").lower().strip()

    return {
        "no": "Brukskonto",
        "sv": "Lönekonto",
        "da": "Lønkonto",
        "de": "Girokonto",
        "es": "Cuenta corriente",
        "fr": "Compte courant",
        "nl": "Betaalrekening",
        "it": "Conto corrente",
        "uk": "Поточний рахунок",
        "en": "Checking account",
    }.get(lang, "Brukskonto")



def category_seed(lang: str) -> list[tuple]:
    lang = (lang or "en").lower().strip()

    C = {
        "no": [
            ("Dagligvarer", "expense"),
            ("Restaurant", "expense"),
            ("Transport", "expense"),
            ("Bolig", "expense"),
            ("Abonnement", "expense"),
            ("Helse", "expense"),
            ("Shopping", "expense"),
            ("Reise", "expense"),
            ("Lønn", "income"),
            ("Refusjon", "income"),
            ("Overføring", "transfer"),
            ("Inngående saldo", "income"),
        ],
        "sv": [
            ("Matvaror", "expense"),
            ("Restaurang", "expense"),
            ("Transport", "expense"),
            ("Boende", "expense"),
            ("Abonnemang", "expense"),
            ("Hälsa", "expense"),
            ("Shopping", "expense"),
            ("Resor", "expense"),
            ("Lön", "income"),
            ("Återbetalning", "income"),
            ("Överföring", "transfer"),
            ("Ingående saldo", "income"),
        ],
        "da": [
            ("Dagligvarer", "expense"),
            ("Restaurant", "expense"),
            ("Transport", "expense"),
            ("Bolig", "expense"),
            ("Abonnementer", "expense"),
            ("Sundhed", "expense"),
            ("Shopping", "expense"),
            ("Rejser", "expense"),
            ("Løn", "income"),
            ("Refusion", "income"),
            ("Overførsel", "transfer"),
            ("Startsaldo", "income"),
        ],
        "de": [
            ("Lebensmittel", "expense"),
            ("Restaurant", "expense"),
            ("Transport", "expense"),
            ("Wohnen", "expense"),
            ("Abonnements", "expense"),
            ("Gesundheit", "expense"),
            ("Einkäufe", "expense"),
            ("Reisen", "expense"),
            ("Gehalt", "income"),
            ("Rückerstattung", "income"),
            ("Überweisung", "transfer"),
            ("Anfangssaldo", "income"),
        ],
        "es": [
            ("Supermercado", "expense"),
            ("Restaurantes", "expense"),
            ("Transporte", "expense"),
            ("Vivienda", "expense"),
            ("Suscripciones", "expense"),
            ("Salud", "expense"),
            ("Compras", "expense"),
            ("Viajes", "expense"),
            ("Salario", "income"),
            ("Reembolso", "income"),
            ("Transferencia", "transfer"),
            ("Saldo inicial", "income"),
        ],
        "fr": [
            ("Courses", "expense"),
            ("Restaurants", "expense"),
            ("Transport", "expense"),
            ("Logement", "expense"),
            ("Abonnements", "expense"),
            ("Santé", "expense"),
            ("Achats", "expense"),
            ("Voyages", "expense"),
            ("Salaire", "income"),
            ("Remboursement", "income"),
            ("Virement", "transfer"),
            ("Solde initial", "income"),
        ],
        "nl": [
            ("Boodschappen", "expense"),
            ("Restaurants", "expense"),
            ("Vervoer", "expense"),
            ("Wonen", "expense"),
            ("Abonnementen", "expense"),
            ("Gezondheid", "expense"),
            ("Winkelen", "expense"),
            ("Reizen", "expense"),
            ("Salaris", "income"),
            ("Terugbetaling", "income"),
            ("Overboeking", "transfer"),
            ("Beginsaldo", "income"),
        ],
        "it": [
            ("Spesa", "expense"),
            ("Ristoranti", "expense"),
            ("Trasporti", "expense"),
            ("Casa", "expense"),
            ("Abbonamenti", "expense"),
            ("Salute", "expense"),
            ("Shopping", "expense"),
            ("Viaggi", "expense"),
            ("Stipendio", "income"),
            ("Rimborso", "income"),
            ("Trasferimento", "transfer"),
            ("Saldo iniziale", "income"),
        ],
        "uk": [
            ("Продукти", "expense"),
            ("Ресторани", "expense"),
            ("Транспорт", "expense"),
            ("Житло", "expense"),
            ("Підписки", "expense"),
            ("Здоров’я", "expense"),
            ("Покупки", "expense"),
            ("Подорожі", "expense"),
            ("Зарплата", "income"),
            ("Відшкодування", "income"),
            ("Переказ", "transfer"),
            ("Початковий баланс", "income"),
        ],
        "en": [
            ("Groceries", "expense"),
            ("Dining", "expense"),
            ("Transport", "expense"),
            ("Housing", "expense"),
            ("Subscriptions", "expense"),
            ("Health", "expense"),
            ("Shopping", "expense"),
            ("Travel", "expense"),
            ("Salary", "income"),
            ("Refund", "income"),
            ("Transfer", "transfer"),
            ("Opening Balance", "income"),
        ],
    }

    return C.get(lang, C["en"])


# -----------------------------
# Bootstrap: accounts + cats
# -----------------------------
def ensure_user_bootstrap(user_id: str, lang: str) -> None:
    """
    Ensures the user has:
    - seeded categories in the user's language (idempotent)
    - at least 1 default Checking account (idempotent)
    """
    if not user_id:
        return

    # ------------------------------------------------------------
    # 1) Ensure categories (idempotent per user)
    # ------------------------------------------------------------
    seeds = category_seed(lang)

    for item in seeds:
        # Accept either (name, type) OR (name, type, parent)
        if len(item) == 2:
            name, ctype = item
            parent = None
        else:
            name, ctype, parent = item[0], item[1], item[2]

        # Create parent first if provided
        if parent:
            ensure_category_exists(parent, "expense", user_id=user_id)

        ensure_category_exists(name, ctype, user_id=user_id, parent=parent)

    # ------------------------------------------------------------
    # 2) Ensure at least one default Checking account (idempotent)
    #    Fix: prevent duplicate auto-created accounts
    # ------------------------------------------------------------
    currency = infer_currency_from_language(lang)
    acc_name = default_account_name(lang)

    # Try to find an existing default checking account for this user.
    # Fallback: any checking account. Fallback: any account.
    try:
            with get_connection() as conn:
                # BROADEN THE CHECK: If the user has ANY account, do not create a new one.
                row = conn.execute(
                    "SELECT id FROM accounts WHERE user_id = :uid LIMIT 1",
                    {"uid": user_id},
                ).fetchone()
                
                if row:
                    return # User already has data; stop the bootstrap.

            # B) has any checking account -> make it default if none is default
            row = conn.execute(
                """
                SELECT id
                  FROM accounts
                 WHERE user_id = :uid
                   AND lower(account_type) = 'checking'
                 ORDER BY id ASC
                 LIMIT 1
                """,
                {"uid": user_id},
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE accounts
                       SET is_default = true
                     WHERE id = :id
                    """,
                    {"id": row[0]},
                )
                return

            # C) has any account at all -> make first one default
            row = conn.execute(
                """
                SELECT id
                  FROM accounts
                 WHERE user_id = :uid
                 ORDER BY id ASC
                 LIMIT 1
                """,
                {"uid": user_id},
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE accounts SET is_default = true WHERE id = :id",
                    {"id": row[0]},
                )
                return

    except Exception:
        # If DB check fails for any reason, fall back to the old safe path below
        pass

    # D) No accounts exist -> create exactly ONE onboarding account
    add_record_db(
        "accounts",
        {
            "name": acc_name,
            "account_type": "Checking",
            "balance": 0,
            "currency": currency,
            "is_default": True,
            "description": "Auto-created during onboarding",
            "created_date": None,
            "last_updated": None,
            "user_id": user_id,
        },
    )


def should_show_opening_balance(user_id: str) -> bool:
    """
    Opening balance dialog should appear if:
    - user has exactly 1 account OR any accounts
    - and has no transactions yet
    - and we haven't shown it this session
    """
    if st.session_state.get("opening_balance_done"):
        return False
    tx = load_data_db("transactions", user_id=user_id)
    return (tx is None) or tx.empty


@st.dialog("Welcome to Ziva — quick setup", width="large")
def opening_balance_dialog(user_id: str, lang: str) -> None:
    """
    One-time dialog to optionally create opening balance transaction.
    """
    acc_df = load_data_db("accounts", user_id=user_id)
    if acc_df is None or acc_df.empty:
        st.info("No accounts yet.")
        st.session_state["opening_balance_done"] = True
        return

    accounts = sorted(acc_df["name"].dropna().astype(str).unique().tolist())
    if not accounts:
        st.session_state["opening_balance_done"] = True
        return

    st.write("Let’s set an opening balance (optional).")
    acc = st.selectbox("Account", accounts, index=0)
    amount = st.number_input("Opening balance amount", min_value=0.0, step=100.0, format="%.2f")
    d = st.date_input("Date", value=date.today())

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Skip", use_container_width=True):
            st.session_state["opening_balance_done"] = True
            st.rerun()

    with c2:
        if st.button("Save opening balance", type="primary", use_container_width=True):
            if amount <= 0:
                st.warning("Enter an amount greater than 0, or skip.")
                return

            # Category name based on language seed
            opening_cat = "Inngående saldo" if (lang or "").lower() in ("no", "nb", "nn") else "Opening Balance"

            add_record_db("transactions", {
                "date": d.isoformat(),
                "type": "income",
                "account": acc,
                "category": opening_cat,
                "payee": "Initial Setup",
                "amount": float(amount),
                "description": "Opening balance",
                "user_id": user_id,
            })

            st.session_state["opening_balance_done"] = True
            st.success("Opening balance saved ✅")
            st.rerun()
