# V4 Clean Structure (After Cleanup)

## 🎯 Current V4 Directory Structure

```
V4_refactor/
├── README.md                              # Main documentation
├── run_v4.py                              # ⭐ Startup script
│
├── src/microtutor/                        # Main package
│   ├── __init__.py                        # Package exports
│   ├── models/                            # ✅ Pydantic data models
│   │   ├── __init__.py                    # Model exports
│   │   ├── requests.py                    # Request validation
│   │   ├── responses.py                   # Response schemas
│   │   └── domain.py                      # Business entities
│   ├── services/                          # ✅ Business logic
│   │   ├── __init__.py                    # Service exports
│   │   ├── tutor_service.py              # Core tutor logic (~400 lines)
│   │   ├── case_service.py               # Case management
│   │   └── feedback_service.py           # Feedback handling
│   └── api/                               # ✅ API layer
│       ├── __init__.py
│       ├── app.py                         # FastAPI app (~80 lines)
│       ├── dependencies.py                # Dependency injection
│       └── routes/
│           ├── __init__.py
│           └── chat.py                    # Chat endpoints (~150 lines)
│
├── tests/                                 # ✅ Tests
│   ├── __init__.py
│   ├── test_models.py                     # Model validation tests
│   └── test_api.py                        # API integration tests
│
├── config/                                # Configuration
│   ├── __init__.py
│   ├── base.py
│   ├── config.py                          # Main config
│   ├── development.py
│   ├── production.py
│   └── testing.py
│
├── data/                                  # Data storage (from V3)
│   ├── cases/
│   │   └── cached/                       # Pre-generated cases
│   ├── feedback/
│   │   └── processed/                    # FAISS indices
│   └── models/                           # ML models
│
├── requirements/                          # Dependencies
│   ├── requirements.txt                  # V3 deps
│   └── requirements_v4.txt               # V4 deps
│
├── scripts/                              # Utility scripts (from V3)
│   ├── pregenerate_cases.py
│   ├── create_feedback_index.py
│   └── ...
│
├── notebooks/                            # Jupyter notebooks (from V3)
│   ├── create_faiss_index.ipynb
│   └── generate_cached_HPI.ipynb
│
├── docker/                               # Docker config
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
├── logs/                                 # Log files (gitignored)
│
└── Documentation/                        # ⭐ Comprehensive guides
    ├── IMPLEMENTATION_COMPLETE.md        # What's done & how to use
    ├── V3_TO_V4_MAPPING_GUIDE.md        # This file!
    ├── QUICK_REFERENCE.md               # Quick commands
    ├── FASTAPI_REFACTORING_GUIDE.md     # Technical deep dive
    ├── BEFORE_AFTER_COMPARISON.md       # Code comparisons
    └── ...
```

## 📊 What Each Directory Does

### `src/microtutor/` - Main Application Code

#### `models/` - Data Models (Type Safety)

All Pydantic models for request/response validation and business entities.

**requests.py** - Input validation

```python
class StartCaseRequest(BaseModel):
    organism: str  # Validated automatically
    case_id: str   # Type-checked
```

**responses.py** - Output schemas  

```python
class ChatResponse(BaseModel):
    response: str
    history: List[Message]
```

**domain.py** - Business entities

```python
class TutorContext(BaseModel):
    case_id: str
    organism: str
    conversation_history: List[Dict]
```

#### `services/` - Business Logic Layer

All core business logic, extracted from V3's `tutor.py` and `app.py`.

**tutor_service.py** - Main tutor logic

- `start_case()` - Initialize new case
- `process_message()` - Handle student messages
- Tool management, LLM calls, state transitions

**case_service.py** - Case management

- `get_case()` - Load case for organism
- `get_available_organisms()` - List cached organisms
- Caching logic

**feedback_service.py** - Feedback handling

- `save_feedback()` - Save user feedback
- `save_case_feedback()` - Save case ratings

#### `api/` - API Layer (Routes & App)

FastAPI application and routes.

**app.py** - FastAPI setup

- App initialization
- Middleware (CORS, GZip)
- Exception handlers
- Health check endpoints

**dependencies.py** - Dependency injection

- Service singletons
- Database session management
- Configuration injection

**routes/chat.py** - Chat endpoints

- `POST /api/v1/start_case`
- `POST /api/v1/chat`

### `tests/` - Test Suite

**test_models.py** - Model validation tests

```python
def test_start_case_request_empty_organism():
    with pytest.raises(ValidationError):
        StartCaseRequest(organism="", case_id="test")
```

**test_api.py** - API integration tests

```python
def test_start_case():
    response = client.post("/api/v1/start_case", ...)
    assert response.status_code == 200
```

### `config/` - Configuration Management

Environment-specific configurations with inheritance.

**config.py** - Main configuration class

```python
class Config(BaseConfig):
    API_MODEL_NAME: str = "o3-mini"
    USE_FAISS: bool = False
    # ...
```

### `data/` - Data Storage (From V3)

