from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.runnables import RunnableConfig
from pathlib import Path
import shutil
import uuid

from app.agent.graph import graph
from app.services.database import get_connection, set_active_dataset, get_anomaly_report
from app.services.session_store import session_manager


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024

app = FastAPI(title="AI Data Analyst")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://agentic-ai-data-analyst.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    question: str
    session_id: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/anomalies")
def get_anomalies():
    try:
        report = get_anomaly_report()
        return report
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to scan anomalies: {str(e)}"
        )


@app.post("/session/clear")
def clear_session(request: dict = None):
    sid = (request or {}).get("session_id")
    if sid:
        session_manager.clear_session(sid)
    return {"status": "cleared", "session_id": sid}


@app.get("/session/{session_id}/history")
def get_session_history(session_id: str):
    history = session_manager.get_history(session_id)
    return {"session_id": session_id, "history": history}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):

    session_id = request.session_id or str(uuid.uuid4())
    conversation_history = session_manager.format_history_for_prompt(session_id)

    initial_state = {
        "question": request.question,
        "session_id": session_id,
        "conversation_history": conversation_history,
        "schema": "",
        "data_quality": "",
        "sql_query": "",
        "pandas_code": "",
        "anomalies": [],
        "reasoning": "",
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
            "app": "AI Data Analyst",
            "session_id": session_id
        }
    )

    result = graph.invoke(
        initial_state,
        config=config
    )

    # Record completed turn in session memory
    session_manager.add_turn(
        session_id=session_id,
        question=request.question,
        summary=result.get("summary", ""),
        sql_query=result.get("sql_query", ""),
        findings=result.get("findings", []),
        evidence=result.get("evidence", [])
    )

    return {
        "session_id": session_id,
        "summary": result.get("summary", ""),
        "findings": result.get("findings", []),
        "evidence": result.get("evidence", []),
        "recommendations": result.get("recommendations", []),
        "chart": result.get("chart", {}),
        "final_answer": result.get("final_answer", ""),
        "sql_query": result.get("sql_query", ""),
        "pandas_code": result.get("pandas_code", ""),
        "anomalies": result.get("anomalies", []),
        "reasoning": result.get("reasoning", ""),
        "investigation_plan": result.get("investigation_plan", "")
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
