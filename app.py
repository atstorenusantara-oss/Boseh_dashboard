import sqlite3
import qrcode
import io
import time
import json
import threading
import paho.mqtt.client as mqtt
from flask import Flask, render_template, request, redirect, url_for, send_file, Response
import api_client_station
import mqtt_client_remote

app = Flask(__name__)
DATABASE = 'boseh.db'

# MQTT Constants
MQTT_BROKER = "localhost" # Menggunakan Mosquitto Lokal
MQTT_PORT = 1883
MQTT_TOPIC = "boseh/stasiun/update"

# Simple broadcast mechanism
last_update_time = time.time()
latest_event = None
latest_event_time = time.time()

# ---------------------------------------------------------
# MQTT CLIENT OVERVIEW
# ---------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global last_update_time
    try:
        data = json.loads(msg.payload.decode())
        slot_num = data.get('slot_number')
        tag = data.get('rfid_tag')
        status = data.get('status')
        
        if slot_num is not None:
            # We use a context manager to ensure DB is updated
            with app.app_context():
                db = get_db()
                db.execute('''
                    UPDATE slots 
                    SET rfid_tag = ?, is_detected = ?, has_bike = ?, last_update = CURRENT_TIMESTAMP 
                    WHERE slot_number = ?
                ''', (tag, status, status, slot_num))
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

# Start MQTT thread
mqtt_thread = threading.Thread(target=run_mqtt, daemon=True)
mqtt_thread.start()
# ---------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DATABASE)
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
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migrations for slots
        try:
            db.execute("ALTER TABLE slots ADD COLUMN bike_status TEXT")
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

# Initialize DB on start
init_db()

# Run API sync in background when app starts via external module
api_sync_thread = threading.Thread(target=api_client_station.sync_station_data_from_api, daemon=True)
api_sync_thread.start()

def handle_remote_rental(data):
    """Callback function when a dock open (rent) request arrives from remote API MQTT."""
    global last_update_time, latest_event_time, latest_event
    latest_event = {"type": "rent_request", "data": data}
    latest_event_time = time.time()
    last_update_time = time.time()

    def update_status_after_delay():
        time.sleep(5)
        with app.app_context():
            db = get_db()
            docking_id = data.get('bike', {}).get('docking_id')
            if docking_id is not None:
                db.execute("UPDATE slots SET bike_status = 'Silahkan ambil sepeda' WHERE slot_number = ?", (docking_id,))
                db.commit()
            
            global last_update_time
            last_update_time = time.time()
            
        # Reset back to ready after 1 minute (60 seconds)
        time.sleep(60)
        with app.app_context():
            db = get_db()
            if docking_id is not None:
                # Optional: You may want to check if the status is STILL 'Silahkan ambil sepeda'
                # before setting it to 'ready', just in case someone manually removed the bike.
                db.execute("UPDATE slots SET bike_status = 'ready' WHERE slot_number = ? AND bike_status = 'Silahkan ambil sepeda'", (docking_id,))
                db.commit()
            
            last_update_time = time.time()

    threading.Thread(target=update_status_after_delay, daemon=True).start()

# Run External API MQTT client
remote_mqtt_thread = threading.Thread(target=mqtt_client_remote.start_mqtt_client, args=(handle_remote_rental,), daemon=True)
remote_mqtt_thread.start()

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

# API for dynamic slot updates (AJAX)
# API for dynamic slot updates (AJAX)
@app.route('/api/slots')
def api_slots():
    db = get_db()
    slots = db.execute('SELECT * FROM slots ORDER BY slot_number').fetchall()
    return {"slots": [dict(s) for s in slots]}

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
