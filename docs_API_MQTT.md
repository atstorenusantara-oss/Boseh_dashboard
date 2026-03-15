# Dokumentasi Integrasi API dan MQTT (BosehV2)

Dokumen ini menjelaskan alur kerja, integrasi, dan arsitektur komunikasi antara Stasiun Boseh Lokal (Raspberry Pi/PC) dengan Server Pusat (Boseh API Server & MQTT Broker).

---

## 1. Arsitektur Umum
Sistem Node/Stasiun Lokal terbagi menjadi dua jalur komunikasi eksternal utama:
1.  **REST API (HTTP/POST)**: Bertugas untuk melakukan autentikasi awal (Login), mengambil token akses sementara (JWT), dan mendapatkan memori *state* terbaru dari stasiun (nama, alamat stasiun, dan posisi/ketersediaan sepeda pada masing-masing *docking slot*).
2.  **MQTT (TCP)**: Bertugas untuk menunggu/mendengarkan instruksi penyewaan (Rental/Dock Open) secara seketika (*real-time*) tanpa perlu server lokal melakukan *polling* terus menerus ke server pusat.

Data kredensial untuk kedua koneksi ini dikendalikan oleh Tabel `api_credentials` dalam *database* `boseh.db` yang dikonfigurasi melalui layar Administrator (Dashboard Panel).

---

## 2. Integrasi API (Sinkronisasi Data Station)
**File Terkait**: `api_client_station.py`

### Proses Sinkronisasi:
Fungsi utama dari REST API adalah `sync_station_data_from_api()`. Skema kerjanya sebagai berikut:
1. Membaca `client_id` dan `client_secret` (Kata sandi) yang tersimpan di `api_credentials`.
2. Melakukan metode POST HTTP ke `[base_url]/api/station/login`.
3. Jika berhasil (Status 200), server pusat akan mengembalikan struktur JSON berisi Token Session dan Meta-Data Stasiun (`data.station.name`, `data.station.address`, `data.station.num_docking`, dll).
4. Menyimpan Token tersebut ke variabel lokal dan mengisikannya ke `api_credentials` sebagai token login (*JWT*).
5. Secara otomatis mengatur ukuran kapasitas Docking (Menambah atau Menghapus baris/slot sepeda) di tabel `slots` sesuai dengan variabel kapasitas parameter `num_docking`.
6. Melakukan *looping* untuk membaca _Array_ `bikes[]` dari respon JSON, dan me-replace semua slot *docking* terkait (mengubah `has_bike`, menetapkan `rfid_tag`, menanam tag status).

**Pemanggilan**: Proses ini dipicu (ter-_trigger_) dalam *background thread* otomatis sesaat saat `app.py` baru di-_start_. Selain itu, fungsi ini dipanggil secara *sinkron* (menunggu selesai) ketika Admin mengubah dan meng-klik tombol *Simpan* di tab kelola `/admin`.

---

## 3. Integrasi MQTT (Sinyal Real-time / Popup Customer)
**File Terkait**: `mqtt_client_remote.py`

File ini menangani fungsi _listener_ atau pendengar. Menggunakan pustaka *Eclipse Paho-MQTT* (v2).
### Konfigurasi Koneksi:
*   **Host**: Alamat *domain* dicomot langsung dari *base url* stasiun tanpa awalan https (Contoh: `boseh.devserver.my.id`)
*   **Port**: TCP / 1883
*   **Client ID**: Random *UUID* (`import uuid`) – untuk menghindari penolakan koneksi akibat duplikasi pengguna di MQTT Broker.
*   **Username**: Memakai `token` JWT yang didapatkan dari langkah (2).
*   **Password**: Menggunakan *Client Secret* Stasiun.
*   **Topik Langganan (Subscribe)**: `station/[client_id]/dock/open`

