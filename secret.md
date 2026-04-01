# 🔐 Dokumen Strategi Keamanan & Penguncian Aplikasi Boseh V2

Dokumen ini berisi rencana teknis untuk mengunci aplikasi dan melindungi hak kekayaan intelektual (IP) agar tidak disalahgunakan atau dikopi tanpa izin saat instalasi di 20 station.

---

## 1. Strategi Penguncian Perangkat (Hardware Binding)
Untuk mencegah aplikasi dikopi ke PC lain dan dijalankan tanpa izin, aplikasi harus divalidasi berdasarkan **Hardware ID (HWID)**.

### Rencana Teknis:
*   Ambil **Motherboard Serial Number** atau **Disk ID** menggunakan library `subprocess` atau `wmi`.
*   Simpan daftar Serial Number yang diizinkan (Whitelisting).
*   Jika ID perangkat tidak cocok, aplikasi akan memblokir akses ke dashboard utama.

**Snippet Implementasi (Python):**
```python
import subprocess

def get_hwid():
    try:
        # Mengambil serial number motherboard via WMIC
        cmd = "wmic baseboard get serialnumber"
        serial = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
        return serial
    except:
        return "UNKNOWN"

ALLOWED_HWIDS = ["XYZ-123", "ABC-456"] # Daftar 20 PC Station Anda

def check_activation():
    my_id = get_hwid()
    if my_id not in ALLOWED_HWIDS:
        print(f"❌ UNAUTHORIZED DEVICE: {my_id}")
        # Logika untuk stop server atau tampilkan halaman blokir
```

---

## 2. Proteksi Akses Admin (Menu Panel)
Mencegah petugas atau pihak luar mengubah konfigurasi station, alamat API, dan kredensial.

### Rencana Teknis:
*   Tambahkan **PIN / Password** statis untuk rute `/admin` dan `/maintenance`.
*   Simpan password dalam bentuk hash di database atau file konfigurasi tersembunyi.
*   Gunakan Flask Session untuk menjaga status login selama 30 menit.

---

## 3. Identitas Karya (Watermarking & Branding)
Memastikan jejak pembuat tidak bisa dihapus dengan mudah dari tampilan luar.

### Rencana Teknis:
*   **Invisible Branding:** Menambahkan komentar HTML di source code `<!-- Developed by [Nama Anda] - 08xxxxxxxxxx -->`.
*   **Visual Branding:** Menambahkan teks kecil di footer dashboard yang tidak mengganggu estetika tapi tetap terlihat.
*   **Console Branding:** Mencetak banner ASCII Art saat server Python (`app.py`) pertama kali dijalankan.

---

## 4. Compile ke Executable (.exe)
Langkah akhir untuk menyembunyikan source code aslinya agar tidak bisa diedit secara teks biasa oleh user di station.

### Alat yang Digunakan:
*   **PyInstaller:** Mengemas seluruh folder project menjadi satu folder `dist` yang berisi file executable.
*   **Command:** `pyinstaller --noconsole --add-data "templates;templates" --add-data "static;static" app.py`

---

## 5. Sinkronisasi Lisensi Online (Opsional)
Jika di masa depan Anda ingin kontrol penuh dari jarak jauh:
*   Aplikasi melakukan "Heartbeat" ke server pusat setiap 24 jam.
*   Jika pembayaran/kontrak selesai, Anda bisa mematikan akses dari server pusat secara remote.

---
Dokumen ini bersifat rahasia untuk penggunaan internal pengembang.
