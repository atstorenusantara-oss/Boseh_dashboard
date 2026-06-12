# Panduan Deployment Boseh V2 di Mini PC Linux (Lubuntu 24.04 LTS)

Dokumen ini berisi panduan lengkap langkah demi langkah untuk menginstal OS Lubuntu 24.04 LTS di Mini PC Kiosk, memindahkan program Boseh V2, mengonfigurasi perizinan port serial USB, mengaktifkan mode autostart (Kiosk), dan mengatur jadwal mati otomatis.

---

## 1. Persiapan Media Instalasi

### Tautan Unduh Resmi
*   **Halaman Unduh Utama:** [Lubuntu Downloads Page](https://lubuntu.me/downloads/)
*   **Tautan Unduh ISO Langsung:** [Index of /lubuntu/releases/24.04/release/](https://cdimage.ubuntu.com/lubuntu/releases/24.04/release/) (Pilih berkas berakhiran `.iso`, contohnya: `lubuntu-24.04-desktop-amd64.iso`).

### Membuat USB Bootable (Melalui Windows)
1.  Colokkan Flashdisk kosong (minimal 8 GB) ke PC/Laptop Anda.
2.  Unduh dan jalankan aplikasi **Rufus** dari [rufus.ie](https://rufus.ie/).
3.  Pada **Device**, pilih Flashdisk Anda.
4.  Pada **Boot selection**, klik **SELECT** dan arahkan ke file ISO Lubuntu yang telah diunduh.
5.  Biarkan pengaturan partisi pada mode **GPT** dan target system **UEFI**.
6.  Klik **START** -> pilih **Write in ISO Image mode** -> **OK** dan tunggu hingga selesai (status **READY**).

---

## 2. Proses Instalasi Lubuntu di Mini PC

1.  Colokkan Flashdisk bootable ke port USB Mini PC (sangat disarankan port USB 3.0 berwarna biru).
2.  Nyalakan Mini PC dan tekan tombol **Boot Menu** secara berulang-ulang hingga daftar perangkat boot muncul.
    *   *ASUS / Intel NUC / Asrock:* Tekan tombol `F8`.
    *   *Gigabyte / Lenovo / Dell:* Tekan tombol `F12`.
    *   *HP:* Tekan tombol `F9`.
3.  Pilih Flashdisk Anda (biasanya berlabel **UEFI: [Nama Flashdisk]**) lalu tekan Enter.
4.  Pada menu GRUB hitam, pilih **"Try or Install Lubuntu"** dan tekan Enter.
5.  Setelah masuk ke desktop sementara Lubuntu, klik ganda pada ikon **"Install Lubuntu 24.04 LTS"**.
6.  Ikuti petunjuk konfigurasi bahasa, lokasi/timezone (pilih *Asia/Jakarta*), dan keyboard layout.
7.  Pada bagian partisi, pilih **"Erase disk"** agar instalasi bersih dan menghapus OS lama di Mini PC.
8.  Pada bagian pengisian User Account:
    *   Masukkan nama, username (misal: `boseh`), dan password Anda.
    *   **WAJIB CENTANG** opsi **"Log in automatically without asking for the password"** agar stasiun otomatis masuk desktop setelah dinyalakan tanpa tertahan halaman login.
9.  Klik **Install** -> **Install Now** dan tunggu hingga proses 100% selesai.
10. Klik **Done** untuk restart, cabut Flashdisk ketika layar meminta mencabut media, lalu tekan Enter.

---

## 3. Konfigurasi Lingkungan Program di Linux

### Langkah 1: Instalasi Library Dasar
Buka Terminal (`Ctrl + Alt + T`) pada Lubuntu, lalu jalankan perintah berikut:
```bash
sudo apt update
sudo apt install git python3-pip python3-venv python3-full -y
```

### Langkah 2: Setup Folder Program & Python Virtual Environment
Pindahkan atau kloning repositori Boseh V2 ke direktori home Anda (contoh: `/home/boseh/BosehV2`):
```bash
cd /home/boseh/BosehV2

# Membuat virtual environment terisolasi
python3 -m venv venv

# Mengaktif;kan virtual environment
source venv/bin/activate

# Menginstal dependensi python
pip install -r requirements.txt
```

### Langkah 3: Memberikan Izin Akses Port Serial USB
Secara default, Linux memproteksi port serial USB. Agar program Python bisa berkomunikasi dengan ESP32 Gateway (terdeteksi sebagai `/dev/ttyUSB0` atau `/dev/ttyACM0`), tambahkan user Anda ke grup `dialout`:
```bash
sudo usermod -a -G dialout $USER
```
> [!IMPORTANT]
> Anda harus melakukan restart pada Mini PC agar perubahan izin akses port serial ini diterapkan secara permanen oleh Linux.

### Langkah 4: Instalasi Dependensi GUI Kiosk (`pywebview`)
Agar jendela aplikasi desktop dapat tampil fullscreen di Linux, pasang paket WebKit2GTK sistem berikut:
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 -y

# Pastikan library terinstall di dalam virtual environment Anda
source venv/bin/activate
pip install pywebview
```

---

## 4. Konfigurasi Autostart (Boot to Kiosk)

Agar aplikasi langsung berjalan secara otomatis begitu Mini PC dihidupkan:

1.  Buat berkas script shell bernama `start_boseh.sh` di dalam folder program Anda:
    ```bash
    nano start_boseh.sh
    ```
2.  Masukkan script berikut:
    ```bash
    #!/bin/bash
    # Nonaktifkan screensaver & mode tidur layar
    xset s off
    xset s noblank
    xset -dpms

    sleep 5 # Menunggu 5 detik agar desktop environment siap sepenuhnya
    cd /home/boseh/BosehV2
    source venv/bin/activate
    python app.py
    ```
3.  Simpan berkas (`Ctrl + O` -> `Enter` -> `Ctrl + X`).
4.  Beri izin eksekusi pada berkas tersebut:
    ```bash
    chmod +x start_boseh.sh
    ```
5.  Daftarkan script ke Autostart sistem Lubuntu:
    *   Buka **Menu Utama** (pojok kiri bawah) -> **Preferences** -> **LXQt Settings** -> **Session Settings**.
    *   Klik menu **Autostart** di panel kiri.
    *   Klik tombol **Add** (Tambah).
    *   Isi nama: `Boseh Dashboard`.
    *   Pada kolom **Command**, klik Browse dan arahkan ke file `/home/boseh/BosehV2/start_boseh.sh` yang telah dibuat.
    *   Klik **OK** dan Simpan.

---

## 5. Konfigurasi Jadwal Mati Otomatis (Auto Shutdown)

### Penyesuaian Kode `app.py`
Perintah shutdown default di program menggunakan perintah CMD Windows. Anda harus mengubah perintah tersebut di file `app.py` agar menggunakan perintah shutdown Linux:
*   Cari fungsi `auto_shutdown_loop` dan route `/api/shutdown` di `app.py`.
*   Ubah perintah `os.system("shutdown /s /t 30")` menjadi **`os.system("sudo poweroff")`**.

### Membypass Password Prompt Sudo untuk Shutdown
Karena program Flask berjalan tanpa akses root sedangkan perintah `poweroff` memerlukan root, Anda perlu mendaftarkan izin khusus bebas password untuk perintah shutdown:
1.  Buka terminal Linux dan jalankan editor sudoers:
    ```bash
    sudo visudo
    ```
2.  Tambahkan baris berikut di bagian paling bawah file:
    ```text
    boseh ALL=(ALL) NOPASSWD: /usr/sbin/poweroff
    ```
    *(Ganti `boseh` dengan username Linux yang Anda buat).*
3.  Simpan dan keluar dari editor `visudo`.

---

## 6. Deployment Menggunakan Docker (Rekomendasi Arsitektur Hybrid)

Metode ini sangat direkomendasikan karena mengisolasi Flask server, PySerial, SQLite database, dan MQTT Client di dalam container Docker, sedangkan tampilan visual GUI diluncurkan secara native menggunakan browser Chromium host (Kiosk Mode) guna menghindari bug rendering library visual desktop GUI di dalam container.

### Langkah 1: Memilah Berkas untuk PC Linux
Salin hanya berkas/folder penting berikut dari PC Windows ke folder `/home/boseh/BosehV2` di PC Linux:
*   `app.py`
*   `requirements.txt`
*   `Dockerfile`
*   `docker-compose.yml`
*   `boseh.db` (Database awal stasiun)
*   `sub_programPY/` (Folder)
*   `templates/` (Folder)
*   `static/` (Folder)

*(Anda bisa mengabaikan berkas `*.bat`, `*.spec`, folder `build/`, `dist/`, `offline_setup/`, dan `installres/`)*.

### Langkah 2: Instalasi Docker di Lubuntu
Buka terminal Linux (`Ctrl + Alt + T`) lalu jalankan perintah berikut untuk menginstal dependensi Docker:
```bash
sudo apt update
# Hapus repo AnyDesk jika ada masalah/error update apt
sudo rm -f /etc/apt/sources.list.d/anydesk*.list

# Install Docker & Docker Compose V2 bawaan Ubuntu
sudo apt install docker.io docker-compose-v2 -y

# Daftarkan user ke grup docker & dialout (port serial)
sudo usermod -a -G docker $USER
sudo usermod -a -G dialout $USER
```
> [!IMPORTANT]
> Lakukan **Restart (Reboot)** pada PC Linux agar hak akses grup baru ini diterapkan secara permanen oleh sistem.

### Langkah 3: Menjalankan Container
1. Buka folder proyek di terminal Linux:
   ```bash
   cd /home/boseh/BosehV2
   ```
2. Jalankan docker compose untuk membangun dan menyalakan container backend:
   ```bash
   docker compose up -d --build
   ```
3. Cek log kontainer untuk memastikan backend berjalan lancar dan mendeteksi port serial:
   ```bash
   docker logs -f boseh-backend
   ```

### Langkah 4: Konfigurasi Kiosk Autostart (Menampilkan Layar di Host)
Agar layar monitor stasiun otomatis meluncurkan web dashboard fullscreen saat komputer dinyalakan:
1. Buat skrip shell launcher di host:
   ```bash
   nano start_kiosk.sh
   ```
2. Masukkan kode berikut (menyertakan penonaktifan screensaver & display power management):
   ```bash
   #!/bin/bash
   # Nonaktifkan screensaver & mode tidur layar
   xset s off
   xset s noblank
   xset -dpms

   sleep 8 # Menunggu docker container siap
   chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run --ozone-platform=x11 http://localhost:5000
   ```
3. Simpan berkas (`Ctrl + O` -> `Enter` -> `Ctrl + X`) dan berikan izin eksekusi:
   ```bash
   chmod +x start_kiosk.sh
   ```
4. Daftarkan `start_kiosk.sh` ke autostart sistem Lubuntu:
   * Buka **Menu Utama** -> **Preferences** -> **LXQt Settings** -> **Session Settings**.
   * Klik menu **Autostart** di panel kiri, lalu klik **Add** (Tambah).
   * Isi Nama: `Boseh Kiosk Browser`.
   * Pada kolom **Command**, arahkan ke file `/home/boseh/BosehV2/start_kiosk.sh`.
   * Klik **OK** dan Simpan.

---

## 7. Troubleshooting & Perintah Bantuan

### Konflik Nama Kontainer (Error: Container name already in use)
Jika mendapatkan error konflik nama saat menjalankan container, hapus paksa kontainer lama dan bersihkan sisa-sisa docker compose:
```bash
# Hapus paksa container lama
docker rm -f boseh-backend

# Bersihkan sisa environment docker compose
docker compose down

# Jalankan ulang
docker compose up -d --build
```

### Mengakses Log Docker Backend
```bash
docker logs -f boseh-backend
```

### Menghentikan Container Backend
```bash
docker compose down
```
