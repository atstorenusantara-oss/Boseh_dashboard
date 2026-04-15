import sqlite3
import socket
import os
import qrcode
import io
import time
import json
import threading
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import serial
import serial.tools.list_ports
from flask import Flask, render_template, request, redirect, url_for, send_file, Response
from datetime import datetime
import datetime
from sub_programPY import api_client_station
from sub_programPY import mqtt_client_remote
from sub_programPY import mqtt_client_payment
from sub_programPY import api_confirm_open
from sub_programPY import api_return
from sub_programPY import api_confirm_ready
import requests
import logging
from logging.handlers import RotatingFileHandler

import sys

# Path helper for PyInstaller
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    # Running as compiled .exe
    template_folder = resource_path('templates')
    static_folder = resource_path('static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    # Running normally
    app = Flask(__name__)

DATABASE = 'boseh.db'


# MQTT Constants
MQTT_BROKER = "localhost" # Menggunakan Mosquitto Lokal
MQTT_PORT = 1883
MQTT_TOPIC = "boseh/stasiun/confirm_open"

# Simple broadcast mechanism
latest_event_time = time.time()
last_update_time = time.time()

# Configure Logging
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = 'boseh.log'

# Rotating file handler (5MB per file, max 3 files)
my_handler = RotatingFileHandler(log_file, mode='a', maxBytes=5*1024*1024, 
                                 backupCount=3, encoding=None, delay=0)
my_handler.setFormatter(log_formatter)
my_handler.setLevel(logging.INFO)

app_logger = logging.getLogger('root')
app_logger.setLevel(logging.INFO)
app_logger.addHandler(my_handler)

# Capture standard print to log as well if needed, but better to use log_event
def log_event(category, message, level="INFO"):
    """Global helper to log to file, console, and database."""
    # 1. Console & File
    if level == "INFO":
        app_logger.info(f"[{category}] {message}")
        print(f"INFO: [{category}] {message}")
    elif level == "ERROR":
        app_logger.error(f"[{category}] {message}")
        print(f"ERROR: [{category}] {message}")
    elif level == "WARNING":
        app_logger.warning(f"[{category}] {message}")
        print(f"WARNING: [{category}] {message}")

    # 2. Database (Activity Log)
    try:
        # We use a separate thread/connection to avoid locking the main UI
        def record_to_db():
            try:
                conn = sqlite3.connect(DATABASE, timeout=10)
                conn.execute("INSERT INTO activity_logs (category, message, level) VALUES (?, ?, ?)", 
                             (category, str(message), level))
                conn.commit()
                conn.close()
            except: pass
        
        threading.Thread(target=record_to_db, daemon=True).start()
    except: pass

@app.route('/api/shutdown', methods=['POST'])
def manual_shutdown():
    log_event("SYSTEM", "Manual shutdown triggered from Admin Panel", "WARNING")
    # Shutdown command for Windows
    os.system("shutdown /s /t 5")
    return {"status": "success", "message": "PC will shutdown in 5 seconds"}

@app.route('/api/keyboard', methods=['POST'])
def open_keyboard():
    log_event("SYSTEM", "Virtual keyboard requested")
    try:
        # Menjalankan keyboard virtual Windows. 
        # Menggunakan 'start' agar proses tidak memblokir Flask
        os.system("start osk")
        return {"status": "success", "message": "Keyboard virtual dibuka"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

def auto_shutdown_loop():
    """Background thread to check for scheduled shutdown."""
    print("[Auto Shutdown] Service started...")
    while True:
        try:
            # Check every minute
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            # Use connection to avoid shared-state issues in thread
            conn = sqlite3.connect(DATABASE, timeout=20)
            conn.row_factory = sqlite3.Row
            
            enabled = conn.execute("SELECT value FROM settings WHERE key = 'auto_shutdown_enabled'").fetchone()
            target = conn.execute("SELECT value FROM settings WHERE key = 'auto_shutdown_time'").fetchone()
            conn.close()
            
            if enabled and enabled['value'] == "1" and target:
                if current_time == target['value']:
                    log_event("SYSTEM", f"Auto Shutdown triggered at {current_time}", "WARNING")
                    print(f"[Auto Shutdown] Triggering system shutdown at {current_time}")
                    os.system("shutdown /s /t 30") # 30 seconds delay
                    time.sleep(120) # Wait to avoid repeated trigger during the same minute
            
        except Exception as e:
            print(f"[Auto Shutdown] Error: {e}")
            
        time.sleep(30) # Check every 30 seconds

# API Health Status
last_api_status = False
last_api_message = "Initializing..."

# ---------------------------------------------------------
# MQTT CLIENT OVERVIEW
# ---------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    client.subscribe("boseh/ready")
    client.subscribe("boseh/maintenance")

# Global tracker to prevent duplicate API calls for the same tag within a short time window
last_processed_returns = {} # Format: {f"{slot_num}_{tag}": timestamp}

def handle_device_event(topic, data, source="MQTT"):
    """Unified handler for data from both MQTT and Serial."""
    global last_update_time
    try:
        if topic == "boseh/ready":
            bike_id = data.get('bike_id')
            if bike_id:
                print(f"[{source}] Received Ready Trigger for Bike: {bike_id}")
                threading.Thread(target=api_confirm_ready.confirm_ready, args=(bike_id,), daemon=True).start()
            return

        if topic == "boseh/maintenance":
            slot_num = data.get('slot_number')
            ip = data.get('ip_address')
            status = data.get('status')
            solenoid = data.get('solenoid')
            
            if slot_num is not None:
                with app.app_context():
                    db = get_db()
                    db.execute('''
                        UPDATE slots 
                        SET ip_address = ?, is_connected = ?, solenoid_status = ?, last_update = CURRENT_TIMESTAMP 
                        WHERE slot_number = ?
                    ''', (ip, status, solenoid, slot_num))
                    db.commit()
                    last_update_time = time.time()
                    log_event(source, f"Maintenance Update: Slot {slot_num} (IP: {ip}, Connected: {status})")
            return

        # Default: handle standard bike status updates (boseh/stasiun/confirm_open)
        slot_num = data.get('slot_number')
        tag = data.get('rfid_tag')
        status = data.get('status')
        
        if slot_num is not None:
            # 1. Update Database Lokal SEGERA untuk merekam state terbaru
            with app.app_context():
                db = get_db()
                if tag:
                    db.execute('''
                        UPDATE slots 
                        SET rfid_tag = ?, is_detected = ?, has_bike = ?, last_update = CURRENT_TIMESTAMP 
                        WHERE slot_number = ?
                    ''', (tag, status, status, slot_num))
                else:
                    db.execute('''
                        UPDATE slots 
                        SET is_detected = ?, has_bike = ?, last_update = CURRENT_TIMESTAMP 
                        WHERE slot_number = ?
                    ''', (status, status, slot_num))
                db.commit()
                last_update_time = time.time()

            # 2. Pengecekan Ekskusi API External
            if tag and tag.lower() != "null":
                if status is False:
                    # Sepeda diangkat -> Confirm Open
                    print(f"[{source}] Slot {slot_num} Bike REMOVED (RFID: {tag})")
                    threading.Thread(target=api_confirm_open.confirm_open, args=(tag,), daemon=True).start()
                elif status is True:
                    # Mekanisme Debounce: Cek apakah tag ini baru saja diproses dalam 5 detik terakhir
                    process_key = f"{slot_num}_{tag}"
                    now = time.time()
                    last_time = last_processed_returns.get(process_key, 0)
                    
                    if (now - last_time) > 5:
                        last_processed_returns[process_key] = now
                        print(f"[{source}] Slot {slot_num} Bike RETURNED. Tag: {tag}. Sending API Return.")
                        # Jalankan Return Bike
                        threading.Thread(target=api_return.return_bike, args=(tag, slot_num), daemon=True).start()
                        
                        # Update status dashboard (Visual Feedback)
                        def update_visual_status(s_num):
                            with app.app_context():
                                db_v = get_db()
                                db_v.execute("UPDATE slots SET bike_status = 'Sepeda sudah masuk' WHERE slot_number = ?", (s_num,))
                                db_v.commit()
                                global last_update_time
                                last_update_time = time.time()
                            time.sleep(10)
                            with app.app_context():
                                db_v = get_db()
                                db_v.execute("UPDATE slots SET bike_status = 'ready' WHERE slot_number = ?", (s_num,))
                                db_v.commit()
                                last_update_time = time.time()
                        
                        threading.Thread(target=update_visual_status, args=(slot_num,), daemon=True).start()
                    else:
                        print(f"[{source}] Duplikat terdeteksi untuk Slot {slot_num} Tag {tag}. Mengabaikan.")

            print(f"{source} Update: Slot {slot_num} processed via {topic}")
    except Exception as e:
        print(f"Error in handle_device_event ({source}): {e}")

def on_message(client, userdata, msg):
    # 1. Abaikan pesan lama (retained) agar tidak memicu pengembalian ganda saat startup/reconnect
    if msg.retain:
        print(f"[Local MQTT] Ignoring retained message on topic {msg.topic}")
        return
    try:
        payload_str = msg.payload.decode()
        data = json.loads(payload_str)
        handle_device_event(msg.topic, data, source="MQTT")
    except Exception as e:
        print(f"Error decoding MQTT message: {e}")

# Serial Global Object
ser_obj = None

def run_serial():
    global ser_obj
    print("[Serial] Thread started...")
    while True:
        try:
            # Re-fetch port from DB in case it changed
            with app.app_context():
                db = get_db()
                port = db.execute("SELECT value FROM settings WHERE key = 'serial_port'").fetchone()
                mode = db.execute("SELECT value FROM settings WHERE key = 'comm_mode'").fetchone()
                db.close()
            
            if mode and mode['value'] == 'serial' and port:
                target_port = port['value']
                if ser_obj is None or ser_obj.port != target_port or not ser_obj.is_open:
                    if ser_obj and ser_obj.is_open: ser_obj.close()
                    print(f"[Serial] Connecting to {target_port}...")
                    ser_obj = serial.Serial(target_port, 115200, timeout=1)
                    time.sleep(2) # Wait for reset
                
                if ser_obj.in_waiting > 0:
                    line = ser_obj.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        try:
                            # Serial format from SERIAL_PARSER.md: {"topic":"xxx", "payload":{...}}
                            envelope = json.loads(line)
                            topic = envelope.get('topic')
                            payload = envelope.get('payload')
                            if topic and isinstance(payload, dict):
                                handle_device_event(topic, payload, source="SERIAL")
                        except json.JSONDecodeError:
                            if "Serial command invalid" not in line:
                                print(f"[Serial Raw] {line}")
            else:
                if ser_obj and ser_obj.is_open:
                    ser_obj.close()
                    ser_obj = None
                time.sleep(5) # Idle if not in serial mode
        except Exception as e:
            print(f"[Serial Error] {e}")
            ser_obj = None
            time.sleep(5)
        time.sleep(0.01)

def dispatch_command(topic, payload):
    """Sends command to device using the configured communication mode."""
    try:
        with app.app_context():
            db = get_db()
            mode_row = db.execute("SELECT value FROM settings WHERE key = 'comm_mode'").fetchone()
            mode = mode_row['value'] if mode_row else 'mqtt'
            db.close()
        
        if mode == 'mqtt':
            publish.single(topic, payload=json.dumps(payload), hostname=MQTT_BROKER, port=MQTT_PORT)
            print(f"[Dispatch-MQTT] Sent to {topic}")
        elif mode == 'serial':
            if ser_obj and ser_obj.is_open:
                # Wrap in envelope for SERIAL_PARSER.md
                envelope = {"topic": topic, "payload": payload}
                msg = json.dumps(envelope) + "\n"
                ser_obj.write(msg.encode('utf-8'))
                print(f"[Dispatch-SERIAL] Sent to {topic}")
            else:
                print("[Dispatch-SERIAL] FAILED: Serial port not open")
    except Exception as e:
        print(f"[Dispatch Error] {e}")


def run_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"MQTT Connection Error: {e}")

# Threads will be started at the bottom of the file inside the main block
# ---------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        db = get_db()
        # Create slots table with RFID support
        db.execute('''
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_number INTEGER UNIQUE,
                has_bike BOOLEAN NOT NULL DEFAULT 1,
                rfid_tag TEXT,
                bike_status TEXT,
                is_detected BOOLEAN DEFAULT 0,
                maintenance BOOLEAN DEFAULT 0,
                ip_address TEXT,
                is_connected BOOLEAN DEFAULT 0,
                bike_name TEXT,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migrations for slots
        try:
            db.execute("ALTER TABLE slots ADD COLUMN bike_status TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            db.execute("ALTER TABLE slots ADD COLUMN maintenance BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            db.execute("ALTER TABLE slots ADD COLUMN ip_address TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            db.execute("ALTER TABLE slots ADD COLUMN is_connected BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            db.execute("ALTER TABLE slots ADD COLUMN solenoid_status BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            db.execute("ALTER TABLE slots ADD COLUMN bike_name TEXT")
        except sqlite3.OperationalError:
            pass
        
        # Create settings table
        db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Create api_credentials table
        db.execute('''
            CREATE TABLE IF NOT EXISTS api_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_url TEXT NOT NULL,
                client_id TEXT NOT NULL,
                client_secret TEXT NOT NULL,
                token TEXT
            )
        ''')

        # Attempt to add token column to existing table to support schema migration
        try:
            db.execute("ALTER TABLE api_credentials ADD COLUMN token TEXT")
        except sqlite3.OperationalError:
            pass

        # Create activity_logs table
        db.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT,
                message TEXT,
                level TEXT DEFAULT 'INFO'
            )
        ''')

        # Seed initial data for 5 slots if empty
        cursor = db.execute('SELECT COUNT(*) FROM slots')
        if cursor.fetchone()[0] == 0:
            for i in range(1, 6):
                db.execute('INSERT INTO slots (slot_number, has_bike) VALUES (?, ?)', (i, 1))
        
        # Seed initial settings if they don't exist
        settings_to_seed = [
            ("running_text", "Selamat datang di Station Boseh Dago! Silakan scan QR untuk menyewa sepeda."),
            ("station_name", "Station Dago"),
            ("station_address", "Jl. Ir. H. Juanda No.262"),
            ("total_slots", "5"),
            ("auto_shutdown_enabled", "0"),
            ("auto_shutdown_time", "22:00"),
            ("comm_mode", "mqtt"),
            ("serial_port", "COM3")
        ]
        
        for key, value in settings_to_seed:
            cursor = db.execute('SELECT COUNT(*) FROM settings WHERE key = ?', (key,))
            if cursor.fetchone()[0] == 0:
                db.execute('INSERT INTO settings (key, value) VALUES (?, ?)', (key, value))
        
        # Seed initial api credentials if they don't exist
        cursor = db.execute('SELECT COUNT(*) FROM api_credentials')
        if cursor.fetchone()[0] == 0:
            db.execute('''
                INSERT INTO api_credentials (base_url, client_id, client_secret) 
                VALUES (?, ?, ?)
            ''', ('https://boseh.uptangkutan-bandung.id', 'station-0001', '5U3n6f4GEA6H2mrO'))

        db.commit()

