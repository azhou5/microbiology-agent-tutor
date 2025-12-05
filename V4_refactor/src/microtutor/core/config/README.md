# Configuration Management

Configuration loading, validation, and application lifecycle management.

## Files

### `config_helper.py`

**Purpose**: Centralized configuration access  
**Necessary**: ✅ Yes - Single source of truth  
**Could be more concrete**: ✅ Well-structured

- Loads configuration from environment variables
- Provides typed access to config values
- Handles defaults and validation
- **Usage**: `from microtutor.core.config.config_helper import config`

### `warning_suppression.py`

**Purpose**: Suppress noisy third-party warnings  
**Necessary**: ⚠️ Nice to have, not critical  
**Could be more concrete**: ✅ Simple utility

- Filters warnings from libraries
- Can be removed if not needed

## Recommendations

1. ✅ **Centralized config**: Good single source of truth
2. ✅ **startup.py moved**: Now in `api/` directory (FastAPI-specific)
3. ✅ **Type safety**: Config values are typed
