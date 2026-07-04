"""
Database models untuk COMPINTEL.
"""

from sqlalchemy import Column, Integer, String, BigInteger, Date, DateTime, Text, Index
from sqlalchemy.sql import func
from app_backend.db.database import Base


class DataKompetitor(Base):
    """Model untuk data produk kompetitor."""

    __tablename__ = "data_kompetitor"

    id = Column(Integer, primary_key=True, index=True)
    nama_produk = Column(String(500), nullable=False)
    nama_produk_clean = Column(String(500))
    harga = Column(BigInteger, nullable=False)
    terjual_bln = Column(Integer, default=0)
    tanggal = Column(Date, nullable=False, index=True)
    nama_toko = Column(String(100), nullable=False, index=True)
    status = Column(String(20))  # 'READY' or 'HABIS'
    brand = Column(String(100))
    kategori = Column(String(100))
    sku = Column(String(100), index=True)
    created_at = Column(DateTime, server_default=func.now())

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_kompetitor_toko_tanggal', 'nama_toko', 'tanggal'),
        Index('idx_kompetitor_produk_toko', 'nama_produk', 'nama_toko'),
    )


class DataDbKlik(Base):
    """Model untuk data produk DB KLIK (produk acuan)."""

    __tablename__ = "data_db_klik"

    id = Column(Integer, primary_key=True, index=True)
    nama_produk = Column(String(500), nullable=False)
    nama_produk_clean = Column(String(500))
    harga = Column(BigInteger)
    terjual_bln = Column(Integer, default=0)
    tanggal = Column(Date, nullable=False, index=True)
    brand = Column(String(100))
    kategori = Column(String(100))
    sku = Column(String(100), index=True)
    created_at = Column(DateTime, server_default=func.now())


class UploadHistory(Base):
    """Model untuk riwayat upload file."""

    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    nama_toko = Column(String(100), nullable=False)
    tanggal_scraping = Column(Date)
    status = Column(String(20))  # 'READY' or 'HABIS'
    row_count = Column(Integer, default=0)
    file_size = Column(BigInteger)
    status_upload = Column(String(20), default='PENDING')  # 'SUCCESS', 'FAILED', 'PENDING'
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class ProductEmbedding(Base):
    """Model untuk cache embeddings produk (TF-IDF & SBERT)."""

    __tablename__ = "produk_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    nama_produk = Column(String(500), nullable=False, unique=True, index=True)
    embedding_tfidf = Column(Text)  # Serialized TF-IDF vector
    embedding_sbert = Column(Text)  # Serialized SBERT vector
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
