# Simplified MicroTutor Architecture

This directory contains a refactored and simplified version of the MicroTutor application.

## Structure

- **`agents/`**: Contains the core logic for each phase of the case.
  - `orchestrator.py`: Manages the overall state and transitions between agents.
  - `patient_agent.py`: Handles patient simulation (Information Gathering).
  - `deeper_dive_agent.py`: Handles optional deeper-dive tutoring.
  - `tests_agent.py`: Handles test ordering and management planning.
  - `feedback_agent.py`: Provides final feedback.
  - `quiz_agent.py`: Generates post-case MCQs based on student weaknesses.
  - `base_agent.py`: Common functionality for all agents.

- **`tools/`**: Helper tools used by agents.
  - `csv_tool.py`: Loads pathogen data from CSV for guidance.
  - `feedback_tool.py`: Manages feedback storage and retrieval (RAG).

- **`utils/`**: Utility functions.
  - `case_loader.py`: Loads case data from cache.
  - `llm.py`: Simplified LLM client wrapper.

- **`config/`**: Configuration settings.
  - `config.py`: Loads environment variables.

- **`prompts.py`**: Centralized location for all system prompts.

- **`app.py`**: Simplified FastAPI application that serves the frontend and orchestrates the agents.

## Key Features Retained

1.  **Case Flow**: Follows the `tutor_prompt.py` state machine (Info Gathering -> DDx -> Tests -> Deeper Dive -> MCQ -> Feedback).
2.  **CSV Guidance**: Uses `pathogen_history_domains_complete.csv` to guide the Socratic agent.
3.  **Feedback Mechanism**: Uses the existing feedback data structure.
4.  **Frontend Compatibility**: The API endpoints are designed to work with the existing frontend.

## How to Run

1.  Navigate to `V4_refactor/`.
2.  Ensure you have the required dependencies installed.
3.  Run the simplified app:
    ```bash
    ./run_simplified.sh
    ```
4.  Open your browser to `http://localhost:8000`.