# Threads will be started at the bottom

def handle_remote_mqtt(topic, data):
    """Generic callback function for remote API MQTT messages."""
    global last_update_time, latest_event_time, latest_event
    
    # Check if it's a rent request (dock/open)
    if topic.endswith('/dock/open'):
        # 1. RECOVERY DATA: Ambil data penting segera
        bike_info = data.get('bike', {})
        slot_num = bike_info.get('docking_id')
        bike_id = bike_info.get('bike_id')
        
        if slot_num is None or bike_id is None:
            log_event("MQTT-REMOTE", f"Invalid Rent Request: Data bike tidak lengkap.", "ERROR")
            return

        # 2. IMMEDIATE ACTION: Pemicu Hardware Lokal (Langkah 2) agar solenoid cepat terbuka
        try:
            local_payload = {
                "slot_number": int(slot_num),
                "rfid_tag": str(bike_id)
            }
            local_topic = f"boseh/status/{slot_num}"
            dispatch_command(local_topic, local_payload)
            print(f"[Dispatch] PRIORITY: Triggered {local_topic} for Slot {slot_num}")
        except Exception as e:
            print(f"[Dispatch] Error priority publish: {e}")

        # 3. IMMEDIATE ACTION: Konfirmasi ke Server Pusat (Langkah 3)
        print(f"[Automation] PRIORITY: Sending Confirm Ready for Bike ID: {bike_id}")
        threading.Thread(target=api_confirm_ready.confirm_ready, args=(bike_id,), daemon=True).start()

        # 4. DASHBOARD UPDATE: Menampilkan dialog data penyewa (Langkah 1)
        log_event("MQTT-REMOTE", f"Rent request received for Slot {slot_num}")
        
        # Enrich with local bike_name from slots table
        try:
            with app.app_context():
                db = get_db()
                slot_info = db.execute("SELECT bike_name FROM slots WHERE slot_number = ?", (slot_num,)).fetchone()
                if slot_info and slot_info['bike_name']:
                    data['bike']['bike_name_local'] = slot_info['bike_name']
        except Exception as e:
            print(f"Error enriching remote data: {e}")

        latest_event = {"type": "rent_request", "data": data}
        latest_event_time = time.time()
        last_update_time = time.time()

        # 5. BACKGROUND STATUS MANAGEMENT: Menghandle timer dan instruksi pengambilan
        def update_status_after_delay(s_num, b_data):
            global last_update_time
            time.sleep(5)
            
            with app.app_context():
                db = get_db()
                db.execute("UPDATE slots SET bike_status = 'Silahkan ambil sepeda' WHERE slot_number = ?", (s_num,))
                db.commit()
                last_update_time = time.time()
                
            # Countdown 40s
            for i in range(40, 0, -1):
                with app.app_context():
                    db = get_db()
                    try:
                        cursor = db.execute("SELECT has_bike FROM slots WHERE slot_number = ?", (s_num,))
                        row = cursor.fetchone()
                        if not row or row['has_bike'] == 0:
                            db.execute("UPDATE slots SET bike_status = 'ready' WHERE slot_number = ?", (s_num,))
                            db.commit()
                            last_update_time = time.time()
                            break
                        db.execute("UPDATE slots SET bike_status = ? WHERE slot_number = ? AND (bike_status LIKE 'Silahkan%' OR bike_status = 'ready')", 
                                  (f"Silahkan ambil sepeda ({i}s)", s_num))
                        db.commit()
                        last_update_time = time.time()
                    except: pass
                time.sleep(1)

            with app.app_context():
                db = get_db()
                try:
                    db.execute("UPDATE slots SET bike_status = 'ready' WHERE slot_number = ? AND bike_status LIKE 'Silahkan%'", (s_num,))
                    db.commit()
                    last_update_time = time.time()
                except: pass

        threading.Thread(target=update_status_after_delay, args=(slot_num, data), daemon=True).start()


    # Check if it's a full status update (station/[client_id]/status)
    elif topic.endswith('/status'):
        log_event("MQTT-REMOTE", "Full status sync received from server")
        try:
            with app.app_context():
                db = get_db()
                # Clear and re-populate (Optional: depend on how the API sends data, 
                # usually it sends the current state of all slots)
                db.execute("UPDATE slots SET has_bike = 0, rfid_tag = NULL, bike_status = NULL") # Keep bike_name if you want
                
                bikes = data.get('station', {}).get('bikes', [])
                if not bikes: # Maybe it's directly a list or under another key
                    bikes = data.get('bikes', [])
                
                for bike in bikes:
                    b_id = bike.get('bike_id')
                    b_status = bike.get('status')
                    b_name = bike.get('name')
                    d_id = bike.get('docking_id')
                    
                    if d_id is not None:
                        db.execute('''
                            UPDATE slots 
                            SET rfid_tag = ?, bike_status = ?, bike_name = ?, has_bike = 1 
                            WHERE slot_number = ?
                        ''', (b_id, b_status, b_name, d_id))
                
                db.commit()
                last_update_time = time.time() # This will trigger SSE refresh on dashboard
                print(f"[Remote MQTT] Database updated from Status Topic. {len(bikes)} bikes synced.")
        except Exception as e:
            print(f"[Remote MQTT] Error processing status update: {e}")

