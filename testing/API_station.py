import requests
import json

import os
import sqlite3

def get_api_credentials():
    # Mengambil base path dari boseh.db di parent directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'boseh.db')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Ambil credential dari tabel (id terakhir jika ada lebih dari 1, atau yg pertama)
    cursor = conn.execute('SELECT base_url, client_id, client_secret FROM api_credentials LIMIT 1')
    data = cursor.fetchone()
    conn.close()
    
    if data:
        return data['base_url'], data['client_id'], data['client_secret']
    return None, None, None

def test_station_login():
    base_url, client_id, client_secret = get_api_credentials()
    
    if not base_url:
        print("Error: Kredensial API tidak ditemukan di database.")
        return

    # Menyusun endpoint dari base_url
    url = f"{base_url}/api/station/login"
    
    # Data dari database (menggunakan form-data)
    payload = {
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    print(f"Mengirim permintaan POST ke: {url}")
    print(f"Payload: {{'client_id': '{client_id}', 'client_secret': '***'}}\n")
    
    try:
        # Mengirim POST request dengan form-data
        response = requests.post(url, data=payload)
        
        # Menampilkan status code
        print(f"Status Code: {response.status_code}")
        
        # Mencoba menampilkan response sebagai JSON jika memungkinkan
        try:
            json_response = response.json()
            print("Response JSON:")
            print(json.dumps(json_response, indent=4))
        except ValueError:
            # Jika bukan JSON, tampilkan teks biasa
            print("Response Text:")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"Terjadi kesalahan saat melakukan request: {e}")

if __name__ == "__main__":
    test_station_login()
