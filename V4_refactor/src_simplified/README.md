# MicroTutor Simplified (`src_simplified`)

A streamlined, single-app version of MicroTutor V4. It preserves the same user-facing flow (phases, chat, feedback) but uses a **multi-agent orchestrator** and in-memory sessions instead of the main codebase’s layered services and tool engine. Use it to understand the tutoring flow quickly or to prototype; use **`src`** (main) for production and extensibility.

---

## Directory Structure

```
src_simplified/
├── app.py              # FastAPI app + all API routes (single file)
├── prompts.py          # All orchestrator and agent prompts
├── config/
│   └── config.py       # Environment/config (model, API key, paths)
├── agents/
│   ├── orchestrator.py # Phase state, routing, image handling
│   ├── base_agent.py   # Base class for subagents
│   ├── patient_agent.py
│   ├── deeper_dive_agent.py
│   ├── tests_agent.py
│   ├── feedback_agent.py
│   └── quiz_agent.py
├── tools/
│   ├── feedback_tool.py # Save/load feedback (e.g. JSON file)
│   └── csv_tool.py     # CSV-based guidance (e.g. crucial factors)
├── utils/
│   ├── llm.py          # chat_complete() – thin OpenAI wrapper
│   └── case_loader.py  # Load case content by organism/case ID
└── api/                # Static assets and Jinja2 templates (shared-style UI)
    ├── static/
    └── templates/
```

---

## End-to-End Flow

### 1. Start a case

- **Endpoint**: `POST /api/v1/start_case` with `organism` (or case ID) and `case_id` (session key).
- **Behaviour**: An `Orchestrator(organism)` is created, and stored in `sessions[case_id]`. The orchestrator loads case data (`CaseLoader`), sets up CSV guidance (`CSVTool`), and initializes one agent per phase (Patient, Tests, DeeperDive, Quiz, Feedback). Differential diagnosis has no dedicated agent; the orchestrator handles it with a “manager” prompt.
- **Response**: Initial welcome message and `current_phase` (e.g. `information_gathering`).

### 2. Chat loop

- **Endpoint**: `POST /api/v1/chat` with `case_id`, `message`, and optional `current_phase` / `organism_key` / `history` (for session recovery).
- **Behaviour**:
  1. **Session lookup**: `orchestrator = sessions[case_id]`. If missing and `organism_key` (and optionally `history`) is provided, a new orchestrator is created and history restored.
  2. **History update**: User message is appended to `orchestrator.conversation_history`.
  3. **Phase / state**:
     - **Explicit phase jump**: If the user asks to skip ahead (e.g. “let’s move onto phase: deeper dive”), `_extract_requested_phase_transition` parses it and the orchestrator may emit a “skipped sections” recap, then switches to the requested phase.
     - **Otherwise**: `_determine_state(user_message)` (LLM or heuristics) decides the current phase and any transition message or image to show.
  4. **Routing**: Based on `current_state`, the request is handled by:
     - **Differential diagnosis**: `_manager_phase_chat()` – orchestrator calls `chat_complete()` with `MANAGER_DIFFERENTIAL_SYSTEM_PROMPT` and recent history.
     - **Post-case MCQ**: First time without “mcq” in the message → `QuizAgent.generate_quiz()`; otherwise `QuizAgent.chat()`.
     - **All other phases**: The corresponding agent’s `chat()` (e.g. `PatientAgent`, `TestsAgent`, `FeedbackAgent`). Each agent keeps its own history and uses prompts from `prompts.py`.
  5. **Images**: The orchestrator may attach an image (e.g. from a tool-like `display_image` or from parsing the response / proactive display logic).
  6. **History update**: Orchestrator and subagent messages are appended to `conversation_history`.
- **Response**: `response`, `orchestrator_message`, `subagent_name`, `image_url`, `history`, `metadata.current_phase`, etc., plus a `tool_map`-derived `subagent_speaker` for UI (e.g. patient, maintutor_differential, tests_management).

### 3. Phase order (simplified)

