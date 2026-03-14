import sqlite3
import qrcode
import io
import time
import json
import threading
import paho.mqtt.client as mqtt
from flask import Flask, render_template, request, redirect, url_for, send_file, Response

app = Flask(__name__)
DATABASE = 'boseh.db'

# MQTT Constants
MQTT_BROKER = "localhost" # Menggunakan Mosquitto Lokal
MQTT_PORT = 1883
MQTT_TOPIC = "boseh/stasiun/update"

# Simple broadcast mechanism
last_update_time = time.time()

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
                is_detected BOOLEAN DEFAULT 0,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create settings table
        db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
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
            ("station_id", "DAG-262-001")
        ]
        
        for key, value in settings_to_seed:
            cursor = db.execute('SELECT COUNT(*) FROM settings WHERE key = ?', (key,))
            if cursor.fetchone()[0] == 0:
                db.execute('INSERT INTO settings (key, value) VALUES (?, ?)', (key, value))
        db.commit()

# Initialize DB on start
init_db()

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
    return render_template('admin.html', slots=slots, settings=settings_dict)

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
    setting_keys = ['running_text', 'station_name', 'station_address', 'total_slots', 'station_id']
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
        global last_update_time
        local_last_update = last_update_time
        while True:
            # Check for actual update
            if local_last_update < last_update_time:
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
    station_id = db.execute('SELECT value FROM settings WHERE key = "station_id"').fetchone()
    qr_text = station_id['value'] if station_id else "Boseh"
    
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
