# V4 Refactoring: Complete Implementation Guide

## 🎯 Goal

Transform MicroTutor from a 620-line monolithic Flask app (V3) into a modern, type-safe, production-ready FastAPI application (V4) with Pydantic models.

## 📚 Documentation Overview

We've created comprehensive documentation to guide you through this refactoring:

### 1. **ARCHITECTURE_DIAGRAM.md** 📊

Visual comparison of V3 vs V4 architecture with diagrams showing:

- Structure comparison
- Request flow
- Data flow
- Performance improvements

**Read this first** to understand the big picture.

### 2. **BEFORE_AFTER_COMPARISON.md** 🔄

Detailed side-by-side code comparisons showing:

- Flask vs FastAPI implementations
- Manual vs automatic validation
- Synchronous vs async patterns
- Testing complexity differences

**Read this** to see concrete code examples.

### 3. **FASTAPI_REFACTORING_GUIDE.md** 📖

Complete technical guide covering:

- Why FastAPI + Pydantic?
- Step-by-step refactoring phases
- Service layer architecture
- Modern web architecture patterns
- Testing strategies

**Your technical reference** for implementation details.

### 4. **QUICKSTART_IMPLEMENTATION.md** 🚀

Day-by-day implementation plan with:

- Exact commands to run
- Code to write
- Tests to create
- Deployment steps

**Your actionable checklist** to get started immediately.

### 5. **V3_TO_V4_REFACTORING_SUMMARY.md** 📋

Executive summary including:

- Key changes and impacts
- Technical improvements
- Migration timeline
- ROI analysis

**Share this** with stakeholders for buy-in.

## ✅ Implementation Checklist

### Phase 1: Setup & Models (Days 1-2)

- [ ] **Install dependencies**

  ```bash
  pip install fastapi uvicorn pydantic sqlalchemy[asyncio] python-multipart
  pip install pytest pytest-cov httpx  # For testing
  ```

- [x] **Create Pydantic models** ✅ DONE
  - [x] `src/microtutor/models/requests.py` - Request models with validation
  - [x] `src/microtutor/models/responses.py` - Response models
  - [x] `src/microtutor/models/domain.py` - Domain models (exists as types.py)

- [ ] **Test models**

  ```bash
  python -m pytest tests/unit/test_models.py -v
  ```

### Phase 2: Service Layer (Days 3-4)

- [ ] **Extract TutorService**
  - [ ] Move business logic from `V3/tutor.py` to `src/microtutor/services/tutor_service.py`
  - [ ] Implement `async def start_case()`
  - [ ] Implement `async def process_message()`
  - [ ] Add proper error handling
  - [ ] Add logging

- [ ] **Extract CaseService**
  - [ ] Move case logic to `src/microtutor/services/case_service.py`
  - [ ] Implement `async def get_case()`
  - [ ] Implement case caching

- [ ] **Extract FeedbackService**
  - [ ] Move feedback logic to `src/microtutor/services/feedback_service.py`
  - [ ] Implement `async def save_feedback()`
  - [ ] Implement `async def save_case_feedback()`

- [ ] **Update LLM calls to async**
  - [ ] Convert `llm_router.py` to async
  - [ ] Update `chat_complete` to `async def`

- [ ] **Test services**

  ```bash
  python -m pytest tests/unit/test_services/ -v
  ```

### Phase 3: API Layer (Days 5-6)

- [ ] **Create FastAPI app**
  - [ ] Create `src/microtutor/api/app.py`
  - [ ] Add CORS middleware
  - [ ] Add exception handlers
  - [ ] Add health check endpoint

- [ ] **Set up dependency injection**
  - [ ] Create `src/microtutor/api/dependencies.py`
  - [ ] Implement `get_tutor_service()`
  - [ ] Implement `get_db()`
  - [ ] Implement helper functions

- [ ] **Create chat routes**
  - [ ] Create `src/microtutor/api/routes/chat.py`
  - [ ] Implement `POST /api/v1/start_case`
  - [ ] Implement `POST /api/v1/chat`
  - [ ] Add proper error handling
  - [ ] Add logging

- [ ] **Create feedback routes**
  - [ ] Create `src/microtutor/api/routes/feedback.py`
  - [ ] Implement `POST /api/v1/feedback`
  - [ ] Implement `POST /api/v1/case_feedback`

- [ ] **Create admin routes**
  - [ ] Create `src/microtutor/api/routes/admin.py`
  - [ ] Implement `GET /api/v1/admin/feedback`
  - [ ] Implement `GET /api/v1/admin/live_chats`

- [ ] **Test API locally**

  ```bash
  uvicorn src.microtutor.api.app:app --reload --port 5001
  # Visit http://localhost:5001/api/docs
  ```

### Phase 4: Testing (Days 7-9)

- [ ] **Write unit tests**
  - [ ] Test all Pydantic models (`tests/unit/test_models.py`)
  - [ ] Test all services (`tests/unit/test_services/`)
  - [ ] Test domain logic (`tests/unit/test_core/`)

- [ ] **Write integration tests**
  - [ ] Test API endpoints (`tests/integration/test_api.py`)
  - [ ] Test database operations (`tests/integration/test_db.py`)
  - [ ] Test LLM integration (`tests/integration/test_llm.py`)

- [ ] **Write E2E tests**
  - [ ] Test complete user flows (`tests/e2e/test_flows.py`)
  - [ ] Test error scenarios

