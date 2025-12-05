# Feedback System

Auto-generated feedback indexing and retrieval system. Feedback is stored in PostgreSQL and automatically indexed in FAISS for similarity search.

## Architecture

```
Feedback Flow:
1. User submits feedback → PostgreSQL database
2. Background task → AutoFAISSGenerator creates/updates FAISS indices
3. TutorService → AutoFeedbackRetriever retrieves similar examples
4. Feedback appended to conversation history → Tools receive via history
```

## Structure

```
feedback/
├── __init__.py           # Package exports
├── auto_generator.py     # Generates FAISS indices from database
├── auto_retriever.py     # Retrieves similar feedback examples
├── database_loader.py   # Loads feedback from PostgreSQL
├── processor.py          # Processes feedback entries, creates embeddings
└── prompts.py            # Formats feedback for LLM prompts
```

## Files

### `auto_generator.py`

**Purpose**: Automatically generates FAISS indices from PostgreSQL database  
**Necessary**: ✅ Yes - Core indexing functionality  
**Could be more concrete**: ✅ Well-structured

- `AutoFAISSGenerator` - Main generator class
- `get_auto_faiss_generator()` - Singleton access
- Monitors database for new feedback
- Creates separate indices: `all`, `patient`, `tutor`
- Saves to `data/feedback_auto/`

**Key Features**:

- Full regeneration when needed
- Incremental updates for new feedback
- Automatic index reloading after updates

### `auto_retriever.py`

**Purpose**: Retrieves similar feedback examples using FAISS  
**Necessary**: ✅ Yes - Core retrieval functionality  
**Could be more concrete**: ✅ Well-designed

- `AutoFeedbackRetriever` - Main retriever class
- `get_auto_feedback_retriever()` - Singleton access
- Loads FAISS indices from `data/feedback_auto/`
- Supports filtering by index type (`all`, `patient`, `tutor`)
- Returns `FeedbackExample` objects with similarity scores

**Key Features**:

- Automatic index reloading when updated
- Similarity search with configurable `k`
- Rating-based filtering

### `database_loader.py`

**Purpose**: Loads feedback entries from PostgreSQL  
**Necessary**: ✅ Yes - Database access layer  
**Could be more concrete**: ✅ Clean separation

- `DatabaseFeedbackLoader` - Loads feedback from DB
- `DatabaseFeedbackConfig` - Configuration for DB queries
- Supports filtering by date range, rating, organism
- Converts DB rows to `FeedbackEntry` objects

### `processor.py`

**Purpose**: Processes feedback entries and creates embeddings  
**Necessary**: ✅ Yes - Embedding generation  
**Could be more concrete**: ✅ Well-contained

- `FeedbackEntry` - Dataclass for feedback entries
- `FeedbackExample` - Dataclass for retrieved examples
- `FeedbackProcessor` - Creates embeddings and FAISS indices
- Handles embedding text generation from chat history

**Note**: Also contains legacy JSON loading (can be removed if not used)

### `formatter.py`

**Purpose**: Formats feedback examples into strings for LLM prompt insertion  
**Necessary**: ✅ Yes - Converts structured data to formatted text  
**Could be more concrete**: ✅ Well-named (was `prompts.py`, renamed for clarity)

- `format_feedback_examples()` - Converts `FeedbackExample` objects to formatted string
- `get_feedback_examples_for_tool()` - Retrieves examples and formats them for a specific tool
- Used by `FeedbackClientAdapter` in TutorService
- **Note**: This formats data, not prompts. The actual prompt templates are in `prompts/` directory.

## Integration Points

1. **TutorService** (`services/tutor/service.py`):
   - Uses `FeedbackClientAdapter` which wraps `AutoFeedbackRetriever`
   - Retrieves feedback once per message
   - Appends to conversation history

2. **Background Service** (`services/infrastructure/background.py`):
   - Triggers `AutoFAISSGenerator` when new feedback is added
   - Handles async re-indexing

3. **API Routes** (`api/routes/chat.py`):
   - `/feedback` and `/case_feedback` endpoints
   - Store feedback in PostgreSQL
   - Trigger background re-indexing

## Data Flow

```
User Feedback
    ↓
API Route (chat.py)
    ↓
Background Service (background.py)
    ↓
PostgreSQL Database
    ↓
AutoFAISSGenerator (auto_generator.py)
    ↓
FAISS Index (data/feedback_auto/)
    ↓
AutoFeedbackRetriever (auto_retriever.py)
    ↓
TutorService (service.py)
    ↓
Conversation History
    ↓
Tools (patient, socratic, etc.)
```

## Recommendations

1. ✅ **Well-architected**: Clear separation of concerns
2. ✅ **Singleton pattern**: Prevents duplicate index loading
3. ⚠️ **Legacy code**: Remove JSON loading from `processor.py` if not used
4. ✅ **Auto-reload**: Indices automatically reload when updated
