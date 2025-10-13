# Voice-to-Voice Feature Guide 🎤

## Overview

MicroTutor V4 now supports **voice-to-voice interactions**, allowing students to speak their questions and hear responses in natural speech. The system uses:

- **OpenAI Whisper** for speech-to-text (transcription)
- **OpenAI TTS** for text-to-speech (synthesis)
- **Different voices** for tutor vs. patient responses

---

## Features

### 🎙️ Speech Input

- Click and hold the microphone button to record
- Automatic transcription using Whisper API
- Medical terminology optimization for accuracy

### 🔊 Speech Output

- Natural-sounding voices for responses
- **Nova** voice for tutor (professional, clear)
- **Echo** voice for patient (conversational)
- Automatic playback of responses

### 🔄 Complete Voice Pipeline

- One-click voice interaction: speak → transcribe → process → respond → play audio
- Maintains conversation history
- Works with all tutor features (patient queries, hints, socratic guidance)

---

## API Endpoints

### 1. Transcribe Audio

```http
POST /api/v1/voice/transcribe
Content-Type: multipart/form-data

Parameters:
- audio: Audio file (mp3, wav, m4a, webm, etc.)
- language: Optional language code (default: auto-detect)

Response:
{
  "text": "What are the patient's vital signs?",
  "language": "en"
}
```

### 2. Synthesize Speech

```http
POST /api/v1/voice/synthesize
Content-Type: multipart/form-data

Parameters:
- text: Text to convert to speech
- speaker: "tutor" or "patient" (default: "tutor")
- speed: Speech speed 0.25-4.0 (default: 1.0)
- audio_format: mp3, opus, aac, flac, wav, pcm (default: mp3)

Response: Binary audio file
```

### 3. Voice-to-Voice Chat (All-in-One)

```http
POST /api/v1/voice/chat
Content-Type: multipart/form-data

Parameters:
- audio: User's audio file
- case_id: Current case ID
- organism_key: Organism being studied
- history: Chat history as JSON string

Response:
{
  "transcribed_text": "What symptoms does the patient have?",
  "response_text": "I've been experiencing fever and chills for 3 days.",
  "audio_base64": "SUQzBAAAAAAAI1RTU0UAAAAPAAAD...",
  "speaker": "patient",
  "tool_name": "patient",
  "history": [...]
}
```

---

## Voice Configuration

### Environment Variables

Add to your `.env` file:

```bash
# OpenAI API Key (required for voice features)
OPENAI_API_KEY=sk-...

# Voice Configuration (optional, defaults shown)
VOICE_TUTOR=nova        # Options: alloy, echo, fable, onyx, nova, shimmer
VOICE_PATIENT=echo      # Options: alloy, echo, fable, onyx, nova, shimmer
VOICE_TTS_MODEL=tts-1   # Options: tts-1 (fast), tts-1-hd (high quality)
```

### Voice Options

**Tutor Voice Recommendations:**

- `nova` - Clear, professional female voice (default)
- `shimmer` - Warm, friendly female voice
- `alloy` - Neutral, balanced voice

**Patient Voice Recommendations:**

- `echo` - Conversational male voice (default)
- `fable` - Warm, expressive voice
- `onyx` - Deep, authoritative male voice

---

## Frontend Integration

### HTML Button

```html
<!-- Voice recording button -->
<button id="voiceButton" class="voice-btn">
  <span class="mic-icon">🎤</span>
  <span class="status-text">Hold to Speak</span>
</button>

<!-- Audio playback -->
<audio id="responseAudio" controls hidden></audio>
```

### JavaScript Usage

```javascript
// Start recording
const startRecording = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  // ... handle recording
};

// Send to voice API
const sendVoiceMessage = async (audioBlob) => {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.webm');
  formData.append('case_id', caseId);
  formData.append('organism_key', organism);
  formData.append('history', JSON.stringify(history));
  
  const response = await fetch('/api/v1/voice/chat', {
    method: 'POST',
    body: formData
  });
  
  const data = await response.json();
  
  // Play audio response
  const audioBlob = base64ToBlob(data.audio_base64, 'audio/mpeg');
  const audioUrl = URL.createObjectURL(audioBlob);
  document.getElementById('responseAudio').src = audioUrl;
  document.getElementById('responseAudio').play();
};
```

---

## Usage Examples

### Example 1: Ask Patient a Question

**User speaks:** "What symptoms are you experiencing?"

**System:**

1. Transcribes audio → "What symptoms are you experiencing?"
2. Routes to patient agent
3. Patient responds: "I've had a fever of 39°C for three days, along with severe headache."
4. Synthesizes with **patient voice** (echo)
5. Plays audio response automatically