### Alur Kerja Rental / Dock Open:
1. `app.py` menjalankan skrip `start_mqtt_client(callback)` sebagai proses latar belakang (*daemon thread*).
2. Begitu server pusat menerbitkan (*publish*) instruksi *Dock Open* ke topik terkait stasiunnya, fungsi *callback* bernama `handle_remote_rental()` di `app.py` akan terpicu (*triggered*).
3. JSON dari MQTT yang berisi biodata kastemer dan data sepeda tersebut ditangkap dan dikemas ke dalam *Event Streaming* (`rent_request`).
4. Web browser menangkap _Event_ tersebut (menggunakan `EventSource` / SSE pada `static/js/script.js`), dan memunculkan **Pop-Up Modal** yang berisi foto dan nama profil Customer selama **5 detik**.
5. Di saat yang sama pada backend Python:
   * Menunggu **5 detik** secara tunda (_Sleep_).
   * Mengupdate Tabel `slots`, mengganti status sepeda menjadi *"Silahkan ambil sepeda"*. (Otomatis tampak pada *Dashboard*)
   * Menunggu tunda lagi **60 detik (1 Menit)**.
   * Mereset kembali status di baris yang sama menjadi status siaga semula (`"ready"`).

---

## 4. Integrasi MQTT Payment (QRIS Pop-up)
**File Terkait**: `mqtt_client_payment.py`, `app.py` (Endpoint `/api/qris`)

File ini menangani fungsi _listener_ tambahan khusus untuk mendengar permintaan pembayaran dari *remote server*. Menggunakan pustaka *Eclipse Paho-MQTT* (v2) dengan konfigurasi yang identik dengan listener Rental.

### Alur Kerja Pesan Payment:
1. `app.py` menjalankan skrip `start_mqtt_payment_client(callback)` sebagai proses latar belakang (*daemon thread*) yang paralel.
2. Skrip terhubung ke broker yang sama, namun melakukan *Subscribe* ke topik: `station/[client_id]/payment`.
3. Begitu aplikasi mobile pelanggan melakukan _checkout_ dan server pusat menerbitkan intsruksi tagihan QRIS ke topik ini, fungsi _callback_ `handle_payment_received()` di `app.py` akan terpicu.
4. JSON dari MQTT yang berisi biodata kastemer dan data pembayaran tersebut ditangkap dan dikemas ke dalam *Event Streaming* dengan tipe (`payment_request`).
5. Web browser menangkap _Event_ tersebut asinkron (menggunakan `EventSource` di `script.js`), dan memanggil fungsi `showPaymentPopup()`.
6. Fungsi di *frontend* akan:
   * Menampilkan **Pop-Up Modal Hijau** (Scan QRIS).
   * Menampilkan Nama Customer serta Nominal Tagihan rupiah yang sudah di-format (contoh: Rp 5.000).
   * Me-_request_ render gambar dari *endpoint* internal `/api/qris?data=...` dengan parameter `qris_content` dari *payload* MQTT.
   * Menampilkan gambar QR Code pembayaran kepada _user_ di layar mandiri.
7. Pop-up ini secara otomatis akan tertutup sendiri dalam waktu **10 detik**.
   
---

## 5. Struktur Database yang Digunakan
*   **`api_credentials`**
    *   `client_id`: ID station (Misal: *station-0001*). Dipakai untuk koneksi login dan Subscribe Topik MQTT, juga sumber teks pencetak *QR-Code* layanan.
    *   `client_secret`: Kata Sandi Station.
    *   `base_url`: Tautan dasar Endpoint (https) untuk Login.
    *   `token`: JWT Sesi login. Dipakai menjadi Username di MQTT.

*   **`settings`**
    *   `station_name`: Nama pajangan stasiun, otomatis diretim oleh API Pusat.
    *   `station_address`: Alamat, otomatis ditimpa oleh API Server.
    *   `total_slots`: Jumlah besaran stasiun. Mengikat jumlah iterasi *Docking*. 

*   **`slots`**
    *   `slot_number`: ID Loket Docking (1, 2, 3...)
    *   `rfid_tag`: `bike_id` (Identitas Seri perangkat sepeda dari server)
    *   `bike_status`: Kolom dinamis Status ('ready', 'waiting', 'Silahkan ambil sepeda') pengerak keterangan Dashboard.

---
_Dibuat secara otomatis saat Setup Modul_
