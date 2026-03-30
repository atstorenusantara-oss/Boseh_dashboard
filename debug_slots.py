import sqlite3
DATABASE = 'boseh.db'

def check_slots():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT slot_number, has_bike, bike_status, bike_name FROM slots ORDER BY slot_number")
    rows = cursor.fetchall()
    
    print(f"{'Slot':<5} | {'Has Bike':<8} | {'Status':<15} | {'Name'}")
    print("-" * 50)
    for row in rows:
        print(f"{row['slot_number']:<5} | {row['has_bike']:<8} | {row['bike_status'] or 'None':<15} | {row['bike_name'] or 'None'}")
    
    conn.close()

if __name__ == "__main__":
    check_slots()
