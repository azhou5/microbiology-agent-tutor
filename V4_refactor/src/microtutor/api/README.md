# API Layer

FastAPI-based REST API for MicroTutor. Handles HTTP requests, routing, and serves the frontend.

## Structure

```
api/
├── app.py              # Main FastAPI application (entry point)
├── dependencies.py     # Dependency injection (DB, services)
├── routes/             # API route handlers
│   ├── chat.py         # Main chat/start_case endpoints
│   ├── voice.py        # Voice transcription/synthesis
│   ├── mcq.py          # Multiple choice questions
│   ├── audio.py        # Audio file handling
│   ├── admin/          # Admin endpoints (analytics, monitoring, config)
│   └── data/           # Database and FAISS management endpoints
├── static/             # Frontend static files (CSS, JS)
└── templates/          # HTML templates (Jinja2)
```

## Files

### `app.py`

**Purpose**: Main FastAPI application entry point  
**Necessary**: ✅ Yes - This is the web server entry point  
**Could be more concrete**: ⚠️ Could split middleware setup into separate module

- Sets up FastAPI app with middleware (CORS, GZip)
- Registers all route handlers
- Exception handlers for error responses
- Serves static files and templates
- Health check endpoints

### `startup.py`

**Purpose**: FastAPI application lifecycle management  
**Necessary**: ✅ Yes - Startup/shutdown logic  
**Could be more concrete**: ✅ Well-placed in API layer

- `get_lifespan()` - FastAPI lifespan context manager
- Startup: Initialize database, services, background tasks
- Shutdown: Cleanup resources
- **Note**: Moved from `core/config/` since it's FastAPI-specific

### `dependencies.py`

**Purpose**: Dependency injection for FastAPI routes  
**Necessary**: ✅ Yes - Centralizes DB connections and service creation  
**Could be more concrete**: ✅ Well-structured

- `get_db()` - Database session generator
- `get_tutor_service()` - Creates TutorService instance
- `test_db_connection()` - Database connectivity test

### `routes/chat.py`

**Purpose**: Main chat and case management endpoints  
**Necessary**: ✅ Yes - Core API functionality  
**Could be more concrete**: ⚠️ Could split into separate files (chat vs case management)

- `POST /api/v1/start_case` - Initialize new case
- `POST /api/v1/chat` - Send message to tutor
- `POST /api/v1/feedback` - Submit feedback
- `POST /api/v1/case_feedback` - Submit case-level feedback

### `routes/voice.py`

**Purpose**: Voice interaction endpoints  
**Necessary**: ✅ Yes - Voice features  
**Could be more concrete**: ✅ Good separation

- `POST /api/v1/voice/transcribe` - Speech-to-text
- `POST /api/v1/voice/synthesize` - Text-to-speech
- `POST /api/v1/voice/chat` - Voice chat with tutor

### `routes/mcq.py`

**Purpose**: Multiple choice question endpoints  
**Necessary**: ✅ Yes - MCQ functionality  
**Could be more concrete**: ✅ Well-contained

- `POST /api/v1/mcq/generate` - Generate MCQ
- `POST /api/v1/mcq/validate` - Validate answer

### `routes/audio.py`

**Purpose**: Audio file upload/processing  
**Necessary**: ⚠️ Maybe - Depends on use case  
**Could be more concrete**: ⚠️ Could merge with voice.py if related

- `POST /api/v1/audio/upload` - Upload audio files
- `GET /api/v1/audio/{file_id}` - Retrieve audio

### `routes/admin/`

**Purpose**: Administrative and monitoring endpoints  
**Necessary**: ✅ Yes - For production monitoring  
**Could be more concrete**: ✅ Good separation

- `analytics.py` - Usage analytics
- `monitoring.py` - Health checks, metrics
- `config.py` - Configuration management

### `routes/data/`

**Purpose**: Database and FAISS index management  
**Necessary**: ✅ Yes - For data management  
**Could be more concrete**: ⚠️ Could be in separate admin module

- `database.py` - Database queries and management
- `faiss_management.py` - FAISS index operations

### `static/` and `templates/`

**Purpose**: Frontend assets and HTML templates  
**Necessary**: ✅ Yes - Serves the web UI  
**Could be more concrete**: ✅ Standard FastAPI pattern

## Recommendations

1. **Split `chat.py`**: Separate case management from chat endpoints
2. **Consolidate audio/voice**: If audio.py is just for voice, merge with voice.py
3. **Extract middleware**: Move middleware setup to separate module for clarity
4. **Admin routes**: Consider moving to `/api/v1/admin/` prefix for consistency
