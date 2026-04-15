import serial
import json
import threading
import time
import sys

# Konfigurasi Default
DEFAULT_PORT = 'COM3'  # Sesuaikan dengan port ESP32 Anda
BAUD_RATE = 115200

def list_ports():
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    print("\nAvailable Ports:")
    for i, port in enumerate(ports):
        print(f"{i}: {port.device} ({port.description})")
    return ports

def read_from_serial(ser):
    """Fungsi untuk membaca data dari serial secara terus menerus."""
    print(f"\n[LISTENER] Thread pembaca aktif pada {ser.port}...")
    while ser.is_open:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    try:
                        data = json.loads(line)
                        print(f"\n\n[RX - JSON] {time.strftime('%H:%M:%S')}")
                        print(json.dumps(data, indent=4))
                        print("Input command (atau 'help'): ", end="", flush=True)
                    except json.JSONDecodeError:
                        print(f"\n[RX - RAW] {line}")
        except Exception as e:
            print(f"\n[ERROR] Reading serial: {e}")
            break

def main():
    print("=== Boseh Serial Parser Tester ===")
    
    ports = list_ports()
    if not ports:
        print("No serial ports found!")
        port_input = input(f"Masukkan port secara manual (default {DEFAULT_PORT}): ") or DEFAULT_PORT
    else:
        choice = input(f"\nPilih nomor port (0-{len(ports)-1}) atau masukkan manual: ")
        try:
            port_input = ports[int(choice)].device
        except (ValueError, IndexError):
            port_input = choice if choice else DEFAULT_PORT

    try:
        ser = serial.Serial(port_input, BAUD_RATE, timeout=1)
        time.sleep(2) # Tunggu reset ESP32
        ser.flushInput()
        
        # Jalankan reader di background thread
        reader_thread = threading.Thread(target=read_from_serial, args=(ser,), daemon=True)
        reader_thread.start()

        print(f"\nBerhasil terhubung ke {port_input}")
        print("Ketik 'help' untuk daftar perintah, atau 'exit' untuk keluar.")

        while True:
            cmd = input("Input command: ").strip().lower()
            
            if cmd == 'exit':
                break
            elif cmd == 'help':
                print("\nPerintah Tersedia:")
                print("1. open <slot>    - Mengirim perintah buka solenoid")
                print("2. arm <slot> <rfid> - Mengirim status arming")
                print("3. status <slot>  - Mengirim request maintenance")
                print("4. raw <json>     - Mengirim JSON kustom")
                print("help              - Menampilkan menu ini")
                print("exit              - Keluar program")
            
            elif cmd.startswith('open '):
                try:
                    slot = int(cmd.split(' ')[1])
                    msg = {
                        "topic": f"boseh/device/{slot}/control",
                        "payload": {"command": "solenoid", "value": True}
                    }
                    ser.write((json.dumps(msg) + "\n").encode('utf-8'))
                    print(f"[TX] Command sent: open slot {slot}")
                except:
                    print("Format salah! Contoh: open 12")

            elif cmd.startswith('arm '):
                try:
                    parts = cmd.split(' ')
                    slot = int(parts[1])
                    rfid = parts[2]
                    msg = {
                        "topic": f"boseh/status/{slot}",
                        "payload": {"rfid_tag": rfid}
                    }
                    ser.write((json.dumps(msg) + "\n").encode('utf-8'))
                    print(f"[TX] Command sent: arm slot {slot} with RFID {rfid}")
                except:
                    print("Format salah! Contoh: arm 12 A1B2C3D4")

            elif cmd.startswith('status '):
                try:
                    slot = int(cmd.split(' ')[1])
                    msg = {
                        "topic": f"boseh/{slot}",
                        "payload": {"status": True}
                    }
                    ser.write((json.dumps(msg) + "\n").encode('utf-8'))
                    print(f"[TX] Command sent: request status slot {slot}")
                except:
                    print("Format salah! Contoh: status 12")

            elif cmd.startswith('raw '):
                raw_json = cmd[4:]
                ser.write((raw_json + "\n").encode('utf-8'))
                print(f"[TX] Raw sent: {raw_json}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("\nSerial port closed.")

if __name__ == "__main__":
    main()
