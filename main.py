from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import base64
import time
import json
import uuid
import os
from dotenv import load_dotenv

# Memuat variabel dari .env ke dalam environment system
load_dotenv()

app = FastAPI(title="KameraTamu Middleware Server")

# Izinkan akses CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# KONFIGURASI SUPABASE & AI SERVER DARI .ENV
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TARGET_BUCKET = os.getenv("TARGET_BUCKET", "photos")
TARGET_TABLE = os.getenv("TARGET_TABLE", "photos_data")
AI_SERVER_URL = os.getenv("AI_SERVER_URL")

# Validasi jika variabel .env tidak ditemukan
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL dan SUPABASE_KEY harus diatur di dalam file .env")

if not AI_SERVER_URL:
    print("[WARNING] AI_SERVER_URL tidak diatur di .env. Filter AI tidak akan berfungsi.")

# Headers standar untuk komunikasi dengan API Supabase
HEADERS_SUPA = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ==========================================
# FUNGSI HELPER
# ==========================================

def get_event_settings(slug: str):
    """Ambil Event ID, Filter Settings, dan Capture Settings dari Supabase"""
    rpc_url = f"{SUPABASE_URL}/rest/v1/rpc/get_event_by_slug"
    res_rpc = requests.post(rpc_url, headers=HEADERS_SUPA, json={"p_slug": slug})

    # Cache hasil .json() agar tidak dipanggil dua kali
    rpc_data = res_rpc.json() if res_rpc.status_code == 200 else []
    if not rpc_data:
        raise HTTPException(status_code=404, detail="Event slug tidak ditemukan.")

    # Guard IndexError jika list tidak terduga kosong
    if len(rpc_data) == 0:
        raise HTTPException(status_code=404, detail="Data event kosong.")

    event_data = rpc_data[0]
    event_id = event_data['id']

    # Ambil Filter Settings
    filter_url = f"{SUPABASE_URL}/rest/v1/filter_settings?event_id=eq.{event_id}&select=enabled,prompt,model,resolution"
    res_filter = requests.get(filter_url, headers=HEADERS_SUPA)
    filter_data = res_filter.json() if res_filter.status_code == 200 else []
    filter_settings = filter_data[0] if filter_data else {"enabled": False}

    # Ambil Capture Settings
    capture_url = f"{SUPABASE_URL}/rest/v1/capture_settings?event_id=eq.{event_id}&select=aspect_ratio"
    res_capture = requests.get(capture_url, headers=HEADERS_SUPA)
    capture_data = res_capture.json() if res_capture.status_code == 200 else []
    capture_settings = capture_data[0] if capture_data else {"aspect_ratio": "1:1"}

    return {
        "event_id": event_id,
        "event_name": event_data.get('event_name', ''),
        "filter": filter_settings,
        "capture": capture_settings
    }

def apply_ai_filter(image_bytes: bytes, settings: dict):
    """Kirim gambar ke server AI jika Filter diaktifkan"""
    print("[INFO] Menerapkan Filter AI...")
    
    base64_img = base64.b64encode(image_bytes).decode('utf-8')
    data_uri = f"data:image/jpeg;base64,{base64_img}"
    
    prompt = settings['filter'].get('prompt', '').replace('\n', ' ')
    
    payload = {
        "image": data_uri,
        "prompt": prompt,
        "aspectRatio": settings['capture'].get('aspect_ratio', '1:1'),
        "eventId": settings['event_id'],
        "model": settings['filter'].get('model', ''),
        "resolution": settings['filter'].get('resolution', '')
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "python-requests/2.31.0",
        "Accept": "*/*"
    }
    
    # Validasi AI_SERVER_URL sebelum request
    if not AI_SERVER_URL:
        print("[WARNING] AI_SERVER_URL tidak dikonfigurasi. Fallback ke gambar asli.")
        return image_bytes, False

    try:
        # Timeout ditingkatkan ke 60 detik
        res = requests.post(AI_SERVER_URL, json=payload, headers=headers, timeout=60)
        
        if res.status_code == 200 and len(res.content) > 0:
            print("[SUCCESS] Filter AI berhasil diterapkan oleh AI Server.")
            return res.content, True
        else:
            print(f"[ERROR] AI Server gagal dengan status {res.status_code}: {res.text[:100]}. Fallback ke gambar asli.")
            return image_bytes, False
            
    except requests.exceptions.Timeout:
        print("[WARNING] AI Server Timeout (>60s). Fallback ke gambar asli.")
        return image_bytes, False
    except Exception as e:
        print(f"[ERROR] Gagal memproses AI filter: {e}")
        return image_bytes, False

def upload_to_supabase(image_bytes: bytes):
    """Upload gambar ke Storage Supabase"""
    file_name = f"photo_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
    storage_url = f"{SUPABASE_URL}/storage/v1/object/{TARGET_BUCKET}/{file_name}"
    
    headers = HEADERS_SUPA.copy()
    headers["Content-Type"] = "image/jpeg"
    
    res = requests.post(storage_url, headers=headers, data=image_bytes)
    
    if res.status_code in [200, 201]:
        return file_name
    else:
        raise HTTPException(status_code=500, detail=f"Gagal upload ke storage: {res.text}")

def save_data_to_supabase(event_id: str, file_name: str, is_filtered: bool):
    """Simpan informasi/log ke Table Database Supabase"""
    table_url = f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}"
    
    headers = HEADERS_SUPA.copy()
    headers["Prefer"] = "return=representation"
    
    payload = {
        "event_id": event_id,
        "file_name": file_name,
        "is_ai_filtered": is_filtered,
        "uploaded_at": int(time.time())
    }
    
    res = requests.post(table_url, headers=headers, json=payload)
    if res.status_code not in [200, 201]:
        print(f"[WARNING] Gagal insert data ke tabel: {res.text}")

# ==========================================
# ENDPOINT UTAMA
# ==========================================

@app.post("/upload-image/{slug}")
async def process_camera_image(slug: str, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
        print(f"[INFO] Menerima gambar untuk slug: {slug} (Size: {len(image_bytes)} bytes)")
        
        # 1. Ambil Pengaturan dari Supabase
        settings = get_event_settings(slug)
        print(f"[INFO] Event ID: {settings['event_id']}, Filter Enabled: {settings['filter'].get('enabled')}")
        
        is_filter_enabled = settings['filter'].get('enabled') is True
        is_filtered = False
        final_image = image_bytes
        
        # 2. Proses AI Filter HANYA JIKA Filter Diaktifkan
        if is_filter_enabled:
            final_image, is_filtered = apply_ai_filter(image_bytes, settings)
        else:
            print("[INFO] AI Filter di-disable di Supabase. Menggunakan gambar asli.")
        
        # 3. Upload ke Supabase Storage (Sekarang menggunakan Supabase utama)
        file_name = upload_to_supabase(final_image)
        print(f"[SUCCESS] Gambar terunggah: {file_name}")
        
        # 4. Simpan Log ke Tabel Supabase (Sekarang menggunakan Supabase utama)
        save_data_to_supabase(settings['event_id'], file_name, is_filtered)
        print(f"[SUCCESS] Log tersimpan dengan status is_ai_filtered = {is_filtered}")
        
        return JSONResponse(content={
            "status": "success", 
            "message": "Gambar berhasil diproses dan disimpan.",
            "file_name": file_name,
            "filter_enabled_in_db": is_filter_enabled,
            "is_filtered": is_filtered
        })

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})
    except Exception as e:
        print(f"[FATAL ERROR] {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})
