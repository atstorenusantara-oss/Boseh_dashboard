import sqlite3
import requests
import os

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

def test_confirm_open():
    base_url, token = get_api_credentials()
    
    if not base_url or not token:
        print("Error: base_url atau token tidak ditemukan di database.")
        return

    # Sesuai dengan endpoint yang diberikan di gambar
    url = f"{base_url}/api/station/docking/confirm/open"
    
    # Authorization header menggunakan Bearer Token (diambil dari database)
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    # Body dalam bentuk Multipart Form (sesuai gambar)
    data = {
        'bike_id': '00000006'
    }

    print("--- [TESTING] API Confirm Open ---")
    print(f"Mengirim POST request ke : {url}")
    print(f"Header Authorization     : Bearer {token[:10]}... (disamarkan)")
    print(f"Body (Multipart)         : {data}")
    
    try:
        response = requests.post(url, headers=headers, data=data)
        
        print(f"\n>> HTTP Status Code: {response.status_code}")
        try:
            print(f">> Response JSON: {response.json()}")
        except ValueError:
            print(f">> Response Text:\n{response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n[!] Terjadi kesalahan saat melakukan request: {e}")

if __name__ == "__main__":
    test_confirm_open()
