import sqlite3

paths = [
    r"D:\ziva\finance.db",
    r"D:\ziva\finance_app.db",
    r"D:\ziva\data\finance.db",
]

def count(cur, table):
    try:
        return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return None

for p in paths:
    con = sqlite3.connect(p)
    cur = con.cursor()
    print(
        p,
        "accounts =", count(cur, "accounts"),
        "transactions =", count(cur, "transactions"),
    )
    con.close()
