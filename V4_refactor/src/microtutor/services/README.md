# Services Layer

Business logic layer that orchestrates domain operations. Services are stateless and can be used independently or composed together.

## Structure

```
services/
├── tutor/              # Main tutoring service (orchestrates everything)
├── case/               # Case generation and management
├── feedback/           # Feedback service (API layer for feedback)
├── voice/              # Voice synthesis and transcription
├── mcq/                # Multiple choice question generation
├── guideline/          # Clinical guideline services
├── infrastructure/     # Supporting services (background tasks, cost, factory)
└── adapters/           # Adapter pattern implementations
```

## Files

### `tutor/service.py`

**Purpose**: Main tutoring service - orchestrates the entire tutoring flow  
**Necessary**: ✅ Yes - Core service  
**Could be more concrete**: ⚠️ Large file (483 lines), could split into smaller services

- `TutorService` - Main service class
- `start_case()` - Initialize new case
- `process_message()` - Handle user messages
- Routes to appropriate tools
- Manages conversation history and phase transitions
- Retrieves feedback and appends to conversation

**Key Responsibilities**:

- Message routing to tools
- Phase management (information gathering → diagnosis → management)
- Feedback integration
- Tool execution orchestration

**Recommendations**:

- Consider splitting phase management into separate service
- Extract feedback retrieval logic (already done via adapter)

### `case/`

**Purpose**: Case generation and loading  
**Necessary**: ✅ Yes - Core functionality  
**Could be more concrete**: ✅ Well-organized

- `service.py` - Case service interface
- `case_loader.py` - Loads cached cases
- `case_generator_rag.py` - RAG-based case generation
- `get_case()` - Main entry point

### `feedback/service.py`

**Purpose**: Feedback service (API layer)  
**Necessary**: ⚠️ Maybe - Thin wrapper, could be in API routes  
**Could be more concrete**: ⚠️ Consider if this adds value or can be removed

- `FeedbackService` - Service interface for feedback
- **Note**: Most feedback logic is in `core/feedback/`, this might be redundant

### `voice/service.py`

**Purpose**: Voice synthesis and transcription  
**Necessary**: ✅ Yes - Voice features  
**Could be more concrete**: ✅ Well-contained

- Text-to-speech
- Speech-to-text
- Voice chat integration

### `mcq/`

**Purpose**: Multiple choice question generation  
**Necessary**: ✅ Yes - MCQ functionality  
**Could be more concrete**: ✅ Good separation

- `service.py` - MCQ service
- `mcp_service.py` - MCP-based MCQ agent

### `guideline/`

**Purpose**: Clinical guideline services  
**Necessary**: ✅ Yes - Guideline integration  
**Could be more concrete**: ✅ Well-structured

- `service.py` - Guideline service
- `cache.py` - Guideline caching for performance

### `infrastructure/`

**Purpose**: Supporting infrastructure services  
**Necessary**: ✅ Yes - Critical infrastructure  
**Could be more concrete**: ✅ Well-organized

- `factory.py` - Service factory (creates TutorService with DI)
- `background.py` - Background task service (async operations)
- `cost.py` - Cost tracking service

**Key Files**:

- `factory.py` - Creates services with proper dependency injection
- `background.py` - Handles async tasks (feedback indexing, logging)

### `adapters/`

**Purpose**: Adapter pattern for integrating external systems  
**Necessary**: ✅ Yes - Clean integration pattern  
**Could be more concrete**: ✅ Good use of adapter pattern

- `feedback_adapter.py` - Adapts `AutoFeedbackRetriever` to `FeedbackClient` protocol
- Used by `TutorService` to integrate feedback system

## Service Dependencies

```
TutorService
    ├── ToolEngine (tools/)
    ├── LLMClient (core/llm/)
    ├── FeedbackClient (adapters/feedback_adapter.py)
    ├── CaseService (case/)
    └── GuidelinesCache (guideline/)
```

## Recommendations

1. **Split `TutorService`**: Consider extracting phase management into separate service
2. **Review `FeedbackService`**: Check if it's actually used or can be removed
3. **Factory pattern**: ✅ Well-implemented dependency injection
4. **Background tasks**: ✅ Good separation of async operations
