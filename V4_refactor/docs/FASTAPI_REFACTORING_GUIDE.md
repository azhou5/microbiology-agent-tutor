# FastAPI + Pydantic Refactoring Guide: V3 → V4

## Overview

This guide provides a step-by-step approach to refactor the monolithic Flask `app.py` (620 lines) into a modern, type-safe FastAPI application with Pydantic models.

## Architecture Comparison

### V3 (Flask + No Type Safety)

```
app.py (620 lines)
├── Direct database models in routes
├── Dict-based request/response handling
├── No input validation
├── Session-based state management
└── Mixed concerns (DB, business logic, routing)
```

### V4 (FastAPI + Pydantic)

```
src/microtutor/
├── models/
│   ├── requests.py    # Pydantic request models
│   ├── responses.py   # Pydantic response models
│   └── domain.py      # Domain models
├── services/
│   ├── tutor_service.py
│   ├── case_service.py
│   └── feedback_service.py
├── api/
│   ├── routes/
│   │   ├── chat.py
│   │   ├── cases.py
│   │   └── feedback.py
│   └── dependencies.py
└── core/
    └── database.py
```

## Step-by-Step Refactoring

### Step 1: Define Pydantic Models

#### 1.1 Request Models (`src/microtutor/models/requests.py`)

```python
"""Pydantic request models with automatic validation."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator, constr
from datetime import datetime


class Message(BaseModel):
    """A single message in conversation history."""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'assistant', 'system']:
            raise ValueError('Role must be user, assistant, or system')
        return v


class StartCaseRequest(BaseModel):
    """Request to start a new case."""
    organism: constr(min_length=1) = Field(
        ..., 
        description="Organism name for the case",
        example="staphylococcus aureus"
    )
    case_id: constr(min_length=1) = Field(
        ...,
        description="Client-generated unique case ID",
        example="case_2024_abc123"
    )
    model_name: Optional[str] = Field(
        default="o3-mini",
        description="LLM model to use"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "organism": "staphylococcus aureus",
                "case_id": "case_2024_abc123",
                "model_name": "o3-mini"
            }
        }


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: constr(min_length=1) = Field(
        ...,
        description="User's message to the tutor",
        example="What are the patient's symptoms?"
    )
    history: List[Message] = Field(
        default_factory=list,
        description="Full conversation history"
    )
    organism_key: Optional[str] = Field(
        None,
        description="Current organism being studied"
    )
    case_id: Optional[str] = Field(
        None,
        description="Active case ID"
    )
    
    @validator('message')
    def message_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "message": "What are the patient's vital signs?",
                "history": [
                    {"role": "system", "content": "You are a tutor..."},
                    {"role": "assistant", "content": "Welcome to the case..."}
                ],
                "organism_key": "staphylococcus aureus",
                "case_id": "case_2024_abc123"
            }
        }


class FeedbackRequest(BaseModel):
    """User feedback on a tutor response."""
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Rating from 1-5"
    )
    message: str = Field(
        ...,
        description="The assistant message being rated"
    )
    history: List[Message] = Field(
        ...,
        description="Conversation history at feedback time"
    )
    feedback_text: Optional[str] = Field(
        default="",
        description="Optional feedback text"
    )
    replacement_text: Optional[str] = Field(
        default="",
        description="Optional replacement text"
    )
    case_id: Optional[str] = Field(
        None,
        description="Associated case ID"
    )


class CaseFeedbackRequest(BaseModel):
    """Overall case feedback."""
    detail: int = Field(..., ge=1, le=5, description="Detail rating")
    helpfulness: int = Field(..., ge=1, le=5, description="Helpfulness rating")
    accuracy: int = Field(..., ge=1, le=5, description="Accuracy rating")
    comments: Optional[str] = Field(default="", description="Additional comments")
    case_id: str = Field(..., description="Case ID")
```

#### 1.2 Response Models (`src/microtutor/models/responses.py`)

