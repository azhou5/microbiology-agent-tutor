/**
 * Voice recording functionality for MicroTutor V4
 */

/**
 * Check if the current context is secure for getUserMedia
 * @returns {boolean} True if secure context
 */
function isSecureContext() {
    const hostname = window.location.hostname;
    const protocol = window.location.protocol;

    // Secure contexts: HTTPS, localhost, 127.0.0.1, or file://
    return (
        protocol === 'https:' ||
        hostname === 'localhost' ||
        hostname === '127.0.0.1' ||
        hostname === '[::1]' ||
        protocol === 'file:'
    );
}

/**
 * Check if voice is available (without requesting permission)
 * @returns {boolean} True if voice is available
 */
function checkVoiceAvailability() {
    console.log('[VOICE] Checking voice availability...');

    // Check if we're in a secure context first
    if (!isSecureContext()) {
        const currentUrl = window.location.href;
        const localhostUrl = currentUrl.replace(window.location.hostname, 'localhost');
        const errorMessage = '❌ Use localhost';
        const tooltipMessage = `Microphone requires HTTPS or localhost. Try: ${localhostUrl}`;

        setVoiceStatus(errorMessage);
        if (DOM.voiceBtn) {
            DOM.voiceBtn.disabled = true;
            DOM.voiceBtn.title = tooltipMessage;
        }
        return false;
    }

    // If we're in a secure context, ALWAYS enable the button
    if (DOM.voiceBtn) {
        DOM.voiceBtn.disabled = false;
        DOM.voiceBtn.title = 'Click to request microphone access';
    }

    // Check if the browser supports getUserMedia
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setVoiceStatus('🎤 Click to try');
        if (DOM.voiceBtn) {
            DOM.voiceBtn.title = 'Voice API not detected, but click to try anyway';
        }
        return false;
    }

    // Voice API is available
    setVoiceStatus('🎤 Click to start');
    console.log('[VOICE] ✅ Voice API available, waiting for user interaction');
    return true;
}

/**
 * Request microphone permission (called on first user interaction)
 * @returns {Promise<boolean>} True if permission granted
 */
async function requestMicrophonePermission() {
    if (State.voiceInitialized) {
        return State.voiceEnabled; // Already attempted
    }

    State.voiceInitialized = true;
    setVoiceStatus('⏳ Requesting...');

    try {
        console.log('[VOICE] Requesting microphone permission...');
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        State.voiceEnabled = true;
        setVoiceStatus('🎤 Voice ready');
        console.log('[VOICE] Microphone access granted');

        // Stop the stream immediately (we'll request again when actually recording)
        stream.getTracks().forEach(track => track.stop());

        if (DOM.voiceBtn) {
            DOM.voiceBtn.title = 'Click and hold to record';
        }

        return true;
    } catch (error) {
        console.error('[VOICE] Microphone access denied:', error);
        State.voiceEnabled = false;

        let errorMessage = '❌ Mic unavailable';
        let tooltipMessage = 'Microphone access denied';

        if (error.name === 'NotAllowedError') {
            errorMessage = '❌ Permission denied';
            tooltipMessage = 'You denied microphone access. Click 🔒 in address bar to change permissions.';
        } else if (error.name === 'NotFoundError') {
            errorMessage = '❌ No microphone';
            tooltipMessage = 'No microphone found on this device';
        } else if (error.name === 'NotReadableError') {
            errorMessage = '❌ Mic in use';
            tooltipMessage = 'Microphone is already in use by another application';
        } else {
            tooltipMessage = error.message || 'Could not access microphone';
        }

        setVoiceStatus(errorMessage);
        if (DOM.voiceBtn) {
            DOM.voiceBtn.disabled = true;
            DOM.voiceBtn.title = tooltipMessage;
        }

        return false;
    }
}

/**
 * Set voice status message
 * @param {string} message - Status message
 */
function setVoiceStatus(message) {
    if (DOM.voiceStatus) {
        DOM.voiceStatus.textContent = message;
    }
}

/**
 * Start recording audio
 */
async function startRecording() {
    if (!State.currentCaseId || !State.currentOrganismKey) {
        setStatus('Please start a case first before using voice', true);
        return;
    }

    try {
        console.log('[VOICE] 🎙️ Starting recording...');
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        console.log('[VOICE] ✅ Got media stream');

        // Try formats in order of OpenAI compatibility
        const preferredFormats = [
            'audio/mp4',
            'audio/webm;codecs=opus',
            'audio/webm',
            ''
        ];

        let mimeType = '';
        for (const format of preferredFormats) {
            if (format === '' || MediaRecorder.isTypeSupported(format)) {
                mimeType = format;
                break;
            }
        }

        console.log('[VOICE] Using mimeType:', mimeType || 'browser default');

        const options = mimeType ? { mimeType } : {};
        State.mediaRecorder = new MediaRecorder(stream, options);
        State.audioChunks = [];

        State.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                State.audioChunks.push(event.data);
                console.log('[VOICE] 📊 Data chunk received:', event.data.size, 'bytes');
            }
        };

        State.mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(State.audioChunks, { type: mimeType || 'audio/webm' });
            console.log('[VOICE] ⏹️ Recording stopped, total size:', audioBlob.size, 'bytes');

            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());

            // Send to API
            if (audioBlob.size > 0) {
                await sendVoiceMessage(audioBlob);
            } else {
                console.error('[VOICE] Recording is empty (0 bytes)');
                setStatus('Recording failed - no audio captured', true);
                setVoiceStatus('🎤 Voice ready');
            }
        };

        State.mediaRecorder.start();
        State.isRecording = true;
        State.recordingStartTime = Date.now();
        setVoiceStatus('🔴 RECORDING - Speak now!');
        setStatus('🎙️ Recording in progress... Release to send');

        // Visual feedback on button
        if (DOM.voiceBtn) {
            DOM.voiceBtn.style.background = '#dc3545';
            DOM.voiceBtn.style.animation = 'pulse 1s infinite';
        }

        console.log('[VOICE] ✅ Recording started successfully');

    } catch (error) {
        console.error('[VOICE] ❌ Recording error:', error);
        setStatus('Error accessing microphone: ' + error.message, true);
        setVoiceStatus('❌ Recording failed');
        State.isRecording = false;
    }
}

