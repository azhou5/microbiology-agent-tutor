# Core Infrastructure

Core functionality shared across the application: LLM clients, configuration, logging, feedback, and base classes.

## Structure

```
core/
├── base_agent.py           # Base class for agentic tools
├── config/                 # Configuration management
│   ├── config_helper.py    # Config loading and access
│   ├── startup.py          # Application lifecycle (lifespan)
│   └── warning_suppression.py  # Suppress third-party warnings
├── llm/                    # LLM client and routing
│   ├── llm_client.py       # Main LLM client (OpenAI, Azure)
│   └── llm_router.py       # Model routing logic
├── logging/                # Logging configuration
│   └── logging_config.py  # Structured logging setup
├── cost/                   # Cost tracking
│   └── cost_tracker.py     # Token usage and cost calculation
└── feedback/               # Feedback system (see feedback/README.md)
```

## Files

### `base_agent.py`

**Purpose**: Base class for all agentic tools  
**Necessary**: ✅ Yes - Provides common functionality  
**Could be more concrete**: ⚠️ Could be in `tools/` instead of `core/`

- Abstract base class for tools
- Common LLM calling patterns
- Logging integration
- **Note**: Consider moving to `tools/base.py` if only used by tools

### `config/config_helper.py`

**Purpose**: Centralized configuration access  
**Necessary**: ✅ Yes - Single source of truth for config  
**Could be more concrete**: ✅ Well-structured

- Loads from environment variables
- Provides typed access to config values
- Handles defaults and validation

### `config/startup.py`

**Purpose**: Application lifecycle management  
**Necessary**: ✅ Moved to `api/startup.py` - FastAPI-specific  
**Status**: ✅ Now in `api/` directory where it belongs

- Startup: Initialize services, database
- Shutdown: Cleanup resources
- Background service management
- **Note**: Moved to `api/` since it's FastAPI-specific

### `config/warning_suppression.py`

**Purpose**: Suppress noisy third-party warnings  
**Necessary**: ⚠️ Maybe - Nice to have, not critical  
**Could be more concrete**: ✅ Simple utility

- Filters warnings from libraries
- Can be removed if not needed

### `llm/llm_client.py`

**Purpose**: Unified LLM client interface  
**Necessary**: ✅ Yes - Core LLM functionality  
**Could be more concrete**: ✅ Well-designed

- Supports OpenAI and Azure OpenAI
- Retry logic and fallback models
- Tool calling support
- Streaming support

### `llm/llm_router.py`

**Purpose**: Route requests to appropriate models  
**Necessary**: ⚠️ Maybe - If you have multiple models, yes  
**Could be more concrete**: ⚠️ Could merge with llm_client.py if simple

- Model selection logic
- Load balancing
- **Note**: If only using one model, this might be overkill

### `logging/logging_config.py`

**Purpose**: Structured logging setup  
**Necessary**: ✅ Yes - Important for debugging  
**Could be more concrete**: ✅ Good structure

- Agent context logging
- Request/response logging
- Integration with monitoring

### `cost/cost_tracker.py`

**Purpose**: Track token usage and costs  
**Necessary**: ✅ Yes - Important for budgeting  
**Could be more concrete**: ✅ Well-contained

- Token counting
- Cost calculation per model
- Aggregation and reporting

### `feedback/`

**Purpose**: Feedback indexing and retrieval system  
**Necessary**: ✅ Yes - Core feature  
**See**: `feedback/README.md` for details

## Recommendations

1. **Move `base_agent.py`**: Consider moving to `tools/base.py` if only used by tools
2. **Move `startup.py`**: Since it's FastAPI-specific, could go in `api/`
3. **Simplify `llm_router.py`**: If only using one model, merge with `llm_client.py`
4. **Consolidate config**: All config-related files are well-organized
