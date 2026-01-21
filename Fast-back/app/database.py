from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://palletopt:palletopt@192.168.11.97:5436/palletopt"
)


def create_db_engine(database_url: str, max_retries: int = 10, retry_interval: int = 2):
    """
    Create database engine with retry logic
    """
    for attempt in range(max_retries):
        try:
            engine = create_engine(database_url)
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection established successfully")
            return engine
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_interval * (attempt + 1)  # Progressive wait time
                logger.warning(
                    f"Database connection failed (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(
                    f"Failed to connect to database after {max_retries} attempts"
                )
                raise


engine = create_db_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



# Dependency สำหรับใช้ใน API
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
