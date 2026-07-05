"""
COMPINTEL Backend - FastAPI with Supabase Integration
Sistem Analisis Pencocokan Produk Hybrid (TF-IDF + SBERT)
"""
import os
import sys
import logging

from contextlib import asynccontextmanager
from pathlib import Path

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from pydantic import BaseModel
import pandas as pd
import numpy as np
import csv
import io

# Import from app_backend package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app_backend.core.config import settings
from app_backend.db.database import engine, Base, get_db
from app_backend.models.models import DataKompetitor, DataDbKlik, UploadHistory, ProductEmbedding
from app_backend.services.tfidf_service import TFIDFMatcher
from app_backend.services.sbert_service import SBERTMatcher


# Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logging.warning("Supabase client not installed")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global ML matchers
tfidf_matcher: Optional[TFIDFMatcher] = None
sbert_matcher: Optional[SBERTMatcher] = None

# Supabase client
supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Get or create Supabase client."""
    global supabase_client
    if supabase_client is None and SUPABASE_AVAILABLE:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if supabase_url and supabase_key:
            try:
                supabase_client = create_client(supabase_url, supabase_key)
                logger.info("✅ Supabase client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to init Supabase: {e}")
    return supabase_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("🚀 Starting COMPINTEL Backend...")

    # Create upload directory
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Create database tables (if using DB)
    if "postgresql" in settings.DATABASE_URL:
        try:
            logger.info("🔄 Connecting to database and verifying tables...")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database connection and tables verified.")
        except Exception as db_err:
            logger.error(f"⚠️ Database connection failed on startup: {db_err}")
            logger.warning("⚠️ App starting in offline-DB mode. DB endpoints will return errors but server remains active.")


    # Initialize ML models
    import asyncio
    asyncio.create_task(init_ml_models())

    # Initialize Supabase
    get_supabase_client()

    logger.info("✅ COMPINTEL Backend ready!")

    yield

    logger.info("👋 Shutting down COMPINTEL Backend...")
    if engine:
        await engine.dispose()


# Brand normalization global dict
brand_map = {}

def load_kamus():
    """Load brand alias mapping from app_backend/data/KAMUS.csv."""
    global brand_map
    import csv
    import re
    kamus_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_backend", "data", "KAMUS.csv")
    if not os.path.exists(kamus_path):
        logger.warning(f"⚠️ KAMUS.csv not found at {kamus_path}")
        return
        
    try:
        with open(kamus_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                alias = row.get('Alias', '').strip().upper()
                brand_utama = row.get('Brand_Utama', '').strip().upper()
                if alias and brand_utama:
                    # Save as regex patterns for word boundary mapping
                    regex_pattern = r'\b' + re.escape(alias) + r'\b'
                    brand_map[regex_pattern] = brand_utama
        logger.info(f"✅ Loaded {len(brand_map)} brand mappings from KAMUS.csv")
    except Exception as e:
        logger.error(f"❌ Failed to load KAMUS.csv: {e}")

def apply_name_rules(product_name: str) -> tuple:
    """
    Correct product name based on KAMUS.csv and extract normalized brand.
    Returns (corrected_name, extracted_brand).
    """
    if not product_name:
        return "", "UNKNOWN"
        
    import re
    corrected_name = product_name
    extracted_brand = "UNKNOWN"
    
    # 1. Correct name using alias patterns
    name_upper = product_name.upper()
    sorted_aliases = sorted(brand_map.keys(), key=len, reverse=True)
    
    for alias_regex in sorted_aliases:
        brand_utama = brand_map[alias_regex]
        pattern = re.compile(alias_regex, re.IGNORECASE)
        if pattern.search(corrected_name):
            corrected_name = pattern.sub(brand_utama, corrected_name)
            extracted_brand = brand_utama
            
    # 2. If still UNKNOWN, look for direct brand names in name
    if extracted_brand == "UNKNOWN":
        unique_brands = set(brand_map.values())
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

async def init_ml_models():
    """Initialize ML models asynchronously."""
    global tfidf_matcher, sbert_matcher

    # Load Kamus brand alias mapping
    load_kamus()

    try:
        logger.info("📦 Loading TF-IDF model...")
        tfidf_matcher = TFIDFMatcher()
        logger.info("✅ TF-IDF loaded")
    except Exception as e:
        logger.warning(f"⚠️ TF-IDF init failed: {e}")

    try:
        logger.info(f"🧠 Loading SBERT model ({settings.SBERT_MODEL})...")
        sbert_matcher = SBERTMatcher(model_name=settings.SBERT_MODEL)
        logger.info("✅ SBERT loaded")
    except Exception as e:
        logger.warning(f"⚠️ SBERT init failed: {e}")

    # Warm up SBERT embeddings cache from database
    if sbert_matcher and sbert_matcher.model is not None:
        try:
            logger.info("🔄 Warming up SBERT embeddings cache from database...")
            from app_backend.db.database import AsyncSessionLocal
            import asyncio
            async with AsyncSessionLocal() as db:
                # 1. Load all existing embeddings from DB
                stmt = select(ProductEmbedding)
                result = await db.execute(stmt)
                db_rows = result.scalars().all()
                
                loaded_count = 0
                for row in db_rows:
                    if row.embedding_sbert:
                        emb_vec = np.array([float(x) for x in row.embedding_sbert.split(',')], dtype=np.float32)
                        sbert_matcher.embeddings_cache[row.nama_produk] = emb_vec
                        loaded_count += 1
                logger.info(f"✅ Loaded {loaded_count} SBERT embeddings from database into memory cache.")

                # 2. Check for missing embeddings in background
                res_komp = await db.execute(select(DataKompetitor.nama_produk_clean).distinct())
                res_dbklik = await db.execute(select(DataDbKlik.nama_produk_clean).distinct())
                
                all_names = set(res_komp.scalars().all()) | set(res_dbklik.scalars().all())
                all_names = {n for n in all_names if n} # remove None or empty
                
                missing_names = list(all_names - set(sbert_matcher.embeddings_cache.keys()))
                if missing_names:
                    logger.info(f"Found {len(missing_names)} products with missing SBERT embeddings. Encoding in background...")
                    asyncio.create_task(encode_and_cache_missing_embeddings(missing_names))
        except Exception as e:
            logger.warning(f"⚠️ Failed to warm up SBERT embeddings cache: {e}")

async def encode_and_cache_missing_embeddings(names: List[str]):
    """Encodes names and saves them to DB in background."""
    global sbert_matcher
    if not sbert_matcher or not sbert_matcher.model:
        return
        
    try:
        import asyncio
        from app_backend.db.database import AsyncSessionLocal
        from sqlalchemy import insert
        
        batch_size = 500
        for i in range(0, len(names), batch_size):
            chunk = names[i:i+batch_size]
            logger.info(f"Background SBERT encoding: {i}/{len(names)}...")
            
            loop = asyncio.get_running_loop()
            encoded = await loop.run_in_executor(
                None, 
                lambda: sbert_matcher.model.encode(chunk, batch_size=64, convert_to_numpy=True)
            )
            
            async with AsyncSessionLocal() as db:
                records = []
                for j, name in enumerate(chunk):
                    vec = encoded[j]
                    sbert_matcher.embeddings_cache[name] = vec
                    serialized = ",".join(map(str, vec.tolist()))
                    records.append({
                        "nama_produk": name,
                        "embedding_sbert": serialized
                    })
                
                try:
                    await db.execute(insert(ProductEmbedding), records)
                    await db.commit()
                except Exception as ins_err:
                    await db.rollback()
                    logger.warning(f"Background insert error: {ins_err}. Trying fallback...")
                    for rec in records:
                        try:
                            await db.execute(insert(ProductEmbedding).values(rec))
                            await db.commit()
                        except Exception:
                            await db.rollback()
                            
        logger.info("✅ Background SBERT encoding and caching completed!")
    except Exception as e:
        logger.error(f"❌ Background SBERT encoding failed: {e}")


# Create FastAPI app
app = FastAPI(
    title="COMPINTEL API",
    description="Sistem Analisis Pencocokan Produk Hybrid (TF-IDF + SBERT)",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MODELS
# ============================================================

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(text: str) -> str:
    """Text cleaning for preprocessing."""
    import re
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_filename_metadata(filename: str) -> dict:
    """Parse filename untuk ekstrak metadata."""
    try:
        parts = filename.replace('.csv', '').split('_')
        if len(parts) < 3:
            raise ValueError("Format filename tidak valid")

        date_str = parts[0]
        store_name = '_'.join(parts[1:-1])
        status = parts[-1].upper()

        date_obj = datetime.strptime(date_str, "%d-%m-%Y")

        return {
            "tanggal": date_obj.date(),
            "nama_toko": store_name.upper(),
            "status": "READY" if status == "READY" else "HABIS",
            "valid": True
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


# ============================================================
# AUTH & USER ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """Serve the frontend index.html if it exists, otherwise return API info."""
    index_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
    if os.path.exists(index_path):
        return FileResponse(index_path)
        
    local_index = os.path.abspath(os.path.join(os.path.dirname(__file__), "index.html"))
    if os.path.exists(local_index):
        return FileResponse(local_index)
        
    return JSONResponse({
        "name": "COMPINTEL API",
        "version": "2.0.0",
        "status": "running",
        "description": "Sistem Analisis Pencocokan Produk Hybrid",
        "supabase": SUPABASE_AVAILABLE
    })

# Mount data_local static files for offline/simulated data loading
from fastapi.staticfiles import StaticFiles
data_local_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data_local"))
if os.path.exists(data_local_path):
    app.mount("/data_local", StaticFiles(directory=data_local_path), name="data_local")
else:
    backend_data_local = os.path.abspath(os.path.join(os.path.dirname(__file__), "data_local"))
    if os.path.exists(backend_data_local):
        app.mount("/data_local", StaticFiles(directory=backend_data_local), name="data_local")


@app.get("/health")
async def health_check():
    """Health check."""
    return {
        "status": "healthy",
        "ml_tfidf": tfidf_matcher is not None,
        "ml_sbert": sbert_matcher is not None,
        "supabase": get_supabase_client() is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/auth/register")
async def register_user(
    email: str,
    password: str,
    full_name: str,
    company_name: Optional[str] = None
):
    """
    Register new user via Supabase Auth.
    Falls back to mock response if Supabase not configured.
    """
    sb = get_supabase_client()

    if sb:
        try:
            response = sb.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name,
                        "company_name": company_name
                    }
                }
            })
            return {"success": True, "user": response.user, "session": response.session}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Demo mode
        return {
            "success": True,
            "demo": True,
            "message": "Demo mode - Supabase not configured"
        }


@app.post("/api/auth/login")
async def login_user(email: str, password: str):
    """Login user via Supabase Auth."""
    sb = get_supabase_client()

    if sb:
        try:
            response = sb.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            return {"success": True, "user": response.user, "session": response.session}
        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))
    else:
        # Demo mode
        return {
            "success": True,
            "demo": True,
            "user": {"id": "demo", "email": email},
            "message": "Demo mode - Supabase not configured"
        }


@app.post("/api/auth/logout")
async def logout_user():
    """Logout user."""
    sb = get_supabase_client()
    if sb:
        sb.auth.sign_out()
    return {"success": True}


# ============================================================
# DASHBOARD & STATS
# ============================================================

@app.get("/api/dashboard/stats/")
async def get_dashboard_stats(user_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    query = select(
        DataKompetitor.nama_toko,
        func.count(DataKompetitor.id).label('total'),
        func.avg(DataKompetitor.harga).label('avg_price')
    ).group_by(DataKompetitor.nama_toko)

    if user_id:
        query = query.where(DataKompetitor.user_id == user_id)

    try:
        result = await db.execute(query)
        store_stats = result.fetchall()
    except Exception as db_err:
        logger.error(f"Failed to fetch stats from DB: {db_err}")
        return {
            "total_produk": 0,
            "total_toko": 0,
            "toko_stats": [],
            "error": "Database offline"
        }

    total_products = sum(s.total for s in store_stats)

    return {
        "total_produk": total_products,
        "total_toko": len(store_stats),
        "toko_stats": [
            {
                "nama_toko": s.nama_toko,
                "total_produk": s.total,
                "avg_price": float(s.avg_price) if s.avg_price else 0
            }
            for s in store_stats
        ]
    }


# ============================================================
# UPLOAD CSV
# ============================================================

@app.post("/api/upload-kompetitor/")
async def upload_kompetitor(
    file: UploadFile = File(...),
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Upload CSV data kompetitor."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File harus CSV")

    metadata = parse_filename_metadata(file.filename)
    if not metadata["valid"]:
        raise HTTPException(status_code=400, detail=f"Format tidak valid: {metadata.get('error')}")

    content = await file.read()

    try:
        df = pd.read_csv(io.BytesIO(content))
        required_cols = ['NAMA', 'HARGA', 'TERJUAL/BLN']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Kolom wajib tidak ada: {', '.join(missing)}")

        processed_count = 0
        for _, row in df.iterrows():
            nama_original = str(row['NAMA'])
            if not nama_original or nama_original.lower() == 'nan':
                continue
                
            nama_koreksi, brand_ekstraksi = apply_name_rules(nama_original)
            
            brand_final = brand_ekstraksi
            if 'BRAND' in df.columns and pd.notna(row['BRAND']):
                csv_brand = str(row['BRAND']).strip().upper()
                if csv_brand and csv_brand != 'UNKNOWN':
                    found_clean_brand = False
                    for alias_regex, brand_utama in brand_map.items():
                        clean_alias = alias_regex.replace(r'\b', '')
                        if csv_brand == clean_alias:
                            brand_final = brand_utama
                            found_clean_brand = True
                            break
                    if not found_clean_brand:
                        brand_final = csv_brand

            produk = DataKompetitor(
                user_id=user_id,
                nama_produk=nama_koreksi,
                nama_produk_clean=clean_text(nama_koreksi),
                harga=int(row['HARGA']),
                terjual_bln=int(row.get('TERJUAL/BLN', 0)),
                tanggal=metadata['tanggal'],
                nama_toko=metadata['nama_toko'],
                status=metadata['status'],
                brand=brand_final,
                kategori=row.get('KATEGORI'),
                sku=row.get('SKU')
            )
            db.add(produk)
            processed_count += 1

        upload_record = UploadHistory(
            user_id=user_id,
            filename=file.filename,
            nama_toko=metadata['nama_toko'],
            tanggal_scraping=metadata['tanggal'],
            status=metadata['status'],
            row_count=processed_count,
            file_size=len(content),
            status_upload="SUCCESS"
        )
        db.add(upload_record)
        await db.commit()

        return {
            "success": True,
            "message": f"Berhasil upload {processed_count} produk",
            "filename": file.filename,
            "toko": metadata['nama_toko'],
            "total_rows": processed_count
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/upload/history/")
async def get_upload_history(
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get upload history."""
    query = select(UploadHistory).order_by(UploadHistory.created_at.desc()).limit(limit)

    if user_id:
        query = query.where(UploadHistory.user_id == user_id)

    result = await db.execute(query)
    history = result.scalars().all()

    return {
        "data": [
            {
                "id": h.id,
                "filename": h.filename,
                "nama_toko": h.nama_toko,
                "tanggal_scraping": h.tanggal_scraping.isoformat() if h.tanggal_scraping else None,
                "status": h.status,
                "row_count": h.row_count,
                "status_upload": h.status_upload,
                "created_at": h.created_at.isoformat() if h.created_at else None
            }
            for h in history
        ]
    }


