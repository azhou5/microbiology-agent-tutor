# Schemas Layer

Pydantic data models for type-safe data validation and serialization. Organized by domain (API, database, domain models).

## Structure

```
schemas/
├── api/                 # API request/response models
│   ├── requests.py      # Request models
│   └── responses.py     # Response models
├── database/            # Database models (SQLAlchemy)
│   └── database.py      # ORM models
└── domain/              # Domain models (business logic)
    └── domain.py        # Core domain entities
```

## Files

### `api/requests.py`

**Purpose**: Pydantic models for API request validation  
**Necessary**: ✅ Yes - Type safety and validation  
**Could be more concrete**: ✅ Well-structured

- `StartCaseRequest` - Initialize case request
- `ChatRequest` - Chat message request
- `FeedbackRequest` - Feedback submission
- `CaseFeedbackRequest` - Case-level feedback
- All include validation and documentation

### `api/responses.py`

**Purpose**: Pydantic models for API responses  
**Necessary**: ✅ Yes - Consistent response format  
**Could be more concrete**: ✅ Good structure

- `StartCaseResponse` - Case initialization response
- `ChatResponse` - Chat response
- `ErrorResponse` - Error response format
- Standardized response structure

### `database/database.py`

**Purpose**: SQLAlchemy ORM models  
**Necessary**: ✅ Yes - Database schema definition  
**Could be more concrete**: ✅ Standard ORM pattern

- `Feedback` - Feedback table model
- `CaseFeedback` - Case feedback table model
- Database relationships and constraints
- **Note**: These are the source of truth for database schema

### `domain/domain.py`

**Purpose**: Core domain entities (business logic models)  
**Necessary**: ✅ Yes - Domain model definitions  
**Could be more concrete**: ✅ Well-organized

- `TutorContext` - Conversation context
- `TutorResponse` - Tutor response structure
- `TutorState` - Phase/state enumeration
- Used throughout services layer

## Model Relationships

```
API Request (requests.py)
    ↓
Domain Model (domain.py)
    ↓
Service Logic
    ↓
Database Model (database.py)
    ↓
API Response (responses.py)
```

## Recommendations

1. ✅ **Well-organized**: Clear separation by domain
2. ✅ **Type safety**: Pydantic provides excellent validation
3. ✅ **Documentation**: Models include field descriptions
4. ⚠️ **Consider**: Add more validation rules where appropriate
