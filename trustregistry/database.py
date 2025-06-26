import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Sync engine for migrations
POSTGRES_DATABASE_URL = os.getenv(
    "POSTGRES_DATABASE_URL",
    "postgresql://trustregistry:trustregistry@trustregistry-db:5432/trustregistry",
)

# Async engine for application use - automatically add asyncpg driver
POSTGRES_ASYNC_DATABASE_URL = POSTGRES_DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://", 1
).split("?")[0]  # Ensure no query parameters are included

# Pool settings optimized for pgpool
POSTGRES_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", "5"))
POSTGRES_MAX_OVERFLOW = int(os.getenv("POSTGRES_MAX_OVERFLOW", "2"))
POSTGRES_POOL_RECYCLE = int(os.getenv("POSTGRES_POOL_RECYCLE", "3600"))  # 1 hour
POSTGRES_POOL_TIMEOUT = float(os.getenv("POSTGRES_POOL_TIMEOUT", "30"))
POSTGRES_POOL_PRE_PING = os.getenv("POSTGRES_POOL_PRE_PING", "true").lower() == "true"
POSTGRES_SSL_REQUIRED = os.getenv("POSTGRES_SSL_REQUIRED", "false").lower() == "true"

# For debugging
SQLALCHEMY_ECHO_POOL = os.getenv("SQLALCHEMY_ECHO_POOL", "false").lower() == "true"

# Sync engine for migrations
engine = create_engine(
    url=POSTGRES_DATABASE_URL,
    pool_size=POSTGRES_POOL_SIZE,
    max_overflow=POSTGRES_MAX_OVERFLOW,
    pool_recycle=POSTGRES_POOL_RECYCLE,
    pool_timeout=POSTGRES_POOL_TIMEOUT,
    pool_pre_ping=POSTGRES_POOL_PRE_PING,
    echo_pool=SQLALCHEMY_ECHO_POOL,
)

# Async engine for application
async_engine = create_async_engine(
    url=POSTGRES_ASYNC_DATABASE_URL,
    pool_size=POSTGRES_POOL_SIZE,
    max_overflow=POSTGRES_MAX_OVERFLOW,
    pool_recycle=POSTGRES_POOL_RECYCLE,
    pool_timeout=POSTGRES_POOL_TIMEOUT,
    pool_pre_ping=POSTGRES_POOL_PRE_PING,
    echo_pool=SQLALCHEMY_ECHO_POOL,
    connect_args={"ssl": POSTGRES_SSL_REQUIRED},
)

# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()
