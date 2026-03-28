import sqlite3
import requests
import os
import time
import threading

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(base_dir, 'boseh.db')

def get_api_credentials():
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT base_url, client_id, client_secret FROM api_credentials LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row['base_url'], (row['client_id'], row['client_secret'])
        return None, None
    except Exception as e:
        print(f"[API Sync] Database error: {e}")
        return None, None

def sync_once():
    """Perform a single synchronization with the API to update bike metadata."""
    base_url, creds = get_api_credentials()
    if not base_url or not creds:
        print("[API Sync] API Credentials not found.")
        return
    
    client_id, client_secret = creds
    url = f"{base_url}/api/station/login"
    payload = {
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            station_data = res_json.get('data', {}).get('station', {})
            
            conn = sqlite3.connect(DATABASE)
            conn.row_factory = sqlite3.Row
            
            try:
                # Update settings (Station Name/Address if they changed)
                settings_updates = {}
                if station_data.get('name'):
                    settings_updates['station_name'] = station_data['name']
                if station_data.get('address'):
                    settings_updates['station_address'] = station_data['address']
                
                for key, val in settings_updates.items():
                    conn.execute("UPDATE settings SET value = ? WHERE key = ?", (val, key))

                # Clear and re-populate slots from API state
                # Note: We clear bike_name so it can be updated from API
                conn.execute("UPDATE slots SET has_bike = 0, rfid_tag = NULL, bike_status = NULL, bike_name = NULL")
                
                bikes = station_data.get('bikes', [])
                for bike in bikes:
                    b_id = bike.get('bike_id')
                    b_status = bike.get('status')
                    b_name = bike.get('name')
                    d_id = bike.get('docking_id')
                    
                    if d_id is not None:
                        conn.execute('''
                            UPDATE slots 
                            SET rfid_tag = ?, bike_status = ?, bike_name = ?, has_bike = 1 
                            WHERE slot_number = ?
                        ''', (b_id, b_status, b_name, d_id))
                
                conn.commit()
                print(f"[API Sync] Sync successful. Updated {len(bikes)} bikes.")
            except Exception as ex:
                print(f"[API Sync] DB Update error: {ex}")
            finally:
                conn.close()
        else:
            print(f"[API Sync] API Error {response.status_code}: {response.text[:100]}")
    except Exception as e:
        print(f"[API Sync] Network Error: {e}")

def sync_station_data_from_api():
    """Background loop to periodically sync with API."""
    print("[API Sync] Starting periodic background sync (5 mins)...")
    while True:
        sync_once()
        time.sleep(300)

if __name__ == "__main__":
    sync_once()
