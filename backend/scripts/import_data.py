"""
Script Seeding/Import Data COMPINTEL
Membaca seluruh data CSV dari folder 'DATA UTAMA', menerapkan normalisasi nama menggunakan KAMUS.csv,
dan mengunggah data secara massal ke database PostgreSQL Supabase.
"""

import os
import sys
import csv
import re
from datetime import datetime
import asyncio
import pandas as pd
import numpy as np

# Arahkan path python ke folder backend
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app_backend.core.config import settings
from app_backend.db.database import engine, Base, AsyncSessionLocal
from app_backend.models.models import DataKompetitor, DataDbKlik, UploadHistory
from sqlalchemy import insert, text

# Set paths
DATA_UTAMA_DIR = os.path.join(backend_dir, "..", "DATA UTAMA")
KAMUS_PATH = os.path.join(DATA_UTAMA_DIR, "KAMUS.csv")

def load_kamus() -> dict:
    """Memuat kamus alias brand dari KAMUS.csv."""
    kamus = {}
    if not os.path.exists(KAMUS_PATH):
        print(f"[WARNING] File KAMUS.csv tidak ditemukan di {KAMUS_PATH}")
        return kamus

    with open(KAMUS_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            alias = row['Alias'].strip().upper()
            brand_utama = row['Brand_Utama'].strip().upper()
            if alias and brand_utama:
                kamus[alias] = brand_utama
    print(f"Loaded {len(kamus)} brand aliases dari kamus.")
    return kamus

def clean_text(text: str) -> str:
    """Normalisasi dasar teks."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def apply_name_rules(product_name: str, kamus: dict) -> tuple:
    """
    Mengoreksi ejaan nama produk berdasarkan KAMUS.csv
    dan mengekstrak brand utama yang cocok.
    Returns: (corrected_name, extracted_brand)
    """
    if not product_name:
        return "", "UNKNOWN"
        
    corrected_name = product_name
    extracted_brand = "UNKNOWN"
    name_upper = product_name.upper()

    # Urutkan alias dari yang terpanjang ke terpendek untuk avoid partial match
    sorted_aliases = sorted(kamus.keys(), key=len, reverse=True)

    # 1. Koreksi typo nama produk menggunakan alias di kamus
    for alias in sorted_aliases:
        brand_utama = kamus[alias]
        # Gunakan regex word-boundary agar tidak mengganti potongan kata di tengah
        pattern = re.compile(r'\b' + re.escape(alias) + r'\b', re.IGNORECASE)
        if pattern.search(corrected_name):
            corrected_name = pattern.sub(brand_utama, corrected_name)
            extracted_brand = brand_utama

    # 2. Jika belum teridentifikasi brand-nya, cari apakah ada brand utama yang disebut langsung
    if extracted_brand == "UNKNOWN":
        unique_brands = set(kamus.values())
        # Tambahkan brand komputer standar lainnya secara otomatis agar terdeteksi
        additional_brands = {
            "SANDISK", "ACER", "HP", "DELL", "LENOVO", "ASUS", "MSI", "GIGABYTE", 
            "LOGITECH", "SAMSUNG", "KINGSTON", "XIAOMI", "LG", "INTEL", "AMD", 
            "NVIDIA", "RAZER", "FANTECH", "REXUS", "V-GEN", "TP-LINK", "WD", 
            "ADATA", "SEAGATE", "CORSAIR", "CANON", "EPSON", "BROTHER", "PHILIPS", 
            "AOC", "VIEWSONIC", "BENQ", "ALCATROZ", "UGREEN", "BASEUS", "JBL", 
            "SONY", "RUIJIE", "MERCUSYS", "NETGEAR", "DLINK", "CISCO", "HIKVISION", 
            "SPC", "DAHUA", "EZVIZ"
        }
        unique_brands.update(additional_brands)
        sorted_brands = sorted(unique_brands, key=len, reverse=True)
        for brand in sorted_brands:
            pattern = re.compile(r'\b' + re.escape(brand) + r'\b', re.IGNORECASE)
            if pattern.search(corrected_name.upper()):
                extracted_brand = brand
                break

    return corrected_name, extracted_brand

def parse_filename(filename: str) -> dict:
    """
    Mengurai detail toko dan status dari penamaan file.
    Format yang diharapkan: DATA_REKAP - [NAMA TOKO] - REKAP - [STATUS].csv
    Contoh: DATA_REKAP - DB KLIK - REKAP - READY.csv
    """
    name_clean = filename.replace(".csv", "")
    parts = name_clean.split(" - ")
    
    toko = "UNKNOWN"
    status = "READY"
    
    if len(parts) >= 4:
        toko = parts[1].strip().upper()
        status = parts[3].strip().upper()
    elif len(parts) >= 2:
        toko = parts[1].strip().upper()

    return {
        "nama_toko": toko,
        "status": status
    }

async def import_csv_file(file_path: str, kamus: dict):
    """Membaca satu file CSV dan memasukkannya ke database secara bulk."""
    filename = os.path.basename(file_path)
    meta = parse_filename(filename)
    
    print(f"\nProcessing File: {filename}")
    print(f"   Toko: {meta['nama_toko']} | Status: {meta['status']}")

    try:
        # Baca dengan pandas
        df = pd.read_csv(file_path)
        
        # Standarisasi kolom (case-insensitive)
        df.columns = [col.strip().upper() for col in df.columns]
        
        # Kolom wajib mayoritas data
        required = ['NAMA', 'HARGA', 'TERJUAL/BLN']
        for col in required:
            if col not in df.columns:
                print(f"   [SKIP] Kolom '{col}' tidak ditemukan di {filename}")
                return

        # Pilihan kolom opsional
        has_brand = 'BRAND' in df.columns
        has_kategori = 'KATEGORI' in df.columns
        has_sku = 'SKU' in df.columns
        has_tanggal = 'TANGGAL' in df.columns

        records_to_insert = []
        is_db_klik = "DB KLIK" in meta['nama_toko']

        for _, row in df.iterrows():
            nama_original = str(row['NAMA'])
            if not nama_original or nama_original.lower() == 'nan':
                continue

            # Terapkan koreksi nama produk berdasarkan kamus
            nama_koreksi, brand_ekstraksi = apply_name_rules(nama_original, kamus)
            
            # Jika kolom BRAND ada di CSV dan tidak kosong, gunakan itu
            brand_final = brand_ekstraksi
            if has_brand and pd.notna(row['BRAND']):
                csv_brand = str(row['BRAND']).strip().upper()
                if csv_brand and csv_brand != 'UNKNOWN':
                    # Tetap bersihkan brand CSV menggunakan kamus jika ada aliasnya
                    brand_final = kamus.get(csv_brand, csv_brand)

            # Parsing tanggal
            tanggal_str = str(row['TANGGAL']) if has_tanggal else datetime.now().strftime("%Y-%m-%d")
            # Handle format dd/mm/yyyy atau yyyy-mm-dd
            try:
                if '/' in tanggal_str:
                    tanggal_parsed = datetime.strptime(tanggal_str.strip(), "%d/%m/%Y").date()
                else:
                    tanggal_parsed = datetime.strptime(tanggal_str.strip()[:10], "%Y-%m-%d").date()
            except Exception:
                tanggal_parsed = datetime.now().date()

            # Bersihkan harga dan terjual
            try:
                harga = int(float(str(row['HARGA']).replace('.', '').replace(',', '')))
            except Exception:
                harga = 0

            try:
                terjual = int(float(str(row['TERJUAL/BLN'])))
            except Exception:
                terjual = 0

            # Kategori & SKU opsional (default None jika tidak ada untuk penyamaan mayoritas kolom)
            kategori = str(row['KATEGORI']).strip() if (has_kategori and pd.notna(row['KATEGORI'])) else None
            sku = str(row['SKU']).strip() if (has_sku and pd.notna(row['SKU'])) else None

            record = {
                "nama_produk": nama_koreksi,
                "nama_produk_clean": clean_text(nama_koreksi),
                "harga": harga,
                "terjual_bln": terjual,
                "tanggal": tanggal_parsed,
                "brand": brand_final,
                "kategori": kategori,
                "sku": sku
            }

            if not is_db_klik:
                record["nama_toko"] = meta['nama_toko']
                record["status"] = meta['status']

            records_to_insert.append(record)

        # Lakukan Bulk Insert menggunakan SQLAlchemy Core (Sangat Cepat!)
        if records_to_insert:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Tentukan tabel tujuan
                    if is_db_klik:
                        stmt = insert(DataDbKlik)
                    else:
                        stmt = insert(DataKompetitor)
                    
                    # Eksekusi bulk insert
                    await session.execute(stmt, records_to_insert)
                    
                    # Tambahkan log riwayat upload
                    upload_log = UploadHistory(
                        filename=filename,
                        nama_toko=meta['nama_toko'],
                        tanggal_scraping=records_to_insert[0]['tanggal'],
                        status=meta['status'],
                        row_count=len(records_to_insert),
                        file_size=os.path.getsize(file_path),
                        status_upload="SUCCESS"
                    )
                    session.add(upload_log)
            
            print(f"   [SUCCESS] Bulk insert {len(records_to_insert)} baris ke database.")
        else:
            print("   [WARNING] Tidak ada baris valid untuk diinsert.")

    except Exception as e:
        print(f"   [FAILED] Gagal memproses {filename}: {e}")

async def main():
    print("=========================================================")
    print("     COMPINTEL DATA UTAMA BULK SEEDER / IMPORTER         ")
    print("=========================================================")
    
    # 1. Pastikan tabel di database sudah siap
    print("Membuat/memastikan tabel database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Mengosongkan data lama untuk clean install...")
        await conn.execute(text("TRUNCATE TABLE data_db_klik, data_kompetitor, upload_history RESTART IDENTITY CASCADE;"))
    print("Struktur tabel siap & data lama telah dikosongkan.")

    # 2. Muat kamus
    kamus = load_kamus()

    # 3. Cari seluruh file CSV di folder DATA UTAMA
    if not os.path.exists(DATA_UTAMA_DIR):
        print(f"[ERROR] Folder DATA UTAMA tidak ditemukan di {DATA_UTAMA_DIR}")
        return

    all_files = [f for f in os.listdir(DATA_UTAMA_DIR) if f.endswith('.csv') and f != "KAMUS.csv"]
    print(f"Ditemukan {len(all_files)} file CSV rekap toko di {DATA_UTAMA_DIR}")

    # Urutkan agar DB KLIK diproses pertama
    all_files.sort(key=lambda x: "DB KLIK" not in x)

    # 4. Impor setiap file satu per satu
    for file_name in all_files:
        file_path = os.path.join(DATA_UTAMA_DIR, file_name)
        await import_csv_file(file_path, kamus)

    print("\n=========================================================")
    print("SEMUA DATA UTAMA BERHASIL DIIMPOR KE SUPABASE!")
    print("=========================================================")

if __name__ == "__main__":
    # Jalankan loop async
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
