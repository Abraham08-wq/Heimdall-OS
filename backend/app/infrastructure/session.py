from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Construct the Database URL
# Sync URL for standard requests (using psycopg2 or similar)
# We need to make sure the driver is installed. 
# The config uses "postgresql+asyncpg" for async, but for the basic sync endpoints we might want synchronous.
# For simplicity in this "wiring phase", we will use synchronous `psycopg2` or `psycopg` if available,
# or just standard SQL Alchemy Sync.

# Let's check config again. settings.SQLALCHEMY_DATABASE_URI is built with postgresql+asyncpg.
# For simplicity with FastAPI dependencies (yield), sync is often easier unless we go full async.
# Given the constraints, I will create a Sync Engine for the deps.

SQLALCHEMY_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI.replace("+asyncpg", "")

# PgBouncer Connection Pooling Strategy (Pillar 1)
# With PgBouncer handling transaction-level pooling, we minimize SQLAlchemy's internal pooling overhead.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_size=10,          # Base pool size matching standard PgBouncer capacity
    max_overflow=20,       # Allow bursting for high-throughput bursts
    pool_pre_ping=True,    # Fail fast on stale sockets when PgBouncer is not present
    pool_recycle=300,      # Recycle connections every 5 minutes to prevent stale sockets
    echo=False             # Disable echo for production performance
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