Phases are fixed and ordered in `Orchestrator.PHASE_ORDER`:

1. `information_gathering` → PatientAgent  
2. `differential_diagnosis` → orchestrator (manager prompt)  
3. `tests_management` → TestsAgent  
4. `deeper_dive` → DeeperDiveAgent  
5. `post_case_mcq` → QuizAgent  
6. `feedback` → FeedbackAgent  

State labels (e.g. “tests & management”) are normalized via `PHASE_LABEL_TO_STATE`.

### 4. Other endpoints

- **Feedback**: `POST /api/v1/feedback` and `POST /api/v1/case_feedback` write to `FeedbackTool` (e.g. `new_feedback.json`).
- **Clarify**: `POST /api/v1/clarify` – clarification flow (separate from main chat).
- **Config / analytics / FAISS / DB / guidelines**: Read-only or minimal admin endpoints implemented inline in `app.py` (e.g. `/api/v1/config`, `/api/v1/analytics/feedback/stats`, `/api/v1/faiss/reindex-status`, `/api/v1/guidelines/health`).

---

## How and When It Differs from Main `src`

| Aspect | **src_simplified** | **src (main)** |
|--------|--------------------|----------------|
| **Session / “tutor”** | One **Orchestrator** per session; stored in `sessions: Dict[str, Orchestrator]` in `app.py`. State (phase, history, agents) lives inside the orchestrator. | Single **TutorService** (singleton via `get_tutor_service()`). No in-memory session dict; context is passed per request. |
| **Flow control** | **Explicit multi-agent routing**: orchestrator chooses phase, then calls the right agent’s `chat()` or `_manager_phase_chat()`. Phase order and labels are in the orchestrator. | **Single tutor + tools**: TutorService uses phase utils (`phase_utils`) and one LLM call with a **tool engine**; the model chooses which tools to call (patient, hint, socratic, mcq, feedback, etc.). |
| **“Agents” vs “tools”** | **Agents**: PatientAgent, TestsAgent, QuizAgent, etc., each with its own prompt and history. Orchestrator does not expose OpenAI-style tools; it invokes agents by phase. | **Tools**: Registry + ToolEngine; JSON configs (`*_tool.json`), `BaseTool` implementations. LLM returns tool calls; TutorService executes them via the engine. |
| **LLM / config** | One **`chat_complete()`** in `utils/llm.py` (OpenAI wrapper). Single **`prompts.py`** and one **`config/config.py`**. | **LLMClient** in `core/llm/`, multiple prompt modules under `prompts/`, shared config (e.g. `config_helper`), optional guidelines cache, cost tracking. |
| **Feedback** | **FeedbackTool** plus JSON file; feedback endpoints in `app.py` write/read that. No retrieval pipeline. | **FeedbackService**, **AutoFeedbackRetriever**, **FeedbackClientAdapter**; TutorService gets a FeedbackClient via the factory and injects feedback into the conversation for tools. |
| **API shape** | **Single module**: all routes defined in **`app.py`** (start_case, chat, feedback, clarify, config, analytics, faiss, db, guidelines). | **Routers**: `chat`, `voice`, `mcq`, `assessment`, `admin` (analytics, monitoring, config), `data` (database, faiss_management), optional `guidelines`. **Lifespan** for startup/shutdown. |
| **Dependency injection** | None. Orchestrator and agents are constructed directly; config and `chat_complete` are used as globals/module imports. | **Factory** builds TutorService with injected tool engine, LLM client, feedback client, project root. |
| **Use case** | Understanding the phase flow, quick iteration, or a minimal deploy without the full stack. | Production: testing, scaling, adding tools, analytics, and consistent feedback retrieval. |

**When to use which**

- Use **src_simplified** when you want to read one app file and one orchestrator to see how phases and agents interact, or to run a minimal version.
- Use **src** when you need the full tool-based tutor, feedback retrieval, modular routes, and a single shared TutorService with no per-session in-memory state.

---

## Major functional differences (not just structural)

