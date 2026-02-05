# core/default_translations.py
from __future__ import annotations

import datetime
from typing import Dict, List, Tuple

from core.db_operations import (
    load_data_db,
    execute_query_db,
    get_connection,
    add_record_db,
)

# --------------------------
# DEFAULT CATEGORY TRANSLATIONS (canonical keys)
# --------------------------
_CATEGORY_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "groceries": "Groceries",
        "dining": "Dining",
        "transport": "Transport",
        "housing": "Housing",
        "subscriptions": "Subscriptions",
        "health": "Health",
        "shopping": "Shopping",
        "travel": "Travel",
        "salary": "Salary",
        "refund": "Refund",
        "transfer": "Transfer",
        "opening_balance": "Opening Balance",
    },
    "no": {
        "groceries": "Dagligvarer",
        "dining": "Restaurant",
        "transport": "Transport",
        "housing": "Bolig",
        "subscriptions": "Abonnement",
        "health": "Helse",
        "shopping": "Shopping",
        "travel": "Reise",
        "salary": "Lønn",
        "refund": "Refusjon",
        "transfer": "Overføring",
        "opening_balance": "Inngående saldo",
    },
    "sv": {
        "groceries": "Matvaror",
        "dining": "Restaurang",
        "transport": "Transport",
        "housing": "Boende",
        "subscriptions": "Abonnemang",
        "health": "Hälsa",
        "shopping": "Shopping",
        "travel": "Resor",
        "salary": "Lön",
        "refund": "Återbetalning",
        "transfer": "Överföring",
        "opening_balance": "Ingående saldo",
    },
    "da": {
        "groceries": "Dagligvarer",
        "dining": "Restaurant",
        "transport": "Transport",
        "housing": "Bolig",
        "subscriptions": "Abonnementer",
        "health": "Sundhed",
        "shopping": "Shopping",
        "travel": "Rejser",
        "salary": "Løn",
        "refund": "Refusion",
        "transfer": "Overførsel",
        "opening_balance": "Startsaldo",
    },
    "de": {
        "groceries": "Lebensmittel",
        "dining": "Restaurant",
        "transport": "Transport",
        "housing": "Wohnen",
        "subscriptions": "Abonnements",
        "health": "Gesundheit",
        "shopping": "Einkäufe",
        "travel": "Reisen",
        "salary": "Gehalt",
        "refund": "Rückerstattung",
        "transfer": "Überweisung",
        "opening_balance": "Anfangssaldo",
    },
    "es": {
        "groceries": "Supermercado",
        "dining": "Restaurantes",
        "transport": "Transporte",
        "housing": "Vivienda",
        "subscriptions": "Suscripciones",
        "health": "Salud",
        "shopping": "Compras",
        "travel": "Viajes",
        "salary": "Salario",
        "refund": "Reembolso",
        "transfer": "Transferencia",
        "opening_balance": "Saldo inicial",
    },
    "fr": {
        "groceries": "Courses",
        "dining": "Restaurants",
        "transport": "Transport",
        "housing": "Logement",
        "subscriptions": "Abonnements",
        "health": "Santé",
        "shopping": "Achats",
        "travel": "Voyages",
        "salary": "Salaire",
        "refund": "Remboursement",
        "transfer": "Virement",
        "opening_balance": "Solde initial",
    },
    "nl": {
        "groceries": "Boodschappen",
        "dining": "Restaurants",
        "transport": "Vervoer",
        "housing": "Wonen",
        "subscriptions": "Abonnementen",
        "health": "Gezondheid",
        "shopping": "Winkelen",
        "travel": "Reizen",
        "salary": "Salaris",
        "refund": "Terugbetaling",
        "transfer": "Overboeking",
        "opening_balance": "Beginsaldo",
    },
    "it": {
        "groceries": "Spesa",
        "dining": "Ristoranti",
        "transport": "Trasporti",
        "housing": "Casa",
        "subscriptions": "Abbonamenti",
        "health": "Salute",
        "shopping": "Shopping",
        "travel": "Viaggi",
        "salary": "Stipendio",
        "refund": "Rimborso",
        "transfer": "Trasferimento",
        "opening_balance": "Saldo iniziale",
    },
    "uk": {
        "groceries": "Продукти",
        "dining": "Ресторани",
        "transport": "Транспорт",
        "housing": "Житло",
        "subscriptions": "Підписки",
        "health": "Здоров’я",
        "shopping": "Покупки",
        "travel": "Подорожі",
        "salary": "Зарплата",
        "refund": "Відшкодування",
        "transfer": "Переказ",
        "opening_balance": "Початковий баланс",
    },
}

# Used to build "reverse lookup" from any localized default name -> canonical key
_REVERSE_DEFAULT_NAME_TO_KEY: Dict[str, str] = {}
for lang, mapping in _CATEGORY_TRANSLATIONS.items():
    for key, label in mapping.items():
        _REVERSE_DEFAULT_NAME_TO_KEY[label.strip().lower()] = key

# --------------------------
# DEFAULT ACCOUNT NAME TRANSLATIONS
# --------------------------
_DEFAULT_ACCOUNT_NAME: Dict[str, str] = {
    "en": "Checking",
    "no": "Brukskonto",
    "sv": "Betalkonto",
    "da": "Lønkonto",
    "de": "Girokonto",
    "es": "Cuenta corriente",
    "fr": "Compte courant",
    "nl": "Betaalrekening",
    "it": "Conto corrente",
    "uk": "Поточний рахунок",
}
_DEFAULT_ACCOUNT_REVERSE: Dict[str, bool] = {v.strip().lower(): True for v in _DEFAULT_ACCOUNT_NAME.values()}

