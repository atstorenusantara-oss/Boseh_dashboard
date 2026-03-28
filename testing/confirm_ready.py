import sqlite3
import requests
import os
import json

# Menggunakan boseh.db di direktori utama (parent directory)
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

def test_confirm_ready():
    base_url, token = get_api_credentials()
    
    if not base_url or not token:
        print("Error: base_url atau token tidak ditemukan di database.")
        print("Pastikan tabel 'api_credentials' sudah terisi dengan benar.")
        return

    # Endpoint sesuai permintaan
    url = f"{base_url}/api/station/docking/confirm/ready"
    
    # Authorization header menggunakan Bearer Token (diambil dari database)
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    # Body dalam bentuk Multipart Form (sesuai gambar)
    # bike_id diambil dari gambar: 6125734
    data = {
        'bike_id': '6125738'
    }

    print("--- [TESTING] API Confirm Ready ---")
    print(f"Mengirim POST request ke : {url}")
    print(f"Header Authorization     : Bearer {token[:10]}... (disamarkan)")
    print(f"Body (form-data)         : {data}")
    
    try:
        # Mengirim POST request dengan data (form-data)
        response = requests.post(url, headers=headers, data=data)
        
        print(f"\n>> HTTP Status Code: {response.status_code}")
        try:
            # Mencoba menampilkan response sebagai JSON
            json_response = response.json()
            print(">> Response JSON:")
            print(json.dumps(json_response, indent=4))
        except ValueError:
            # Jika bukan JSON, tampilkan teks biasa
            print(f">> Response Text:\n{response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n[!] Terjadi kesalahan saat melakukan request: {e}")

if __name__ == "__main__":
    test_confirm_ready()
