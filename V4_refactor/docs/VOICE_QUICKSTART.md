# Voice Features Quick Start 🎤

## 5-Minute Setup

### 1. Add OpenAI API Key

Add your OpenAI API key to `.env`:

```bash
# Required for voice features
OPENAI_API_KEY=sk-your-key-here

# Optional voice configuration
VOICE_TUTOR=nova          # Voice for tutor (default)
VOICE_PATIENT=echo        # Voice for patient (default)
VOICE_TTS_MODEL=tts-1     # Use tts-1-hd for higher quality
```

### 2. Start the Server

```bash
python run_v4.py
```

### 3. Open Browser

Navigate to: **<http://localhost:5001>**

### 4. Use Voice

1. **Start a case** (select organism and click "Start New Case")
2. **Click the purple 🎤 Voice button**
3. **Speak your question** (e.g., "What are the patient's symptoms?")
4. **Release the button** - audio transcribes automatically
5. **Listen to the response** - plays automatically with appropriate voice

---

## Usage Modes

### Mode 1: Click to Toggle

- Click once to start recording
- Click again to stop and send

### Mode 2: Press and Hold (Recommended)

- Press and hold the button
- Speak your question
- Release to send

### Mode 3: Mobile Touch

- Touch and hold on mobile devices
- Release to send

---

## How It Works

```
User speaks → Whisper API → Transcription
                    ↓
              Tutor processes question
                    ↓
         Response text generated
                    ↓
    TTS API → Audio (nova/echo voice)
                    ↓
           Auto-plays in browser
```

---

## Voice Indicators

- **🎤 Voice ready** - Ready to record
- **🔴 Recording...** - Currently recording (button turns red)
- **⏸️ Processing...** - Transcribing and processing
- **❌ Mic unavailable** - Microphone access denied

---

## Speaker Voices

The system automatically uses different voices:

| Speaker | Voice | Character |
|---------|-------|-----------|
| **Tutor** 👨‍⚕️ | Nova | Clear, professional, educational |
| **Patient** 🤒 | Echo | Natural, conversational |

---

## Browser Requirements

✅ **Chrome/Edge** - Full support  
✅ **Firefox** - Full support  
✅ **Safari** - Requires iOS 14.5+ / macOS 11+  
❌ **HTTP** - Requires HTTPS for microphone access  

**Note**: When testing locally, most browsers allow microphone access on `localhost`.

---

## Troubleshooting

### "Microphone not found"

1. Check browser permissions (look for 🎤 icon in address bar)
2. Ensure HTTPS (or localhost)
3. Try different browser

### "No OpenAI API key"

1. Add `OPENAI_API_KEY` to `.env`
2. Restart server: `python run_v4.py`

### Audio not playing

1. Check browser audio is not muted
2. Look in browser console (F12) for errors
3. Try different browser

### Poor transcription

1. Speak clearly at moderate pace
2. Reduce background noise
3. Use external microphone if possible
4. Medical terms are optimized automatically

---

## Cost Estimate

Per voice interaction:

- **Whisper**: ~$0.001 (30-second recording)
- **TTS**: ~$0.002 (typical response)
- **Total**: ~$0.003-0.005 per interaction

**Example**: 200 voice interactions = ~$1.00

---

## Next Steps

- See [VOICE_TO_VOICE_GUIDE.md](VOICE_TO_VOICE_GUIDE.md) for full documentation
- Try different voice combinations in `.env`
- Use `tts-1-hd` for higher quality audio
- Add custom medical terminology prompts

---

## API Endpoints

If you want to integrate programmatically:

```python
import requests

# Voice-to-voice chat
files = {'audio': open('question.mp3', 'rb')}
data = {
    'case_id': 'case_123',
    'organism_key': 'staphylococcus aureus',
    'history': '[]'
}

response = requests.post(
    'http://localhost:5001/api/v1/voice/chat',
    files=files,
    data=data
)

result = response.json()
print(f"Transcribed: {result['transcribed_text']}")
print(f"Response: {result['response_text']}")
# result['audio_base64'] contains the audio response
```

---

## Quick Demo

1. Start case with "Staphylococcus aureus"
2. Click voice button and say: **"What symptoms does the patient have?"**
3. Listen to patient respond with symptoms (echo voice)
4. Click voice button and say: **"Can you give me a hint?"**
5. Listen to tutor provide guidance (nova voice)

**That's it! You're using voice-to-voice tutoring! 🎉**
