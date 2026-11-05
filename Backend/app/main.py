from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.runnables import RunnableConfig
from pathlib import Path
import shutil
import uuid
import time

from app.agent.graph import graph
from app.services.database import (
    get_connection,
    set_active_dataset,
    get_anomaly_report,
    get_active_dataset_name
)
from app.services.session_store import session_manager
from app.services.logger_service import logger, get_recent_logs
from app.services.cache_service import query_cache


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

logger.info("Agentic AI Data Analyst Backend initialized.")


class AnalyzeRequest(BaseModel):
    question: str
    session_id: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_stats": query_cache.get_stats()
    }


@app.get("/cache/stats")
def get_cache_stats():
    """Returns real-time query cache telemetry and hit ratio."""
    return query_cache.get_stats()


@app.post("/cache/clear")
def clear_cache():
    """Purges the in-memory query cache."""
    query_cache.clear()
    return {"status": "cleared", "message": "In-memory query cache cleared."}


@app.get("/logs")
def get_logs(lines: int = 50):
    """Retrieves recent backend application logs for observability."""
    return {
        "lines": lines,
        "logs": get_recent_logs(lines)
    }


@app.get("/anomalies")
def get_anomalies():
    try:
        report = get_anomaly_report()
        logger.info(f"[ANOMALY SCAN] completed successfully (anomalies_detected={report.get('anomalies_detected')})")
        return report
    except Exception as e:
        logger.error(f"[ANOMALY ERROR]: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to scan anomalies: {str(e)}"
        )


@app.post("/session/clear")
def clear_session(request: dict = None):
    sid = (request or {}).get("session_id")
    if sid:
        session_manager.clear_session(sid)
        logger.info(f"[SESSION CLEARED] session_id={sid}")
    return {"status": "cleared", "session_id": sid}


@app.get("/session/{session_id}/history")
def get_session_history(session_id: str):
    history = session_manager.get_history(session_id)
    return {"session_id": session_id, "history": history}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())
    dataset_name = get_active_dataset_name()

    logger.info(f"[REQUEST] /analyze session_id={session_id} dataset={dataset_name} question='{request.question}'")

    # 1. Check in-memory query cache
    cached_data = query_cache.get(dataset_name, request.question)
    if cached_data:
        cached_data["session_id"] = session_id
        cached_data["latency_ms"] = round((time.time() - start_time) * 1000, 2)
        # Record turn into session memory
        session_manager.add_turn(
            session_id=session_id,
            question=request.question,
            summary=cached_data.get("summary", ""),
            sql_query=cached_data.get("sql_query", ""),
            findings=cached_data.get("findings", []),
            evidence=cached_data.get("evidence", [])
        )
        return cached_data

    # 2. Prepare conversational agent state
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

    try:
        result = graph.invoke(
            initial_state,
            config=config
        )
    except Exception as e:
        logger.error(f"[AGENT ERROR] session_id={session_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis pipeline error: {str(e)}"
        )

    elapsed = round(time.time() - start_time, 2)
    chart_type = result.get("chart", {}).get("type", "none")
    logger.info(f"[ANALYSIS SUCCESS] session_id={session_id} duration={elapsed}s chart={chart_type} sql_len={len(result.get('sql_query', ''))}")

    # Record completed turn in session memory
    session_manager.add_turn(
        session_id=session_id,
        question=request.question,
        summary=result.get("summary", ""),
        sql_query=result.get("sql_query", ""),
        findings=result.get("findings", []),
        evidence=result.get("evidence", [])
    )

    response_payload = {
        "session_id": session_id,
        "cached": False,
        "latency_ms": round(elapsed * 1000, 2),
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

    # Store fresh result in cache
    query_cache.set(dataset_name, request.question, response_payload)

    return response_payload


@app.post("/upload")
async def upload(file: UploadFile = File(...)):

    if not file.filename:
        logger.warning("[UPLOAD REJECTED] No file selected.")
        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )

    if not file.filename.lower().endswith(".csv"):
        logger.warning(f"[UPLOAD REJECTED] Non-csv file attempted: {file.filename}")
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
            logger.warning(f"[UPLOAD REJECTED] File too large: {file_size} bytes")
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

        # Invalidate old cache entries on new dataset upload
        query_cache.clear()
        logger.info(f"[UPLOAD SUCCESS] file='{safe_filename}' size={file_size} bytes rows={row_count} columns={column_count}")

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

        logger.error(f"[UPLOAD FAILED] file='{file.filename}': {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load CSV: {str(e)}"
        )
