"""
Database connection and session management.
"""

import socket

# Force IPv4 to prevent IPv6 connection timeout issues (common on Windows/certain ISPs)
original_getaddrinfo = socket.getaddrinfo
def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if family == socket.AF_UNSPEC or family == socket.AF_INET6:
        family = socket.AF_INET
    return original_getaddrinfo(host, port, family, type, proto, flags)
socket.getaddrinfo = ipv4_only_getaddrinfo

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app_backend.core.config import settings

# Convert postgresql:// to postgresql+asyncpg:// for async engine
db_url = settings.DATABASE_URL
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(
    db_url,
    echo=False,  # Set to True for SQL debugging
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"prepared_statement_cache_size": 0}
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


async def get_db():
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