# Threads will be started at the bottom

def handle_payment_received(data):
    """Callback function when a payment request arrives from remote API MQTT."""
    global last_update_time, latest_event_time, latest_event
    log_event("PAYMENT", f"Incoming payment request: IDR {data.get('payment', {}).get('amount')}")
    latest_event = {"type": "payment_request", "data": data}
    latest_event_time = time.time()
    last_update_time = time.time()

# Threads will be started at the bottom

@app.route('/')
def index():
    db = get_db()
    slots = db.execute('SELECT * FROM slots ORDER BY slot_number').fetchall()
    settings = db.execute('SELECT * FROM settings').fetchall()
    settings_dict = {s['key']: s['value'] for s in settings}
    return render_template('index.html', slots=slots, settings=settings_dict)

# Route for admin to toggle bikes
@app.route('/admin')
def admin():
    db = get_db()
    slots = db.execute('SELECT * FROM slots ORDER BY slot_number').fetchall()
    settings = db.execute('SELECT * FROM settings').fetchall()
    settings_dict = {s['key']: s['value'] for s in settings}
    api_creds_row = db.execute('SELECT * FROM api_credentials LIMIT 1').fetchone()
    api_creds = dict(api_creds_row) if api_creds_row else {'client_id': '', 'client_secret': ''}
    
    # Get available serial ports for UI selection (device name and description)
    available_ports = [{"device": p.device, "description": p.description} for p in serial.tools.list_ports.comports()]
    return render_template('admin.html', slots=slots, settings=settings_dict, api_creds=api_creds, available_ports=available_ports)