- [ ] **Achieve 90%+ coverage**

  ```bash
  pytest tests/ --cov=microtutor --cov-report=html
  open htmlcov/index.html
  ```

### Phase 5: Deployment (Day 10)

- [ ] **Create Docker configuration**
  - [ ] Create `docker/Dockerfile`
  - [ ] Create `docker/docker-compose.yml`
  - [ ] Test local Docker build

- [ ] **Set up CI/CD**
  - [ ] Create `.github/workflows/ci.yml`
  - [ ] Add automated testing
  - [ ] Add linting (ruff)

- [ ] **Deploy to staging**
  - [ ] Build and deploy Docker image
  - [ ] Test in staging environment
  - [ ] Monitor logs and metrics

- [ ] **Deploy to production**
  - [ ] Blue-green deployment
  - [ ] Monitor error rates
  - [ ] Validate all endpoints

## 🏃 Quick Start Commands

### Development

```bash
# Activate environment
cd V4_refactor

# Install dependencies
pip install -r requirements/requirements.txt

# Run development server
uvicorn src.microtutor.api.app:app --reload --port 5001

# Visit interactive API docs
open http://localhost:5001/api/docs
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_models.py -v

# Run with coverage
pytest tests/ --cov=microtutor --cov-report=html

# Run only fast tests
pytest tests/unit/ -v
```

### Code Quality

```bash
# Format code
ruff format src/

# Lint code
ruff check src/

# Type check
mypy src/
```

## 📊 Progress Tracking

Track your progress with this simple table:

| Phase | Tasks | Status | Notes |
|-------|-------|--------|-------|
| 1. Models | Create Pydantic models | ✅ DONE | requests.py, responses.py created |
| 2. Services | Extract service layer | ⏳ TODO | Start with TutorService |
| 3. API | Build FastAPI routes | ⏳ TODO | After services are done |
| 4. Testing | Write comprehensive tests | ⏳ TODO | Aim for 90%+ coverage |
| 5. Deployment | Deploy to production | ⏳ TODO | Docker + CI/CD |

## 🎓 Learning Resources

### FastAPI

- Official docs: <https://fastapi.tiangolo.com/>
- Tutorial: <https://fastapi.tiangolo.com/tutorial/>
- Async guide: <https://fastapi.tiangolo.com/async/>

### Pydantic

- Official docs: <https://docs.pydantic.dev/>
- Validation guide: <https://docs.pydantic.dev/usage/validators/>
- Settings management: <https://docs.pydantic.dev/usage/settings/>

### Testing

- pytest docs: <https://docs.pytest.org/>
- FastAPI testing: <https://fastapi.tiangolo.com/tutorial/testing/>
- pytest-cov: <https://pytest-cov.readthedocs.io/>

## 🐛 Common Issues & Solutions

### Issue: Import errors

**Solution:** Make sure you're in the right directory and have installed dependencies:

```bash
cd V4_refactor
pip install -e .  # Install package in editable mode
```

### Issue: Async errors

**Solution:** Make sure all LLM calls and DB operations are async:

```python
# Wrong
def call_llm():
    return openai.ChatCompletion.create(...)

# Right
async def call_llm():
    return await openai.ChatCompletion.acreate(...)
```

### Issue: Validation errors

**Solution:** Check the Pydantic model definition matches your data:

```python
# Add debug print to see what's failing
try:
    request = ChatRequest(**data)
except ValidationError as e:
    print(e.json())  # See detailed error
```

### Issue: Tests failing

**Solution:** Make sure to override dependencies in tests:

```python
# In tests
from fastapi.testclient import TestClient

app.dependency_overrides[get_tutor_service] = lambda: MockTutorService()
```

## 💡 Tips for Success

1. **Start small** - Begin with just `/start_case` endpoint
2. **Test as you go** - Write tests immediately after implementing
3. **Use the docs** - Interactive docs at `/api/docs` help debugging
4. **Commit often** - Small, focused commits make rollback easy
5. **Run V3 parallel** - Keep V3 running until V4 is fully tested

## 📞 Getting Help

If you get stuck:

1. Check the documentation files in this directory
2. Read the FastAPI docs
3. Check the Pydantic validation guide
4. Look at the test examples
5. Use the interactive API docs for debugging

## 🎉 Success Criteria

You'll know the refactoring is complete when:

- ✅ All V3 endpoints are replicated in V4
- ✅ All tests pass with 90%+ coverage
- ✅ Interactive API docs work perfectly
- ✅ Type checking passes (`mypy src/`)
- ✅ No linting errors (`ruff check src/`)
- ✅ Performance is equal or better than V3
- ✅ Can deploy to production successfully

## 📈 Expected Outcomes

After completing this refactoring, you'll have:

- ✅ **68% less code** to maintain (620 → 200 lines)
- ✅ **90% test coverage** vs 20% before
- ✅ **5-10x better performance** with async
- ✅ **100% type safety** throughout
- ✅ **Automatic API documentation**
- ✅ **Easy testing** with dependency injection
- ✅ **Production-ready** error handling
- ✅ **Modern architecture** ready for scaling

## 🚀 Let's Build V4

You now have everything you need:

- ✅ Complete documentation
- ✅ Pydantic models ready
- ✅ Clear implementation plan
- ✅ Step-by-step guide
- ✅ Testing strategy

**Time to transform MicroTutor into a state-of-the-art application! 🎓**

---

**Questions? Review the other documentation files in this directory for detailed answers.**
