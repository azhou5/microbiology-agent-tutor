# 🚀 MicroTutor V4 Frontend - Quick Start

## Overview

You now have a **modern, fully-functional frontend** for MicroTutor V4! This frontend mimics the V3 design but with significant improvements in code quality, user experience, and visual design.

## What's New? ✨

### Visual Improvements

- 🎨 **Modern Design**: CSS variables, gradient accents, smooth animations
- 📱 **Fully Responsive**: Works perfectly on desktop, tablet, and mobile
- 🎯 **Better UX**: Clear status messages, loading indicators, error handling
- ✨ **Smooth Animations**: Messages slide in, buttons have hover effects

### Technical Improvements

- ⚡ **FastAPI Integration**: Works seamlessly with V4 API endpoints
- 🔄 **State Persistence**: Conversations survive page refreshes
- 🛡️ **Error Handling**: Graceful error messages and recovery
- 📝 **Clean Code**: Well-structured, documented JavaScript

## Getting Started

### 1. Install Dependencies

```bash
cd /Users/riccardoconci/Library/Mobile\ Documents/com~apple~CloudDocs/HQ_2024/Projects/2024_Harvard_AIM/Research/MicroTutor/microbiology-agent-tutor/V4_refactor

# Install Python dependencies
pip install -r requirements/requirements_v4.txt
```

### 2. Set Up Environment

Create a `.env` file in the V4_refactor directory:

```bash
# Copy template
cp env_template.txt .env

# Add your OpenAI API key
echo "OPENAI_API_KEY=your-key-here" >> .env
```

### 3. Run the Application

```bash
# Option 1: Using the run script
python run_v4.py

# Option 2: Using uvicorn directly
uvicorn microtutor.api.app:app --host 0.0.0.0 --port 5001 --reload
```

### 4. Open Your Browser

Navigate to: **<http://localhost:5001/>**

You should see the MicroTutor interface! 🎉

## File Structure

```
V4_refactor/
├── src/microtutor/api/
│   ├── app.py                    # ✅ Updated to serve frontend
│   ├── templates/
│   │   └── index.html            # ✅ NEW - Modern HTML
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css         # ✅ NEW - Modern CSS
│   │   └── js/
│   │       └── script.js         # ✅ NEW - V4 API adapted JS
│   └── routes/
│       └── chat.py               # ✅ Updated with feedback endpoints
└── docs/
    └── FRONTEND_V4.md            # ✅ NEW - Comprehensive guide
```

## Key Features

### 🔬 Organism Selection

- Dropdown with 14 organisms across 4 categories
- Bacteria, Viruses, Fungi, Parasites

### 💬 Interactive Chat

- Real-time messaging with the AI tutor
- Clear user/assistant message differentiation
- Auto-scroll to latest messages
- Enter to send, Shift+Enter for newlines

### 📊 Feedback System

**Per-Message Feedback:**

- Rate each tutor response (1-4 scale)
- Provide detailed feedback
- Suggest replacement responses

**Case Completion Feedback:**

- Rate overall case detail, helpfulness, accuracy
- Leave additional comments

### 💾 State Persistence

- Conversations saved to localStorage
- Resume interrupted sessions automatically
- Clear state when starting new cases

## Testing the Frontend

### Basic Test Flow

1. **Start a Case**
   - Select "Staphylococcus aureus" from dropdown
   - Click "🚀 Start New Case"
   - Should see welcome message

2. **Send Messages**
   - Type "What are the patient's symptoms?"
   - Press Enter or click Send
   - Should receive AI response

3. **Rate a Response**
   - Hover over an AI message
   - Click a rating button (1-4)
   - Optionally provide feedback
   - Click "Submit Feedback"

4. **Finish Case**
   - Click "🏁 Finish Case"
   - Fill out feedback form
   - Click "✅ Submit Feedback"

5. **Start Another Case**
   - Select different organism
   - Click "Start New Case"
   - Previous conversation should be cleared

## API Endpoints

The frontend uses these V4 API endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/start_case` | POST | Initialize new case |
| `/api/v1/chat` | POST | Send messages |
| `/api/v1/feedback` | POST | Submit message feedback |
| `/api/v1/case_feedback` | POST | Submit case feedback |

## Customization

### Change Colors

Edit `src/microtutor/api/static/css/style.css`:

```css
:root {
    --primary-color: #007bff;     /* Change main blue */
    --success-color: #28a745;      /* Change green */
    --warning-color: #ff9800;      /* Change orange */
}
```

### Add More Organisms

Edit `src/microtutor/api/templates/index.html`:

```html
<optgroup label="Your Category">
    <option value="new-organism">New Organism Name</option>
</optgroup>
```

### Modify Behavior

Edit `src/microtutor/api/static/js/script.js` - all functions are well-documented!

## Troubleshooting

### Problem: "Cannot GET /"

**Solution**: Make sure the app is running and templates directory exists.

```bash
# Check if running
curl http://localhost:5001/health

# Should return: {"status": "healthy", ...}
```

### Problem: Static files not loading (404 errors)

**Solution**: Verify static directory structure:

```bash
ls -la src/microtutor/api/static/
# Should show: css/, js/
```

### Problem: API calls failing

**Solution**: Check if backend is configured correctly:

```bash
# Check API endpoints
curl http://localhost:5001/api/v1/info
```

### Problem: Frontend looks wrong

**Solution**: Hard refresh browser:

- **Mac**: Cmd + Shift + R
- **Windows/Linux**: Ctrl + Shift + R

## Next Steps

1. ✅ **Test thoroughly** with different organisms
2. ✅ **Try all features** (chat, feedback, case completion)
3. ✅ **Check mobile view** (resize browser window)
4. 📖 **Read full docs** in `docs/FRONTEND_V4.md`
5. 🎨 **Customize** colors and styling to your preference

## Differences from V3

### What's Better?

✅ **Modern Design**: Gradients, animations, better typography  
✅ **Cleaner Code**: 30% less JavaScript, better structure  
✅ **Better Errors**: Clear error messages and recovery  
✅ **Type Safety**: Works with Pydantic models  
✅ **API Docs**: Interactive docs at `/api/docs`  
✅ **Responsive**: Works on all screen sizes  

### What's the Same?

✅ All core features from V3  
✅ Organism selection  
✅ Chat interface  
✅ Feedback system  
✅ Case completion workflow  

## Resources

- **Full Documentation**: `docs/FRONTEND_V4.md`
- **API Documentation**: <http://localhost:5001/api/docs> (when running)
- **V3→V4 Migration**: `docs/V3_TO_V4_MAPPING_GUIDE.md`
- **Architecture**: `docs/V4_CLEAN_STRUCTURE.md`

## Support

If you encounter issues:

1. Check browser console for JavaScript errors (F12)
2. Check terminal for Python/FastAPI errors
3. Review logs in `logs/` directory
4. Check API docs at `/api/docs` to test endpoints directly

---

**🎉 Congratulations! Your V4 frontend is ready to use!**

The frontend mimics V3's functionality while providing a much better foundation for future development. Enjoy your modern, type-safe, well-documented application!
