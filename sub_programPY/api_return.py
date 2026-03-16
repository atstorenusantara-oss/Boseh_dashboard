import sqlite3
import requests
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(base_dir, 'boseh.db')

def get_api_credentials():
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT base_url, token FROM api_credentials LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row['base_url'], row['token']
        return None, None
    except Exception as e:
        print(f"Database error: {e}")
        return None, None

def return_bike(bike_id, docking_id):
    base_url, token = get_api_credentials()
    
    if not base_url or not token:
        print("[API Return] Error: base_url atau token tidak ditemukan di database.")
        return False, "Kredensial tidak ditemukan"

    url = f"{base_url}/api/station/docking/bike/return"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    data = {
        'bike_id': str(bike_id),
        'docking_id': str(docking_id)
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            print(f"[API Return] Berhasil! Sepeda {bike_id} di dock {docking_id} | Response: {response.text}")
            return True, response.json()
        else:
            print(f"[API Return] Gagal! Status: {response.status_code} | Response: {response.text}")
            return False, response.text
            
    except Exception as e:
        print(f"[API Return] Request Error: {e}")
        return False, str(e)
