# Dokumentasi Dashboard & Admin API V1

Dokumen ini menjelaskan struktur URL dan fitur yang tersedia pada aplikasi Boseh Dashboard.

## 1. Halaman Tampilan (Web Interface)

| URL | Deskripsi |
| :--- | :--- |
| `/` | **Dashboard Utama**: Menampilkan status stasiun, jam real-time, docking sepeda, dan running text. |
| `/admin` | **Halaman Pengaturan**: Mengelola nama stasiun, alamat, ID stasiun, jumlah slot, dan status manual sepeda. |

## 2. Fitur Real-Time (SSE)

Dashboard menggunakan **Server-Sent Events (SSE)** untuk memantau perubahan data tanpa perlu refresh manual.

- **URL Stream:** `/stream`
- **Tipe Event:** `data: refresh`
- **Cara Kerja:** Browser akan mendengarkan event dari server. Jika ada perubahan di database (baik dari Admin maupun IoT), server mengirimkan sinyal `refresh` dan dashboard akan memuat ulang data secara otomatis.

## 3. Fitur QR Code Dinamis

QR Code digenerate secara otomatis berdasarkan **ID Stasiun** yang diatur di database.

- **URL Gambar:** `/qrcode`
- **Method:** `GET`
- **Format:** Image (PNG)
- **Logika:** Mengambil nilai `station_id` dari tabel `api_credentials` dan mengubahnya menjadi QR Code secara real-time.

---

## 4. Struktur Backend & Otomatisasi
Proyek telah diperbarui dengan pemisahan modul di folder `sub_programPY/` untuk efisiensi dan skalabilitas.

### Modul Utama (`sub_programPY/`)
- `api_client_station.py`: Sinkronisasi data stasiun dari API Pusat.
- `mqtt_client_remote.py`: Menangani perintah pembukaan dock jarak jauh (Rent). **Dinamis**: Otomatis reconnect jika URL/Client ID berubah.
- `mqtt_client_payment.py`: Mendeteksi notifikasi pembayaran masuk. **Dinamis**: Otomatis reconnect jika URL/Client ID berubah.
- `api_confirm_open.py`: Memverifikasi pembukaan dock ke API Pusat (Triggered by Local MQTT).
- `api_return.py`: Melakukan proses pengembalian sepeda ke API Pusat (Triggered by Local MQTT).

### Fitur Dynamic Reconnection
Modul MQTT Remote dan Payment dikonfigurasi untuk terus memantau database. Jika user mengubah Client ID atau Token melalui halaman `/admin`, modul ini akan mendeteksi perubahan tersebut dan melakukan koneksi ulang ke broker tanpa perlu mematikan aplikasi server.

---

## 5. Endpoint Pengaturan (Internal)

Digunakan oleh formulir di halaman Admin untuk memperbarui konfigurasi.

| Endpoint | Method | Deskripsi |
| :--- | :--- | :--- |
| `/update_settings` | `POST` | Memperbarui Nama Stasiun, Alamat, ID Stasiun, Running Text, dan Jumlah Slot. |
| `/toggle_slot/<id>` | `GET` | Merubah status keberadaan sepeda (True/False) secara manual pada slot tertentu. |

---

## Struktur Database (SQLite)

### Tabel: `settings`
Menampilkan konfigurasi global stasiun.
- `key`: Kunci pengaturan (misal: `station_name`).
- `value`: Nilai pengaturan.

### Tabel: `slots`
Menampilkan status fisik setiap slot docking.
- `slot_number`: Nomor identifikasi fisik slot.
- `has_bike`: Status ketersediaan sepeda (1/0).
- `rfid_tag`: ID Kartu RFID unik dari IoT.
- `is_detected`: Status deteksi sensor IoT.
- `last_update`: Timestamp terakhir data masuk.