```python
"""Pydantic response models for API endpoints."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from .requests import Message


class StartCaseResponse(BaseModel):
    """Response when starting a new case."""
    initial_message: str = Field(
        ...,
        description="Initial tutor message to start the case"
    )
    history: List[Message] = Field(
        ...,
        description="Initial conversation history"
    )
    case_id: str = Field(
        ...,
        description="Case ID for this session"
    )
    organism: str = Field(
        ...,
        description="Organism for this case"
    )


class ChatResponse(BaseModel):
    """Response from a chat interaction."""
    response: str = Field(
        ...,
        description="Tutor's response message"
    )
    history: List[Message] = Field(
        ...,
        description="Updated conversation history"
    )
    tools_used: Optional[List[str]] = Field(
        default_factory=list,
        description="Tools used in generating this response"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata (tokens, timing, etc.)"
    )


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    status: str = Field(default="Feedback received")
    feedback_id: Optional[int] = None


class CaseFeedbackResponse(BaseModel):
    """Response after submitting case feedback."""
    status: str = Field(default="Case feedback received")
    feedback_id: Optional[int] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    needs_new_case: bool = Field(default=False, description="Whether client should start new case")


class OrganismListResponse(BaseModel):
    """List of available organisms."""
    organisms: List[str] = Field(
        ...,
        description="Available organisms with cached cases"
    )
    count: int = Field(
        ...,
        description="Number of organisms available"
    )
```

#### 1.3 Domain Models (`src/microtutor/models/domain.py`)

```python
"""Domain models representing core business entities."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class TutorState(str, Enum):
    """Current state of the tutoring session."""
    INITIALIZING = "initializing"
    INFORMATION_GATHERING = "information_gathering"
    PROBLEM_REPRESENTATION = "problem_representation"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    INVESTIGATIONS = "investigations"
    TREATMENT = "treatment"
    SOCRATIC_MODE = "socratic_mode"
    COMPLETED = "completed"


class AgentType(str, Enum):
    """Types of agents available."""
    PATIENT = "patient"
    SOCRATIC = "socratic"
    HINT = "hint"
    CASE_GENERATOR = "case_generator"


class CaseData(BaseModel):
    """Represents a medical case."""
    organism: str
    description: str
    case_id: str
    difficulty: str = "intermediate"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TutorContext(BaseModel):
    """Context for a tutoring session."""
    case_id: str
    organism: str
    case_description: Optional[str] = None
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    current_state: TutorState = TutorState.INITIALIZING
    model_name: str = "o3-mini"
    session_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class TokenUsage(BaseModel):
    """Tracks token usage for LLM calls."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class TutorResponse(BaseModel):
    """Complete response from tutor service."""
    content: str
    tools_used: List[str] = Field(default_factory=list)
    token_usage: Optional[TokenUsage] = None
    processing_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### Step 2: Create Service Layer

#### 2.1 Tutor Service (`src/microtutor/services/tutor_service.py`)

```python
"""Service layer for tutor operations - separates business logic from API routes."""

from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from microtutor.models.domain import TutorContext, TutorResponse, TutorState, TokenUsage
from microtutor.models.requests import Message
from microtutor.core.llm_router import chat_complete, llm_manager
from microtutor.agents.patient import run_patient
from microtutor.agents.case import get_case
from microtutor.utils.tutor_helpers import should_append_user_message, extract_action_json

logger = logging.getLogger(__name__)