**cases/cached/** - Pre-generated cases

- `case_cache.json` - Cached case data
- `HPI_per_organism.json` - HPIs by organism

**feedback/processed/** - Feedback indices

- `output_index.faiss` - FAISS index
- `output_index.faiss.texts` - Text data

### `scripts/` - Utility Scripts (From V3)

Standalone scripts for data preparation and management:

- `pregenerate_cases.py` - Generate cases in advance
- `create_feedback_index.py` - Build FAISS indices
- `prepare_reward_data.py` - Prepare reward model data

### Documentation Files

**Essential Guides:**

- `README.md` - Main documentation
- `IMPLEMENTATION_COMPLETE.md` - What's done & how to use
- `V3_TO_V4_MAPPING_GUIDE.md` - V3 → V4 transformation
- `QUICK_REFERENCE.md` - Quick commands & examples

**Technical Guides:**

- `FASTAPI_REFACTORING_GUIDE.md` - Technical deep dive
- `BEFORE_AFTER_COMPARISON.md` - Side-by-side code comparisons
- `QUICKSTART_IMPLEMENTATION.md` - Step-by-step implementation
- `ARCHITECTURE_DIAGRAM.md` - Visual architecture diagrams
- `V3_TO_V4_REFACTORING_SUMMARY.md` - Executive summary

## 🔄 How Data Flows Through V4

### 1. **Request Arrives**

```
HTTP POST /api/v1/start_case
{"organism": "staphylococcus aureus", "case_id": "123"}
```

### 2. **Pydantic Validates** (models/requests.py)

```python
request = StartCaseRequest(**request_data)
# ✅ Validated! Would fail if organism empty
```

### 3. **Route Handler Called** (api/routes/chat.py)

```python
@router.post("/start_case")
async def start_case(
    request: StartCaseRequest,  # Already validated
    tutor_service: TutorService = Depends(...)  # Injected
):
```

### 4. **Service Processes** (services/tutor_service.py)

```python
response = await tutor_service.start_case(
    organism=request.organism,
    case_id=request.case_id
)
# Business logic: get case, build message, call LLM
```

### 5. **Response Built** (models/responses.py)

```python
return StartCaseResponse(
    initial_message=response.content,
    history=[...],
    case_id=request.case_id,
    organism=request.organism
)
# ✅ Type-checked!
```

### 6. **JSON Returned**

```json
{
  "initial_message": "Welcome! Let me present...",
  "history": [...],
  "case_id": "123",
  "organism": "staphylococcus aureus"
}
```

## 📦 What's Using What

### Import Dependencies

```python
# api/routes/chat.py imports from:
from microtutor.models.requests import StartCaseRequest, ChatRequest
from microtutor.models.responses import StartCaseResponse, ChatResponse
from microtutor.models.domain import TutorContext
from microtutor.services.tutor_service import TutorService

# services/tutor_service.py imports from:
from microtutor.models.domain import TutorContext, TutorResponse, TutorState
# Plus V3 imports:
from agents.patient import run_patient  # From V3!
from agents.case import get_case        # From V3!
from llm_router import chat_complete    # From V3!
```

### Where V3 Code is Used

V4 services import directly from V3 for:

- **agents/patient.py** - Patient simulation tool
- **agents/case.py** - Case loading (`get_case()`)
- **agents/case_generator_rag.py** - Case generation
- **llm_router.py** - LLM calls (`chat_complete()`)
- **Feedback/feedback_faiss.py** - FAISS retrieval (optional)

**This means:**

- ✅ V4 leverages existing V3 agent logic
- ✅ No need to rewrite working code
- ✅ Gradual migration possible

## 🎯 Key Files to Know

### To Run The App

```bash
python run_v4.py
```

### To Make Changes

**Add a new endpoint:**

1. Add request model in `models/requests.py`
2. Add response model in `models/responses.py`
3. Add route handler in `api/routes/chat.py`

**Modify business logic:**

1. Edit `services/tutor_service.py`
2. Tests automatically validate changes

**Change configuration:**

1. Edit `config/config.py`

### To Test

```bash
pytest tests/test_models.py -v    # Test models
pytest tests/test_api.py -v       # Test API
```

## 📈 What Was Removed (Cleanup)

We removed these empty/duplicate directories:

- ❌ `src/microtutor/core/` - Duplicated V3 code
- ❌ `src/microtutor/web/` - Old Flask app
- ❌ `src/microtutor/utils/` - Duplicate utilities
- ❌ `src/microtutor/agents/` - Duplicate agents (using V3's)
- ❌ `tests/unit/`, `tests/integration/`, `tests/e2e/` - Empty scaffolding
- ❌ `docs/` - Empty documentation structure

**Result:** Clean, minimal structure with only what's needed!

## 🚀 Next Steps

### Current Status

- ✅ Core API working (`/start_case`, `/chat`)
- ✅ Pydantic models for validation
- ✅ Service layer for business logic
- ✅ Tests for models and API
- ✅ Comprehensive documentation

### To Add (Optional)

- [ ] Feedback endpoints (`/feedback`, `/case_feedback`)
- [ ] Admin endpoints (`/admin/feedback`, `/admin/live_chats`)
- [ ] Database integration (async SQLAlchemy)
- [ ] Authentication (JWT)
- [ ] WebSocket support for real-time chat
- [ ] Monitoring & metrics

### To Deploy

- [ ] Build Docker image (`docker build -f docker/Dockerfile .`)
- [ ] Deploy to cloud (Render, AWS, etc.)
- [ ] Set up CI/CD
- [ ] Configure production environment

---

**This is your clean, production-ready V4 structure! 🎉**
