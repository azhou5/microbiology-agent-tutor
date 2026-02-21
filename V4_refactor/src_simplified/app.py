import logging
import os
import json
from datetime import datetime
from typing import Dict, Optional, List, Any
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src_simplified.agents.orchestrator import Orchestrator
from src_simplified.utils.case_loader import CaseLoader
from src_simplified.utils.llm import chat_complete
from src_simplified.tools.feedback_tool import FeedbackTool
from src_simplified.config.config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MicroTutor Simplified")

APP_FILE = Path(__file__).resolve()
PROJECT_ROOT = APP_FILE.parent.parent
SRC_SIMPLIFIED_DIR = APP_FILE.parent

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage (in-memory for simplicity)
sessions: Dict[str, Orchestrator] = {}

# Templates
templates = Jinja2Templates(directory=str(SRC_SIMPLIFIED_DIR / "api" / "templates"))

# Mount static files using absolute paths so startup cwd does not matter.
app.mount("/static", StaticFiles(directory=str(SRC_SIMPLIFIED_DIR / "api" / "static")), name="static")
app.mount("/images", StaticFiles(directory=str(PROJECT_ROOT / "ID_Images")), name="images")

# Initialize Feedback Tool
feedback_tool = FeedbackTool(
    index_dir=config.FEEDBACK_INDEX_DIR,
    enabled=config.FEEDBACK_INDEXING_ENABLED,
)


def _feedback_file_path() -> Path:
    return feedback_tool.index_dir / "new_feedback.json"


def _load_feedback_entries() -> List[Dict[str, Any]]:
    path = _feedback_file_path()
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _parse_iso_day(ts: str) -> Optional[str]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return None


def _trend_counts(entries: List[Dict[str, Any]], kind: str) -> Dict[str, int]:
    per_day: Dict[str, int] = {}
    for e in entries:
        if e.get("feedback_kind", "message") != kind:
            continue
        day = _parse_iso_day(str(e.get("timestamp", "")))
        if not day:
            continue
        per_day[day] = per_day.get(day, 0) + 1
    return dict(sorted(per_day.items()))

# --- Pydantic Models ---

class Message(BaseModel):
    role: str
    content: str

class StartCaseRequest(BaseModel):
    organism: str
    case_id: str
    model_name: Optional[str] = None
    model_provider: Optional[str] = None
    enable_guidelines: Optional[bool] = False

class ChatRequest(BaseModel):
    message: str
    case_id: str
    history: Optional[List[Dict[str, Any]]] = None
    organism_key: Optional[str] = None
    model_name: Optional[str] = None
    model_provider: Optional[str] = None
    feedback_enabled: Optional[bool] = None
    feedback_threshold: Optional[float] = None
    current_phase: Optional[str] = None
    enable_guidelines: Optional[bool] = False

class FeedbackRequest(BaseModel):
    rating: int
    message: str
    history: List[Dict[str, Any]]
    feedback_text: Optional[str] = ""
    replacement_text: Optional[str] = ""
    case_id: Optional[str] = None
    organism: Optional[str] = ""

class CaseFeedbackRequest(BaseModel):
    detail: int
    helpfulness: int
    accuracy: int
    comments: Optional[str] = ""
    case_id: str
    organism: Optional[str] = ""

class ClarifyRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = []

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/v1/organisms")
async def get_available_organisms():
    """Get list of organisms that have pre-generated cases available."""
    loader = CaseLoader()
    organisms = loader.list_available_organisms()
    return {
        "status": "success",
        "organisms": organisms,
        "hpi_organisms": organisms, # Simplified: same list
        "count": len(organisms)
    }

