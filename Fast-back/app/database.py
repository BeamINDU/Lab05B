from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://palletopt:palletopt@13.212.22.165:5432/palletopt"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency สำหรับใช้ใน API
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