# ============================================================
# MATCHING
# ============================================================

@app.get("/api/match/")
async def match_products(
    query: str = Query(..., description="Nama produk yang dicari"),
    base_price: Optional[int] = None,
    threshold: float = Query(0.40, ge=0.1, le=1.0),
    stores: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Pencocokan produk hybrid (TF-IDF + SBERT) menggunakan pemrosesan batch NumPy."""
    base_query = select(DataKompetitor)

    if user_id:
        base_query = base_query.where(DataKompetitor.user_id == user_id)

    if stores:
        store_list = [s.strip().upper() for s in stores.split(',')]
        base_query = base_query.where(DataKompetitor.nama_toko.in_(store_list))

    # Stage 1: Candidate Filtering (Brand & Keyword Matching)
    # Extract query brand and clean text
    corrected_query, query_brand = apply_name_rules(query)
    query_brand = query_brand.upper().strip()
    query_clean = clean_text(corrected_query)
    
    # Extract keywords (length >= 3)
    words = query_clean.split()
    keywords = [w for w in words if len(w) >= 3]
    
    # Common stop words to exclude from keyword search
    stop_words = {
        'dan', 'dengan', 'untuk', 'yang', 'dari', 'toko', 'ready', 'habis', 
        'original', 'promo', 'murah', 'diskon', 'sale', 'termurah', 'baru',
        'new', 'pcs', 'pack', 'unit', 'set', 'box', 'dijual', 'jual'
    }
    keywords = [w for w in keywords if w not in stop_words]
    
    filters = []
    
    # Filter by brand if known (reduces search space significantly)
    if query_brand and query_brand != "UNKNOWN":
        filters.append(
            or_(
                DataKompetitor.brand == query_brand,
                DataKompetitor.brand == "TIDAK ADA BRAND"
            )
        )
        
    # Filter by containing at least one keyword
    if keywords:
        keyword_conditions = [DataKompetitor.nama_produk_clean.ilike(f"%{kw}%") for kw in keywords]
        filters.append(or_(*keyword_conditions))
        
    if filters:
        base_query = base_query.where(and_(*filters))

    try:
        result = await db.execute(base_query)
        products = result.scalars().all()
    except Exception as db_err:
        logger.error(f"Database query failed in /api/match/: {db_err}")
        raise HTTPException(status_code=503, detail="Database connection offline")

    if not products:
        return {"data": [], "count": 0}

    query_clean = clean_text(query)
    target_names = [product.nama_produk_clean or clean_text(product.nama_produk) for product in products]

    # 1. BATCH TF-IDF SIMILARITY
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3))
        tfidf_matrix = vectorizer.fit_transform(target_names)
        query_vec = vectorizer.transform([query_clean])
        tfidf_scores = cosine_similarity(query_vec, tfidf_matrix)[0]
    except Exception as tfidf_err:
        logger.warning(f"Batch TF-IDF calculation failed: {tfidf_err}, using loop fallback")
        # Fallback loop
        tfidf_scores = np.array([
            calculate_tfidf_similarity(query_clean, name) for name in target_names
        ], dtype=np.float32)

    # 2. BATCH SBERT SIMILARITY
    if sbert_matcher and sbert_matcher.model is not None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Encode query once
            query_emb = sbert_matcher.encode([query_clean])
            # Get embeddings from batch cache
            target_embeddings = await sbert_matcher.get_embeddings_batch(target_names, db)
            sbert_scores = cosine_similarity(query_emb, target_embeddings)[0]
        except Exception as sbert_err:
            logger.warning(f"Batch SBERT calculation failed: {sbert_err}, using loop fallback")
            sbert_scores = np.array([
                calculate_sbert_similarity(query_clean, name) for name in target_names
            ], dtype=np.float32)
    else:
        # Fallback loop
        sbert_scores = np.array([
            calculate_sbert_similarity(query_clean, name) for name in target_names
        ], dtype=np.float32)

    # 3. HYBRID SCORE CALCULATION
    alpha = settings.TFIDF_ALPHA
    hybrid_scores = (alpha * tfidf_scores) + ((1 - alpha) * sbert_scores)

    # 4. FILTER AND FORMAT RESULTS
    results = []
    for i, product in enumerate(products):
        score = float(hybrid_scores[i])
        if score >= threshold:
            results.append({
                "id": product.id,
                "nama_produk": product.nama_produk,
                "harga": product.harga,
                "terjual_bln": product.terjual_bln,
                "tanggal": product.tanggal.isoformat() if product.tanggal else None,
                "nama_toko": product.nama_toko,
                "status": product.status,
                "brand": product.brand,
                "sku": product.sku,
                "skor_tfidf": round(float(tfidf_scores[i]), 4),
                "skor_sbert": round(float(sbert_scores[i]), 4),
                "skor_akhir": round(score, 4)
            })

    results.sort(key=lambda x: x["skor_akhir"], reverse=True)

    return {
        "data": results,
        "count": len(results),
        "formula": "S_hybrid = (α × S_TFIDF) + ((1 - α) × S_SBERT)",
        "alpha": settings.TFIDF_ALPHA
    }


# ============================================================
# SIMILARITY CALCULATIONS
# ============================================================

def calculate_tfidf_similarity(query: str, target: str) -> float:
    """TF-IDF character n-gram cosine similarity."""
    if tfidf_matcher:
        return tfidf_matcher.get_similarity(query, target)

    # Fallback: simple character n-gram
    def get_ngrams(text, n):
        text = text.lower().strip()
        return [text[i:i+n] for i in range(max(0, len(text) - n + 1))]

    q_ng = get_ngrams(query, 2) + get_ngrams(query, 3)
    t_ng = get_ngrams(target, 2) + get_ngrams(target, 3)

    if not q_ng or not t_ng:
        return 0.0

    q_freq = {}
    t_freq = {}
    for ng in q_ng:
        q_freq[ng] = q_freq.get(ng, 0) + 1
    for ng in t_ng:
        t_freq[ng] = t_freq.get(ng, 0) + 1

    dot = sum(q_freq.get(t, 0) * t_freq.get(t, 0) for t in set(q_ng + t_ng))
    q_norm = sum(v * v for v in q_freq.values()) ** 0.5
    t_norm = sum(v * v for v in t_freq.values()) ** 0.5

    return dot / (q_norm * t_norm) if q_norm and t_norm else 0.0


def calculate_sbert_similarity(query: str, target: str) -> float:
    """SBERT semantic similarity."""
    if sbert_matcher:
        return sbert_matcher.get_similarity(query, target)

    # Fallback: keyword matching
    q_words = set(query.lower().split())
    t_words = set(target.lower().split())
    intersection = len(q_words & t_words)
    union = len(q_words | t_words)

    return intersection / union if union > 0 else 0.0


# ============================================================
# EXPORT
# ============================================================

@app.get("/api/export/csv/")
async def export_to_csv(
    toko: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Export data ke CSV."""
    query = select(DataKompetitor)

    if user_id:
        query = query.where(DataKompetitor.user_id == user_id)
    if toko:
        query = query.where(DataKompetitor.nama_toko == toko.upper())

    result = await db.execute(query.order_by(DataKompetitor.tanggal))
    products = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Nama Produk', 'Toko', 'Harga', 'Terjual/Bulan', 'Tanggal', 'Status', 'Brand', 'SKU'])

    for p in products:
        writer.writerow([
            p.nama_produk, p.nama_toko, p.harga, p.terjual_bln,
            p.tanggal.isoformat() if p.tanggal else '', p.status,
            p.brand or '', p.sku or ''
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=compintel_export_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
