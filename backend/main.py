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
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
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


async def init_ml_models():
    """Initialize ML models asynchronously."""
    global tfidf_matcher, sbert_matcher

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
    """Root endpoint."""
    return {
        "name": "COMPINTEL API",
        "version": "2.0.0",
        "status": "running",
        "description": "Sistem Analisis Pencocokan Produk Hybrid",
        "supabase": SUPABASE_AVAILABLE
    }


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

    result = await db.execute(query)
    store_stats = result.fetchall()

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
            produk = DataKompetitor(
                user_id=user_id,
                nama_produk=row['NAMA'],
                nama_produk_clean=clean_text(str(row['NAMA'])),
                harga=int(row['HARGA']),
                terjual_bln=int(row.get('TERJUAL/BLN', 0)),
                tanggal=metadata['tanggal'],
                nama_toko=metadata['nama_toko'],
                status=metadata['status'],
                brand=row.get('BRAND'),
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

    result = await db.execute(base_query)
    products = result.scalars().all()

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
            target_embeddings = sbert_matcher.get_embeddings_batch(target_names)
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