@app.post("/api/v1/start_case")
async def start_case(request: StartCaseRequest):
    try:
        orchestrator = Orchestrator(request.organism)
        sessions[request.case_id] = orchestrator
        
        first_message = orchestrator.get_first_message()
        
        # Format response to match frontend expectation
        return {
            "initial_message": f"Welcome to today's case.\n\n{first_message}\n\nBegin by asking specific questions.",
            "history": [
                {"role": "assistant", "content": f"Welcome to today's case.\n\n{first_message}\n\nBegin by asking specific questions."}
            ],
            "case_id": request.case_id,
            "organism": request.organism,
            "metadata": {
                "case_id": request.case_id,
                "organism": request.organism,
                "current_phase": orchestrator.current_state
            }
        }
    except Exception as e:
        logger.error(f"Failed to start case: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    case_id = request.case_id
    if case_id not in sessions:
        # Try to recover session if organism is provided
        if request.organism_key:
             try:
                 orchestrator = Orchestrator(request.organism_key)
                 sessions[case_id] = orchestrator
                 # Restore history if provided
                 if request.history:
                     orchestrator.conversation_history = request.history
             except Exception:
                 raise HTTPException(status_code=404, detail="Session expired. Please start a new case.")
        else:
            raise HTTPException(status_code=404, detail="Session expired. Please start a new case.")
    
    orchestrator = sessions[case_id]
    
    # Sync state if provided and different
    if request.current_phase and request.current_phase != orchestrator.current_state:
        # We could update the orchestrator state here if we trust the frontend
        # For now, we'll log it
        logger.info(f"Frontend phase: {request.current_phase}, Backend phase: {orchestrator.current_state}")

    result = orchestrator.process_message(request.message)
    
    if isinstance(result, dict):
        response_text = result.get("response", "")
        subagent_response = result.get("subagent_response", response_text)
        orchestrator_message = result.get("orchestrator_message")
        subagent_name = result.get("subagent_name", orchestrator.current_state)
        image_url = result.get("image_url")
    else:
        response_text = result
        subagent_response = result
        orchestrator_message = None
        subagent_name = orchestrator.current_state
        image_url = None
    
    # Determine tools used based on state
    tool_map = {
        "information_gathering": "patient",
        "differential_diagnosis": "maintutor_differential",
        "tests_management": "tests_management",
        "deeper_dive": "deeper_dive_tutor",
        "feedback": "feedback",
        "post_case_mcq": "post_case_assessment"
    }
    tool_used = tool_map.get(orchestrator.current_state, "tutor")

    return {
        "response": response_text,
        "orchestrator_message": orchestrator_message,
        "subagent_response": subagent_response,
        "main_speaker": "maintutor",
        "subagent_speaker": tool_used,
        "subagent_name": subagent_name,
        "image_url": image_url,
        "history": orchestrator.conversation_history,
        "tools_used": [tool_used],
        "metadata": {
            "current_phase": orchestrator.current_state,
            "organism": orchestrator.organism_name,
            "case_id": case_id,
            "state": orchestrator.current_state, # For compatibility
            "image_url": image_url, # Pass image URL to frontend
            "main_speaker": "maintutor",
            "subagent_speaker": tool_used,
            "subagent_name": subagent_name
        },
        "feedback_examples": [] # Placeholder for feedback examples
    }

@app.post("/api/v1/feedback")
async def submit_feedback(request: FeedbackRequest):
    logger.info(f"[FEEDBACK] Rating: {request.rating}, Message: {request.message[:50]}...")
    
    try:
        feedback_data = {
            "feedback_kind": "message",
            "rating": request.rating,
            "message": request.message,
            "feedback_text": request.feedback_text,
            "replacement_text": request.replacement_text,
            "case_id": request.case_id,
            "organism": request.organism,
            "history": request.history,
            "timestamp": datetime.now().isoformat()
        }
        feedback_tool.save_feedback(feedback_data)
        return {"status": "success", "message": "Feedback saved"}
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")

@app.post("/api/v1/case_feedback")
async def submit_case_feedback(request: CaseFeedbackRequest):
    logger.info(f"[CASE_FEEDBACK] Case: {request.case_id}, Ratings: {request.detail}/{request.helpfulness}/{request.accuracy}")
    try:
        avg_case_rating = round((request.detail + request.helpfulness + request.accuracy) / 3.0, 2)
        feedback_data = {
            "feedback_kind": "case",
            "rating": avg_case_rating,
            "detail": request.detail,
            "helpfulness": request.helpfulness,
            "accuracy": request.accuracy,
            "comments": request.comments,
            "case_id": request.case_id,
            "organism": request.organism,
            "timestamp": datetime.now().isoformat()
        }
        feedback_tool.save_feedback(feedback_data)
        return {"status": "success", "message": "Case feedback received"}
    except Exception as e:
        logger.error(f"Failed to save case feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to save case feedback")

@app.post("/api/v1/clarify")
async def clarify_question(request: Dict[str, Any]):
    message = request.get("message", "")
    history = request.get("history", [])
    
    if not message:
        return {"response": "Please ask a question!"}
    
    try:
        system_prompt = "You are a helpful medical education assistant. Answer questions clearly and concisely. Keep answers brief (2-4 sentences)."
        messages = [{"role": "system", "content": system_prompt}]
        if history:
             # Take last few messages for context
             messages.extend(history[-4:])
        messages.append({"role": "user", "content": message})
        
        response = chat_complete(messages)
        return {"response": response}
    except Exception as e:
        logger.error(f"Clarify failed: {e}")
        return {"response": "Sorry, I couldn't process that question."}

@app.get("/api/v1/config")
async def get_config():
    return {
        "use_azure": True,
        "current_model": config.MODEL_NAME
    }

# --- Stub Endpoints for Missing Features ---

@app.get("/api/v1/analytics/feedback/stats")
async def get_feedback_stats():
    entries = _load_feedback_entries()
    message_entries = [e for e in entries if e.get("feedback_kind", "message") == "message"]
    case_entries = [e for e in entries if e.get("feedback_kind", "message") == "case"]

    ratings: List[float] = []
    for e in entries:
        try:
            ratings.append(float(e.get("rating")))
        except Exception:
            pass
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    today = datetime.now().date().isoformat()
    msg_trend = sum(1 for e in message_entries if _parse_iso_day(str(e.get("timestamp", ""))) == today)
    case_trend = sum(1 for e in case_entries if _parse_iso_day(str(e.get("timestamp", ""))) == today)

    last_update = None
    for e in entries:
        ts = e.get("timestamp")
        if isinstance(ts, str):
            if last_update is None or ts > last_update:
                last_update = ts
    if last_update is None:
        last_update = datetime.now().isoformat()

    # Shape matches dashboard.js -> updateStatsDisplay(statsData.data)
    return {
        "status": "success",
        "data": {
            "message_feedback": {"total": len(message_entries), "trend": msg_trend},
            "case_feedback": {"total": len(case_entries), "trend": case_trend},
            "overall": {
                "avg_rating": str(avg_rating),
                "last_update": last_update
            }
        }
    }

@app.get("/api/v1/analytics/feedback/trends")
async def get_feedback_trends(time_range: str = "all"):
    entries = _load_feedback_entries()
    message_by_day = _trend_counts(entries, "message")
    case_by_day = _trend_counts(entries, "case")

    all_days = sorted(set(message_by_day.keys()) | set(case_by_day.keys()))
    if time_range == "30d":
        all_days = all_days[-30:]
    elif time_range == "7d":
        all_days = all_days[-7:]

    msg_cum: List[int] = []
    case_cum: List[int] = []
    m_total = 0
    c_total = 0
    for d in all_days:
        m_total += message_by_day.get(d, 0)
        c_total += case_by_day.get(d, 0)
        msg_cum.append(m_total)
        case_cum.append(c_total)

    # Shape matches dashboard.js -> updateTrendsChart(trendsData.data)
    return {
        "status": "success",
        "data": {
            "labels": all_days,
            "datasets": [
                {
                    "label": "Message Feedback",
                    "data": msg_cum,
                    "borderColor": "#3b82f6",
                    "backgroundColor": "rgba(59, 130, 246, 0.15)",
                    "tension": 0.2
                },
                {
                    "label": "Case Feedback",
                    "data": case_cum,
                    "borderColor": "#10b981",
                    "backgroundColor": "rgba(16, 185, 129, 0.15)",
                    "tension": 0.2
                }
            ]
        }
    }

@app.get("/api/v1/faiss/reindex-status")
async def get_faiss_status():
    if not feedback_tool.enabled:
        return {
            "is_reindexing": False,
            "last_reindex_complete": None,
            "current_duration": None,
            "reindex_count": 0,
            "last_error": "disabled"
        }
    # Shape matches dashboard.js -> updateFAISSStatus(data)
    reindex_count = int(getattr(feedback_tool.index, "ntotal", 0) or 0)
    has_error = None if reindex_count >= 0 else "FAISS unavailable"
    return {
        "is_reindexing": False,
        "last_reindex_complete": None,
        "current_duration": None,
        "reindex_count": reindex_count,
        "last_error": has_error
    }

@app.post("/api/v1/faiss/update")
async def trigger_faiss_update(request: Dict[str, Any]):
    del request
    if not feedback_tool.enabled:
        return {"status": "disabled", "message": "FAISS indexing is disabled by configuration"}
    return {"status": "queued", "message": "FAISS re-index queued (stub)"}

@app.get("/api/v1/db/stats")
async def db_stats():
    # Used by dashboard.js fetchFeedbackStats()
    entries = _load_feedback_entries()
    case_count = sum(1 for e in entries if e.get("feedback_kind", "message") == "case")
    return {"stats": {"case_feedback": case_count}}

@app.get("/api/v1/db/feedback")
async def db_feedback(limit: int = 1):
    entries = _load_feedback_entries()
    message_entries = [e for e in entries if e.get("feedback_kind", "message") == "message"]
    items = message_entries[-max(limit, 0):] if limit else message_entries
    return {"count": len(message_entries), "items": items}

@app.get("/api/v1/guidelines/health")
async def get_guidelines_health():
    return {"status": "disabled", "message": "Guidelines service not enabled in simplified mode"}

@app.get("/api/v1/guidelines/sources")
async def get_guidelines_sources():
    return {"sources": []}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5001))
    uvicorn.run(app, host="0.0.0.0", port=port)