### Example 2: Request a Hint

**User speaks:** "Can you give me a hint about the diagnosis?"

**System:**

1. Transcribes audio
2. Routes to hint agent
3. Tutor responds: "Consider the combination of fever and neurological symptoms. What infections commonly present this way?"
4. Synthesizes with **tutor voice** (nova)
5. Plays audio response

---

## Browser Compatibility

### Supported Browsers

- ✅ Chrome/Edge (best support)
- ✅ Firefox
- ✅ Safari (iOS 14.5+)
- ⚠️ Older browsers may need polyfills

### Required Permissions

- Microphone access
- HTTPS connection (required for `getUserMedia`)

---

## Cost Considerations

### OpenAI Pricing (as of 2024)

**Whisper (Speech-to-Text):**

- $0.006 per minute of audio
- Example: 1,000 30-second queries = $3.00

**TTS (Text-to-Speech):**

- `tts-1`: $0.015 per 1K characters
- `tts-1-hd`: $0.030 per 1K characters
- Example: 1,000 responses (150 chars avg) = $2.25

**Total Cost Estimate:**

- ~$0.005 per voice interaction
- 1,000 interactions ≈ $5-6

---

## Performance

### Latency Breakdown

1. **Recording**: Instant (client-side)
2. **Upload**: ~200-500ms (depends on audio size)
3. **Transcription**: ~1-2 seconds
4. **LLM Processing**: ~2-5 seconds
5. **TTS Synthesis**: ~1-2 seconds
6. **Download**: ~200-500ms

**Total**: 5-10 seconds per interaction

### Optimization Tips

- Use `tts-1` instead of `tts-1-hd` for faster synthesis
- Compress audio before upload (webm/opus format)
- Stream audio responses when possible
- Cache common responses

---

## Advanced Features

### 1. Voice Interruption

Allow users to interrupt long responses:

```javascript
const stopPlayback = () => {
  const audio = document.getElementById('responseAudio');
  audio.pause();
  audio.currentTime = 0;
};
```

### 2. Speed Control

Adjust playback speed:

```javascript
document.getElementById('responseAudio').playbackRate = 1.25; // 25% faster
```

### 3. Voice Selection

Let users choose their preferred voices:

```javascript
const voiceSettings = {
  tutor: 'nova',    // User preference
  patient: 'echo',
  speed: 1.0
};
```

---

## Troubleshooting

### "Microphone not found"

- Check browser permissions
- Ensure HTTPS connection
- Try different browser

### "No OpenAI API key"

- Add `OPENAI_API_KEY` to `.env`
- Restart the server
- Check key validity

### "Audio not playing"

- Check browser audio permissions
- Verify audio format support
- Check console for errors

### Poor Transcription Quality

- Speak clearly and at moderate pace
- Reduce background noise
- Use better microphone
- Add medical terminology to prompt

---

## Testing

### Test Transcription

```bash
curl -X POST "http://localhost:5001/api/v1/voice/transcribe" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@test_audio.mp3"
```

### Test Synthesis

```bash
curl -X POST "http://localhost:5001/api/v1/voice/synthesize" \
  -F "text=Hello, this is a test." \
  -F "speaker=tutor" \
  --output test_output.mp3
```

### Test Complete Pipeline

```bash
curl -X POST "http://localhost:5001/api/v1/voice/chat" \
  -F "audio=@question.mp3" \
  -F "case_id=case_123" \
  -F "organism_key=staphylococcus aureus" \
  -F "history=[]"
```

---

## Future Enhancements

### Planned Features

- 🎯 Real-time streaming transcription
- 🔊 Voice activity detection
- 🌍 Multi-language support
- 📝 Transcription correction interface
- 🎨 Voice cloning for consistent patient voices
- 📊 Pronunciation assessment
- 🔇 Background noise cancellation

---

## Security Considerations

1. **Audio Storage**: Audio files are NOT stored on server (processed in memory)
2. **Privacy**: User recordings are sent to OpenAI (see their privacy policy)
3. **HTTPS**: Required for microphone access
4. **Rate Limiting**: Consider adding to prevent abuse
5. **API Key**: Keep OpenAI key secure, never expose to client

---

## Summary

✅ **Complete voice-to-voice pipeline**
✅ **Separate voices for tutor and patient**
✅ **Medical terminology optimization**
✅ **Simple one-button interface**
✅ **Automatic transcription and synthesis**
✅ **Works with all existing tutor features**

**Ready to use! Just add your OpenAI API key and click the mic button! 🎤**
