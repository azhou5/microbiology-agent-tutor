# Tools Layer

Agentic tools that provide specialized functionality (patient simulation, socratic questioning, hints, etc.). Follows ToolUniverse patterns.

## Architecture

```
Tools are called by TutorService when LLM decides to use them.
Feedback is passed via conversation history (not retrieved by tools directly).

During Case:
  patient → socratic → hint → tests_management → feedback

After Case:
  post_case_assessment → targeted MCQs based on weak areas
```

## Structure

```
tools/
├── __init__.py              # Package exports
├── engine.py                # Tool execution engine
├── registry.py              # Tool registration and discovery
├── patient/                 # Patient simulation tool
├── socratic/                # Socratic questioning tool
├── hint/                    # Hint generation tool
├── tests_management/        # Test selection and management (simplified)
├── feedback/                # Feedback tool
├── post_case_assessment/    # NEW: Targeted MCQ generation after case
└── mcq/                     # Legacy MCQ tool (prefer post_case_assessment)
```

## Files

### `engine.py`

**Purpose**: Main tool execution engine  
**Necessary**: ✅ Yes - Core tool infrastructure  
**Could be more concrete**: ✅ Well-designed

- `MicroTutorToolEngine` - Main engine class
- `get_tool_engine()` - Singleton access
- Executes tools based on name
- Returns tool schemas for LLM

### `registry.py`

**Purpose**: Tool registration and discovery  
**Necessary**: ✅ Yes - Dynamic tool loading  
**Could be more concrete**: ✅ Good abstraction

- `ToolRegistry` - Registry class
- Loads tools from JSON configs
- Supports dynamic tool registration

### `patient/patient.py`

**Purpose**: Simulates patient responses  
**Necessary**: ✅ Yes - Core tutoring feature  
**Could be more concrete**: ✅ Well-contained

- `PatientTool` - Patient simulation agent
- Responds as patient would
- Uses conversation history (includes feedback from TutorService)

### `socratic/socratic.py`

**Purpose**: Socratic questioning tool  
**Necessary**: ✅ Yes - Teaching methodology  
**Could be more concrete**: ✅ Good separation

- `SocraticTool` - Socratic questioning agent
- Guides student through questions
- Encourages critical thinking

### `hint/hint.py`

**Purpose**: Hint generation tool  
**Necessary**: ✅ Yes - Learning support  
**Could be more concrete**: ✅ Well-contained

- `HintTool` - Hint generation agent
- Provides progressive hints
- Avoids giving direct answers

### `tests_management/tests_management.py`

**Purpose**: Test selection and management guidance  
**Necessary**: ✅ Yes - Clinical decision-making  
**Could be more concrete**: ✅ Recently simplified (was 521 lines, now ~170)

- `TestsManagementTool` - Test selection agent
- Helps students choose appropriate diagnostic tests
- Management plan development
- Receives guidelines from database (via context)
- **Note**: MCQ generation moved to `post_case_assessment`

### `feedback/feedback.py`

**Purpose**: Comprehensive feedback tool  
**Necessary**: ✅ Yes - Feedback delivery  
**Could be more concrete**: ✅ Good structure

- `FeedbackTool` - Feedback agent
- Provides detailed feedback on performance

### `post_case_assessment/post_case_assessment.py` (NEW)

**Purpose**: Generates targeted MCQs after case completion  
**Necessary**: ✅ Yes - Post-case assessment  
**Could be more concrete**: ✅ Well-structured

- `PostCaseAssessmentTool` - MCQ generation agent
- Analyzes conversation to find weak areas
- Generates MCQs targeting those weaknesses
- Returns structured data for interactive display

**Key Features**:

- Called AFTER case is complete (not during conversation)
- Analyzes full conversation for weaknesses
- Generates 5 (configurable) targeted MCQs
- Each MCQ includes explanations for ALL options
- Interactive: answers hidden until clicked

**Output Structure**:

```json
{
    "mcqs": [
        {
            "question_id": "uuid",
            "question_text": "...",
            "topic": "antimicrobial selection",
            "weakness_addressed": "Student struggled with...",
            "options": [
                {"letter": "A", "text": "...", "is_correct": false, "explanation": "Why wrong..."},
                {"letter": "B", "text": "...", "is_correct": true, "explanation": "Why correct..."},
                ...
            ],
            "correct_answer": "B",
            "learning_point": "Key takeaway..."
        }
    ],
    "summary": {
        "weak_areas_covered": ["topic1", "topic2"],
        "total_questions": 5
    }
}
```

### `mcq/mcq_tool.py` (Legacy)

**Purpose**: Legacy MCQ generation  
**Necessary**: ⚠️ Deprecated - Use `post_case_assessment` instead  
**Status**: Kept for backward compatibility

## Tool Execution Flow

### During Case

```
1. User sends message
2. TutorService retrieves feedback (once)
3. TutorService appends feedback to conversation history
4. TutorService calls LLM with tools available
5. LLM decides which tool(s) to call
6. TutorService executes tool(s) via ToolEngine
7. Tool receives conversation history (with feedback)
8. Tool generates response
9. Response returned to user
```

### After Case (Post-Case Assessment)

```
1. Case is complete (feedback phase done)
2. User clicks "Generate Assessment" or similar
3. PostCaseAssessmentTool called with full conversation
4. Tool analyzes conversation for weak areas
5. Tool generates targeted MCQs
6. MCQs returned for interactive display
7. User answers MCQs, sees explanations on click
```

## Important Notes

⚠️ **Tools do NOT retrieve feedback directly** - They receive it via conversation history from TutorService.

✅ **Feedback is retrieved once** at TutorService level and passed to all tools.

✅ **MCQs are now post-case** - Not generated during conversation, but after case completion.

## Recommendations

1. ✅ **Well-architected**: Clear separation of concerns
2. ✅ **Simplified tests_management**: Removed MCQ and ToolUniverse code
3. ✅ **New post_case_assessment**: Proper separation of assessment from tutoring
4. ✅ **ToolUniverse pattern**: Good use of established patterns
