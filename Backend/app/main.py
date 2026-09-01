from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.runnables import RunnableConfig
from pathlib import Path
import shutil

from app.agent.graph import graph
from app.services.database import get_connection, set_active_dataset


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024

app = FastAPI(title="AI Data Analyst")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/analyze")
def analyze(request: AnalyzeRequest):

    initial_state = {
        "question": request.question,
        "schema": "",
        "data_quality": "",
        "sql_query": "",
        "query_result": "",
        "error": "",
        "sql_attempts": 0,
        "investigation_plan": "",
        "observations": "",
        "query_count": 0,
        "summary": "",
        "findings": [],
        "evidence": [],
        "recommendations": [],
        "chart": {},
        "final_answer": ""
    }

    config = RunnableConfig(
        run_name="Data Analysis",
        tags=["data-analyst", "development"],
        metadata={
            "app": "AI Data Analyst"
        }
    )

    result = graph.invoke(
        initial_state,
        config=config
    )

    return {
        "summary": result["summary"],
        "findings": result["findings"],
        "evidence": result["evidence"],
        "recommendations": result["recommendations"],
        "chart": result["chart"],
        "final_answer": result["final_answer"]
    }


@app.post("/upload")
async def upload(file: UploadFile = File(...)):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported."
        )

    safe_filename = Path(file.filename).name
    file_path = UPLOAD_DIR / safe_filename

    try:

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = file_path.stat().st_size

        if file_size > MAX_FILE_SIZE:
            file_path.unlink()

            raise HTTPException(
                status_code=400,
                detail="File size cannot exceed 50MB."
            )

        set_active_dataset(file_path)

        conn = get_connection()

        row_count = conn.execute(
            "SELECT COUNT(*) FROM dataset"
        ).fetchone()[0]

        columns = conn.execute(
            "DESCRIBE dataset"
        ).fetchall()

        column_count = len(columns)

        conn.close()

        return {
            "success": True,
            "filename": safe_filename,
            "size": file_size,
            "rows": row_count,
            "columns": column_count,
            "status": "ready"
        }

    except HTTPException:
        raise

    except Exception as e:

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=400,
            detail=f"Failed to load CSV: {str(e)}"
        )