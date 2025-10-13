# Professional Directory Restructure Plan

## Current Issues

- Mixed concerns (config, data, logs, source code in root)
- No clear separation of source, tests, docs, data
- Missing development tools and CI/CD setup
- Inconsistent naming conventions
- No proper Python packaging structure

## Proposed Structure

```
microbiology-tutor/
├── README.md                           # Project overview and quick start
├── CHANGELOG.md                        # Version history and changes
├── LICENSE                             # License file
├── pyproject.toml                      # Modern Python packaging and tool config
├── requirements/                       # Dependency management
│   ├── base.txt                       # Core dependencies
│   ├── dev.txt                        # Development dependencies
│   └── prod.txt                       # Production dependencies
│
├── src/                               # Source code (importable package)
│   └── microtutor/
│       ├── __init__.py
│       ├── core/                      # Core business logic
│       │   ├── __init__.py
│       │   ├── tutor.py              # Main tutor engine
│       │   └── llm_router.py         # LLM routing logic
│       ├── agents/                    # Multi-agent system
│       │   ├── __init__.py
│       │   ├── base.py               # Base agent class
│       │   ├── case_generator.py     # Case generation agent
│       │   ├── patient.py            # Patient simulation agent
│       │   └── hint.py               # Hint generation agent
│       ├── models/                    # Data models and schemas
│       │   ├── __init__.py
│       │   ├── case.py               # Case data models
│       │   └── feedback.py           # Feedback data models
│       ├── services/                  # Business services
│       │   ├── __init__.py
│       │   ├── case_service.py       # Case management service
│       │   ├── feedback_service.py   # Feedback processing service
│       │   └── rag_service.py        # RAG and FAISS service
│       ├── utils/                     # Utility functions
│       │   ├── __init__.py
│       │   ├── llm_utils.py          # LLM utilities
│       │   └── data_utils.py         # Data processing utilities
│       └── web/                       # Web application
│           ├── __init__.py
│           ├── app.py                # Flask application
│           ├── routes/               # Route handlers
│           │   ├── __init__.py
│           │   ├── api.py            # API routes
│           │   └── web.py            # Web routes
│           ├── static/               # Static assets
│           │   ├── css/
│           │   ├── js/
│           │   └── images/
│           └── templates/            # HTML templates
│               ├── base.html
│               ├── index.html
│               └── admin/
│
├── tests/                             # Test suite
│   ├── __init__.py
│   ├── conftest.py                   # Pytest configuration
│   ├── unit/                         # Unit tests
│   │   ├── test_agents/
│   │   ├── test_core/
│   │   └── test_services/
│   ├── integration/                  # Integration tests
│   └── e2e/                          # End-to-end tests
│
├── docs/                              # Documentation
│   ├── index.md                      # Documentation home
│   ├── api/                          # API documentation
│   ├── guides/                       # User guides
│   ├── development/                  # Development guides
│   └── deployment/                   # Deployment guides
│
├── data/                              # Data storage
│   ├── cases/                        # Case data
│   │   ├── generated/
│   │   ├── cached/
│   │   └── templates/
│   ├── feedback/                     # Feedback data
│   │   ├── logs/
│   │   └── processed/
│   ├── models/                       # ML model artifacts
│   │   ├── faiss_indices/
│   │   └── reward_models/
│   └── raw/                          # Raw data files
│
├── config/                           # Configuration files
│   ├── __init__.py
│   ├── base.py                      # Base configuration
│   ├── development.py               # Development config
│   ├── production.py                # Production config
│   └── testing.py                   # Testing config
│
├── scripts/                          # Utility scripts
│   ├── setup.py                     # Setup script
│   ├── pregenerate_cases.py         # Case generation script
│   ├── create_indices.py            # Index creation script
│   └── deploy.py                    # Deployment script
│
├── notebooks/                        # Jupyter notebooks
│   ├── exploration/                 # Data exploration
│   ├── experiments/                 # ML experiments
│   └── analysis/                    # Analysis notebooks
│
├── logs/                             # Log files (gitignored)
│   ├── app.log
│   ├── feedback.log
│   └── error.log
│
├── .github/                          # GitHub workflows
│   └── workflows/
│       ├── ci.yml                   # Continuous integration
│       ├── cd.yml                   # Continuous deployment
│       └── tests.yml                # Test automation
│
├── docker/                           # Docker configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
└── .devcontainer/                    # VS Code dev container
    ├── devcontainer.json
    └── Dockerfile
```

## Key Improvements

### 1. **Proper Python Package Structure**

- `src/microtutor/` layout for clean imports
- Clear separation of concerns with dedicated modules
- Proper `__init__.py` files for package structure

### 2. **Configuration Management**

- Environment-specific configs in `config/`
- Modern `pyproject.toml` for tool configuration
- Separate requirements files for different environments

### 3. **Testing Infrastructure**

- Comprehensive test structure (unit, integration, e2e)
- `conftest.py` for pytest configuration
- Test coverage and quality gates

### 4. **Documentation**

- Structured documentation in `docs/`
- API documentation generation
- Development and deployment guides

### 5. **Data Management**

- Organized data storage in `data/`
- Separate directories for different data types
- Version control for data artifacts

### 6. **Development Tools**

- Pre-commit hooks for code quality
- CI/CD pipelines in `.github/workflows/`
- Docker support for containerization
- Dev container for consistent development environment

### 7. **Professional Standards**

- README, CHANGELOG, LICENSE files
- Proper dependency management
- Code formatting and linting configuration
- Security scanning and vulnerability checks

## Migration Strategy

1. **Phase 1**: Create new structure and move core files
2. **Phase 2**: Set up development tools and CI/CD
3. **Phase 3**: Migrate data and configuration
4. **Phase 4**: Update imports and dependencies
5. **Phase 5**: Add comprehensive testing and documentation
