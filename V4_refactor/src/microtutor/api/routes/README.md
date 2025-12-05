# API Routes

FastAPI route handlers for all API endpoints. Organized by feature domain.

## Structure

```
routes/
├── chat.py              # Main chat and case endpoints
├── voice.py             # Voice interaction endpoints
├── mcq.py               # Multiple choice question endpoints
├── audio.py             # Audio file handling
├── admin/               # Administrative endpoints
│   ├── analytics.py     # Usage analytics
│   ├── monitoring.py    # Health checks and metrics
│   └── config.py        # Configuration management
└── data/                # Data management endpoints
    ├── database.py      # Database queries
    └── faiss_management.py  # FAISS index management
```

## Core Routes

### `chat.py`

**Endpoints**:

- `POST /api/v1/start_case` - Initialize new case
- `POST /api/v1/chat` - Send message to tutor
- `POST /api/v1/feedback` - Submit feedback
- `POST /api/v1/case_feedback` - Submit case-level feedback

**Purpose**: Main interaction endpoints  
**Necessary**: ✅ Yes - Core functionality

### `voice.py`

**Endpoints**:

- `POST /api/v1/voice/transcribe` - Speech-to-text
- `POST /api/v1/voice/synthesize` - Text-to-speech
- `POST /api/v1/voice/chat` - Voice chat with tutor

**Purpose**: Voice interaction  
**Necessary**: ✅ Yes - Voice features

### `mcq.py`

**Endpoints**:

- `POST /api/v1/mcq/generate` - Generate MCQ
- `POST /api/v1/mcq/validate` - Validate answer

**Purpose**: Assessment functionality  
**Necessary**: ✅ Yes - MCQ features

### `audio.py`

**Endpoints**:

- `POST /api/v1/audio/upload` - Upload audio files
- `GET /api/v1/audio/{file_id}` - Retrieve audio

**Purpose**: Audio file management  
**Necessary**: ⚠️ Maybe - Check if used or can merge with voice.py

## Admin Routes

### `admin/analytics.py`

**Purpose**: Usage analytics and statistics  
**Necessary**: ✅ Yes - For monitoring and insights

### `admin/monitoring.py`

**Purpose**: Health checks and system metrics  
**Necessary**: ✅ Yes - Production monitoring

### `admin/config.py`

**Purpose**: Configuration management  
**Necessary**: ✅ Yes - Runtime configuration

## Data Routes

### `data/database.py`

**Purpose**: Database query endpoints  
**Necessary**: ✅ Yes - Data access

### `data/faiss_management.py`

**Purpose**: FAISS index management endpoints  
**Necessary**: ✅ Yes - Index operations

## Recommendations

1. **Consolidate audio/voice**: If `audio.py` is just for voice, merge with `voice.py`
2. **Admin prefix**: Consider `/api/v1/admin/` prefix for admin routes
3. **Error handling**: All routes use consistent error response format
