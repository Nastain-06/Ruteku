# Ruteku — Perencanaan Perjalanan Wisata Berbasis AI dengan Harga Real-Time

> **Tugas Besar / UTS Mata Kuliah Implementasi & Pengujian Perangkat Lunak (IPPL)**  
> **Identitas Pengembang**: Nasta'in (NIM: 11241081)  
> **Tautan Video Presentasi & Demo**: [Tonton Video Demo di YouTube](https://youtu.be/GANTI_DENGAN_LINK_YOUTUBE_ANDA)

---

## 📌 Ringkasan Proyek

**Ruteku** adalah aplikasi perencana perjalanan wisata (*smart itinerary planner*) berbasis kecerdasan buatan (AI) yang mengintegrasikan estimasi biaya riil secara *real-time*.

Aplikasi ini mengatasi kelemahan model perencana konvensional dengan memisahkan secara tegas antara **perencanaan logistik rute oleh AI** dan **perhitungan anggaran oleh sistem matematis deterministik**, sehingga terbebas dari risiko halusinasi harga oleh LLM.

---

## 📊 Ketercapaian Progres Fitur UTS (Target >= 30%)

Berdasarkan dokumen SRS (Software Requirements Specification) yang memuat **20 Kebutuhan Fungsional (RF)**, pada tahap UTS ini telah diimplementasikan **8 fitur esensial (40% ketercapaian)**, melampaui ambang batas minimal 30%:

| Kode RF | Deskripsi Fitur Esensial | Implementasi Backend | Antarmuka Frontend | Status Pengujian |
|:---:|:---|:---:|:---:|:---:|
| **RF-01** | Autentikasi Pengguna (Registrasi, Login, Logout JWT, Bcrypt, Blacklist Redis) | ✅ Selesai | ✅ Modal Login/Register | ✅ Lulus Test |
| **RF-03** | Formulir Input Preferensi Perjalanan (Asal, Tujuan, Tanggal, Orang, Budget, Minat) | ✅ Selesai | ✅ Form Wizard Interaktif | ✅ Lulus Test |
| **RF-04** | Generasi Itinerary Wisata Berbasis AI (OpenAI API + Algoritma Fallback Mandiri) | ✅ Selesai | ✅ Timeline Harian Visual | ✅ Lulus Test |
| **RF-05** | Pencarian & Filter Katalog Destinasi Wisata (Bali, Jogja, Labuan Bajo, Derawan) | ✅ Selesai | ✅ Halaman Katalog Destinasi | ✅ Lulus Test |
| **RF-06** | Integrasi Harga Real-Time (Simulasi OTA + Redis Cache TTL + Fallback Stale Data) | ✅ Selesai | ✅ Rincian Tiket & Akomodasi | ✅ Lulus Test |
| **RF-08** | Kalkulasi Estimasi Anggaran & Deteksi Status Over-Budget | ✅ Selesai | ✅ Kartu Status Anggaran Dinamis | ✅ Lulus Test |
| **RF-09** | Penyimpanan Draf Rencana Perjalanan ke Basis Data | ✅ Selesai | ✅ Tombol Simpan 1-Klik | ✅ Lulus Test |
| **RF-13** | Riwayat Perjalanan Pengguna & Penampil Rincian Rencana | ✅ Selesai | ✅ Halaman Riwayat & Detail Modal | ✅ Lulus Test |

**Total Progres**: **8 / 20 Fitur = 40% (Full-Stack Frontend & Backend Selesai)**.

---

## 🛡️ Prinsip Desain & Pengujian (Perspektif IPPL)

1. **Anti-Halusinasi AI**: AI (LLM) hanya diberi tugas logistik (memilih destinasi yang valid dari basis data lokal dan mengurutkannya searah). Harga tiket, akomodasi, dan transportasi **dihitung murni oleh sistem**.
2. **Pola Desain Adapter (Adapter Pattern)**: Modul harga di `app/prices.py` mengimplementasikan adapter `MockPriceProvider` yang mensimulasikan fluktuasi harga OTA tiap 10 menit. API riil seperti Tiket.com atau Traveloka dapat dihubungkan tanpa mengubah logika inti.
3. **Graceful Degradation & Resilience (NFR-11)**: Jika OpenAI API down atau tanpa API Key, sistem otomatis beralih ke algoritma heuristik internal (`_fallback`) dengan penanda `ai_used: false` sehingga sistem tidak pernah crash.
4. **Caching & Stale Fallback (NFR-17)**: Cache Redis memiliki TTL 30 menit. Jika penyedia harga gagal merespons, sistem menyajikan harga terakhir yang tercatat dengan penanda label `stale` dan menampilkan peringatan transparan ke pengguna.
5. **Keamanan Data (NFR-06)**: Password dienkripsi dengan **Bcrypt** (cost 12 rounds), sesi otorisasi dilindungi dengan **JWT** berumur 24 jam, dan fitur logout memasukkan token ke **Redis Blacklist**.

---

## 🚀 Panduan Menjalankan Aplikasi

Aplikasi dapat dijalankan secara instan di komputer lokal (Windows / Linux / macOS) baik menggunakan mode cepat (SQLite + FakeRedis) maupun mode container (Docker).

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

### Langkah 2: Menjalankan Server Aplikasi
Jalankan server FastAPI (secara otomatis menyajikan Frontend Web dan Backend API):

```bash
uvicorn app.main:app --reload
```

Akses melalui peramban web:
- 🌐 **Aplikasi Web Ruteku**: [http://localhost:8000/](http://localhost:8000/)
- 📖 **Dokumentasi Interaktif API (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Pengujian Otomatis (Smoke Test IPPL)

Untuk memvalidasi integritas perangkat lunak sesuai standar pengujian IPPL, telah disediakan skrip uji mandiri tanpa dependensi eksternal:

```bash
cd backend
python smoke_test.py
```

Skrip ini menguji skenario end-to-end secara otomatis:
1. Registrasi akun baru & penolakan duplikasi email.
2. Login gagal & login sukses menghasilkan token JWT Bearer.
3. Pencarian katalog destinasi.
4. Generasi rencana perjalanan AI & perhitungan biaya real-time.
5. Verifikasi *cache hit* pada panggilan berulang.
6. Simulasi kegagalan penyedia harga (*mock fail*) & validasi pesan peringatan.
7. Penyimpanan draf rencana ke database & penarikan riwayat perjalanan.
8. Logout & pembuktian token hangus melalui Redis Blacklist.

**Hasil Pengujian:**
```text
total: 5816000 | ai_used: False | cache hit: True
SEMUA UJI LULUS
```

---

## 🎬 Panduan Perekaman Video Presentasi (YouTube)

Struktur durasi video (disarankan 5 - 7 menit):
1. **Pendahuluan (1 Menit)**:
   - Salam, perkenalan diri (Nama: Nasta'in, NIM: 11241081), mata kuliah IPPL.
   - Latar belakang & permasalahan perencanaan liburan yang diselesaikan Ruteku.
2. **Ketercapaian Fitur UTS (1 Menit)**:
   - Menjelaskan bahwa progres telah mencapai **40% (8 dari 20 RF)**, melampaui syarat 30%.
3. **Demo Aplikasi Langsung (3 Menit)**:
   - Registrasi & Login di `http://localhost:8000/`.
   - Mengisi form preferensi liburan (Samarinda -> Bali, 2 orang, budget Rp 9.000.000).
   - Menampilkan hasil itinerary AI, rincian biaya (hotel, transportasi, tiket), dan status sisa anggaran.
   - Menyimpan itinerary dan mengecek menu **Riwayat Perjalanan**.
   - Menjelaskan menu **Katalog Destinasi**.
4. **Pembuktian Pengujian Perangkat Lunak (1 Menit)**:
   - Membuka terminal, menjalankan `python smoke_test.py`.
   - Menunjukkan hasil output `SEMUA UJI LULUS`.
5. **Penutup (30 Detik)**:
   - Rencana pengembangan selanjutnya pasca-UTS.

---

## 📁 Struktur Direktori

```text
ruteku/
├── .gitignore               # Berkas yang dikecualikan dari repositori Git
├── docker-compose.yml       # Konfigurasi container PostgreSQL & Redis
├── README.md                # Dokumentasi utama proyek & laporan progres UTS
├── frontend/
│   └── index.html           # Antarmuka web modern (Tailwind CSS + Vanilla JS)
└── backend/
    ├── .env.example         # Template konfigurasi environment
    ├── requirements.txt     # Daftar pustaka Python yang dibutuhkan
    ├── smoke_test.py        # Pengujian otomatis end-to-end IPPL
    ├── test_flow.py         # Skrip uji alur API
    └── app/
        ├── main.py          # Entrypoint FastAPI & static mount frontend
        ├── config.py        # Konfigurasi aplikasi (Pydantic Settings)
        ├── db.py            # Abstraksi basis data SQLAlchemy
        ├── models.py        # Skema tabel User, Destination, Itinerary
        ├── schemas.py       # Validasi skema request/response Pydantic
        ├── security.py      # Autentikasi JWT, hashing Bcrypt, blacklist token
        ├── cache.py         # Lapisan caching Redis & fallback FakeRedis
        ├── prices.py        # Provider adapter harga real-time & mitigasi stale
        ├── ai.py            # Modul generasi rute AI (OpenAI + Fallback)
        └── seed.py          # Seeding awal 15 destinasi wisata populer
```
