import sqlite3
import requests
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(base_dir, 'boseh.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def sync_station_data_from_api():
    """Fetches station data and token from API and updates local database."""
    try:
        conn = get_db_connection()
        cursor = conn.execute('SELECT base_url, client_id, client_secret FROM api_credentials LIMIT 1')
        creds = cursor.fetchone()
        
        if not creds:
            print("[API Sync] API Credentials not found in database.")
            conn.close()
            return

        base_url = creds['base_url']
        client_id = creds['client_id']
        client_secret = creds['client_secret']

        if not base_url:
            conn.close()
            return

        url = f"{base_url}/api/station/login"
        payload = {
            'client_id': client_id,
            'client_secret': client_secret
        }

        print(f"[API Sync] Attempting sync with {url}...")
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # 1. Update Token
            token = data.get('token') or data.get('access_token')
            if not token and 'data' in data and isinstance(data['data'], dict):
                token = data['data'].get('token')

            if token:
                conn.execute('UPDATE api_credentials SET token = ? WHERE client_id = ?', (token, client_id))
            
            # 2. Extract Metadata (mapping as requested)
            # adress -> station_address, name -> station_name, num_docking -> total_slots
            settings_updates = {}
            
            # Check station data inside data['data']['station']
            station_data = {}
            if 'data' in data and isinstance(data['data'], dict) and 'station' in data['data']:
                station_data = data['data']['station']
            
            # Extract Address
            address = data.get('address') or station_data.get('address')
            if address:
                settings_updates['station_address'] = address
            
            # Extract Name
            name = data.get('name') or station_data.get('name')
            if name:
                settings_updates['station_name'] = name
            
            # Extract Num Docking
            num_docking = data.get('num_docking')
            if num_docking is None:
                num_docking = station_data.get('num_docking')

            if num_docking is not None:
                settings_updates['total_slots'] = str(num_docking)
            
            # Update settings table
            for key, value in settings_updates.items():
                conn.execute('UPDATE settings SET value = ? WHERE key = ?', (value, key))

            # 3. Sync Slots Table (if num_docking exists)
            if num_docking is not None:
                new_total = int(num_docking)
                current_slots = conn.execute('SELECT COUNT(*) FROM slots').fetchone()[0]
                
                if new_total > current_slots:
                    # Add missing slots
                    for i in range(current_slots + 1, new_total + 1):
                        conn.execute('INSERT OR IGNORE INTO slots (slot_number, has_bike) VALUES (?, ?)', (i, 0))
                elif new_total < current_slots:
                    # Remove extra slots
                    conn.execute('DELETE FROM slots WHERE slot_number > ?', (new_total,))
            
            # 4. Sync bikes to slots
            try:
                # We optionally clear existing first to reflect exact state from server
                conn.execute("UPDATE slots SET has_bike = 0, rfid_tag = NULL, bike_status = NULL")
                
                bikes = data.get('bikes') or station_data.get('bikes') or []
                if bikes:
                    for bike in bikes:
                        b_id = bike.get('bike_id')
                        b_status = bike.get('status')
                        d_id = bike.get('docking_id')
                        
                        if d_id is not None:
                            conn.execute('''
                                UPDATE slots 
                                SET rfid_tag = ?, bike_status = ?, has_bike = 1 
                                WHERE slot_number = ?
                            ''', (b_id, b_status, d_id))
            except Exception as ex:
                print(f"[API Sync] Warning while syncing bikes: {ex}")
            
            conn.commit()
            print("[API Sync] Station data successfully synchronized and saved.")
        else:
            print(f"[API Sync] Failed to sync. Status Code: {response.status_code}")
            
        conn.close()
    except Exception as e:
        print(f"[API Sync] Error during sync: {e}")

if __name__ == "__main__":
    # Allows running this file directly for debugging
    sync_station_data_from_api()
