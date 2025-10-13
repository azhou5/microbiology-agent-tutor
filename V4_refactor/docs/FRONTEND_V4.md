# MicroTutor V4 Frontend Guide

## Overview

The V4 frontend is a modern, clean implementation that works with the FastAPI backend. It maintains all the features from V3 while providing a better user experience with improved design and architecture.

## Architecture

### File Structure

```
V4_refactor/src/microtutor/api/
├── templates/
│   └── index.html          # Main HTML template
├── static/
│   ├── css/
│   │   └── style.css       # Modern CSS with CSS variables
│   └── js/
│       └── script.js       # Frontend JavaScript (adapted for V4 API)
└── app.py                  # FastAPI app (serves static files + HTML)
```

## Key Features

### ✨ Modern Design

- **CSS Variables**: Easy theming and consistent colors throughout
- **Responsive Layout**: Works on desktop, tablet, and mobile
- **Smooth Animations**: Slide-in effects for messages, hover states
- **Modern Typography**: System font stack for native look and feel
- **Gradient Accents**: Beautiful gradient backgrounds for headers and info sections

### 🎯 User Experience

1. **Organism Selection**: Dropdown with categorized organisms (Bacteria, Viruses, Fungi, Parasites)
2. **Case Management**:
   - Start new cases with unique IDs
   - Persistent state (saved to localStorage)
   - Resume interrupted sessions
3. **Interactive Chat**:
   - Real-time messaging
   - Message history display
   - User/Assistant message differentiation
   - Auto-scroll to latest message
4. **Feedback System**:
   - Per-message feedback (1-4 rating)
   - Optional detailed feedback text
   - Optional replacement text suggestion
   - Case completion feedback modal

### 🔧 Technical Features

- **LocalStorage Persistence**: Conversations survive page refreshes
- **Error Handling**: Graceful error messages and recovery
- **Loading States**: Clear "Processing..." indicators
- **Keyboard Shortcuts**: Enter to send, Shift+Enter for newline
- **Async API Calls**: Non-blocking fetch requests

## API Integration

### Endpoints Used

```javascript
// V4 API Base
const API_BASE = '/api/v1';

// Endpoints
POST ${API_BASE}/start_case    // Start a new case
POST ${API_BASE}/chat          // Send a message
POST ${API_BASE}/feedback      // Submit message feedback
POST ${API_BASE}/case_feedback // Submit case completion feedback
```

### Request/Response Format

**Start Case:**

```json
// Request
{
  "organism": "staphylococcus aureus",
  "case_id": "case_1234567890_xyz",
  "model_name": "o3-mini"
}

// Response
{
  "initial_message": "Welcome to the case...",
  "history": [
    {"role": "system", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "case_id": "case_1234567890_xyz",
  "organism": "staphylococcus aureus"
}
```

**Chat:**

```json
// Request
{
  "message": "What are the patient's symptoms?",
  "history": [...],
  "organism_key": "staphylococcus aureus",
  "case_id": "case_1234567890_xyz"
}

// Response
{
  "response": "The patient presents with...",
  "history": [...],
  "tools_used": [],
  "metadata": {
    "processing_time_ms": 1234.56,
    "case_id": "case_1234567890_xyz",
    "organism": "staphylococcus aureus"
  }
}
```

## Differences from V3

### Backend Changes

| Feature | V3 (Flask) | V4 (FastAPI) |
|---------|-----------|--------------|
| Templates | Jinja2 with Flask | Jinja2 with FastAPI |
| Static Files | Flask static | FastAPI StaticFiles |
| API Prefix | `/` (root) | `/api/v1` |
| Response Format | Plain dict | Pydantic models |
| Error Format | Inconsistent | Standardized ErrorResponse |

### Frontend Changes

| Feature | V3 | V4 |
|---------|----|----|
| CSS | Basic styling | Modern with CSS variables |
| Design | Functional | Modern gradient accents |
| Animations | Minimal | Smooth transitions |
| Responsive | Basic | Full mobile support |
| Error Handling | Basic alerts | Detailed status messages |
| API Calls | Fetch to `/` | Fetch to `/api/v1` |

### Code Quality

