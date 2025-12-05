# MicroTutor Source Code

This directory contains the complete source code for MicroTutor V4, an AI-powered microbiology tutoring system.

## Directory Structure

```
src/
└── microtutor/          # Main package
    ├── api/             # FastAPI REST API layer
    ├── core/            # Core infrastructure
    ├── services/        # Business logic services
    ├── tools/           # Agentic tools
    ├── schemas/         # Pydantic data models
    ├── prompts/         # LLM prompt templates
    └── utils/           # Shared utilities
```

## Quick Start

1. **API Entry Point**: `microtutor.api.app` - FastAPI application
2. **Main Service**: `microtutor.services.TutorService` - Core tutoring service
3. **Tools**: `microtutor.tools` - Agentic tool implementations

## Documentation

Each directory contains a README.md with detailed documentation:

- [Main Package](microtutor/README.md)
- [API Layer](microtutor/api/README.md)
- [Core Infrastructure](microtutor/core/README.md)
- [Services Layer](microtutor/services/README.md)
- [Tools Layer](microtutor/tools/README.md)
- [Schemas](microtutor/schemas/README.md)
- [Prompts](microtutor/prompts/README.md)
- [Utilities](microtutor/utils/README.md)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                  │
│  Routes, Dependencies, Static Files                      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                 Services Layer                           │
│  TutorService, CaseService, FeedbackService, etc.       │
└──────┬──────────────┬──────────────┬────────────────────┘
       │              │              │
┌──────▼──────┐  ┌───▼──────┐  ┌───▼──────────┐
│   Tools     │  │   Core   │  │   Schemas    │
│  (Agents)   │  │ (LLM,    │  │  (Models)    │
│             │  │  Config) │  │              │
└─────────────┘  └──────────┘  └──────────────┘
```

## Key Design Principles

1. **Separation of Concerns**: Clear layer boundaries
2. **Dependency Injection**: Services created via factory
3. **Type Safety**: Extensive Pydantic validation
4. **Tool-Based Architecture**: Agentic tools for specialized tasks
5. **Feedback Integration**: Centralized at TutorService level

## Development

- **Entry Point**: `python -m microtutor.api.app` or `uvicorn microtutor.api.app:app`
- **Testing**: See test files in project root
- **Configuration**: Environment variables (see `.env` or `dot_env_microtutor.txt`)