@app.route('/maintenance')
def maintenance():
    def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    db = get_db()
    slots = db.execute('SELECT * FROM slots ORDER BY slot_number').fetchall()
    settings = db.execute('SELECT * FROM settings').fetchall()
    settings_dict = {s['key']: s['value'] for s in settings}
    return render_template('maintenance.html', slots=slots, settings=settings_dict, server_ip=get_local_ip())
    return render_template('maintenance.html', slots=slots, settings=settings_dict)

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/toggle_maintenance/<int:slot_id>', methods=['POST'])
def toggle_maintenance(slot_id):
    global last_update_time
    data = request.json
    status = data.get('maintenance', False)
    db = get_db()
    db.execute('UPDATE slots SET maintenance = ? WHERE id = ?', (status, slot_id))
    db.commit()
    last_update_time = time.time()
    return {"status": "success"}

@app.route('/update_device_info/<int:slot_id>', methods=['POST'])
def update_device_info(slot_id):
    global last_update_time
    data = request.json
    ip = data.get('ip_address')
    connected = data.get('is_connected')
    
    db = get_db()
    if ip is not None:
        db.execute('UPDATE slots SET ip_address = ? WHERE id = ?', (ip, slot_id))
    if connected is not None:
        db.execute('UPDATE slots SET is_connected = ? WHERE id = ?', (connected, slot_id))
    db.commit()
    last_update_time = time.time()
    return {"status": "success"}

