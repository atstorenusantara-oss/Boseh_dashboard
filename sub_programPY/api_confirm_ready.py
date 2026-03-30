import sqlite3
import requests
import os
import json

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(base_dir, 'boseh.db')

def get_api_credentials():
    try:
        conn = sqlite3.connect(DATABASE, timeout=20)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT base_url, token FROM api_credentials LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row['base_url'], row['token']
        return None, None
    except Exception as e:
        print(f"[API Confirm Ready] Database error: {e}")
        return None, None

def confirm_ready(bike_id):
    """
    Trigger API Confirm Ready to external server.
    """
    base_url, token = get_api_credentials()
    
    if not base_url or not token:
        print("[API Confirm Ready] Error: base_url atau token tidak ditemukan.")
        return

    url = f"{base_url}/api/station/docking/confirm/ready"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    data = {
        'bike_id': bike_id
    }

    print(f"[API Confirm Ready] Sending request for Bike ID: {bike_id}")
    
    try:
        response = requests.post(url, headers=headers, data=data)
        print(f"[API Confirm Ready] Status: {response.status_code}")
        try:
            print(f"[API Confirm Ready] Response: {response.json()}")
        except:
            print(f"[API Confirm Ready] Response Text: {response.text[:100]}")
            
    except Exception as e:
        print(f"[API Confirm Ready] Error: {e}")
