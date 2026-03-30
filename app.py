import sqlite3
import os
import qrcode
import io
import time
import json
import threading
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from flask import Flask, render_template, request, redirect, url_for, send_file, Response
from sub_programPY import api_client_station
from sub_programPY import mqtt_client_remote
from sub_programPY import mqtt_client_payment
from sub_programPY import api_confirm_open
from sub_programPY import api_return
from sub_programPY import api_confirm_ready

app = Flask(__name__)
DATABASE = 'boseh.db'

# MQTT Constants
MQTT_BROKER = "localhost" # Menggunakan Mosquitto Lokal
MQTT_PORT = 1883
MQTT_TOPIC = "boseh/stasiun/confirm_open"

# Simple broadcast mechanism
latest_event_time = time.time()
last_update_time = time.time()

# ---------------------------------------------------------
# MQTT CLIENT OVERVIEW
# ---------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    client.subscribe("boseh/ready")
    client.subscribe("boseh/maintenance")

def on_message(client, userdata, msg):
    global last_update_time
    try:
        payload_str = msg.payload.decode()
        data = json.loads(payload_str)
        
        if msg.topic == "boseh/ready":
            bike_id = data.get('bike_id')
            if bike_id:
                print(f"[Local MQTT] Received Ready Trigger for Bike: {bike_id}")
                threading.Thread(target=api_confirm_ready.confirm_ready, args=(bike_id,), daemon=True).start()
            return

        if msg.topic == "boseh/maintenance":
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
                    print(f"Maintenance MQTT Update: Slot {slot_num} (IP: {ip}, Connected: {status}, Solenoid: {solenoid})")
            return

        # Default: handle standard bike status updates (boseh/stasiun/confirm_open or similar)
        slot_num = data.get('slot_number')
        tag = data.get('rfid_tag')
        status = data.get('status')
        
        if slot_num is not None:
            # Pengecekan status untuk eksekusi API Eksternal
            if tag and tag.lower() != "null":
                if status is False:
                    # Sepeda diangkat -> Confirm Open
                    threading.Thread(target=api_confirm_open.confirm_open, args=(tag,), daemon=True).start()
                elif status is True:
                    # 1. Sepeda disimpan -> Return Bike (Dijalankan di thread terpisah)
                    threading.Thread(target=api_return.return_bike, args=(tag, slot_num), daemon=True).start()
                    
                    # 2. Update status ke "Sepeda sudah masuk" dan kembalikan ke "ready" setelah 10 detik
                    def update_return_status(s_num):
                        # Simpan ke DB "Sepeda sudah masuk"
                        with app.app_context():
                            db = get_db()
                            db.execute("UPDATE slots SET bike_status = 'Sepeda sudah masuk' WHERE slot_number = ?", (s_num,))
                            db.commit()
                            global last_update_time
                            last_update_time = time.time()
                            
                        # Tunggu 10 detik
                        time.sleep(10)
                        
                        # Set balik ke "ready"
                        with app.app_context():
                            db = get_db()
                            db.execute("UPDATE slots SET bike_status = 'ready' WHERE slot_number = ?", (s_num,))
                            db.commit()
                            last_update_time = time.time()
                    
                    threading.Thread(target=update_return_status, args=(slot_num,), daemon=True).start()

            # We use a context manager to ensure DB is updated
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
                print(f"MQTT Update: Slot {slot_num} updated via {msg.topic}")

    except Exception as e:
        print(f"Error processing MQTT message: {e}")

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
            ("total_slots", "5")
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
        print(f"[Remote MQTT] Received Rent Request topic: {topic}")
        latest_event = {"type": "rent_request", "data": data}
        latest_event_time = time.time()
        last_update_time = time.time()

        # Publish to local MQTT boseh/status for IoT/Hardware pulse
        try:
            slot_num = data.get('bike', {}).get('docking_id')
            bike_id = data.get('bike', {}).get('bike_id')
            if slot_num is not None and bike_id is not None:
                # 1. Provide IoT pulse to local hardware (if any)
                local_payload = json.dumps({
                    "slot_number": int(slot_num),
                    "rfid_tag": str(bike_id)
                })
                publish.single("boseh/status", payload=local_payload, hostname=MQTT_BROKER, port=MQTT_PORT)
                print(f"[Local MQTT] Triggered boseh/status: {local_payload}")

                # 2. AUTOMATION: Immediately Send Confirm Ready back to Server Pusat
                print(f"[Automation] Automatically sending Confirm Ready for Bike ID: {bike_id}")
                threading.Thread(target=api_confirm_ready.confirm_ready, args=(bike_id,), daemon=True).start()
        except Exception as e:
            print(f"[Local MQTT] Error publishing/automating: {e}")

        def update_status_after_delay():
            global last_update_time
            time.sleep(5)
            docking_id = data.get('bike', {}).get('docking_id')
            
            with app.app_context():
                db = get_db()
                if docking_id is not None:
                    db.execute("UPDATE slots SET bike_status = 'Silahkan ambil sepeda' WHERE slot_number = ?", (docking_id,))
                    db.commit()
                last_update_time = time.time()
                
            # Countdown 60s
            for i in range(60, 0, -1):
                with app.app_context():
                    db = get_db()
                    try:
                        cursor = db.execute("SELECT has_bike FROM slots WHERE slot_number = ?", (docking_id,))
                        row = cursor.fetchone()
                        if not row or row['has_bike'] == 0:
                            db.execute("UPDATE slots SET bike_status = 'ready' WHERE slot_number = ?", (docking_id,))
                            db.commit()
                            last_update_time = time.time()
                            break
                        db.execute("UPDATE slots SET bike_status = ? WHERE slot_number = ? AND (bike_status LIKE 'Silahkan%' OR bike_status = 'ready')", 
                                  (f"Silahkan ambil sepeda ({i}s)", docking_id))
                        db.commit()
                        last_update_time = time.time()
                    except: pass
                time.sleep(1)

            with app.app_context():
                db = get_db()
                try:
                    db.execute("UPDATE slots SET bike_status = 'ready' WHERE slot_number = ? AND bike_status LIKE 'Silahkan%'", (docking_id,))
                    db.commit()
                    last_update_time = time.time()
                except: pass

        threading.Thread(target=update_status_after_delay, daemon=True).start()

    # Check if it's a full status update (station/[client_id]/status)
    elif topic.endswith('/status'):
        print(f"[Remote MQTT] Received Status Sync topic: {topic}")
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
    return render_template('admin.html', slots=slots, settings=settings_dict, api_creds=api_creds)