class TutorService:
    """Service handling all tutor-related business logic."""
    
    def __init__(
        self,
        output_tool_directly: bool = True,
        run_with_faiss: bool = False,
        reward_model_sampling: bool = False
    ):
        """Initialize tutor service with configuration."""
        self.output_tool_directly = output_tool_directly
        self.run_with_faiss = run_with_faiss
        self.reward_model_sampling = reward_model_sampling
        logger.info(
            f"TutorService initialized: "
            f"output_tool_directly={output_tool_directly}, "
            f"run_with_faiss={run_with_faiss}, "
            f"reward_model_sampling={reward_model_sampling}"
        )
    
    async def start_case(
        self,
        organism: str,
        case_id: str,
        model_name: str = "o3-mini"
    ) -> TutorResponse:
        """
        Start a new case for the given organism.
        
        Args:
            organism: The organism to study
            case_id: Unique case identifier
            model_name: LLM model to use
            
        Returns:
            TutorResponse with initial message
            
        Raises:
            ValueError: If case cannot be loaded
        """
        start_time = datetime.now()
        logger.info(f"Starting new case: organism={organism}, case_id={case_id}")
        
        # Get case description
        case_description = get_case(organism)
        if not case_description:
            raise ValueError(f"Could not load case for organism: {organism}")
        
        # Create initial system message
        system_message = self._build_system_message(case_description)
        
        # Create context
        context = TutorContext(
            case_id=case_id,
            organism=organism,
            case_description=case_description,
            conversation_history=[{"role": "system", "content": system_message}],
            model_name=model_name,
            current_state=TutorState.INFORMATION_GATHERING
        )
        
        # Generate initial message
        initial_prompt = (
            "Start the case by welcoming the student and providing "
            "the initial patient presentation."
        )
        
        response = await self._call_llm(
            messages=context.conversation_history + [
                {"role": "user", "content": initial_prompt}
            ],
            model_name=model_name
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return TutorResponse(
            content=response["content"],
            tools_used=response.get("tools_used", []),
            token_usage=response.get("token_usage"),
            processing_time_ms=processing_time,
            metadata={
                "case_id": case_id,
                "organism": organism,
                "state": context.current_state
            }
        )
    
    async def process_message(
        self,
        message: str,
        context: TutorContext
    ) -> TutorResponse:
        """
        Process a user message and return tutor response.
        
        Args:
            message: User's message
            context: Current tutor context
            
        Returns:
            TutorResponse with tutor's reply
        """
        start_time = datetime.now()
        logger.info(f"Processing message for case_id={context.case_id}")
        
        # Add user message to history
        context.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        # Call LLM
        response = await self._call_llm(
            messages=context.conversation_history,
            model_name=context.model_name
        )
        
        # Add assistant response to history
        context.conversation_history.append({
            "role": "assistant",
            "content": response["content"]
        })
        
        # Update state based on response
        context.current_state = self._determine_state(
            response["content"],
            context.current_state
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return TutorResponse(
            content=response["content"],
            tools_used=response.get("tools_used", []),
            token_usage=response.get("token_usage"),
            processing_time_ms=processing_time,
            metadata={
                "case_id": context.case_id,
                "state": context.current_state
            }
        )
    
    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        model_name: str
    ) -> Dict[str, Any]:
        """
        Call LLM with proper error handling and token tracking.
        
        Args:
            messages: Conversation history
            model_name: Model to use
            
        Returns:
            Dict with content, tools_used, and token_usage
        """
        try:
            response = await chat_complete(
                messages=messages,
                model=model_name,
                temperature=0.7,
                max_tokens=16000
            )
            
            return {
                "content": response["content"],
                "tools_used": response.get("tools_used", []),
                "token_usage": TokenUsage(
                    prompt_tokens=response.get("usage", {}).get("prompt_tokens", 0),
                    completion_tokens=response.get("usage", {}).get("completion_tokens", 0),
                    total_tokens=response.get("usage", {}).get("total_tokens", 0)
                )
            }
        except Exception as e:
            logger.error(f"Error calling LLM: {e}", exc_info=True)
            raise
    
    def _build_system_message(self, case_description: str) -> str:
        """Build the system message for the tutor."""
        # Import your system_message_template from tutor.py
        from microtutor.core.tutor_prompts import system_message_template, tool_descriptions
        
        return system_message_template.format(
            case_description=case_description,
            tool_descriptions=tool_descriptions
        )
    
    def _determine_state(self, response: str, current_state: TutorState) -> TutorState:
        """Determine the new state based on the response."""
        # Simple state machine logic
        response_lower = response.lower()
        
        if "problem representation" in response_lower:
            return TutorState.PROBLEM_REPRESENTATION
        elif "differential" in response_lower or "ddx" in response_lower:
            return TutorState.DIFFERENTIAL_DIAGNOSIS
        elif "investigation" in response_lower or "test" in response_lower:
            return TutorState.INVESTIGATIONS
        elif "treatment" in response_lower or "management" in response_lower:
            return TutorState.TREATMENT
        elif "[SOCRATIC_COMPLETE]" in response:
            return TutorState.INFORMATION_GATHERING
        
        return current_state
```

### Step 3: Create FastAPI Application

#### 3.1 Main App (`src/microtutor/api/app.py`)

```python
"""FastAPI application entry point."""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from microtutor.models.responses import ErrorResponse
from microtutor.api.routes import chat, cases, feedback, admin
from microtutor.core.database import init_db
from config.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO if not config.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager for startup and shutdown events.
    
    This replaces the old @app.on_event decorators with modern async context manager.
    """
    # Startup
    logger.info("Starting MicroTutor API...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MicroTutor API...")


# Create FastAPI app
app = FastAPI(
    title="MicroTutor API",
    description="AI-powered microbiology tutoring system",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with detailed messages."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Invalid request data",
            error_code="VALIDATION_ERROR",
            details={"errors": exc.errors()}
        ).dict()
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    logger.error(f"ValueError: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error=str(exc),
            error_code="VALUE_ERROR"
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            error_code="INTERNAL_ERROR",
            details={"message": str(exc)} if config.DEBUG else None
        ).dict()
    )


# Include routers
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(cases.router, prefix="/api/v1", tags=["cases"])
app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MicroTutor API",
        "version": "4.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "microtutor.api.app:app",
        host="0.0.0.0",
        port=5001,
        reload=config.DEBUG,
        log_level="info"
    )
```

#### 3.2 Chat Routes (`src/microtutor/api/routes/chat.py`)

```python
"""Chat-related API endpoints."""

import logging
from typing import Dict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from microtutor.models.requests import StartCaseRequest, ChatRequest
from microtutor.models.responses import StartCaseResponse, ChatResponse, ErrorResponse
from microtutor.models.domain import TutorContext
from microtutor.services.tutor_service import TutorService
from microtutor.api.dependencies import (
    get_tutor_service,
    get_db,
    log_conversation
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/start_case",
    response_model=StartCaseResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Start a new case",
    description="Initialize a new microbiology case for the given organism"
)
async def start_case(
    request: StartCaseRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    db=Depends(get_db)
) -> StartCaseResponse:
    """
    Start a new case with the selected organism.
    
    - **organism**: The microorganism to study
    - **case_id**: Client-generated unique case ID
    - **model_name**: LLM model to use (default: o3-mini)
    """
    logger.info(f"Starting case: organism={request.organism}, case_id={request.case_id}")
    
    try:
        # Call tutor service
        response = await tutor_service.start_case(
            organism=request.organism,
            case_id=request.case_id,
            model_name=request.model_name
        )
        
        # Log to database
        if db:
            await log_conversation(
                db=db,
                case_id=request.case_id,
                role="assistant",
                content=response.content
            )
        
        return StartCaseResponse(
            initial_message=response.content,
            history=[
                {"role": "system", "content": "System initialized"},
                {"role": "assistant", "content": response.content}
            ],
            case_id=request.case_id,
            organism=request.organism
        )
        
    except ValueError as e:
        logger.error(f"ValueError starting case: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting case: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start case"
        )


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Send a chat message",
    description="Send a message to the tutor and receive a response"
)
async def chat(
    request: ChatRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    db=Depends(get_db)
) -> ChatResponse:
    """
    Process a chat message from the student.
    
    - **message**: The student's question or response
    - **history**: Full conversation history
    - **organism_key**: Current organism being studied
    - **case_id**: Active case ID
    """
    start_time = datetime.now()
    logger.info(f"Chat request: case_id={request.case_id}, message_len={len(request.message)}")
    
    # Validate case_id
    if not request.case_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="No active case ID. Please start a new case.",
                error_code="NO_CASE_ID",
                needs_new_case=True
            ).dict()
        )
    
    try:
        # Create context from request
        context = TutorContext(
            case_id=request.case_id,
            organism=request.organism_key or "",
            conversation_history=[msg.dict() for msg in request.history]
        )
        
        # Log user message
        if db:
            await log_conversation(
                db=db,
                case_id=request.case_id,
                role="user",
                content=request.message
            )
        
        # Process message
        response = await tutor_service.process_message(
            message=request.message,
            context=context
        )
        
        # Log assistant response
        if db:
            await log_conversation(
                db=db,
                case_id=request.case_id,
                role="assistant",
                content=response.content
            )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"Chat processed in {processing_time:.2f}ms")
        
        return ChatResponse(
            response=response.content,
            history=context.conversation_history,
            tools_used=response.tools_used,
            metadata={
                "processing_time_ms": processing_time,
                "token_usage": response.token_usage.dict() if response.token_usage else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )
```

#### 3.3 Dependencies (`src/microtutor/api/dependencies.py`)

```python
"""FastAPI dependencies for dependency injection."""

from typing import Optional, AsyncGenerator
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from microtutor.services.tutor_service import TutorService
from microtutor.services.case_service import CaseService
from microtutor.services.feedback_service import FeedbackService
from microtutor.core.database import get_async_session
from config.config import config
import logging

logger = logging.getLogger(__name__)

# Service singletons (consider using dependency-injector library for production)
_tutor_service: Optional[TutorService] = None
_case_service: Optional[CaseService] = None
_feedback_service: Optional[FeedbackService] = None


def get_tutor_service() -> TutorService:
    """
    Dependency injection for TutorService.
    
    Returns singleton instance configured from config.
    """
    global _tutor_service
    if _tutor_service is None:
        _tutor_service = TutorService(
            output_tool_directly=config.OUTPUT_TOOL_DIRECTLY,
            run_with_faiss=config.USE_FAISS,
            reward_model_sampling=config.REWARD_MODEL_SAMPLING
        )
    return _tutor_service


def get_case_service() -> CaseService:
    """Dependency injection for CaseService."""
    global _case_service
    if _case_service is None:
        _case_service = CaseService()
    return _case_service


def get_feedback_service() -> FeedbackService:
    """Dependency injection for FeedbackService."""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for database session.
    
    Yields async database session that auto-commits/rollbacks.
    """
    async with get_async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            await session.close()


async def log_conversation(
    db: AsyncSession,
    case_id: str,
    role: str,
    content: str
):
    """Helper to log conversation to database."""
    from microtutor.core.database import ConversationLog
    from datetime import datetime
    
    log_entry = ConversationLog(
        case_id=case_id,
        role=role,
        content=content,
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)
```

## Key Benefits

### 1. **Automatic Validation**

```python
# Bad request automatically rejected with detailed error
{
  "error": "Invalid request data",
  "error_code": "VALIDATION_ERROR",
  "details": {
    "errors": [
      {
        "loc": ["body", "rating"],
        "msg": "ensure this value is greater than or equal to 1",
        "type": "value_error.number.not_ge"
      }
    ]
  }
}
```

### 2. **Interactive API Documentation**

FastAPI automatically generates:

- Swagger UI at `/api/docs`
- ReDoc at `/api/redoc`
- OpenAPI schema at `/api/openapi.json`

### 3. **Type Safety**

```python
# IDE autocomplete works perfectly
request: ChatRequest  # IDE knows all fields
print(request.message)  # Autocomplete suggests .message
```

### 4. **Dependency Injection**

```python
# Clean, testable code
async def chat(
    request: ChatRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    db: AsyncSession = Depends(get_db)
):
    # Services injected automatically
    # Easy to mock in tests
```

### 5. **Async Performance**

```python
# Non-blocking I/O
async def process_message(...):
    response = await llm_service.call(...)  # Other requests processed during wait
    await db.save(...)
    return response
```

## Migration Steps

1. **Create Pydantic models** (Day 1-2)
2. **Extract service layer** (Day 3-4)
3. **Build FastAPI routes** (Day 5-6)
4. **Set up dependencies** (Day 7)
5. **Add tests** (Day 8-9)
6. **Deploy & monitor** (Day 10)

## Testing

```python
# tests/test_chat_api.py
import pytest
from fastapi.testclient import TestClient
from microtutor.api.app import app

client = TestClient(app)

def test_start_case():
    response = client.post(
        "/api/v1/start_case",
        json={
            "organism": "staphylococcus aureus",
            "case_id": "test_case_123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "initial_message" in data
    assert data["organism"] == "staphylococcus aureus"

def test_chat_without_case_id():
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "Hello",
            "history": []
        }
    )
    assert response.status_code == 400
    assert "No active case ID" in response.json()["error"]
```

## Conclusion

This refactoring provides:

- ✅ Type safety with Pydantic
- ✅ Automatic validation
- ✅ Interactive documentation
- ✅ Clean separation of concerns
- ✅ Dependency injection
- ✅ Async performance
- ✅ Easy testing
- ✅ Production-ready error handling
