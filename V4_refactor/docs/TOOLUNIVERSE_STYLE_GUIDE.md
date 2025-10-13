# 🛠️ MicroTutor ToolUniverse-Style Tool System

## 📚 Complete Guide to Our New Tool Architecture

This document explains how V4's refactored tool system works, following ToolUniverse best practices.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     MicroTutor V4                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │          config/tools/*.json                       │     │
│  │  • Tool schemas (WHAT tools do)                    │     │
│  │  • Parameter definitions                           │     │
│  │  • Metadata                                        │     │
│  └────────────────────────────────────────────────────┘     │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │     src/microtutor/tools/                          │     │
│  │  • registry.py - Tool discovery & loading          │     │
│  │  • engine.py - Execution engine                    │     │
│  │  • patient.py, socratic.py, hint.py - Tools       │     │
│  │  • prompts.py - Centralized prompts                │     │
│  └────────────────────────────────────────────────────┘     │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │     src/microtutor/models/                         │     │
│  │  • tool_models.py - BaseTool, AgenticTool         │     │
│  │  • tool_errors.py - Structured exceptions          │     │
│  └────────────────────────────────────────────────────┘     │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │     core/tutor_prompts_tools.py                    │     │
│  │  • Tutor orchestration prompts                     │     │
│  │  • WHEN to call tools (routing logic)             │     │
│  └────────────────────────────────────────────────────┘     │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │     services/tutor_service.py                      │     │
│  │  • Business logic                                  │     │
│  │  • Uses tool engine to execute tools              │     │
│  └────────────────────────────────────────────────────┘     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 File Organization

### **`config/tools/*.json`** - Tool Configurations

**Purpose**: Define WHAT tools exist and their schemas  
**When to edit**: Adding new tools, changing parameters  
**Keep here**: ✅ Yes, it's configuration data

```json
{
  "name": "patient",
  "description": "The PATIENT tool: use when...",
  "type": "PatientTool",
  "parameter": {
    "type": "object",
    "properties": {
      "input_text": {"type": "string"},
      "case": {"type": "string"}
    }
  }
}
```

### **`src/microtutor/tools/`** - Tool Implementations

**Purpose**: Define HOW tools execute  
**When to edit**: Changing tool behavior, adding logic

- `registry.py` - Discovers and loads tools
- `engine.py` - Main execution interface
- `patient.py`, `socratic.py`, `hint.py` - Tool implementations
- `prompts.py` - Tool-level prompts (HOW each tool behaves)

### **`src/microtutor/models/`** - Tool Models

**Purpose**: Define tool structure/interface  
**When to edit**: Changing tool architecture

- `tool_models.py` - `BaseTool`, `AgenticTool` classes
- `tool_errors.py` - Exception types

### **`core/tutor_prompts_tools.py`** - Tutor Orchestration

**Purpose**: Define WHEN to call tools  
**When to edit**: Changing tutor routing logic

Contains prompts that tell the main tutor agent:

- When to route to patient
- When to route to socratic
- When to route to hint

---

## 🎯 Two Tool-Calling Patterns

### **Pattern 1: Prompt-Based (Current V3 Style)**

**How it works:**

1. Tutor LLM sees tool descriptions in system prompt
2. LLM generates text like `[Action]: {"patient": "question"}`
3. We parse with regex
4. Execute via tool engine

**Code:**

```python
# In tutor_prompts_tools.py
def get_tool_descriptions_for_prompt():
    """Get tool descriptions from tool engine for system prompt."""
    from microtutor.tools import get_tool_engine
    
    engine = get_tool_engine()
    tools = engine.list_tools()
    
    descriptions = []
    for tool_name in tools:
        tool_instance = engine.registry.get_tool_instance(tool_name)
        if tool_instance:
            descriptions.append(f"- {tool_name}: {tool_instance.description}")
    
    return "\n".join(descriptions)

# In tutor loop
system_message = f"""
You are a medical tutor. Available tools:
{get_tool_descriptions_for_prompt()}

When calling a tool, use: [Action]: {{"tool_name": "input"}}
"""

# Parse LLM response
if "[Action]:" in llm_response:
    tool_call = parse_action(llm_response)  # {"patient": "..."}
    
    # Execute with tool engine
    from microtutor.tools import get_tool_engine
    engine = get_tool_engine()
    
    result = engine.execute_tool(
        tool_name='patient',
        arguments={
            'input_text': tool_call['patient'],
            'case': case_description,
            'conversation_history': history,
            'model': model_name
        }
    )
    
    if result['success']:
        return result['result']
    else:
        # Handle error
        error = result['error']
        logger.error(f"Tool failed: {error['message']}")
```

