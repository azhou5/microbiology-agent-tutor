# Utilities Layer

Shared utility functions used across the application. Domain-agnostic helpers.

## Structure

```
utils/
├── conversation_utils.py    # Conversation history manipulation
├── embedding_utils.py        # Embedding generation
├── phase_utils.py           # Phase/state management
└── protocols.py             # Protocol definitions (type hints)
```

## Files

### `conversation_utils.py`

**Purpose**: Conversation history manipulation utilities  
**Necessary**: ✅ Yes - Used throughout application  
**Could be more concrete**: ✅ Well-organized

- `filter_system_messages()` - Remove system messages from history
- `prepare_llm_messages()` - Format messages for LLM
- `normalize_organism_name()` - Standardize organism names
- `get_cached_first_pt_sentence()` - Get cached patient sentences
- `has_cached_case()` - Check if case is cached

**Usage**: Used by TutorService and tools to manage conversation state

### `embedding_utils.py`

**Purpose**: Embedding generation utilities  
**Necessary**: ✅ Yes - Used by feedback system  
**Could be more concrete**: ✅ Well-contained

- `get_embedding()` - Generate embedding for text
- `get_embeddings_batch()` - Batch embedding generation
- `get_embedding_model_name()` - Get model name
- `get_embedding_dimension()` - Get embedding dimension

**Usage**: Used by `core/feedback/processor.py` for FAISS indexing

### `phase_utils.py`

**Purpose**: Phase/state management utilities  
**Necessary**: ✅ Yes - Core tutoring flow  
**Could be more concrete**: ✅ Good structure

- `PHASE_AGENT_MAPPING` - Map phases to tools
- `determine_phase_from_tools()` - Infer phase from tool usage
- `validate_phase_transition()` - Validate phase changes
- `get_next_phase()` - Get next phase in sequence
- `is_phase_complete()` - Check if phase is complete
- `get_completion_token()` - Get phase completion token

**Usage**: Used by TutorService to manage case progression

### `protocols.py`

**Purpose**: Protocol definitions for type hints  
**Necessary**: ✅ Yes - Type safety  
**Could be more concrete**: ✅ Good use of protocols

- `ToolEngine` - Protocol for tool engines
- `FeedbackClient` - Protocol for feedback clients

**Usage**: Used for dependency injection and type checking

## Recommendations

1. ✅ **Well-organized**: Clear separation of concerns
2. ✅ **Reusable**: Functions are domain-agnostic
3. ✅ **Type-safe**: Good use of type hints
4. ✅ **No circular dependencies**: Clean import structure
