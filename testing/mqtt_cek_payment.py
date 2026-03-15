import paho.mqtt.client as mqtt
import json
import sqlite3
import os
import uuid

# Automatically use the boseh.db in the parent directory
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

def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"Connected with result code {reason_code}")
    
    client_id = userdata['client_id']
    topic = f"station/{client_id}/payment"
    
    print(f"Subscribing to topic: {topic}")
    client.subscribe(topic)

def on_message(client, userdata, msg):
    print(f"[{msg.topic}] MESSAGE RECEIVED: {msg.payload.decode()}")

def simulate_payment_subscribe():
    base_url, client_id, client_secret, token = get_mqtt_credentials()
    
    if not client_id or not token:
        print("Error: client_id atau token tidak ditemukan di database. Pastikan sudah login via aplikasi admin.")
        return
        
    # Ambil host dari base_url
    host = base_url.replace("https://", "").replace("http://", "").split("/")[0]
    port = 1883
    
    mqtt_client_id = str(uuid.uuid4())
    username = token
    password = client_secret
    
    MQTT_TOPIC = f"station/{client_id}/payment"
    
    print(f"--- KONFIGURASI MQTT ---")
    print(f"Host           : {host}")
    print(f"Port           : {port}")
    print(f"MQTT Client ID : {mqtt_client_id}")
    print(f"Username       : {username[:10]}... (Token JWT)")
    print(f"Topik Sub      : {MQTT_TOPIC}")
    print("------------------------\n")
    
    # Using MQTT Callback API v2
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=mqtt_client_id, userdata={'client_id': client_id})
    client.username_pw_set(username=username, password=password)
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"Menghubungkan ke Broker: {host}...")
        client.connect(host, port, 60)
        print("Menunggu pesan payment (tekan Ctrl+C untuk keluar)...")
        client.loop_forever()
    except Exception as e:
        print(f"Error MQTT: {e}")

if __name__ == "__main__":
    print("--- Simulasi Cek Payment via MQTT (SUBSCRIBER) ---")
    simulate_payment_subscribe()
