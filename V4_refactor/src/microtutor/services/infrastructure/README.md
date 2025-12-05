# Infrastructure Services

Supporting services that provide cross-cutting concerns: dependency injection, background tasks, and cost tracking.

## Files

### `factory.py`

**Purpose**: Service factory with dependency injection  
**Necessary**: ✅ Yes - Creates services with proper DI  
**Could be more concrete**: ✅ Well-implemented

- `create_tutor_service()` - Creates TutorService with all dependencies
- Handles feedback system initialization
- Manages project root resolution
- **Key**: Ensures proper initialization order and dependency resolution

### `background.py`

**Purpose**: Background task service for async operations  
**Necessary**: ✅ Yes - Handles async tasks  
**Could be more concrete**: ✅ Good separation

- `BackgroundTaskService` - Manages background tasks
- `get_background_service()` - Singleton access
- Handles:
  - Feedback logging to database
  - FAISS index regeneration
  - Async operations that don't block API responses

**Key Features**:

- Async task execution
- Error handling and logging
- Integration with FastAPI lifespan

### `cost.py`

**Purpose**: Cost tracking service  
**Necessary**: ✅ Yes - Budget management  
**Could be more concrete**: ✅ Well-contained

- `CostService` - Tracks token usage and costs
- Aggregates costs per model
- Provides cost reporting

## Usage

```python
# Create service via factory
tutor_service = create_tutor_service(
    model_name="gpt-4",
    enable_feedback=True
)

# Background tasks
background_service = get_background_service()
await background_service.log_feedback_async(...)
```

## Recommendations

1. ✅ **Well-designed**: Clean separation of concerns
2. ✅ **Dependency injection**: Proper use of factory pattern
3. ✅ **Async handling**: Good use of background tasks
