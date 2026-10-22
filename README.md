# Ruteku — Perencanaan Perjalanan Wisata Berbasis AI dengan Harga Real-Time

> **Tugas Besar / UTS & Code Review Mata Kuliah Implementasi & Pengujian Perangkat Lunak (IPPL)**  
> **Identitas Pengembang**: Nasta'in (NIM: 11241081)  
> **Tautan Video Presentasi & Demo**: [https://youtu.be/8cZWcUy8K04?si=fnklFwoN_IK_vGy2](https://youtu.be/8cZWcUy8K04?si=fnklFwoN_IK_vGy2)

---

## 📌 Ringkasan Proyek

**Ruteku** adalah aplikasi perencana perjalanan wisata (*smart itinerary planner*) berbasis kecerdasan buatan (AI) yang mengintegrasikan estimasi biaya riil secara *real-time*.

Aplikasi ini mengatasi kelemahan model perencana konvensional dengan memisahkan secara tegas antara **perencanaan logistik rute oleh AI** dan **perhitungan anggaran oleh sistem matematis deterministik**, sehingga terbebas dari risiko halusinasi harga oleh LLM.

---

## 📊 Ketercapaian Progres Fitur SRS (10 Fitur Utama = 50% + 4 Fitur Visual/Mobile)

Berdasarkan dokumen SRS (*Software Requirements Specification*) yang memuat **20 Kebutuhan Fungsional (RF)**, telah diimplementasikan **10 Fitur Utama SRS (50% ketercapaian)** ditambah **4 Fitur Pendukung/Visualisasi Modern**, melampaui ambang batas minimal 30%:

### A. 10 Fitur Utama Sesuai Requirement SRS

| Kode RF | Deskripsi Fitur Utama SRS | Implementasi Backend | Antarmuka Frontend | Status Pengujian (149 TC) |
|:---:|:---|:---:|:---:|:---:|
| **RF-01** | **Autentikasi & Pemulihan Akun** (Registrasi, Login, Logout JWT, Bcrypt 12 Rounds, Blacklist Redis, **Lupa & Reset Kata Sandi OTP**, Rate Limit & Brute-Force per IP+Email) | ✅ Selesai | ✅ Modal Login, Daftar, & Lupa Sandi | ✅ **27 / 27 PASS** |
| **RF-03** | **Input Preferensi Perjalanan** (Kota Asal, Tujuan, Tanggal Berangkat/Pulang, Peserta, Budget, Minat Wisata) | ✅ Selesai | ✅ Form Wizard & Kartu Kota Interaktif | ✅ **21 / 21 PASS** |
| **RF-04** | **Generasi Itinerary Wisata Berbasis AI** (OpenAI API + Algoritma Fallback Cerdas Tanpa Pengulangan Destinasi & Prioritas Minat) | ✅ Selesai | ✅ Timeline Harian Visual | ✅ **17 / 17 PASS** |
| **RF-05** | **Pencarian & Filter Katalog Destinasi Wisata** (Bali, Yogyakarta, Labuan Bajo, Derawan) | ✅ Selesai | ✅ Halaman Katalog & Filter Kategori | ✅ **12 / 12 PASS** |
| **RF-06** | **Integrasi Harga Real-Time** (Adapter OTA + Redis Cache TTL 30 Menit + Fallback Stale Data) | ✅ Selesai | ✅ Rincian Tiket & Akomodasi | ✅ **12 / 12 PASS** |
| **RF-08** | **Kalkulasi Estimasi Anggaran & Deteksi Status Over-Budget** | ✅ Selesai | ✅ Progress Bar & Grafik Donut Biaya | ✅ **11 / 11 PASS** |
| **RF-09** | **Penyimpanan Draf Rencana Perjalanan ke Basis Data** (Dilengkapi Proteksi Idempotent Anti-Duplikat) | ✅ Selesai | ✅ Tombol Simpan 1-Klik | ✅ **13 / 13 PASS** |
| **RF-11** | **Penghapusan Rencana Perjalanan (`UC-13`)** (Konfirmasi Hapus + Pencabutan Otomatis *Shareable Link*) | ✅ Selesai | ✅ Tombol Hapus di Riwayat & Detail | ✅ **12 / 12 PASS** |
| **RF-13** | **Riwayat Perjalanan Pengguna & Penampil Rincian Rencana** (Dilengkapi Paginasi `limit` & `offset`) | ✅ Selesai | ✅ Halaman Rencana Saya & Detail Modal | ✅ **12 / 12 PASS** |
| **RF-14** | **Berbagi Rencana Perjalanan via Tautan Unik (`UC-16`)** (Akses Publik *Read-Only* Tanpa Login `/?share=<token>`) | ✅ Selesai | ✅ Tombol Bagikan & Mode Read-Only | ✅ **12 / 12 PASS** |

### B. 4 Fitur Pendukung & Visualisasi Modern (Web & Mobile)

1. **Peta Rute Interaktif (`Leaflet.js`)**: Menampilkan pin bernomor sesuai urutan kunjungan harian dan garis rute antardestinasi.
2. **Grafik Donut Proporsi Biaya & Cetak PDF (`window.print()`)**: Visualisasi persentase *Akomodasi vs Transportasi vs Tiket* serta dukungan cetak dokumen itinerary rapi.
3. **Akses Mobile Instan via QR Code (`Buka di HP`)**: Endpoint `/network-info` mendeteksi IP lokal (Wi-Fi/Hotspot) secara otomatis dan menyajikan QR Code agar aplikasi bisa langsung dibuka dari kamera smartphone.
4. **Progressive Web App (`manifest.json`) & Navigasi Mobile**: Mendukung *Add to Home Screen* di Android/iOS dengan *Bottom Navigation Bar* khusus layar sentuh.

---

## 🧪 Code Review, Refactoring, & Pengujian 149 Test Case Otomatis

Proyek ini dilengkapi suite pengujian otomatis komprehensif di [`backend/review_runner.py`](backend/review_runner.py) yang mengeksekusi **149 Test Case** nyata terhadap aplikasi menggunakan `FastAPI TestClient`, `SQLite`, dan `fakeredis`, serta langsung menghasilkan laporan Excel Code Review di [`review/Code_Review_Ruteku.xlsx`](review/Code_Review_Ruteku.xlsx).

### Ringkasan Hasil Eksekusi Test Case (`149 / 149 PASS — 100%`)

| Fitur SRS | Total TC | Happy Path | Bad Case (+ Security) | Blocker | PASS | FAIL |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **RF-01 Autentikasi** | 27 | 6 | 18 | 3 | **27** | 0 |
| **RF-03 Input Preferensi** | 21 | 4 | 14 | 3 | **21** | 0 |
| **RF-04 Itinerary AI** | 17 | 4 | 11 | 2 | **17** | 0 |
| **RF-05 Pencarian Destinasi** | 12 | 5 | 6 | 1 | **12** | 0 |
| **RF-06 Harga Real-Time** | 12 | 5 | 5 | 2 | **12** | 0 |
| **RF-08 Estimasi Anggaran** | 11 | 5 | 5 | 1 | **11** | 0 |
| **RF-09 Simpan Rencana** | 13 | 4 | 7 | 2 | **13** | 0 |
| **RF-11 Hapus Rencana** | 12 | 4 | 5 | 3 | **12** | 0 |
| **RF-13 Riwayat Perjalanan** | 12 | 4 | 6 | 2 | **12** | 0 |
| **RF-14 Berbagi Rencana** | 12 | 3 | 6 | 3 | **12** | 0 |
| **TOTAL KESELURUHAN** | **149** | **44** | **83** | **22** | **149** | **0** |

### Cakupan Pengujian Keamanan & Blocker (22 Temuan `F-01` s/d `F-22`)
- **Keamanan (*Security Bad Cases*)**: Proteksi *SQL Injection*, *Wildcard LIKE Injection (`%`/`_`)*, *Stored & Reflected XSS*, *IDOR (akses/hapus/bagikan rencana pengguna lain)*, *Mass Assignment*, *JWT Signature Tampering & `alg:none`*, *Timing Attack (Constant-Time Dummy Hash)*, *Bcrypt 72-Byte Overflow Protection*, *Prompt Injection Filter*, *Replay Attack OTP*, serta *Brute-Force & Registration Rate Limiting per IP*.
- **Ketahanan Sistem (*Blocker*)**: Simulasi database terputus (`SQLAlchemyError` → `HTTP 503`), Redis mati di tengah jalan (`RedisError` → `HTTP 503` / *direct provider fallback*), serta OpenAI API timeout/invalid JSON (`_fallback` otomatis).

---

## 🚀 Panduan Menjalankan Aplikasi (Desktop & Mobile)

### Langkah 1: Persiapan Environment
Pastikan Python 3.10+ telah terpasang di komputer Anda.

```bash
# Masuk ke folder backend
cd backend

# Buat virtual environment dan aktifkan
python -m venv .venv
# Untuk Windows:
.venv\Scripts\activate
# Untuk Linux / macOS:
# source .venv/bin/activate

# Instal seluruh dependensi
pip install -r requirements.txt

# Salin template konfigurasi environment
cp .env.example .env
```

### Langkah 2: Menjalankan Server Aplikasi (Mendukung Laptop & HP)
Jalankan server FastAPI dengan `--host 0.0.0.0` agar dapat diakses dari laptop maupun perangkat HP di jaringan Wi-Fi/Hotspot yang sama:

```bash
cd backend
.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000
```

Akses melalui peramban web:
- 💻 **Di Laptop**: [http://localhost:8000/](http://localhost:8000/)
- 📱 **Di Smartphone (HP)**: Klik tombol **"Buka di HP"** di pojok kanan atas website pada laptop lalu scan **QR Code** yang tampil.
- 📖 **Dokumentasi Interaktif API (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Cara Menjalankan Test Runner Otomatis

### 1. Menjalankan Suite Code Review Lengkap (149 Test Case + Generate Excel)
```bash
cd backend
.venv\Scripts\python.exe review_runner.py
```
File spreadsheet hasil pengujian otomatis akan tersimpan di [`review/Code_Review_Ruteku.xlsx`](review/Code_Review_Ruteku.xlsx) (terdiri dari 4 sheet: `Info`, `Testcase`, `Temuan Review`, dan `Ringkasan`).

### 2. Menjalankan Smoke Test Cepat (End-to-End)
```bash
cd backend
.venv\Scripts\python.exe smoke_test.py
```

---

## 📁 Struktur Direktori

```text
ruteku/
├── .gitignore                      # Berkas yang dikecualikan dari repositori Git
├── docker-compose.yml              # Konfigurasi container PostgreSQL & Redis
├── README.md                       # Dokumentasi utama proyek, fitur SRS, & pengujian
├── frontend/
│   ├── index.html                  # Antarmuka web & mobile responsif (Tailwind + Leaflet JS)
│   └── manifest.json               # Konfigurasi Progressive Web App (PWA) untuk Mobile
├── review/
│   ├── Code_Review_Ruteku.xlsx     # Spreadsheet Code Review & 149 Test Case (4 Sheet)
│   └── hasil_review.json           # Hasil eksekusi nyata 149 test case dalam format JSON
└── backend/
    ├── .env.example                # Template konfigurasi environment yang aman
    ├── requirements.txt            # Daftar pustaka Python yang dibutuhkan
    ├── review_runner.py            # Test runner otomatis 149 test case & generator Excel
    ├── smoke_test.py               # Pengujian cepat alur utama end-to-end
    ├── test_flow.py                # Skrip uji alur API
    └── app/
        ├── main.py                 # Entrypoint FastAPI, 10 fitur SRS, & exception handler
        ├── config.py               # Konfigurasi aplikasi (Pydantic Settings)
        ├── db.py                   # Abstraksi basis data SQLAlchemy
        ├── models.py               # Skema tabel User, Destination, Itinerary
        ├── schemas.py              # Validasi skema request/response Pydantic ketat
        ├── security.py             # Autentikasi JWT, Bcrypt 72-byte safe, anti-timing attack
        ├── cache.py                # Lapisan caching Redis & fallback FakeRedis
        ├── prices.py               # Provider adapter harga real-time & mitigasi stale
        ├── ai.py                   # Modul generasi rute AI + sanitasi prompt + fallback cerdas
        └── seed.py                 # Seeding awal katalog destinasi wisata populer
```
