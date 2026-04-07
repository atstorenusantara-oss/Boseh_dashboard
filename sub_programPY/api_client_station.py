import sqlite3
import requests
import os
import time
import threading

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(base_dir, 'boseh.db')

def get_api_credentials():
    try:
        conn = sqlite3.connect(DATABASE, timeout=20)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT base_url, client_id, client_secret, token FROM api_credentials LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row['base_url'], (row['client_id'], row['client_secret']), row['token']
        return None, None, None
    except Exception as e:
        print(f"[API Sync] Database error: {e}")
        return None, None, None

def sync_once():
    """Perform a single synchronization with the API to update bike metadata."""
    # Added old_token to unpack match get_api_credentials change
    base_url, creds, old_token = get_api_credentials()
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
            
            conn = sqlite3.connect(DATABASE, timeout=20)
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

                # Update token if provided by API (Check top-level and data-level)
                token = res_json.get('token') or res_json.get('data', {}).get('token')
                if token:
                    conn.execute("UPDATE api_credentials SET token = ?", (token,))
                    print(f"[API Sync] Token updated successfully from API response.")
                else:
                    print(f"[API Sync] Warning: No token found in API response.")

                # Clear and re-populate slots from API state
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
                return True
            except Exception as ex:
                print(f"[API Sync] DB Update error: {ex}")
                return False
            finally:
                conn.close()
        else:
            print(f"[API Sync] API Error {response.status_code}: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"[API Sync] Network Error: {e}")
        return False

def refresh_token():
    """Refresh the API token using the refresh endpoint and update database."""
    base_url, creds, old_token = get_api_credentials()
    if not base_url or not old_token:
        print("[API Refresh] Missing base_url or old_token.")
        return

    url = f"{base_url}/api/station/refresh"
    headers = {'Authorization': f'Bearer {old_token}'}
    
    try:
        response = requests.post(url, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            # Get token from data.token based on image provided
            new_token = res_json.get('data', {}).get('token')
            if new_token:
                conn = sqlite3.connect(DATABASE, timeout=10)
                conn.execute("UPDATE api_credentials SET token = ?", (new_token,))
                conn.commit()
                conn.close()
                print(f"[API Refresh] Token refreshed successfully.")
            else:
                print(f"[API Refresh] Warning: No new token in refresh response.")
        else:
            print(f"[API Refresh] Failed! Status: {response.status_code}")
    except Exception as e:
        print(f"[API Refresh] Error: {e}")

def api_token_refresh_loop():
    """Loop to refresh token every 5 minutes (300 seconds)."""
    print("[API Refresh] Starting refresh loop (300s interval)...")
    while True:
        time.sleep(300)
        refresh_token()

def sync_station_data_from_api():
    """Run synchronization once at startup with up to 3 retries."""
    print("[API Sync] Starting startup sync (Retries: 3)...")
    
    max_retries = 3
    retry_delay = 5 # seconds
    
    for attempt in range(1, max_retries + 1):
        print(f"[API Sync] Sync attempt {attempt}/{max_retries}...")
        success = sync_once()
        
        if success:
            print(f"[API Sync] Startup sync successful on attempt {attempt}.")
            return True
        else:
            if attempt < max_retries:
                print(f"[API Sync] Sync attempt {attempt} failed. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"[API Sync] All {max_retries} sync attempts failed.")
                return False

if __name__ == "__main__":
    sync_once()
