import os
import pandas as pd
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from db import engine, SessionLocal, Base
from models import FileRecord, ScrapeRecord
from fastapi.middleware.cors import CORSMiddleware


# Create DB tables
from db import init_db
init_db()

app = FastAPI()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # <- Wildcard for any origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- Dummy scraping logic ----
def scrape_data(item_id: str):
    """Simulate scraping. Replace this with actual Selenium logic later."""
    print(f"Scraping data for ID: {item_id}")
    return f"Data for {item_id}"


# ---- Background task ----
def process_file(file_id: int, file_path: str):
    db = SessionLocal()
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        first_col = df.columns[0]
        ids = df[first_col].dropna().astype(str).tolist()

        for item_id in ids:
            # Simulate scraping
            result = scrape_data(item_id)
            record = ScrapeRecord(file_id=file_id, item_id=item_id, status="done")
            db.add(record)
            db.commit()

        # After all scraping is done, create dummy output Excel
        file_record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
        if file_record:
            output_filename = f"output_{file_record.input_filename}.xlsx"
            output_path = os.path.join(UPLOAD_DIR, output_filename)
            
            # Example dummy data
            dummy_df = pd.DataFrame({
                "id": ids,
                "scraped_data": [f"Data for {i}" for i in ids]
            })
            dummy_df.to_excel(output_path, index=False, engine="openpyxl")

            # Update output_filename in FileRecord
            file_record.output_filename = output_filename
            db.commit()

    finally:
        db.close()

@app.post("/upload/")
async def upload_excel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    new_record = FileRecord(input_filename=file.filename)
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    background_tasks.add_task(process_file, new_record.id, file_path)
    return {
        "file_id": new_record.id,
        "filename": new_record.input_filename,
        "status": "processing"
    }


@app.get("/scrape-records/")
def get_scrape_records(db: Session = Depends(get_db)):
    return db.query(ScrapeRecord).all()

@app.get("/files/scrap_records/{file_id}/")
def get_scrap_records(file_id: int, db: Session = Depends(get_db)):
    records = db.query(ScrapeRecord).filter(ScrapeRecord.file_id == file_id).all()
    if not records:
        raise HTTPException(status_code=404, detail="No scrap records found for this file ID")
    return records


@app.get("/download/{file_id}", response_class=FileResponse)
def download_file(file_id: int, db: Session = Depends(get_db)):
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = os.path.join(UPLOAD_DIR, record.input_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File missing on server")

    return FileResponse(file_path, filename=record.input_filename)


@app.get("/files/")
def list_files(db: Session = Depends(get_db)):
    files = db.query(FileRecord).all()
    return [
        {
            "id": f.id,
            "input_filename": f.input_filename,
            "output_filename": f.output_filename,
            "created_date": f.created_date
        }
        for f in files
    ]

@app.get("/download/output/{file_id}")
def download_output(file_id: int, db: Session = Depends(get_db)):
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not record or not record.output_filename:
        raise HTTPException(status_code=404, detail="Output file not found")

    file_path = os.path.join(UPLOAD_DIR, record.output_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Output file missing on server")

    return FileResponse(file_path, filename=record.output_filename)


@app.get("/files/output/")
def list_output_files(db: Session = Depends(get_db)):
    """List only files that have output_filename (not null or empty)"""
    files = db.query(FileRecord).filter(
        FileRecord.output_filename.isnot(None),
        FileRecord.output_filename != ""
    ).all()
    
    return [
        {
            "id": f.id,
            "input_filename": f.input_filename,
            "output_filename": f.output_filename,
            "created_date": f.created_date
        }
        for f in files
    ]