/**
 * Stop recording audio
 */
function stopRecording() {
    if (State.mediaRecorder && State.isRecording) {
        // Check recording duration
        const duration = Date.now() - State.recordingStartTime;
        console.log('[VOICE] ⏹️ Stopping recording... Duration:', duration, 'ms');

        if (duration < 500) {
            console.warn('[VOICE] ⚠️ Recording too short:', duration, 'ms');
            setStatus('Recording too short - please hold longer', true);
            setVoiceStatus('⚠️ Too short');

            // Stop and reset
            State.mediaRecorder.stop();
            State.isRecording = false;

            // Reset button
            if (DOM.voiceBtn) {
                DOM.voiceBtn.style.background = '';
                DOM.voiceBtn.style.animation = '';
            }

            // Reset status after delay
            setTimeout(() => {
                setVoiceStatus('🎤 Voice ready');
                setStatus('');
            }, 2000);

            return;
        }

        State.mediaRecorder.stop();
        State.isRecording = false;
        setVoiceStatus('⏸️ Processing...');
        setStatus('Processing audio...');

        // Reset button appearance
        if (DOM.voiceBtn) {
            DOM.voiceBtn.style.background = '';
            DOM.voiceBtn.style.animation = '';
        }

        console.log('[VOICE] ✅ Recording stopped after', duration, 'ms, processing...');
    }
}

/**
 * Send voice message to API
 * @param {Blob} audioBlob - Audio blob to send
 */
async function sendVoiceMessage(audioBlob) {
    console.log('[VOICE] Sending audio to API...');

    disableInput(true);
    setStatus('Transcribing and processing...');

    try {
        // Determine file extension from MIME type
        let extension = 'webm';
        if (audioBlob.type.includes('mp4')) {
            extension = 'mp4';
        } else if (audioBlob.type.includes('ogg')) {
            extension = 'ogg';
        } else if (audioBlob.type.includes('wav')) {
            extension = 'wav';
        }

        const filename = `recording.${extension}`;

        // Create form data
        const formData = new FormData();
        formData.append('audio', audioBlob, filename);
        formData.append('case_id', State.currentCaseId);
        formData.append('organism_key', State.currentOrganismKey);
        formData.append('history', JSON.stringify(State.chatHistory));

        // Send to voice chat endpoint
        const response = await fetch(`${API_BASE}/voice/chat`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || errData.error || `HTTP ${response.status}`);
        }

        const data = await response.json();
        console.log('[VOICE] Response received:', data);

        // Add transcribed user message
        addMessage('user', data.transcribed_text);
        addMessageToHistory('user', data.transcribed_text);

        // Add assistant response
        const speakerIcon = data.speaker === 'patient' ? '🤒' : '👨‍⚕️';
        addMessage('assistant', `${speakerIcon} ${data.response_text}`, true);
        addMessageToHistory('assistant', data.response_text);

        // Play audio response
        if (data.audio_base64) {
            playAudioResponse(data.audio_base64);
        }

        setStatus('');
        setVoiceStatus('🎤 Voice ready');
        disableInput(false);
        saveConversationState();

    } catch (error) {
        console.error('[VOICE] Error:', error);
        setStatus(`Voice error: ${error.message}`, true);
        setVoiceStatus('❌ Error');
        disableInput(false);
    }
}

/**
 * Play audio response from base64
 * @param {string} audioBase64 - Base64 encoded audio
 */
function playAudioResponse(audioBase64) {
    try {
        // Convert base64 to blob
        const byteCharacters = atob(audioBase64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const audioBlob = new Blob([byteArray], { type: 'audio/mpeg' });

        // Create URL and play
        const audioUrl = URL.createObjectURL(audioBlob);

        if (DOM.responseAudio) {
            DOM.responseAudio.src = audioUrl;
            DOM.responseAudio.play();
            console.log('[VOICE] Playing audio response');

            // Clean up URL after playing
            DOM.responseAudio.onended = () => {
                URL.revokeObjectURL(audioUrl);
            };
        }
    } catch (error) {
        console.error('[VOICE] Error playing audio:', error);
    }
}

/**
 * Handle voice button click (toggle recording on/off)
 */
async function handleVoiceButton() {
    // First-time setup: request permission
    if (!State.voiceInitialized) {
        const granted = await requestMicrophonePermission();
        if (!granted) {
            setStatus('Microphone access denied. Check permissions.', true);
            return;
        }
    }

    if (!State.voiceEnabled) {
        setStatus('Voice is not available. Check microphone permissions.', true);
        return;
    }

    if (!State.currentCaseId || !State.currentOrganismKey) {
        setStatus('Please start a case first before using voice', true);
        return;
    }

    // Toggle recording
    if (State.isRecording) {
        console.log('[VOICE] 🛑 Stopping recording (user clicked button)');
        stopRecording();
        if (DOM.voiceBtn) {
            DOM.voiceBtn.classList.remove('recording');
            DOM.voiceBtn.textContent = '🎤';
        }
    } else {
        console.log('[VOICE] ▶️ Starting recording (user clicked button)');
        startRecording();
        if (DOM.voiceBtn) {
            DOM.voiceBtn.classList.add('recording');
            DOM.voiceBtn.textContent = '⏹️';
        }
    }
}