**Pros:**

- ✅ Works with any LLM
- ✅ No special LLM features required
- ✅ Backward compatible with V3

**Cons:**

- ❌ Requires regex parsing
- ❌ No automatic validation (we add it with tool engine)
- ❌ More fragile

### **Pattern 2: Native Function Calling (New Capability)**

**How it works:**

1. Get OpenAI-compatible schemas from tool engine
2. LLM natively calls functions
3. Execute via tool engine

**Code:**

```python
from microtutor.tools import get_tool_engine
import openai

engine = get_tool_engine()

# Get OpenAI-compatible schemas
tool_schemas = engine.get_tool_schemas()
# Returns: [{"type": "function", "function": {"name": "patient", ...}}, ...]

# Call LLM with native function calling
response = openai.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=tool_schemas  # ← Magic happens here
)

# Execute tool calls
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        result = engine.execute_tool(
            tool_name=tool_call.function.name,
            arguments=json.loads(tool_call.function.arguments)
        )
        
        if result['success']:
            # Add to conversation
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result['result'])
            })
```

**Pros:**

- ✅ Native LLM integration
- ✅ Automatic validation
- ✅ Structured, reliable
- ✅ No parsing needed

**Cons:**

- ❌ Requires LLM with function calling
- ❌ Not all models support it

---

## 🔄 Migration Strategy

### **Phase 1: Keep V3 Pattern, Use New Engine (Current)**

```python
# tutor_service.py
from microtutor.tools import get_tool_engine

class TutorService:
    def __init__(self):
        self.tool_engine = get_tool_engine()
    
    def process_message(self, message, context):
        # Old: Parse tool calls from LLM text
        if "[Action]:" in llm_response:
            tool_call = self._parse_action(llm_response)
            
            # New: Execute via tool engine
            result = self.tool_engine.execute_tool(
                tool_name=list(tool_call.keys())[0],
                arguments={
                    'input_text': list(tool_call.values())[0],
                    'case': context.case_description,
                    'conversation_history': context.history,
                    'model': context.model_name
                }
            )
            
            # Get automatic validation, error handling, caching
            if result['success']:
                return result['result']
            else:
                # Structured error information
                error = result['error']
                self._handle_tool_error(error)
```

### **Phase 2: Support Both Patterns**

```python
class TutorService:
    def __init__(self, use_native_function_calling=False):
        self.tool_engine = get_tool_engine()
        self.use_native_fc = use_native_function_calling
    
    def process_message(self, message, context):
        if self.use_native_fc:
            # Pattern 2: Native function calling
            return self._process_with_native_fc(message, context)
        else:
            # Pattern 1: Prompt-based
            return self._process_with_prompt_based(message, context)
```

### **Phase 3: Migrate to Native (Future)**

Once comfortable, switch default to native function calling for:

- Better reliability
- Automatic validation
- Cleaner code

---

## 🎓 Usage Examples

### **Example 1: Basic Tool Execution**

```python
from microtutor.tools import get_tool_engine

# Initialize engine (loads all tools from config/tools/)
engine = get_tool_engine()

# Method 1: Direct execution
result = engine.execute_tool('patient', {
    'input_text': "How long have you had this fever?",
    'case': case_description,
    'conversation_history': [],
    'model': 'gpt-4'
})

if result['success']:
    print(f"Patient says: {result['result']}")
    print(f"Took: {result['execution_time_ms']}ms")
else:
    print(f"Error: {result['error']['message']}")
```

### **Example 2: Direct Tool Access (ToolUniverse.tools style)**

```python
engine = get_tool_engine()

# Call tools like functions!
try:
    patient_response = engine.tools.patient(
        input_text="What symptoms do you have?",
        case=case_description,
        conversation_history=[],
        model='gpt-4'
    )
    print(patient_response)
except RuntimeError as e:
    print(f"Tool error: {e}")
```

### **Example 3: Legacy Function Wrappers**