These affect what the user can do or how the system behaves, not only how the code is organized.

| Feature | **src_simplified** | **src (main)** |
|--------|--------------------|----------------|
| **Phase set** | **6 phases**: information_gathering → differential_diagnosis → tests_management → **deeper_dive** → **post_case_mcq** → feedback. “Deeper dive” and “Post-case MCQ” are explicit steps with dedicated agents. | **5 phases** (in `TutorState`): initializing → information_gathering → differential_diagnosis → tests_management → feedback. No separate deeper_dive or post_case_mcq phase; MCQ/post_case_assessment are **tools** the LLM can call when appropriate. |
| **Voice (speech)** | **Not implemented.** The frontend calls `/api/v1/voice/chat` (transcribe + tutor response); there is no voice router in `app.py`, so those requests 404. | **Implemented.** Voice router with transcribe (e.g. Whisper) and TTS; `VoiceService` and dedicated routes. |
| **Guidelines** | **Not implemented.** Only `/api/v1/guidelines/health` and `/api/v1/guidelines/sources` (stubs). No `POST /guidelines/fetch`. Frontend fetch returns 404 → “Guidelines feature is under development.” | **Implemented.** `POST /guidelines/fetch` with RAG cache; returns clinical_guidelines, diagnostic_approach, treatment_protocols, recent_evidence. TutorContext can be enriched with pre-fetched guidelines. |
| **Feedback retrieval** | **Save only.** Feedback is written to JSON via `FeedbackTool`; it is **not** retrieved or injected into the conversation. The tutor does not adapt from past feedback. | **Retrieve + inject.** TutorService uses a FeedbackClient (AutoFeedbackRetriever + adapter) to get similar past feedback and appends it to the message/context so the LLM can avoid repeating past mistakes. |
| **“Hint”** | **No dedicated hint.** If the user asks for a hint, the active agent just replies in chat; there is no HintTool or structured hint logic. | **HintTool.** The LLM can call a hint tool to produce a strategic hint based on conversation history. |
| **Differential diagnosis** | **Single manager prompt.** Orchestrator calls `chat_complete()` once with `MANAGER_DIFFERENTIAL_SYSTEM_PROMPT` and recent history (no multi-turn Socratic tool). | **SocraticTool.** Differential phase is mapped to the socratic tool; the model uses it for structured Socratic questioning. |
| **Post-case / MCQ** | **Phase-driven batch.** When the user enters the post_case_mcq phase, `QuizAgent.generate_quiz()` runs once (weakness analysis + MCQ generation); then chat. One batch of MCQs per phase entry. | **Tool-on-demand.** `MCQTool` and `PostCaseAssessmentTool` are available to the LLM; the model (or UI) can request MCQs when appropriate. Separate MCQ routes for generate/submit. |

**Summary:** Simplified has **two extra explicit phases** (deeper_dive, post_case_mcq) and a **phase-driven MCQ batch**, but **no voice backend**, **no guidelines fetch**, **no feedback retrieval**, and **no hint or Socratic tools**—so several features the main app supports are missing or behave differently in simplified.

---

## Quick Start

- **Entry point**: Run the FastAPI app from `V4_refactor` (or adjust paths as needed):
  - `uvicorn src_simplified.app:app --reload`
  - Or ensure `src_simplified` is on `PYTHONPATH` and run `uvicorn src_simplified.app:app`.
- **Config**: Set environment variables (e.g. OpenAI API key, model name) as expected by `config/config.py`.
- **Session behaviour**: Sessions are in-memory; restarting the process clears them. The chat endpoint can recreate a session from `organism_key` and optional `history` if `case_id` is missing.

---

## Summary

- **Flow**: Start case → create Orchestrator → chat requests update history, compute phase, route to an agent (or manager phase), then return response and optional image.
- **Difference from main**: Simplified uses a **per-session Orchestrator** and **explicit agents** with a single `chat_complete()` and no tool engine; main uses a **single TutorService**, **LLM-driven tool calls**, and layered services with dependency injection and centralized feedback.
