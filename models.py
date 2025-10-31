from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from db import Base, engine, SessionLocal

# Table to store uploaded files
class FileRecord(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    input_filename = Column(String, nullable=False)
    output_filename = Column(String, nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)

# New table to track scraping status
class ScrapeRecord(Base):
    __tablename__ = "scrape_records"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, nullable=False)       # linked to FileRecord
    item_id = Column(String, nullable=False)        # ID from Excel file
    status = Column(String, default="pending")      # e.g., pending / done / failed
    created_date = Column(DateTime, default=datetime.utcnow)
