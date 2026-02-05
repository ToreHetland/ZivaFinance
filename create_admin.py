import sqlite3
import uuid
from datetime import datetime
from core.db_operations import get_connection, init_db

def setup_test_environment():
    # 1. Initialize DB to ensure all new tables exist
    init_db()
    
    with get_connection() as conn:
        # 2. Create your Admin Account (replace 'your_password' with a real one)
        # Note: In a real app, we would hash this password for security.
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", "your_password", "admin")
            )
            print("✅ Admin user 'admin' created.")
        except sqlite3.IntegrityError:
            print("ℹ️ Admin user already exists.")

        # 3. Generate 10 License Codes for your testers
        print("\n--- YOUR TESTER LICENSE CODES ---")
        for _ in range(10):
            code = str(uuid.uuid4())[:8].upper()
            conn.execute(
                "INSERT INTO licenses (code, created_at) VALUES (?, ?)",
                (code, datetime.now().isoformat())
            )
            print(f"Code: {code}")
        
        conn.commit()
        print("\n✅ Setup complete. Copy these codes for your users.")

if __name__ == "__main__":
    setup_test_environment()