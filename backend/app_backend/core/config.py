"""
Konfigurasi aplikasi dari environment variables.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API
    API_PREFIX: str = "/api"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/compintel"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/compintel"

    # ML Configuration
    TFIDF_ALPHA: float = 0.5  # Weight for TF-IDF in hybrid formula
    TFIDF_THRESHOLD: float = 0.60  # Default threshold
    
    # Dynamically check if fine-tuned local model exists in workspace root
    _local_path: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "model_sbert_local"))
    SBERT_MODEL: str = _local_path if os.path.exists(_local_path) else "paraphrase-multilingual-MiniLM-L12-v2"

    # Upload Settings
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "./data/uploads"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
