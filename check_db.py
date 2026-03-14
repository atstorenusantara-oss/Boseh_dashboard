import sqlite3
import os

DATABASE = 'boseh.db'

def check_db():
    if not os.path.exists(DATABASE):
        print(f"File {DATABASE} tidak ditemukan!")
        return
        
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    
    print("--- Isi Tabel Settings ---")
    cursor = conn.execute("SELECT * FROM settings WHERE key IN ('station_name', 'station_address', 'total_slots')")
    for row in cursor.fetchall():
        print(f"{row['key']}: {row['value']}")
        
    print("\n--- Isi Tabel API Credentials (Token) ---")
    cursor = conn.execute("SELECT client_id, token FROM api_credentials LIMIT 1")
    row = cursor.fetchone()
    if row:
        token_val = row['token'][:20] + "..." if row['token'] else "None"
        print(f"Client ID: {row['client_id']}")
        print(f"Token: {token_val}")
        
    conn.close()

if __name__ == "__main__":
    check_db()