def translate_defaults_for_user(user_id: str, target_lang: str) -> Tuple[int, int]:
    """
    Translate/rename default categories + default account to target language.
    Returns: (categories_changed_count, accounts_changed_count)
    """
    target_lang = (target_lang or "no").strip().lower()
    if target_lang not in _CATEGORY_TRANSLATIONS:
        target_lang = "en"

    # ---------- CATEGORIES ----------
    categories_changed = 0
    df_cat = load_data_db("categories", user_id=user_id)
    if df_cat is None or df_cat.empty:
        df_cat = None

    # Make sure all target defaults exist (insert if missing)
    for key, target_name in _CATEGORY_TRANSLATIONS[target_lang].items():
        if df_cat is not None:
            exists = (df_cat["name"].astype(str).str.strip().str.lower() == target_name.strip().lower()).any()
        else:
            exists = False

        if not exists:
            # Guess type based on canonical key
            ctype = "expense"
            if key in ("salary", "refund", "opening_balance"):
                ctype = "income"
            if key == "transfer":
                ctype = "transfer"

            add_record_db("categories", {
                "name": target_name,
                "type": ctype,
                "parent_category": None,
                "user_id": user_id,
            })

    # Reload after ensuring
    df_cat = load_data_db("categories", user_id=user_id)
    existing_names = set(df_cat["name"].dropna().astype(str).str.strip().tolist())

    # Rename defaults that exist under a different language
    for old_name in list(existing_names):
        old_norm = old_name.strip().lower()
        key = _REVERSE_DEFAULT_NAME_TO_KEY.get(old_norm)
        if not key:
            continue  # not a known default -> do not touch

        target_name = _CATEGORY_TRANSLATIONS[target_lang].get(key)
        if not target_name or target_name.strip().lower() == old_norm:
            continue  # already correct

        # If target exists, merge references -> then delete old category row
        target_exists = target_name in existing_names

        # Update references everywhere (safe even if tables empty)
        # NOTE: your schema stores category by NAME in several tables.
        ref_updates = [
            ("transactions", "category"),
            ("budgets", "category"),
            ("recurring", "category"),
            ("budget_rules", "category"),  # may or may not exist
        ]

        for table, col in ref_updates:
            try:
                execute_query_db(
                    f"UPDATE {table} SET {col} = :new WHERE user_id = :uid AND {col} = :old",
                    {"new": target_name, "uid": user_id, "old": old_name},
                )
            except Exception:
                # ignore missing tables like budget_rules
                pass

        # Ensure target category exists (should, but safe)
        if not target_exists:
            # Create it with same type as old row
            try:
                old_row = df_cat[df_cat["name"].astype(str) == old_name].iloc[0]
                ctype = str(old_row.get("type", "expense") or "expense")
            except Exception:
                ctype = "expense"
            add_record_db("categories", {"name": target_name, "type": ctype, "parent_category": None, "user_id": user_id})

        # Delete old category entry to avoid duplicates
        try:
            execute_query_db(
                "DELETE FROM categories WHERE user_id = :uid AND name = :old",
                {"uid": user_id, "old": old_name},
            )
        except Exception:
            pass

        categories_changed += 1

    # ---------- DEFAULT ACCOUNT ----------
    accounts_changed = 0
    df_acc = load_data_db("accounts", user_id=user_id)
    if df_acc is not None and not df_acc.empty:
        # pick default account row
        df_def = df_acc[df_acc.get("is_default", False) == True]  # noqa: E712
        if df_def.empty:
            df_def = df_acc.head(1)

        if not df_def.empty:
            current_name = str(df_def.iloc[0].get("name", "") or "").strip()
            current_norm = current_name.lower()
            target_acc_name = _DEFAULT_ACCOUNT_NAME.get(target_lang, _DEFAULT_ACCOUNT_NAME["en"]).strip()

            # only auto-rename if it looks like a known default name
            if current_name and (_DEFAULT_ACCOUNT_REVERSE.get(current_norm) or current_norm in _DEFAULT_ACCOUNT_REVERSE):
                if current_name != target_acc_name:
                    # If target name already exists as another account, do nothing (avoid collision)
                    if (df_acc["name"].astype(str).str.strip().str.lower() == target_acc_name.lower()).any():
                        pass
                    else:
                        # rename in accounts + update references in transactions/recurring
                        try:
                            with get_connection() as conn:
                                conn.execute(
                                    """
                                    UPDATE accounts
                                       SET name = :new
                                     WHERE user_id = :uid
                                       AND name = :old
                                    """,
                                    {"new": target_acc_name, "uid": user_id, "old": current_name},
                                )

                                conn.execute(
                                    """
                                    UPDATE transactions
                                       SET account = :new
                                     WHERE user_id = :uid
                                       AND account = :old
                                    """,
                                    {"new": target_acc_name, "uid": user_id, "old": current_name},
                                )

                                conn.execute(
                                    """
                                    UPDATE recurring
                                       SET account = :new
                                     WHERE user_id = :uid
                                       AND account = :old
                                    """,
                                    {"new": target_acc_name, "uid": user_id, "old": current_name},
                                )

                                conn.conn.commit()
                            accounts_changed = 1
                        except Exception:
                            pass

    return categories_changed, accounts_changed
