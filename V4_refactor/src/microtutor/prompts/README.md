# Prompts Layer

LLM prompt templates for different agents and use cases. Centralized prompt management for consistency and easy updates.

## Structure

```
prompts/
├── tutor_prompt.py                    # Main tutor system prompts
├── patient_prompts.py                 # Patient simulation prompts
├── socratic_prompts.py               # Socratic questioning prompts
├── hint_prompts.py                   # Hint generation prompts
├── tests_management_prompts.py       # Test selection prompts (simplified)
├── final_feedback_agent_prompts.py   # Feedback agent prompts
└── post_case_assessment_prompts.py   # NEW: MCQ generation prompts
```

## Files

### `tutor_prompt.py`

**Purpose**: Main tutor system prompts  
**Necessary**: ✅ Yes - Core tutoring prompts  
**Could be more concrete**: ✅ Well-organized

- `get_system_message_template()` - Main system prompt
- `get_first_pt_sentence_generation_system_prompt()` - Case initialization
- Defines tutor behavior and capabilities
- Includes tool descriptions

### `patient_prompts.py`

**Purpose**: Patient simulation prompts  
**Necessary**: ✅ Yes - Patient tool prompts  
**Could be more concrete**: ✅ Good separation

- Patient response generation
- Realistic patient behavior
- Context-aware responses

### `socratic_prompts.py`

**Purpose**: Socratic questioning prompts  
**Necessary**: ✅ Yes - Teaching methodology  
**Could be more concrete**: ✅ Well-contained

- Question generation
- Guidance without direct answers
- Progressive difficulty

### `hint_prompts.py`

**Purpose**: Hint generation prompts  
**Necessary**: ✅ Yes - Learning support  
**Could be more concrete**: ✅ Good structure

- Progressive hint system
- Encourages discovery
- Avoids spoilers

### `tests_management_prompts.py`

**Purpose**: Test selection and management prompts  
**Necessary**: ✅ Yes - Clinical decision-making  
**Could be more concrete**: ✅ Recently simplified (removed MCQ sections)

- Diagnostic test selection
- Management planning
- Clinical reasoning
- **Note**: MCQ-related prompts moved to `post_case_assessment_prompts.py`

### `final_feedback_agent_prompts.py`

**Purpose**: Prompts for the feedback agent (LLM that gives feedback to students)  
**Necessary**: ✅ Yes - Used by FeedbackTool  
**Could be more concrete**: ✅ Well-named

- `get_feedback_system_prompt()` - System prompt for the feedback agent
- Defines HOW the feedback agent behaves
- Separate from `tutor_prompt.py` which defines WHEN to call tools

### `post_case_assessment_prompts.py` (NEW)

**Purpose**: Prompts for post-case MCQ generation  
**Necessary**: ✅ Yes - Used by PostCaseAssessmentTool  
**Could be more concrete**: ✅ Well-structured

- `get_post_case_assessment_system_prompt()` - MCQ generation prompt
- `get_weakness_analysis_prompt()` - Analyze conversation for weak areas
- Generates structured JSON output for MCQs
- Each MCQ includes explanations for all options

## Prompt Management Best Practices

1. ✅ **Centralized**: All prompts in one place
2. ✅ **Template-based**: Use format strings for dynamic content
3. ✅ **Version control**: Easy to track changes
4. ✅ **Clear naming**: Files clearly indicate their purpose

## Recommendations

1. ✅ **Well-organized**: Clear separation by agent
2. ✅ **Clear naming**: `final_feedback_agent_prompts.py` and `post_case_assessment_prompts.py` clearly indicate purpose
3. ✅ **Template pattern**: Good use of format strings
4. ⚠️ **Consider**: Add prompt versioning for experimentation
