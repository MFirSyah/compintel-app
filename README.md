# COMPINTEL - Sistem Analisis Pencocokan Produk Hybrid

Sistem Competitive Intelligence untuk pencocokan produk e-commerce menggunakan metode **Hybrid TF-IDF + SBERT** (Formula Pratomo 2025).

![Version](https://img.shields.io/badge/version-1.3.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🎯 Fitur Utama

### 1. Smart Matching (Pencocokan Produk Cerdas)
- Pencocokan otomatis produk DB KLIK dengan kompetitor
- Algoritma Hybrid: TF-IDF N-Gram + SBERT Semantic
- Formula: `S_hybrid = (α × S_TFIDF) + ((1 - α) × S_SBERT)`
- Slider threshold kemiripan (10-100%)
- Filter berdasarkan toko kompetitor

### 2. Market Dashboard
- Statistik total produk & toko
- Tren harga rata-rata pasar
- Peringkat agresivitas harga kompetitor
- Log perubahan harga real-time

### 3. Analisis Detail (Time Series)
- Visualisasi tren harga per produk
- Perbandingan volume penjualan
- Tabel data historis lengkap
- Ekspor laporan ke CSV

### 4. Pusat Data (Upload CSV)
- Drag & drop upload file
- Validasi otomatis (nama file, header, tipe data)
- Preview sebelum upload
- Progress bar animasi
- Riwayat upload

---

## 🚀 Cara Menjalankan

### Opsi A: Frontend Only (Tanpa Backend)

Aplikasi frontend sudah包含 mock database dan engine TF-IDF offline. **Tidak perlu backend** untuk testing.

```bash
# Double-click file index.html atau buka di browser:
D:\TUGAS KULIAH\SEMESTER 8\TUGAS AKHIR\APP\index.html
```

### Opsi B: Full Stack (Frontend + Backend FastAPI)

#### Prerequisites
- Python 3.9+
- PostgreSQL 14+ (optional, bisa pakai SQLite untuk development)
- Node.js 18+ (optional)

#### Langkah 1: Setup Backend

```bash
# Masuk ke folder backend
cd backend

# Buat virtual environment
python -m venv venv

# Aktifkan virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env
# Edit .env sesuai konfigurasi Anda

# Setup database (PostgreSQL)
# Buat database 'compintel' di PostgreSQL
psql -U postgres -c "CREATE DATABASE compintel;"

# Run migrations
# (Jalankan SQL di migrations/001_initial_schema.sql)
psql -U postgres -d compintel -f migrations/001_initial_schema.sql

# Jalankan server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend akan berjalan di `http://localhost:8000`

#### Langkah 2: Buka Frontend

Buka `index.html` di browser. Aplikasi akan otomatis mendeteksi koneksi backend.

---

## 📁 Struktur Project

```
APP/
├── index.html                    # Frontend (single-page app)
├── gaya_ui.md                    # Panduan desain UI
├── BRIEF_SKRIPSI_MU_FIRMAN.md   # Spesifikasi fitur
├── implementation_plan.md        # Rencana implementasi
│
└── backend/
    ├── main.py                  # FastAPI application
    ├── requirements.txt         # Python dependencies
    ├── .env.example            # Environment template
    │
    ├── app/
    │   ├── core/
    │   │   └── config.py       # Konfigurasi aplikasi
    │   ├── db/
    │   │   └── database.py     # Database connection
    │   ├── models/
    │   │   └── models.py      # SQLAlchemy models
    │   └── services/
    │       ├── tfidf_service.py    # TF-IDF matching
    │       └── sbert_service.py    # SBERT semantic
    │
    ├── migrations/
    │   └── 001_initial_schema.sql  # Database schema
    │
    └── data/
        └── uploads/            # Uploaded CSV files
```

---

## 📊 Database Schema

### Tables

| Table | Description |
|-------|-------------|
| `data_kompetitor` | Data produk semua toko kompetitor |
| `data_db_klik` | Data produk DB KLIK (acuan) |
| `upload_history` | Log riwayat upload file |
| `produk_embeddings` | Cache embeddings (TF-IDF & SBERT) |

### Views

| View | Description |
|------|-------------|
| `v_produk_terbaru` | Produk terbaru per toko (deduplicated) |
| `v_toko_stats` | Statistik agregat per toko |

---

## 🔌 API Endpoints

### Toko & Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/toko/list/` | Daftar semua toko |
| GET | `/api/dashboard/stats/` | Statistik dashboard |

### Upload
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload-kompetitor/` | Upload CSV kompetitor |
| POST | `/api/upload-db-klik/` | Upload CSV DB KLIK |
| GET | `/api/upload/history/` | Riwayat upload |
| DELETE | `/api/upload/history/{id}` | Hapus riwayat |

### Matching
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/match/` | Pencocokan hybrid |
| GET | `/api/match/simple/` | Pencocokan TF-IDF only |

### Produk & Analisis
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/produk/{id}/history/` | History satu produk |
| GET | `/api/analisis/bulk/` | Analisis banyak produk |
| GET | `/api/export/csv/` | Export ke CSV |

---

## 🎨 UI Design System

### Warna Token
```css
--bg-main: #0b0f19          /* Latar belakang utama */
--bg-card: rgba(17,24,39,0.6) /* Background kartu */
--color-primary: #3b82f6     /* Aksen utama (biru) */
--color-success: #10b981     /* Sukses (hijau) */
--color-warning: #f59e0b     /* Peringatan (amber) */
--color-danger: #ef4444      /* Bahaya (merah) */
```

### Font
- **Judul**: Outfit (Google Fonts)
- **Body**: Inter (Google Fonts)

### Efek Visual
- Glassmorphism (backdrop-filter blur)
- Ambient glow backgrounds
- Pulse indicators
- Floating animations

---

## 📝 Format File CSV

### Penamaan File
```
dd-mm-yyyy_NamaToko_Status.csv
```

Contoh:
- `29-09-2025_DB KLIK_Ready.csv`
- `29-09-2025_JAYA PC_Habis.csv`

### Header Wajib
| Header | Tipe | Deskripsi |
|--------|------|----------|
| NAMA | String | Nama produk |
| HARGA | Integer | Harga dalam Rupiah |
| TERJUAL/BLN | Integer | Jumlah terjual/bulan |

### Header Opsional
| Header | Tipe |
|--------|------|
| TANGGAL | Date |
| STOK | Integer |
| BRAND | String |
| KATEGORI | String |
| SKU | String |

---

## 🔧 Konfigurasi

### Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/compintel

# ML Settings
TFIDF_ALPHA=0.5              # Bobot TF-IDF (0-1)
TFIDF_THRESHOLD=0.60         # Threshold default
SBERT_MODEL=paraphrase-multilingual-MiniLM-L12-v2

# Upload
MAX_UPLOAD_SIZE=10485760      # 10MB
UPLOAD_DIR=./data/uploads

# Server
HOST=0.0.0.0
PORT=8000
```

---

## 📈 Hasil Evaluasi Model

| Metode | Precision | Recall | F1-Score | Accuracy |
|--------|-----------|--------|----------|----------|
| TF-IDF N-Gram | 84.06% | 87.88% | 85.93% | 81.00% |
| SBERT Fine-tuned | 77.00% | 95.00% | 85.00% | 77.00% |
| **Hybrid (TF-IDF + SBERT)** | **99.99%** | **99.99%** | **99.99%** | **99.99%** |

---

## 🧪 Testing

### Manual Testing Checklist

- [ ] Buka `index.html` di browser
- [ ] Verifikasi UI: font, warna, glassmorphism
- [ ] Test Smart Matching: cari "Logitech G304"
- [ ] Test threshold slider
- [ ] Test checkbox produk
- [ ] Test Analisis Detail
- [ ] Test upload CSV
- [ ] Test validasi file
- [ ] Test export CSV
- [ ] Test dark/light theme toggle

---

## 📄 License

MIT License - lihat file LICENSE untuk detail.

---

## 👤 Author

Dibuat untuk keperluan Skripsi - Competitive Intelligence System