```python
# For backward compatibility with V3
from microtutor.tools import run_patient, run_socratic, run_hint

# Works exactly like V3!
response = run_patient(
    "How long?",
    case_description,
    conversation_history=[],
    model='gpt-4'
)
```

### **Example 4: List Available Tools**

```python
engine = get_tool_engine()

# List all tools
tools = engine.list_tools()
print(f"Available tools: {tools}")
# Output: ['patient', 'socratic', 'hint']

# Get tool schemas for LLM
schemas = engine.get_tool_schemas()
for schema in schemas:
    print(f"Tool: {schema['function']['name']}")
    print(f"Description: {schema['function']['description']}")
```

### **Example 5: Error Handling**

```python
result = engine.execute_tool('patient', {
    'input_text': "question",
    # Missing 'case' - will fail validation
})

if not result['success']:
    error = result['error']
    
    if error['error_type'] == 'ToolValidationError':
        print("Invalid parameters!")
        print(f"Details: {error['details']}")
    elif error['error_type'] == 'ToolLLMError':
        print("LLM call failed!")
    else:
        print(f"Unknown error: {error['message']}")
```

---

## 🆕 Adding a New Tool

### **Step 1: Create JSON Config**

`config/tools/diagnosis_tool.json`:

```json
{
  "name": "diagnosis",
  "description": "The DIAGNOSIS tool: use when student proposes final diagnosis",
  "type": "DiagnosisTool",
  "category": "educational_agents",
  "cacheable": false,
  "parameter": {
    "type": "object",
    "properties": {
      "proposed_diagnosis": {
        "type": "string",
        "description": "The diagnosis proposed by the student"
      },
      "case": {
        "type": "string",
        "description": "The case description"
      },
      "reasoning": {
        "type": "string",
        "description": "Student's reasoning for the diagnosis"
      }
    },
    "required": ["proposed_diagnosis", "case", "reasoning"]
  },
  "llm_config": {
    "max_new_tokens": 600,
    "temperature": 0.7
  }
}
```

### **Step 2: Add Prompt to `tools/prompts.py`**

```python
def get_diagnosis_system_prompt() -> str:
    """System prompt for diagnosis evaluation tool."""
    return """You are a medical educator evaluating a student's diagnosis.

Your role:
1. Assess if the diagnosis is correct
2. Evaluate the reasoning provided
3. Provide constructive feedback
4. Highlight what was done well
5. Point out gaps in reasoning

DO NOT simply say right or wrong - explain WHY."""

def get_diagnosis_user_prompt(proposed_diagnosis: str, case: str, reasoning: str) -> str:
    """User prompt for diagnosis evaluation."""
    return f"""Case: {case}

Student's proposed diagnosis: {proposed_diagnosis}

Student's reasoning: {reasoning}

Evaluate this diagnosis and reasoning:"""
```

### **Step 3: Create Tool Implementation**

`src/microtutor/tools/diagnosis.py`:

```python
from typing import Dict, Any
import logging

from microtutor.models.tool_models import AgenticTool
from microtutor.models.tool_errors import ToolLLMError
from microtutor.core.llm_router import chat_complete
from microtutor.tools.prompts import (
    get_diagnosis_system_prompt,
    get_diagnosis_user_prompt
)

logger = logging.getLogger(__name__)


class DiagnosisTool(AgenticTool):
    """Diagnosis evaluation tool."""
    
    def __init__(self, tool_config: Dict[str, Any]):
        super().__init__(tool_config)
        logger.info(f"Initialized {self.name}")
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        try:
            max_tokens = kwargs.get('max_new_tokens', self.llm_config.get('max_new_tokens', 600))
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            
            system_prompt = get_diagnosis_system_prompt()
            
            proposed_diagnosis = kwargs.get('proposed_diagnosis', '')
            case = kwargs.get('case', '')
            reasoning = kwargs.get('reasoning', '')
            
            user_prompt = get_diagnosis_user_prompt(
                proposed_diagnosis, case, reasoning
            )
            
            response = chat_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                max_new_tokens=max_tokens
            )
            
            if not response or not response.strip():
                raise ToolLLMError(
                    "LLM returned empty response",
                    tool_name=self.name
                )
            
            return response
            
        except Exception as e:
            logger.error(f"LLM call failed in {self.name}: {e}")
            raise ToolLLMError(
                f"Failed to evaluate diagnosis: {e}",
                tool_name=self.name
            )
    
    def _execute(self, arguments: Dict[str, Any]) -> str:
        proposed_diagnosis = arguments.get('proposed_diagnosis', '')
        case = arguments.get('case', '')
        reasoning = arguments.get('reasoning', '')
        model = arguments.get('model', 'gpt-4')
        
        logger.info(f"Diagnosis tool evaluating: {proposed_diagnosis}")
        
        response = self._call_llm(
            prompt="",
            proposed_diagnosis=proposed_diagnosis,
            case=case,
            reasoning=reasoning,
            model=model
        )
        
        return response.strip()
```

