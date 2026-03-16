import sqlite3
import paho.mqtt.client as mqtt
import time
import json
import uuid
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(base_dir, 'boseh.db')

def get_mqtt_credentials():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT base_url, client_id, client_secret, token FROM api_credentials LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row['base_url'], row['client_id'], row['client_secret'], row['token']
    return None, None, None, None

def start_mqtt_client(rental_callback):
    """
    Start the MQTT client in a blocking way. Usually run in a thread.
    rental_callback(data: dict) will be called when a dock open message is received.
    """
    base_url, client_id, client_secret, token = get_mqtt_credentials()
    
    if not client_id or not token:
        print("[MQTT Remote] Credentials not found.")
        return
        
    host = base_url.replace("https://", "").replace("http://", "").split("/")[0]
    port = 1883
    mqtt_client_id = str(uuid.uuid4())
    username = token
    password = client_secret
    
    print(f"[MQTT Remote] Connecting to {host}:{port} as {mqtt_client_id}...")

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            print(f"[MQTT Remote] Connected successfully to API Server MQTT")
            topic = f"station/{client_id}/dock/open"
            print(f"[MQTT Remote] Subscribing to: {topic}")
            client.subscribe(topic)
        else:
            print(f"[MQTT Remote] Failed to connect, reason_code: {reason_code}")

    def on_message(client, userdata, msg):
        try:
            payload = msg.payload.decode()
            print(f"[MQTT Remote] Received rent request: {payload[:50]}...")
            data = json.loads(payload)
            if rental_callback:
                rental_callback(data)
        except Exception as e:
            print(f"[MQTT Remote] Error parsing message: {e}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=mqtt_client_id)
    client.username_pw_set(username=username, password=password)
    client.on_connect = on_connect
    client.on_message = on_message
    
    while True:
        try:
            client.connect(host, port, 60)
            client.loop_forever()
        except Exception as e:
            print(f"[MQTT Remote] Connection error: {e}. Reconnecting in 5s...")
            time.sleep(5)
