import requests
import time
import json

# URL API Server Flask Anda
URL = "http://127.0.0.1:5000/api/iot/update"

def simulate_iot(slot_number, rfid_tag, status):
    payload = {
        "slot_number": slot_number,
        "rfid_tag": rfid_tag,
        "status": status
    }
    
    print(f"Mengirim data ke Slot {slot_number}...")
    try:
        response = requests.post(URL, json=payload)
        if response.status_code == 200:
            print(f"Berhasil! Server merespon: {response.json()}")
        else:
            print(f"Gagal! Status code: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}. Pastikan server Flask sudah jalan (python app.py)")

if __name__ == "__main__":
    # SIMULASI 1: Sepeda masuk ke Slot 1
    simulate_iot(3, "RFID-USER-005", True )
    
    time.sleep(3) # Tunggu 3 detik
    
    # SIMULASI 2: Sepeda keluar dari Slot 1
    # simulate_iot(1, None, False)
    
    print("\nSimulasi selesai. Cek dashboard Anda untuk melihat perubahan!")