@app.route('/maintenance')
def maintenance():
    db = get_db()
    slots = db.execute('SELECT * FROM slots ORDER BY slot_number').fetchall()
    settings = db.execute('SELECT * FROM settings').fetchall()
    settings_dict = {s['key']: s['value'] for s in settings}
    return render_template('maintenance.html', slots=slots, settings=settings_dict)

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
        # Publish MQTT command to the device
        payload = json.dumps({
            "slot_number": slot_num,
            "command": "solenoid",
            "value": status
        })
        # Topic example: boseh/device/1/control
        publish.single(f"boseh/device/{slot_num}/control", payload=payload, hostname=MQTT_BROKER, port=MQTT_PORT)
        print(f"Sent Solenoid Command to Slot {slot_num}: {status}")
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
        return {"status": "success", "message": "Synchronization complete"}
    except Exception as e:
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
    setting_keys = ['running_text', 'station_name', 'station_address', 'total_slots']
    for key in setting_keys:
        if key in request.form:
            value = request.form.get(key)
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
        
        # Publish MQTT payload {"status": true} to topic boseh/1, boseh/2...
        topic = f"boseh/{slot_num}"
        payload = json.dumps({"status": True})
        publish.single(topic, payload=payload, hostname=MQTT_BROKER, port=MQTT_PORT)
        print(f"Sent Device Check to Topic {topic}: {payload}")
        
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
        return {"error": "Missing slot_number"}, 400

    db = get_db()
    db.execute('''
        UPDATE slots 
        SET rfid_tag = ?, is_detected = ?, has_bike = ?, last_update = CURRENT_TIMESTAMP 
        WHERE slot_number = ?
    ''', (rfid_tag, is_detected, is_detected, slot_number))
    db.commit()
    
    last_update_time = time.time() # Trigger dashboard refresh
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

if __name__ == '__main__':
    # Initialize DB first before anything else
    print("Initializing Database...")
    init_db()

    # Start all background threads only once (avoid double threads in Flask Debug mode)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        print("Starting background service threads...")
        
        # 1. Local MQTT
        threading.Thread(target=run_mqtt, daemon=True).start()
        
        # 2. API Sync
        threading.Thread(target=api_client_station.sync_station_data_from_api, daemon=True).start()
        
        # 3. Remote Rental & Status MQTT
        threading.Thread(target=mqtt_client_remote.start_mqtt_client, args=(handle_remote_mqtt,), daemon=True).start()
        
        # 4. Remote Payment MQTT
        threading.Thread(target=mqtt_client_payment.start_mqtt_payment_client, args=(handle_payment_received,), daemon=True).start()

    app.run(host='0.0.0.0', debug=True, port=5000)
