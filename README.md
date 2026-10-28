# Ruteku — Perencanaan Perjalanan Wisata Berbasis AI dengan Harga Real-Time

> **Tugas Besar / UTS & Code Review Mata Kuliah Implementasi & Pengujian Perangkat Lunak (IPPL)**  
> **Identitas Pengembang**: Nasta'in (NIM: 11241081)  
> **Tautan Video Presentasi & Demo**: [https://youtu.be/8cZWcUy8K04?si=fnklFwoN_IK_vGy2](https://youtu.be/8cZWcUy8K04?si=fnklFwoN_IK_vGy2)

---

## 📌 Ringkasan Proyek

**Ruteku** adalah aplikasi perencana perjalanan wisata (*smart itinerary planner*) berbasis kecerdasan buatan (AI) yang mengintegrasikan estimasi biaya riil secara *real-time* serta kalkulasi jarak dan waktu tempuh antardestinasi.

Aplikasi ini mengatasi kelemahan model perencana konvensional dengan memisahkan secara tegas antara **perencanaan logistik rute oleh AI** dan **perhitungan anggaran serta jarak oleh sistem matematis deterministik**, sehingga terbebas dari risiko halusinasi harga oleh LLM.

---

## 📊 Ketercapaian Progres Fitur SRS (13 Fitur Utama = 65% + 4 Fitur Visual/Mobile)

Berdasarkan dokumen SRS (*Software Requirements Specification*) yang memuat **20 Kebutuhan Fungsional (RF)**, telah diimplementasikan **13 Fitur Utama SRS (65% ketercapaian)** ditambah **4 Fitur Pendukung/Visualisasi Modern**, melampaui target minimal 50%:

### A. 13 Fitur Utama Sesuai Requirement SRS

| Kode RF | Deskripsi Fitur Utama SRS | Implementasi Backend | Antarmuka Frontend | Status Pengujian (180 TC) |
|:---:|:---|:---:|:---:|:---:|
| **RF-01** | **Autentikasi & Pemulihan Akun** (Registrasi, Login, Logout JWT, Bcrypt 12 Rounds, Blacklist Redis, **Lupa & Reset Kata Sandi OTP** dengan batas 5x percobaan, Rate Limit & Brute-Force per IP+Email + Validasi `trusted_proxies`) | ✅ Selesai | ✅ Modal Login, Daftar, & Lupa Sandi | ✅ **31 / 31 PASS** |
| **RF-02** | **Manajemen Profil & Preferensi Default (`UC-04`)** (Ubah Nama Lengkap, Simpan Preferensi Default Kota Asal/Peserta/Budget/Minat Otomatis ke Form, serta **Ubah Kata Sandi** dengan Pencabutan Sesi Lama) | ✅ Selesai | ✅ Modal Profil & Preferensi Default | ✅ **10 / 10 PASS** |
| **RF-03** | **Input Preferensi Perjalanan** (Kota Asal, Tujuan, Tanggal Berangkat/Pulang, Peserta, Budget, Minat Wisata) | ✅ Selesai | ✅ Form Wizard & Kartu Kota Interaktif | ✅ **21 / 21 PASS** |
| **RF-04** | **Generasi Itinerary Wisata Berbasis AI** (OpenAI API + Algoritma Fallback Cerdas Tanpa Pengulangan Destinasi & Prioritas Minat) | ✅ Selesai | ✅ Timeline Harian Visual | ✅ **17 / 17 PASS** |
| **RF-05** | **Pencarian & Filter Katalog Destinasi Wisata** (Bali, Yogyakarta, Labuan Bajo, Derawan) | ✅ Selesai | ✅ Halaman Katalog & Filter Kategori | ✅ **12 / 12 PASS** |
| **RF-06** | **Integrasi Harga Real-Time** (Adapter OTA + Redis Cache TTL 30 Menit + Fallback Stale Data) | ✅ Selesai | ✅ Rincian Tiket & Akomodasi | ✅ **12 / 12 PASS** |
| **RF-08** | **Kalkulasi Estimasi Anggaran & Deteksi Status Over-Budget** | ✅ Selesai | ✅ Progress Bar & Grafik Donut Biaya | ✅ **11 / 11 PASS** |
| **RF-09** | **Penyimpanan Draf Rencana Perjalanan ke Basis Data** (Dilengkapi Proteksi Idempotent Anti-Duplikat) | ✅ Selesai | ✅ Tombol Simpan 1-Klik | ✅ **13 / 13 PASS** |
| **RF-10** | **Pengeditan Rencana Perjalanan** (`PATCH /itineraries/{id}`: Ubah Judul, Peserta, Anggaran, Tambah/Hapus/Atur Jam Destinasi Harian + **Hitung Ulang Biaya Otomatis** di Server) | ✅ Selesai | ✅ Modal Edit Rencana Interaktif | ✅ **9 / 9 PASS** |
| **RF-11** | **Penghapusan Rencana Perjalanan (`UC-13`)** (Konfirmasi Hapus + Pencabutan Otomatis *Shareable Link* di DB & Redis) | ✅ Selesai | ✅ Tombol Hapus di Riwayat & Detail | ✅ **12 / 12 PASS** |
| **RF-13** | **Riwayat Perjalanan Pengguna & Penampil Rincian Rencana** (Dilengkapi Paginasi `limit`/`offset` & Header `X-Total-Count`) | ✅ Selesai | ✅ Halaman Rencana Saya & Detail Modal | ✅ **13 / 13 PASS** |
| **RF-14** | **Berbagi Rencana Perjalanan via Tautan Unik (`UC-16`)** (Akses Publik *Read-Only* Tanpa Login `/?share=<token>` + Tabel `ShareLink` dengan Masa Berlaku 7 Hari) | ✅ Selesai | ✅ Tombol Bagikan & Mode Read-Only | ✅ **13 / 13 PASS** |
| **RF-20** | **Integrasi Peta Interaktif & Kalkulasi Jarak/Waktu Tempuh** (Rumus *Haversine* × 1.25 Jarak Jalan Raya & Estimasi Waktu Tempuh Menit Antar Destinasi + Endpoint `/route-metrics`) | ✅ Selesai | ✅ Peta Rute Leaflet + Badge Jarak & Waktu | ✅ **6 / 6 PASS** |

### B. 4 Fitur Pendukung & Visualisasi Modern (Web & Mobile)

1. **Peta Rute Interaktif (`Leaflet.js`) & Indikator Jarak**: Menampilkan pin bernomor sesuai urutan kunjungan harian, garis rute antardestinasi, serta badge jarak (`± km`) dan waktu tempuh (`~menit`).
2. **Grafik Donut Proporsi Biaya & Cetak PDF (`window.print()`)**: Visualisasi persentase *Akomodasi vs Transportasi vs Tiket* serta dukungan cetak dokumen itinerary rapi.
3. **Akses Mobile Instan via QR Code (`Buka di HP`)**: Endpoint `/network-info` mendeteksi IP lokal (Wi-Fi/Hotspot) secara otomatis dan menyajikan QR Code agar aplikasi bisa langsung dibuka dari kamera smartphone.
4. **Progressive Web App (`manifest.json`) & Navigasi Mobile**: Mendukung *Add to Home Screen* di Android/iOS dengan *Bottom Navigation Bar* khusus layar sentuh.

---

## 🧪 Code Review, Refactoring, & Pengujian 180 Test Case Otomatis

Proyek ini dilengkapi suite pengujian otomatis komprehensif di [`backend/review_runner.py`](backend/review_runner.py) yang mengeksekusi **180 Test Case** nyata terhadap aplikasi menggunakan `FastAPI TestClient`, `SQLite`, dan `fakeredis`, serta langsung menghasilkan laporan Excel Code Review di [`review/Code_Review_Ruteku.xlsx`](review/Code_Review_Ruteku.xlsx).

### Ringkasan Hasil Eksekusi Test Case (`180 / 180 PASS — 100%`)

| Fitur SRS | Total TC | Happy Path | Bad Case (+ Security) | Blocker | PASS | FAIL |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **RF-01 Autentikasi** | 31 | 7 | 21 | 3 | **31** | 0 |
| **RF-02 Manajemen Profil** | 10 | 3 | 5 | 2 | **10** | 0 |
| **RF-03 Input Preferensi** | 21 | 4 | 14 | 3 | **21** | 0 |
| **RF-04 Itinerary AI** | 17 | 4 | 11 | 2 | **17** | 0 |
| **RF-05 Pencarian Destinasi** | 12 | 5 | 6 | 1 | **12** | 0 |
| **RF-06 Harga Real-Time** | 12 | 5 | 5 | 2 | **12** | 0 |
| **RF-08 Estimasi Anggaran** | 11 | 5 | 5 | 1 | **11** | 0 |
| **RF-09 Simpan Rencana** | 13 | 4 | 7 | 2 | **13** | 0 |
| **RF-10 Edit Rencana** | 9 | 3 | 4 | 2 | **9** | 0 |
| **RF-11 Hapus Rencana** | 12 | 4 | 5 | 3 | **12** | 0 |
| **RF-13 Riwayat Perjalanan** | 13 | 5 | 6 | 2 | **13** | 0 |
| **RF-14 Berbagi Rencana** | 13 | 3 | 7 | 3 | **13** | 0 |
| **RF-20 Peta & Metrik Rute** | 6 | 2 | 2 | 2 | **6** | 0 |
| **TOTAL KESELURUHAN** | **180** | **54** | **98** | **28** | **180** | **0** |

### Cakupan Pengujian Keamanan & Blocker (28 Temuan `F-01` s/d `F-28`)
- **Keamanan (*Security Bad Cases*)**: Proteksi *SQL Injection*, *Wildcard LIKE Injection (`%`/`_`)*, *Stored & Reflected XSS*, *IDOR (akses/edit/hapus/bagikan/route-metrics rencana pengguna lain)*, *Cross-City Destination Tampering*, *JWT Signature Tampering & `alg:none`*, *Session Revocation saat Ganti/Reset Sandi*, *Timing Attack (Constant-Time Dummy Hash)*, *Bcrypt 72-Byte Overflow Protection*, *Prompt Injection Filter*, *Replay & Brute-Force OTP Protection (maks 5x)*, *X-Forwarded-For Spoofing Protection (`trusted_proxies`)*, serta *Brute-Force & Registration Rate Limiting per IP*.
- **Ketahanan Sistem (*Blocker*)**: Simulasi database terputus (`SQLAlchemyError` → `HTTP 503`), Redis mati di tengah jalan (`RedisError` → `HTTP 503` / *direct provider fallback*), serta OpenAI API timeout/invalid JSON (`_fallback` otomatis).

---

## 🚀 Panduan Menjalankan Aplikasi (Desktop & Mobile)

### Cara Paling Mudah (1-Klik di Windows)
Cukup klik 2x file **[`Jalankan_Ruteku.bat`](Jalankan_Ruteku.bat)** di folder utama proyek. Script akan otomatis membersihkan port `8000` jika ada proses lama yang menyangkut, menyalakan server FastAPI, dan membuka `http://localhost:8000` di browser.

### Cara Manual lewat Terminal
```powershell
cd backend
$env:PYTHONPATH = "$PWD\.venv\Lib\site-packages;$PWD"
& "$env:APPDATA\uv\python\cpython-3.12-windows-x86_64-none\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Akses melalui peramban web:
- 💻 **Di Laptop**: [http://localhost:8000/](http://localhost:8000/)
- 📱 **Di Smartphone (HP)**: Klik tombol **"Buka di HP"** di pojok kanan atas website pada laptop lalu scan **QR Code** yang tampil.
- 📖 **Dokumentasi Interaktif API (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Cara Menjalankan Test Runner Otomatis (180 Test Case)

```powershell
cd backend
$env:PYTHONPATH = "$PWD\.venv\Lib\site-packages;$PWD"
& "$env:APPDATA\uv\python\cpython-3.12-windows-x86_64-none\python.exe" review_runner.py
```
File spreadsheet hasil pengujian otomatis akan tersimpan di [`review/Code_Review_Ruteku.xlsx`](review/Code_Review_Ruteku.xlsx) (terdiri dari 4 sheet: `Info`, `Testcase`, `Temuan Review`, dan `Ringkasan`).

---

## 📁 Struktur Direktori

```text
ruteku/
├── .gitignore                      # Berkas yang dikecualikan dari repositori Git
├── docker-compose.yml              # Konfigurasi container PostgreSQL & Redis
├── Jalankan_Ruteku.bat             # Peluncur 1-klik server web & mobile di Windows
├── README.md                       # Dokumentasi utama proyek, 13 fitur SRS, & pengujian
├── frontend/
│   ├── index.html                  # Antarmuka web & mobile responsif (Tailwind + Leaflet JS)
│   └── manifest.json               # Konfigurasi Progressive Web App (PWA) untuk Mobile
├── review/
│   ├── Code_Review_Ruteku.xlsx     # Spreadsheet Code Review & 180 Test Case (4 Sheet)
│   └── hasil_review.json           # Hasil eksekusi nyata 180 test case dalam format JSON
└── backend/
    ├── .env.example                # Template konfigurasi environment yang aman
    ├── requirements.txt            # Daftar pustaka Python yang dibutuhkan
    ├── review_runner.py            # Test runner otomatis 180 test case & generator Excel
    ├── smoke_test.py               # Pengujian cepat alur utama end-to-end
    ├── test_flow.py                # Skrip uji alur API
    └── app/
        ├── main.py                 # Entrypoint FastAPI, 13 fitur SRS, & exception handler
        ├── config.py               # Konfigurasi aplikasi (Pydantic Settings, trusted_proxies)
        ├── db.py                   # Abstraksi basis data SQLAlchemy
        ├── models.py               # Skema tabel User, UserPreference, Destination, Itinerary, ShareLink
        ├── schemas.py              # Validasi skema request/response Pydantic ketat
        ├── security.py             # Autentikasi JWT, Bcrypt 72-byte safe, pencabutan sesi
        ├── cache.py                # Lapisan caching Redis & fallback FakeRedis
        ├── prices.py               # Provider adapter harga real-time & mitigasi stale
        ├── ai.py                   # Modul generasi rute AI + sanitasi prompt + fallback cerdas
        └── seed.py                 # Seeding awal katalog destinasi wisata populer
```
