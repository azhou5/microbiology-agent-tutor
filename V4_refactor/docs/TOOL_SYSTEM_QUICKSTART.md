# 🚀 Tool System Quick Start

## Get Started in 5 Minutes

### 1. **Basic Usage**

```python
from microtutor.tools import get_tool_engine

# Initialize (auto-loads tools from config/tools/)
engine = get_tool_engine()

# See what's available
print(engine.list_tools())  # ['patient', 'socratic', 'hint']

# Execute a tool
result = engine.execute_tool('patient', {
    'input_text': "How long have you had this cough?",
    'case': "45yo male with 3 week cough...",
    'conversation_history': [],
    'model': 'gpt-4'
})

if result['success']:
    print(result['result'])
else:
    print(f"Error: {result['error']['message']}")
```

### 2. **Direct Tool Access (Cleaner)**

```python
# Call tools like Python functions
engine = get_tool_engine()

response = engine.tools.patient(
    input_text="What symptoms do you have?",
    case=case_description
)

print(response)
```

### 3. **Legacy V3 Compatibility**

```python
# Old V3 code still works!
from microtutor.tools import run_patient

response = run_patient(
    "How long?",
    case_description
)
```

---

## 📂 File Structure

```
V4_refactor/
├── config/tools/           ← Tool schemas (JSON)
│   ├── patient_tool.json
│   ├── socratic_tool.json
│   └── hint_tool.json
│
├── src/microtutor/
│   ├── models/             ← Tool base classes
│   │   ├── tool_models.py      (BaseTool, AgenticTool)
│   │   └── tool_errors.py      (Error types)
│   │
│   ├── tools/              ← Tool implementations
│   │   ├── __init__.py         (Main exports)
│   │   ├── engine.py           (Execution engine)
│   │   ├── registry.py         (Discovery & loading)
│   │   ├── prompts.py          (Centralized prompts)
│   │   ├── patient.py          (Patient tool)
│   │   ├── socratic.py         (Socratic tool)
│   │   └── hint.py             (Hint tool)
│   │
│   └── core/
│       └── tutor_prompts_tools.py  (Tutor orchestration)
```

---

## 🎯 Two Calling Patterns

### **Pattern 1: Prompt-Based (Current)**

```python
# Tutor LLM generates text like:
# "[Action]: {"patient": "How long?"}"

# We parse and execute:
if "[Action]:" in llm_response:
    tool_call = parse_action(llm_response)
    result = engine.execute_tool('patient', {
        'input_text': tool_call['patient'],
        'case': case
    })
```

### **Pattern 2: Native Function Calling (New)**

```python
# Get OpenAI-compatible schemas
schemas = engine.get_tool_schemas()

# LLM natively calls functions
response = openai.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=schemas  # ← Magic!
)

# Execute tool calls
for tool_call in response.choices[0].message.tool_calls:
    result = engine.execute_tool(
        tool_call.function.name,
        json.loads(tool_call.function.arguments)
    )
```

---

## ➕ Add a New Tool (5 Steps)

### **1. Create JSON Config** (`config/tools/my_tool.json`)

```json
{
  "name": "my_tool",
  "description": "What this tool does",
  "type": "MyTool",
  "parameter": {
    "type": "object",
    "properties": {
      "input": {"type": "string"}
    },
    "required": ["input"]
  }
}
```

### **2. Add Prompts** (`src/microtutor/tools/prompts.py`)

```python
def get_my_tool_system_prompt() -> str:
    return "System prompt here..."

def get_my_tool_user_prompt(input: str) -> str:
    return f"User prompt: {input}"
```

### **3. Implement Tool** (`src/microtutor/tools/my_tool.py`)

```python
from microtutor.models.tool_models import AgenticTool
from microtutor.core.llm_router import chat_complete
from microtutor.tools.prompts import get_my_tool_system_prompt

class MyTool(AgenticTool):
    def _call_llm(self, prompt: str, **kwargs) -> str:
        return chat_complete(
            system_prompt=get_my_tool_system_prompt(),
            user_prompt=kwargs.get('input', ''),
            model=kwargs.get('model', 'gpt-4')
        )
    
    def _execute(self, arguments):
        return self._call_llm("", **arguments)
```

### **4. Register** (update `tools/engine.py`)

```python
from microtutor.tools.my_tool import MyTool
register_tool_class("MyTool", MyTool)
```

### **5. Use It!**

```python
engine = get_tool_engine()
result = engine.tools.my_tool(input="test")
```

---

## 🔧 Key Features

### ✅ **Automatic Validation**

```python
# JSON schema validation happens automatically
result = engine.execute_tool('patient', {
    'input_text': 123  # Wrong type!
})
# Returns: ToolValidationError
```

### ✅ **Structured Errors**

```python
if not result['success']:
    error = result['error']
    print(error['error_type'])  # ToolValidationError, ToolLLMError, etc.
    print(error['message'])
    print(error['details'])
```

### ✅ **Caching** (optional)

```python
# Set cacheable: true in JSON config
result1 = engine.tools.patient(input="test")  # Calls LLM
result2 = engine.tools.patient(input="test")  # Cached! (instant)
```

### ✅ **Execution Metrics**

```python
result = engine.execute_tool('patient', {...})
print(result['execution_time_ms'])  # How long it took
print(result['cached'])              # Was it cached?
```

---

## 📖 Full Documentation

- **[TOOLUNIVERSE_STYLE_GUIDE.md](TOOLUNIVERSE_STYLE_GUIDE.md)** - Complete architecture guide
- **[TOOLUNIVERSE_ARCHITECTURE_GUIDE.md](../../TOOLUNIVERSE_ARCHITECTURE_GUIDE.md)** - ToolUniverse comparison
- **[examples/tool_system_demo.py](../examples/tool_system_demo.py)** - Runnable examples

---

## 🎓 Examples

Run the demo:

```bash
cd V4_refactor
python examples/tool_system_demo.py
```

Covers:

- Basic tool execution
- Direct tool access
- Legacy functions
- Both calling patterns
- Error handling
- Tool metadata

---

## 💡 Tips

1. **Tool configs** (`config/tools/*.json`) = WHAT tools do
2. **Tool prompts** (`tools/prompts.py`) = HOW they behave
3. **Tutor prompts** (`core/tutor_prompts_tools.py`) = WHEN to call them

4. **Pattern 1** (Prompt-based) = Works with any LLM
5. **Pattern 2** (Native) = Requires function calling support

6. Use `run_patient()` etc. for V3 compatibility
7. Use `engine.tools.patient()` for cleaner code
8. Use `engine.execute_tool()` for full control

---

**Questions?** Check the full guide: [TOOLUNIVERSE_STYLE_GUIDE.md](TOOLUNIVERSE_STYLE_GUIDE.md)