@app.route('/test_solenoid/<int:slot_id>', methods=['POST'])
def test_solenoid(slot_id):
    data = request.json
    status = data.get('solenoid', False)
    
    db = get_db()
    slot = db.execute('SELECT slot_number FROM slots WHERE id = ?', (slot_id,)).fetchone()
    
    if slot:
        slot_num = slot['slot_number']
        # Topic example: boseh/device/1/control
        payload = {
            "slot_number": slot_num,
            "command": "solenoid",
            "value": status
        }
        dispatch_command(f"boseh/device/{slot_num}/control", payload)
        return {"status": "success", "message": f"Command sent to slot {slot_num}"}
    
    return {"status": "error", "message": "Slot not found"}, 404

@app.route('/update_rfid/<int:slot_id>', methods=['POST'])
def update_rfid(slot_id):
    global last_update_time
    data = request.json
    rfid = data.get('rfid_tag')
    
    db = get_db()
    db.execute('UPDATE slots SET rfid_tag = ? WHERE id = ?', (rfid, slot_id))
    db.commit()
    last_update_time = time.time()
    return {"status": "success"}

@app.route('/sync_now')
def sync_now():
    global last_update_time
    try:
        api_client_station.sync_station_data_from_api()
        last_update_time = time.time()
        log_event("SYSTEM", "Synchronization complete from API")
        return {"status": "success", "message": "Synchronization complete"}
    except Exception as e:
        log_event("SYSTEM", f"Sync failed: {e}", "ERROR")
        return {"status": "error", "message": str(e)}, 500

