# reset_password.py
from core.db_operations import execute_query_db, hash_password

# 1. Define your user details
USERNAME = "Tore Hetland"
EMAIL = "tore.hetland@gmail.com"
NEW_PASSWORD = "Holding1"  # <--- Temporary password

print(f"🔄 Resetting user: {USERNAME}...")

# 2. Generate a valid hash using the app's own security logic
hashed_pw = hash_password(NEW_PASSWORD)

# 3. Delete the broken user record (to prevent duplicates/errors)
execute_query_db("DELETE FROM users WHERE username = :u", {"u": USERNAME})

# 4. Re-create the admin user
query = """
INSERT INTO users (username, full_name, email, password_hash, role, language, created_at)
VALUES (:u, :u, :e, :h, 'admin', 'en', CURRENT_TIMESTAMP)
"""

execute_query_db(query, {
    "u": USERNAME,
    "e": EMAIL,
    "h": hashed_pw
})

print(f"✅ Success! You can now login with:")
print(f"   Username: {USERNAME}")
print(f"   Password: {NEW_PASSWORD}")