### **Step 4: Register in Engine**

Update `tools/engine.py`:

```python
def _register_tool_classes(self) -> None:
    """Register all available tool classes."""
    try:
        from microtutor.tools.patient import PatientTool
        from microtutor.tools.socratic import SocraticTool
        from microtutor.tools.hint import HintTool
        from microtutor.tools.diagnosis import DiagnosisTool  # ← Add this
        
        register_tool_class("PatientTool", PatientTool)
        register_tool_class("SocraticTool", SocraticTool)
        register_tool_class("HintTool", HintTool)
        register_tool_class("DiagnosisTool", DiagnosisTool)  # ← Add this
        
        logger.info("Registered 4 tool classes")  # ← Update count
        
    except ImportError as e:
        logger.error(f"Failed to import tool classes: {e}")
```

### **Step 5: Update Tutor Prompts**

In `core/tutor_prompts_tools.py`, add routing rule:

```python
def get_diagnosis_tool_rule():
    """Get the diagnosis tool rule for the system prompt."""
    return """
    d) When the student proposes a FINAL DIAGNOSIS, use the DIAGNOSIS tool.
    Example: "[User Input]: I believe the final diagnosis is tuberculosis because..." 
    -> [Action]: {"diagnosis": "tuberculosis", "reasoning": "because..."}
    """
```

### **Step 6: Test It**

```python
from microtutor.tools import get_tool_engine

engine = get_tool_engine()

result = engine.execute_tool('diagnosis', {
    'proposed_diagnosis': 'Tuberculosis',
    'case': case_description,
    'reasoning': 'Patient has chronic cough, night sweats, weight loss...'
})

print(result['result'])
```

**Done!** The tool is now available throughout MicroTutor.

---

## 🎯 Best Practices

### **DO:**

- ✅ Keep tool configs in `config/tools/`
- ✅ Keep tool prompts in `tools/prompts.py`
- ✅ Keep orchestration prompts in `core/tutor_prompts_tools.py`
- ✅ Use structured error handling
- ✅ Validate parameters automatically
- ✅ Log tool executions
- ✅ Test tools in isolation

### **DON'T:**

- ❌ Mix configuration with code
- ❌ Hardcode prompts in tool classes
- ❌ Skip parameter validation
- ❌ Ignore error handling
- ❌ Duplicate tool logic

---

## 📊 Comparison: Old vs New

| Aspect | V3 (Old) | V4 ToolUniverse-Style (New) |
|--------|----------|----------------------------|
| **Tool Definition** | Python functions | JSON configs + Python classes |
| **Tool Discovery** | Hardcoded dict | Dynamic loading from config |
| **Parameter Validation** | None | Automatic (jsonschema) |
| **Error Handling** | Try-catch | Structured ToolError classes |
| **Caching** | None | Built-in (optional) |
| **Prompts** | Mixed in functions | Centralized in prompts.py |
| **Extensibility** | Edit 3+ files | Add 1 JSON + 1 Python file |
| **Testing** | Hard | Easy (isolated) |
| **Native Function Calling** | No | Yes (optional) |

---

## 🚀 Summary

**We now have:**

1. ✅ **ToolUniverse-style architecture** - Proven patterns
2. ✅ **Backward compatibility** - V3 code still works
3. ✅ **Two calling patterns** - Prompt-based + Native FC
4. ✅ **Structured errors** - Better debugging
5. ✅ **Automatic validation** - Fewer bugs
6. ✅ **Centralized prompts** - Easier maintenance
7. ✅ **Easy extensibility** - Add tools quickly
8. ✅ **Professional foundation** - Ready for scale

**Next steps:**

- Update `tutor_service.py` to use tool engine
- Add tests for new tool system
- Consider migrating to native function calling
- Add more tools (diagnosis, treatment, etc.)