- **V3**: ~780 lines of JavaScript with complex logic
- **V4**: ~550 lines with cleaner structure
- **Improvements**:
  - Better separation of concerns
  - Clearer function names
  - More consistent error handling
  - Better comments and documentation

## Running the Application

### Development Mode

```bash
cd V4_refactor
python run_v4.py
```

The app will start on `http://localhost:5001`

### Production Mode

```bash
uvicorn microtutor.api.app:app --host 0.0.0.0 --port 5001 --workers 4
```

## Accessing the Application

- **Frontend**: <http://localhost:5001/>
- **API Docs**: <http://localhost:5001/api/docs>
- **ReDoc**: <http://localhost:5001/api/redoc>
- **Health Check**: <http://localhost:5001/health>

## State Management

The frontend uses localStorage to persist:

1. **Chat History**: Full conversation array
2. **Case ID**: Current case identifier
3. **Organism**: Selected organism

### LocalStorage Keys

```javascript
const STORAGE_KEYS = {
    HISTORY: 'microtutor_v4_chat_history',
    CASE_ID: 'microtutor_v4_case_id',
    ORGANISM: 'microtutor_v4_organism'
};
```

### State Lifecycle

1. **Page Load**: Attempt to restore previous session
2. **Start Case**: Clear old state, generate new case ID
3. **Each Message**: Save updated history
4. **Finish Case**: Clear state, show feedback modal

## Customization

### Changing Colors

Edit CSS variables in `style.css`:

```css
:root {
    --primary-color: #007bff;      /* Main blue */
    --success-color: #28a745;       /* Green buttons */
    --warning-color: #ff9800;       /* Orange finish button */
    --background: #f4f7f9;          /* Page background */
    /* ... more variables ... */
}
```

### Adding Organisms

Update the select dropdown in `index.html`:

```html
<optgroup label="Your Category">
    <option value="organism-name">Organism Display Name</option>
</optgroup>
```

### Modifying Chat Behavior

Edit functions in `script.js`:

- `handleStartCase()` - Case initialization
- `handleSendMessage()` - Message sending
- `addMessage()` - Message display
- `createFeedbackUI()` - Feedback interface

## Browser Support

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

Modern features used:

- CSS Variables
- Fetch API
- localStorage
- ES6+ JavaScript
- CSS Grid & Flexbox

## Troubleshooting

### Frontend Not Loading

**Issue**: Blank page or 404 errors

**Solution**:

- Check that static files are in correct location
- Verify FastAPI is mounting static files:

  ```python
  app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
  ```

### API Calls Failing

**Issue**: "Failed to start case" or network errors

**Solution**:

- Check API is running on correct port
- Verify endpoint paths match (should be `/api/v1/...`)
- Check browser console for detailed errors
- Review FastAPI logs

### State Not Persisting

**Issue**: Conversations lost on refresh

**Solution**:

- Check browser localStorage is enabled
- Clear localStorage if corrupted: `localStorage.clear()`
- Check browser console for storage errors

### Styling Issues

**Issue**: CSS not loading or looks wrong

**Solution**:

- Hard refresh browser (Cmd+Shift+R / Ctrl+Shift+R)
- Check static files path in browser dev tools
- Verify CSS file exists at expected location
- Check for CSS syntax errors

## Future Enhancements

Potential improvements for V4 frontend:

1. **WebSocket Support**: Real-time streaming responses
2. **Markdown Rendering**: Rich text formatting for responses
3. **Code Highlighting**: Syntax highlighting for medical terminology
4. **Export Conversation**: Download chat history as PDF
5. **Dark Mode**: Toggle between light/dark themes
6. **Accessibility**: ARIA labels, keyboard navigation
7. **PWA Support**: Offline capability, install as app
8. **Multi-language**: i18n support

## Contributing

When modifying the frontend:

1. Test in multiple browsers
2. Verify mobile responsiveness
3. Check console for errors
4. Update this documentation
5. Follow existing code style

## Questions?

- Check FastAPI logs for backend issues
- Check browser console for frontend issues
- Review API docs at `/api/docs`
- See V3_TO_V4_MAPPING_GUIDE.md for migration details