@app.route('/toggle_slot/<int:slot_id>')
def toggle_slot(slot_id):
    global last_update_time
    db = get_db()
    db.execute('UPDATE slots SET has_bike = NOT has_bike WHERE id = ?', (slot_id,))
    db.commit()
    last_update_time = time.time() # Signal update
    return redirect(url_for('admin'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    global last_update_time
    db = get_db()
    setting_keys = ['running_text', 'station_name', 'station_address', 'total_slots', 'auto_shutdown_enabled', 'auto_shutdown_time', 'comm_mode', 'serial_port']
    
    # Pre-process auto_shutdown_enabled as it's a checkbox usually
    if 'auto_shutdown_enabled' not in request.form:
        db.execute('UPDATE settings SET value = ? WHERE key = ?', ("0", "auto_shutdown_enabled"))
    
    for key in setting_keys:
        if key in request.form:
            value = request.form.get(key)
            if key == 'auto_shutdown_enabled':
                value = "1"
            db.execute('UPDATE settings SET value = ? WHERE key = ?', (value, key))
            
            # If total_slots is changed, sync the slots table
            if key == 'total_slots' and value:
                new_total = int(value)
                current_slots = db.execute('SELECT COUNT(*) FROM slots').fetchone()[0]
                
                if new_total > current_slots:
                    # Add more slots
                    for i in range(current_slots + 1, new_total + 1):
                        db.execute('INSERT INTO slots (slot_number, has_bike) VALUES (?, ?)', (i, 1))
                elif new_total < current_slots:
                    # Remove extra slots
                    db.execute('DELETE FROM slots WHERE slot_number > ?', (new_total,))
    
    # Update API Credentials
    client_id = request.form.get('client_id')
    client_secret = request.form.get('client_secret')
    if client_id is not None and client_secret is not None:
        count = db.execute('SELECT COUNT(*) FROM api_credentials').fetchone()[0]
        if count > 0:
            db.execute('UPDATE api_credentials SET client_id = ?, client_secret = ?', (client_id, client_secret))
        else:
            db.execute('INSERT INTO api_credentials (base_url, client_id, client_secret) VALUES (?, ?, ?)', ('https://boseh.devserver.my.id', client_id, client_secret))
        # Trigger an API sync when credentials change to immediately test mapping
        # We must commit first so the sync script (which uses its own connection) reads the new credentials.
        db.commit()
        
        # Run sync synchronously so the webpage waits for the new data before reloading
        api_client_station.sync_station_data_from_api()
    
    db.commit()
    last_update_time = time.time() # Signal update
    return redirect(url_for('admin'))

@app.route('/update_bike_names', methods=['POST'])
def update_bike_names():
    global last_update_time
    db = get_db()
    for key, value in request.form.items():
        if key.startswith('bike_name_'):
            slot_id = key.split('_')[-1]
            db.execute('UPDATE slots SET bike_name = ? WHERE id = ?', (value, slot_id))
    db.commit()
    last_update_time = time.time()
    return redirect(url_for('admin'))

@app.route('/api/slots')
def api_slots():
    db = get_db()
    slots = db.execute('SELECT * FROM slots ORDER BY slot_number').fetchall()
    return {"slots": [dict(s) for s in slots]}

@app.route('/check_device/<int:slot_id>', methods=['POST'])
def check_device(slot_id):
    db = get_db()
    slot = db.execute('SELECT slot_number, last_update FROM slots WHERE id = ?', (slot_id,)).fetchone()
    
    if slot:
        slot_num = slot['slot_number']
        initial_update = slot['last_update']
        
        # Publish payload {"status": true} to topic boseh/1, boseh/2...
        topic = f"boseh/{slot_num}"
        payload = {"status": True}
        dispatch_command(topic, payload)
        
        # Start a 5-second timer to check for response
        threading.Timer(5.0, verify_device_response, [slot_id, initial_update]).start()
        
        return {"status": "success", "message": f"Check command sent to {topic}. Waiting 5s for response..."}
    
    return {"status": "error", "message": "Slot not found"}, 404

def verify_device_response(slot_id, initial_update):
    global last_update_time
    with app.app_context():
        db = get_db()
        current_slot = db.execute('SELECT last_update FROM slots WHERE id = ?', (slot_id,)).fetchone()
        
        if current_slot:
            # If last_update is still the same, device didn't respond
            if current_slot['last_update'] == initial_update:
                print(f"[Timeout] Device ID {slot_id} failed to respond in 5s. Setting Offline.")
                db.execute('UPDATE slots SET is_connected = 0 WHERE id = ?', (slot_id,))
                db.commit()
                last_update_time = time.time() # Refresh UI
            else:
                print(f"[Response] Device ID {slot_id} responded successfully.")

# Global tracker for last seen time per slot
device_last_seen = {}

def is_device_online(slot_num):
    last_seen = device_last_seen.get(slot_num, 0)
    return (time.time() - last_seen) < 10

def update_device_seen(slot_num):
    device_last_seen[slot_num] = time.time()

def check_api_health_loop():
    global last_api_status, last_api_message
    while True:
        try:
            db = get_db()
            row = db.execute("SELECT base_url FROM api_credentials LIMIT 1").fetchone()
            db.close()
            
            if row:
                base_url = row['base_url']
                # Try to ping the base URL or a known health endpoint
                try:
                    # Using a 5s timeout to not hang
                    # Any response from the server indicates we have internet and server is up
                    response = requests.get(base_url, timeout=5)
                    last_api_status = True
                    if response.status_code == 200:
                        last_api_message = "Connected"
                    else:
                        last_api_message = f"Online ({response.status_code})"
                except requests.exceptions.RequestException as e:
                    last_api_status = False
                    last_api_message = "No Connection"
            else:
                last_api_status = False
                last_api_message = "Config Missing"
        except Exception as e:
            print(f"[Health Check] Error: {e}")
            last_api_status = False
            last_api_message = "System Error"
            
        time.sleep(30) # Check every 30 seconds

@app.route('/api/health')
def api_health():
    return {
        "status": last_api_status,
        "message": last_api_message
    }

@app.route('/api/logs')
def api_logs():
    db = get_db()
    logs = db.execute('SELECT * FROM activity_logs ORDER BY id DESC LIMIT 100').fetchall()
    return {"logs": [dict(l) for l in logs]}

@app.route('/stream')
def stream():
    def event_stream():
        global last_update_time, latest_event_time, latest_event
        local_last_update = last_update_time
        local_event_time = latest_event_time
        while True:
            # Check for generic events like rent requests first
            if local_event_time < latest_event_time:
                local_event_time = latest_event_time
                if latest_event:
                    yield f"event: {latest_event['type']}\ndata: {json.dumps(latest_event['data'])}\n\n"
            # Else check for standard refresh signals
            elif local_last_update < last_update_time:
                local_last_update = last_update_time
                yield "event: refresh\ndata: update\n\n"
            else:
                # Heartbeat to keep connection alive
                yield ": heartbeat\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")

# IoT API Endpoint
@app.route('/api/iot/update', methods=['POST'])
def iot_update():
    global last_update_time
    data = request.json
    slot_number = data.get('slot_number')
    rfid_tag = data.get('rfid_tag')
    is_detected = data.get('status') # true if attached, false if out of range

    if slot_number is None:
        log_event("IOT", "Missing slot_number in update request", "ERROR")
        return {"error": "Missing slot_number"}, 400

    db = get_db()
    db.execute('''
        UPDATE slots 
        SET rfid_tag = ?, is_detected = ?, has_bike = ?, last_update = CURRENT_TIMESTAMP 
        WHERE slot_number = ?
    ''', (rfid_tag, is_detected, is_detected, slot_number))
    db.commit()
    
    last_update_time = time.time()
    log_event("IOT", f"Slot {slot_number} updated via API (RFID: {rfid_tag})")
    return {"status": "success", "message": f"Slot {slot_number} updated"}, 200

@app.route('/qrcode')
def get_qrcode():
    db = get_db()
    client = db.execute('SELECT client_id FROM api_credentials LIMIT 1').fetchone()
    qr_text = client['client_id'] if client else "Boseh"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@app.route('/api/qris')
def get_qris():
    data = request.args.get('data', 'No Data')
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

import webview

def run_flask():
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    # Initialize DB first before anything else
    print("Initializing Database...")
    init_db()

    # Start all background threads
    print("Starting background service threads...")
    
    # 1. Local MQTT
    threading.Thread(target=run_mqtt, daemon=True).start()

    # 1b. Local Serial (New Pathway)
    threading.Thread(target=run_serial, daemon=True).start()
    
    # 2. API Sync
    threading.Thread(target=api_client_station.sync_station_data_from_api, daemon=True).start()
    
    # 3. Remote Rental & Status MQTT
    threading.Thread(target=mqtt_client_remote.start_mqtt_client, args=(handle_remote_mqtt,), daemon=True).start()
    
    # 4. Remote Payment MQTT
    threading.Thread(target=mqtt_client_payment.start_mqtt_payment_client, args=(handle_payment_received,), daemon=True).start()

    # 5. API Health Check
    threading.Thread(target=check_api_health_loop, daemon=True).start()
    
    # 5b. Auto Shutdown Check
    threading.Thread(target=auto_shutdown_loop, daemon=True).start()

    # 6. Automatic Token Refresh (Every 5 Minutes)
    threading.Thread(target=api_client_station.api_token_refresh_loop, daemon=True).start()

    # 7. Start Flask Server in a thread
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # 8. Start Webview window (Kiosk Mode: Fullscreen & Frameless)
    print("Launching Desktop UI in Fullscreen...")
    webview.create_window('Boseh Dashboard V2', 'http://127.0.0.1:5000', 
                          fullscreen=True)
    webview.start()


