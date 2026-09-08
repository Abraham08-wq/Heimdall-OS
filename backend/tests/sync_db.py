# sync_db.py
from app.models.models import Base
from app.core.database import engine # Ensure this imports your SQLAlchemy engine

print("Starting database schema synchronization...")

try:
    # This checks all models and creates tables that don't exist yet
    Base.metadata.create_all(bind=engine)
    print("Database tables created/updated successfully.")
except Exception as e:
    print(f"Error during synchronization: {e}")
    