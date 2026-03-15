import paho.mqtt.client as mqtt
import json
import sqlite3
import os
import uuid

# Automatically use the boseh.db in the parent directory
base_dir = os.path.dirname(os.path.abspath(__file__))
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

def start_mqtt_payment_client(on_payment_received_callback):
    base_url, client_id, client_secret, token = get_mqtt_credentials()
    
    if not client_id or not token:
        print("Payment MQTT Error: client_id atau token tidak ditemukan.")
        return
        
    host = base_url.replace("https://", "").replace("http://", "").split("/")[0]
    port = 1883
    mqtt_client_id = f"payment-{uuid.uuid4()}"
    username = token
    password = client_secret
    
    def on_connect(client, userdata, flags, reason_code, properties=None):
        print(f"Payment MQTT Connected with result code {reason_code}")
        topic = f"station/{client_id}/payment"
        print(f"Subscribing to payment topic: {topic}")
        client.subscribe(topic)

    def on_message(client, userdata, msg):
        try:
            payload = msg.payload.decode()
            print(f"[{msg.topic}] PAYMENT MESSAGE RECEIVED")
            
            data = json.loads(payload)
            # Invoke the callback passed from app.py
            if on_payment_received_callback:
                on_payment_received_callback(data)
                
        except Exception as e:
            print(f"Error parse payment message: {e}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=mqtt_client_id)
    client.username_pw_set(username=username, password=password)
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"Menghubungkan ke Broker Payment: {host}...")
        client.connect(host, port, 60)
        client.loop_forever()
    except Exception as e:
        print(f"Error MQTT Payment: {e}")
