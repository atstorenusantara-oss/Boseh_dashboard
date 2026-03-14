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
- **Logika:** Mengambil nilai `station_id` dari tabel `settings` dan mengubahnya menjadi QR Code secara real-time.

## 4. Endpoint Pengaturan (Internal)

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
