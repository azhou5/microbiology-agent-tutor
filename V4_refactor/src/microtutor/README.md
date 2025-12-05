# MicroTutor Package Overview

This is the main package for MicroTutor V4, an AI-powered microbiology tutoring system.

## Architecture

```
microtutor/
├── api/          # FastAPI REST API layer (routes, dependencies, static files)
├── core/         # Core infrastructure (LLM, config, logging, feedback)
├── services/     # Business logic services (tutor, case, feedback, etc.)
├── tools/        # Agentic tools (patient, socratic, hint, etc.)
├── schemas/      # Pydantic data models (API, database, domain)
├── prompts/      # LLM prompt templates
└── utils/        # Shared utility functions
```

## Key Design Principles

1. **Separation of Concerns**: API layer → Service layer → Core utilities
2. **Type Safety**: Extensive use of Pydantic models for validation
3. **Dependency Injection**: Services are created via factory pattern
4. **Tool-Based Architecture**: Agentic tools follow ToolUniverse patterns
5. **Feedback Integration**: Centralized feedback retrieval at TutorService level

## Entry Points

- **API**: `microtutor.api.app` - FastAPI application
- **Services**: `microtutor.services` - Business logic layer
- **Tools**: `microtutor.tools` - Agentic tool implementations

## Main Exports

See `__init__.py` for the main public API:

- `TutorService` - Main tutoring service
- `CaseService` - Case management
- `FeedbackService` - Feedback handling
- Domain schemas (`TutorContext`, `TutorState`, etc.)
