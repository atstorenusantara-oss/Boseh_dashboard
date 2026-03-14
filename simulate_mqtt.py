import paho.mqtt.client as mqtt
import json
import time

# Konfigurasi MQTT (Harus sama dengan di app.py)
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "boseh/stasiun/update"

def simulate_mqtt_publish(slot_number, rfid_tag, status):
    client = mqtt.Client()
    
    try:
        print(f"Menghubungkan ke Broker: {MQTT_BROKER}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        payload = {
            "slot_number": slot_number,
            "rfid_tag": rfid_tag,
            "status": status
        }
        
        message = json.dumps(payload)
        client.publish(MQTT_TOPIC, message)
        print(f"Terpublish ke {MQTT_TOPIC}: {message}")
        
        client.disconnect()
    except Exception as e:
        print(f"Error MQTT: {e}")

if __name__ == "__main__":
    print("--- Simulasi IoT Boseh via MQTT ---")
    
    # Simulasi: Kartu Terdeteksi di Slot 3
    simulate_mqtt_publish(8, "RFID-MQTT-777", False)
    
    # Tunggu sebentar
    time.sleep(2)
    
    print("\nSelesai. Silakan cek dashboard Anda!")
