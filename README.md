================================================================================
.env.example
================================================================================

# Konfigurasi Supabase
SUPABASE_URL="https://wqqrjsjytlcvkkgziana.supabase.co"
SUPABASE_KEY="sb_publishable_nqnraHg2CUUot95hRWv5fA_ZuDozNyM"

# Konfigurasi Bucket & Tabel Supabase
TARGET_BUCKET="photos"
TARGET_TABLE="photos_data"

# Konfigurasi AI Server
AI_SERVER_URL="https://www.kameratamu.com/api/apply-filter"


================================================================================
requirements.txt
================================================================================

fastapi>=0.100.0
uvicorn>=0.22.0
requests>=2.31.0
python-dotenv>=1.0.0
python-multipart>=0.0.6


================================================================================
README.md
================================================================================

# KameraTamu Middleware Server

Middleware Server berbasis FastAPI untuk menghubungkan aplikasi KameraTamu dengan Supabase dan AI Filter Processing Server.

---

## 📌 Fitur & Alur Kerja

1. Fetch Event Settings: Memanggil RPC Supabase (get_event_by_slug) untuk mengambil konfigurasi event, filter AI, dan rasio pemotretan berdasarkan slug.
2. AI Filter Processing: Jika filter AI diaktifkan pada event tersebut, foto dikirim ke AI Server. Jika filter dinonaktifkan atau AI Server bermasalah/timeout, sistem secara otomatis melakukan fallback menggunakan foto asli.
3. Supabase Storage Upload: Menyimpan foto hasil pemrosesan (atau foto asli) ke Supabase Storage Bucket.
4. Data Logging: Mencatat metadata foto dan status filter ke tabel database Supabase.

---

## 🛠️ Persyaratan Sistem

- Python: 3.9 atau versi yang lebih baru
- Pip: Package manager Python

---

## 🚀 Panduan Instalasi & Menjalankan Project

### 1. Clone / Siapkan Project
Pastikan seluruh file project sudah berada dalam satu folder kerja.

### 2. Buat Virtual Environment
Diperlukan untuk memisahkan dependensi project dari sistem global:

- Linux / macOS:
  python3 -m venv venv
  source venv/bin/activate

- Windows (CMD / PowerShell):
  python -m venv venv
  venv\Scripts\activate

### 3. Install Dependensi
pip install -r requirements.txt

### 4. Konfigurasi Environment Variables
Salin file .env.example menjadi .env:
cp .env.example .env

Buka file .env dan sesuaikan nilainya dengan konfigurasi Supabase dan AI Server Anda.

### 5. Jalankan Server
Gunakan Uvicorn untuk menjalankan server FastAPI dalam mode development:
uvicorn main:app --reload

Server akan berjalan secara lokal di http://127.0.0.1:8000.

---

## 📂 Rekomendasi Struktur Folder

kameratamu-middleware/
├── .env                  # Variabel lingkungan (Supabase URL, Key, dll)
├── .env.example          # Template variabel lingkungan
├── .gitignore            # Mencegah file sensitif / venv ter-upload ke Git
├── requirements.txt      # Daftar pustaka Python
├── main.py               # File utama FastAPI
└── README.md             # Dokumentasi project

---

## 📡 Dokumentasi API Endpoints

### POST /upload-image/{slug}

Mengunggah dan memproses foto dari kamera berdasarkan slug event.

#### Parameter Path
- slug (string, required): Slug unik untuk mengidentifikasi event di database Supabase.

#### Body (multipart/form-data)
- image (file, required): File gambar (image/jpeg, image/png, dsb.)

#### Contoh Request (cURL)
curl -X POST "http://127.0.0.1:8000/upload-image/my-event-slug" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "image=@/path/to/photo.jpg"

#### Contoh Response Sukses (200 OK)
{
  "status": "success",
  "message": "Gambar berhasil diproses dan disimpan.",
  "file_name": "photo_1771949561_a1b2c3.jpg",
  "filter_enabled_in_db": true,
  "is_filtered": true
}

---
