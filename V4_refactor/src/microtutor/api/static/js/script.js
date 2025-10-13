/**
 * MicroTutor V4 Frontend JavaScript
 * Modern frontend adapted for FastAPI backend
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const startCaseBtn = document.getElementById('start-case-btn');
    const organismSelect = document.getElementById('organism-select');
    const statusMessage = document.getElementById('status-message');
    const finishBtn = document.getElementById('finish-btn');
    const feedbackModal = document.getElementById('feedback-modal');
    const closeFeedbackBtn = document.getElementById('close-feedback-btn');
    const submitFeedbackBtn = document.getElementById('submit-feedback-btn');
    const correctOrganismSpan = document.getElementById('correct-organism');

    // Voice elements
    const voiceBtn = document.getElementById('voice-btn');
    const voiceStatus = document.getElementById('voice-status');
    const responseAudio = document.getElementById('response-audio');

    // API Configuration
    const API_BASE = '/api/v1';

    // State
    let chatHistory = [];
    let currentCaseId = null;
    let currentOrganismKey = null;

    // Voice state
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    let voiceEnabled = false;
    let voiceInitialized = false; // Track if we've attempted initialization
    let recordingStartTime = null; // Track when recording started

    // LocalStorage keys
    const STORAGE_KEYS = {
        HISTORY: 'microtutor_v4_chat_history',
        CASE_ID: 'microtutor_v4_case_id',
        ORGANISM: 'microtutor_v4_organism'
    };

    /**
     * Save conversation state to localStorage
     */
    function saveConversationState() {
        try {
            localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(chatHistory));
            localStorage.setItem(STORAGE_KEYS.CASE_ID, currentCaseId || '');
            localStorage.setItem(STORAGE_KEYS.ORGANISM, currentOrganismKey || '');
            console.log('[SAVE] State saved:', {
                historyLength: chatHistory.length,
                caseId: currentCaseId
            });
        } catch (e) {
            console.error('[SAVE] Error saving state:', e);
            setStatus('Could not save conversation state', true);
        }
    }

    /**
     * Load conversation state from localStorage
     */
    function loadConversationState() {
        try {
            const savedHistory = localStorage.getItem(STORAGE_KEYS.HISTORY);
            const savedCaseId = localStorage.getItem(STORAGE_KEYS.CASE_ID);
            const savedOrganism = localStorage.getItem(STORAGE_KEYS.ORGANISM);

            if (savedHistory && savedCaseId && savedOrganism) {
                chatHistory = JSON.parse(savedHistory);
                currentCaseId = savedCaseId;
                currentOrganismKey = savedOrganism;

                if (chatHistory.length > 0) {
                    chatbox.innerHTML = '';
                    chatHistory.forEach(msg => {
                        if (msg.role !== 'system') {
                            addMessage(msg.role, msg.content, false);
                        }
                    });

                    disableInput(false);
                    finishBtn.disabled = false;
                    organismSelect.value = currentOrganismKey;
                    setStatus(`Resumed case. Case ID: ${currentCaseId}`);
                    console.log('[LOAD] State loaded successfully');
                    return true;
                }
            }
        } catch (e) {
            console.error('[LOAD] Error loading state:', e);
            clearConversationState();
        }
        return false;
    }

    /**
     * Clear conversation state
     */
    function clearConversationState() {
        try {
            localStorage.removeItem(STORAGE_KEYS.HISTORY);
            localStorage.removeItem(STORAGE_KEYS.CASE_ID);
            localStorage.removeItem(STORAGE_KEYS.ORGANISM);
            console.log('[CLEAR] State cleared');
        } catch (e) {
            console.error('[CLEAR] Error clearing state:', e);
        }
    }

    /**
     * Generate unique case ID
     */
    function generateCaseId() {
        return 'case_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Add a message to the chatbox
     */
    function addMessage(sender, messageContent, addFeedbackUI = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'assistant-message');
        messageDiv.id = 'msg-' + Date.now();

        const messageTextSpan = document.createElement('span');
        messageTextSpan.textContent = messageContent;
        messageDiv.appendChild(messageTextSpan);

        // Add feedback UI for assistant messages
        if (sender === 'assistant' && addFeedbackUI) {
            const feedbackContainer = createFeedbackUI(messageDiv.id, messageContent);
            messageDiv.appendChild(feedbackContainer);
        }

        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    /**
     * Create feedback UI for assistant messages
     */
    function createFeedbackUI(messageId, messageContent) {
        const feedbackContainer = document.createElement('div');
        feedbackContainer.classList.add('feedback-container');

        // Rating prompt
        const ratingPrompt = document.createElement('span');
        ratingPrompt.textContent = "Rate this response (1-4):";
        ratingPrompt.classList.add('feedback-prompt');
        feedbackContainer.appendChild(ratingPrompt);

        // Rating buttons container
        const ratingButtonsDiv = document.createElement('div');
        ratingButtonsDiv.classList.add('feedback-buttons');

        // Create rating buttons (1-4)
        for (let i = 1; i <= 4; i++) {
            const ratingBtn = document.createElement('button');
            ratingBtn.textContent = i;
            ratingBtn.title = `Rate ${i} out of 4`;
            ratingBtn.classList.add('feedback-btn', 'rating-btn');
            ratingBtn.dataset.rating = i;
            ratingButtonsDiv.appendChild(ratingBtn);
        }

        // Cancel button
        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.classList.add('feedback-btn', 'cancel-btn');
        ratingButtonsDiv.appendChild(cancelBtn);

        feedbackContainer.appendChild(ratingButtonsDiv);

        // Feedback textboxes
        const feedbackTextboxes = document.createElement('div');
        feedbackTextboxes.classList.add('feedback-textboxes');

        feedbackTextboxes.innerHTML = `
            <div class="feedback-textbox">
                <label for="feedback-text-${messageId}">Why this score?</label>
                <textarea id="feedback-text-${messageId}" placeholder="Please explain your rating..."></textarea>
            </div>
            <div class="feedback-textbox">
                <label for="replacement-text-${messageId}">Preferred response (optional):</label>
                <textarea id="replacement-text-${messageId}" placeholder="Enter your preferred response..."></textarea>
            </div>
        `;

        const submitButton = document.createElement('button');
        submitButton.classList.add('feedback-submit');
        submitButton.textContent = 'Submit Feedback';
        submitButton.disabled = true;

        feedbackTextboxes.appendChild(submitButton);
        feedbackContainer.appendChild(feedbackTextboxes);

        // Event listeners
        ratingButtonsDiv.addEventListener('click', (event) => {
            const ratingBtn = event.target.closest('.rating-btn');
            const cancelBtn = event.target.closest('.cancel-btn');

            if (cancelBtn) {
                ratingButtonsDiv.querySelectorAll('.rating-btn').forEach(btn => {
                    btn.classList.remove('rated');
                    btn.disabled = false;
                });
                feedbackTextboxes.classList.remove('visible');
                submitButton.disabled = true;
                return;
            }

            if (!ratingBtn) return;

            ratingButtonsDiv.querySelectorAll('.rating-btn').forEach(btn => {
                btn.classList.remove('rated');
                btn.disabled = false;
            });

            ratingBtn.classList.add('rated');
            ratingBtn.disabled = true;
            feedbackTextboxes.classList.add('visible');
            submitButton.disabled = false;
        });

        submitButton.addEventListener('click', async () => {
            const feedbackText = document.getElementById(`feedback-text-${messageId}`).value;
            const replacementText = document.getElementById(`replacement-text-${messageId}`).value;
            const ratingElement = ratingButtonsDiv.querySelector('.rated');

            if (!ratingElement) {
                setStatus('Please select a rating first.', true);
                return;
            }

            await submitFeedback(
                parseInt(ratingElement.dataset.rating),
                messageContent,
                feedbackText,
                replacementText
            );

            // Show feedback submitted
            feedbackContainer.innerHTML = `
                <div class="feedback-submitted">
                    <div class="feedback-rating">✅ Rating: ${ratingElement.dataset.rating}/4</div>
                    ${feedbackText.trim() ? `<div class="feedback-text">${feedbackText}</div>` : ''}
                </div>
            `;

            // If replacement provided, add it to chat
            if (replacementText.trim()) {
                addMessage('assistant', replacementText, true);
                chatHistory.push({ role: 'assistant', content: replacementText });
                saveConversationState();
            }
        });

        return feedbackContainer;
    }

    /**
     * Submit feedback for a message
     */
    async function submitFeedback(rating, message, feedbackText, replacementText) {
        setStatus('Sending feedback...');
        try {
            const response = await fetch(`${API_BASE}/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    rating,
                    message,
                    history: chatHistory,
                    feedback_text: feedbackText,
                    replacement_text: replacementText,
                    case_id: currentCaseId,
                    organism: currentOrganismKey
                }),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || err.error || `HTTP ${response.status}`);
            }

            setStatus('Feedback submitted — thank you!');
        } catch (error) {
            console.error('[FEEDBACK] Error:', error);
            setStatus(`Error: ${error.message}`, true);
        }
    }

    /**
     * Set status message
     */
    function setStatus(message, isError = false) {
        statusMessage.textContent = message;
        statusMessage.className = isError ? 'status error' : 'status';
    }

    /**
     * Enable/disable input controls
     */
    function disableInput(disabled = true) {
        userInput.disabled = disabled;
        sendBtn.disabled = disabled;
        if (disabled && !statusMessage.textContent.includes("Error")) {
            setStatus('Processing...');
        } else if (!disabled && statusMessage.textContent === 'Processing...') {
            setStatus('');
        }
    }

    /**
     * Start a new case
     */
    async function handleStartCase() {
        console.log('[START_CASE] Starting new case...');

        const selectedOrganism = organismSelect.value;
        if (!selectedOrganism) {
            setStatus('Please select an organism first.', true);
            return;
        }

        // Clear previous state
        clearConversationState();
        chatHistory = [];
        chatbox.innerHTML = '';
        currentCaseId = generateCaseId();
        currentOrganismKey = selectedOrganism;

        setStatus('Starting new case...');
        disableInput(true);
        finishBtn.disabled = true;

        try {
            const response = await fetch(`${API_BASE}/start_case`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    organism: currentOrganismKey,
                    case_id: currentCaseId,
                    model_name: 'o3-mini'
                }),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || err.error || `HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('[START_CASE] Response:', data);

            // Initialize history from response
            chatHistory = data.history || [];

            // Display messages
            chatbox.innerHTML = '';
            chatHistory.forEach(msg => {
                if (msg.role !== 'system') {
                    addMessage(msg.role, msg.content, msg.role === 'assistant');
                }
            });

            setStatus(`Case started. Case ID: ${currentCaseId}`);
            disableInput(false);
            finishBtn.disabled = false;
            saveConversationState();
            console.log('[START_CASE] Success!');
        } catch (error) {
            console.error('[START_CASE] Error:', error);
            setStatus(`Error: ${error.message}`, true);
            disableInput(false);
            currentOrganismKey = null;
            currentCaseId = null;
        }
    }

    /**
     * Send a chat message
     */
    async function handleSendMessage() {
        const messageText = userInput.value.trim();
        if (!messageText) return;

        console.log('[CHAT] Sending message...');

        addMessage('user', messageText);
        chatHistory.push({ role: 'user', content: messageText });
        userInput.value = '';
        disableInput(true);

        try {
            const response = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: messageText,
                    history: chatHistory,
                    organism_key: currentOrganismKey,
                    case_id: currentCaseId
                }),
            });

            if (!response.ok) {
                const errData = await response.json();

                if (errData.detail && errData.detail.includes('case')) {
                    setStatus("Session expired. Please start a new case.", true);
                    disableInput(true);
                    finishBtn.disabled = true;
                    clearConversationState();
                    return;
                }

                throw new Error(errData.detail || errData.error || `HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('[CHAT] Response:', data);

            addMessage('assistant', data.response, true);
            chatHistory = data.history || chatHistory;
            chatHistory.push({ role: 'assistant', content: data.response });

            disableInput(false);
            setStatus('');
            saveConversationState();
        } catch (error) {
            console.error('[CHAT] Error:', error);
            setStatus(`Error: ${error.message}`, true);
            disableInput(false);
        }
    }

    /**
     * Finish case and show feedback modal
     */
    function handleFinishCase() {
        console.log('[FINISH] Finishing case...');
        if (currentOrganismKey) {
            correctOrganismSpan.textContent = currentOrganismKey;
        } else {
            correctOrganismSpan.textContent = "Unknown";
        }
        feedbackModal.classList.add('is-active');
    }

    /**
     * Close feedback modal
     */
    function closeFeedbackModal() {
        feedbackModal.classList.remove('is-active');
    }

    /**
     * Submit case feedback
     */
    async function submitCaseFeedback() {
        const detailRating = document.querySelector('input[name="detail"]:checked');
        const helpfulnessRating = document.querySelector('input[name="helpfulness"]:checked');
        const accuracyRating = document.querySelector('input[name="accuracy"]:checked');
        const comments = document.getElementById('feedback-comments').value;

        if (!detailRating || !helpfulnessRating || !accuracyRating) {
            alert('Please provide a rating for all categories or use skip.');
            return;
        }

        const feedbackData = {
            detail: parseInt(detailRating.value),
            helpfulness: parseInt(helpfulnessRating.value),
            accuracy: parseInt(accuracyRating.value),
            comments: comments,
            case_id: currentCaseId,
            organism: currentOrganismKey
        };

        setStatus('Submitting case feedback...');
        try {
            const response = await fetch(`${API_BASE}/case_feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(feedbackData),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || err.error || `HTTP ${response.status}`);
            }

            setStatus('Case feedback submitted! Thank you. You can start a new case.');
            closeFeedbackModal();

            // Reset UI
            chatbox.innerHTML = '<div class="welcome-message"><p>👋 Case completed!</p><p>Select an organism and start a new case.</p></div>';
            disableInput(true);
            finishBtn.disabled = true;
            userInput.value = '';

            // Clear state
            clearConversationState();
            chatHistory = [];
            currentCaseId = null;
            currentOrganismKey = null;

            // Reset feedback form
            document.querySelectorAll('input[type="radio"]').forEach(radio => radio.checked = false);
            document.getElementById('feedback-comments').value = '';
            document.querySelectorAll('.skip-btn').forEach(btn => btn.disabled = false);

        } catch (error) {
            console.error('[CASE_FEEDBACK] Error:', error);
            setStatus(`Error submitting feedback: ${error.message}`, true);
        }
    }

    // Event Listeners
    if (startCaseBtn) {
        startCaseBtn.addEventListener('click', handleStartCase);
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', handleSendMessage);
    }

    if (userInput) {
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !sendBtn.disabled) {
                e.preventDefault();
                handleSendMessage();
            }
        });
    }

    if (finishBtn) {
        finishBtn.addEventListener('click', handleFinishCase);
    }

    if (closeFeedbackBtn) {
        closeFeedbackBtn.addEventListener('click', closeFeedbackModal);
    }

    if (submitFeedbackBtn) {
        submitFeedbackBtn.addEventListener('click', submitCaseFeedback);
    }

    // Skip buttons
    document.querySelectorAll('.skip-btn').forEach(button => {
        button.addEventListener('click', function () {
            const questionName = this.dataset.question;
            const radioButtons = document.querySelectorAll(`input[name="${questionName}"]`);
            radioButtons.forEach(radio => {
                radio.checked = false;
                radio.disabled = true;
            });
            this.textContent = 'Skipped';
            this.disabled = true;
        });
    });

    // ============================================================
    // VOICE FUNCTIONALITY
    // ============================================================

    /**
     * Check if the current context is secure for getUserMedia
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
     */
    function checkVoiceAvailability() {
        console.log('[VOICE] Checking voice availability...');
        console.log('[VOICE] navigator:', typeof navigator);
        console.log('[VOICE] navigator.mediaDevices:', typeof navigator.mediaDevices);
        console.log('[VOICE] window.location.href:', window.location.href);
        console.log('[VOICE] window.isSecureContext:', window.isSecureContext);
        console.log('[VOICE] window.location.protocol:', window.location.protocol);
        console.log('[VOICE] window.location.hostname:', window.location.hostname);

        // Check if we're in a secure context first (this we can determine for sure)
        if (!isSecureContext()) {
            const currentUrl = window.location.href;
            const localhostUrl = currentUrl.replace(window.location.hostname, 'localhost');
            const errorMessage = '❌ Use localhost';
            const tooltipMessage = `Microphone requires HTTPS or localhost. Try: ${localhostUrl}`;

            setVoiceStatus(errorMessage);
            if (voiceBtn) {
                voiceBtn.disabled = true;
                voiceBtn.title = tooltipMessage;
            }

            console.warn(
                '%c[VOICE] Security Warning',
                'color: orange; font-weight: bold; font-size: 14px;',
                `\nMicrophone requires HTTPS or localhost.\nCurrent: ${window.location.hostname}\nTry: ${localhostUrl}`
            );
            return false;
        }

        // If we're in a secure context, ALWAYS enable the button
        // Let the actual getUserMedia call fail with a proper error if there's an issue
        if (voiceBtn) {
            voiceBtn.disabled = false;
            voiceBtn.title = 'Click to request microphone access';
        }

        // Check if the browser supports getUserMedia (but don't disable button)
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            let statusMessage = '🎤 Click to try';
            let warning = 'Voice API not detected, but click to try anyway';

            if (!navigator.mediaDevices) {
                console.warn('[VOICE] navigator.mediaDevices is undefined - this is unusual on localhost');
                warning = 'navigator.mediaDevices is undefined. Click to attempt access anyway.';
            } else if (!navigator.mediaDevices.getUserMedia) {
                console.warn('[VOICE] getUserMedia is undefined');
                warning = 'getUserMedia is undefined. Click to attempt access anyway.';
            }

            setVoiceStatus(statusMessage);
            if (voiceBtn) {
                voiceBtn.title = warning;
            }
            console.warn('[VOICE] Voice API not detected. Browser:', navigator.userAgent);
            console.warn('[VOICE] Button enabled anyway - will attempt on click');
            return false;
        }

        // Voice API is available
        setVoiceStatus('🎤 Click to start');
        console.log('[VOICE] ✅ Voice API available, waiting for user interaction');
        return true;
    }

    /**
     * Request microphone permission (called on first user interaction)
     */
    async function requestMicrophonePermission() {
        if (voiceInitialized) {
            return voiceEnabled; // Already attempted
        }

        voiceInitialized = true;
        setVoiceStatus('⏳ Requesting...');

        try {
            console.log('[VOICE] Requesting microphone permission...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            voiceEnabled = true;
            setVoiceStatus('🎤 Voice ready');
            console.log('[VOICE] Microphone access granted');

            // Stop the stream immediately (we'll request again when actually recording)
            stream.getTracks().forEach(track => track.stop());

            if (voiceBtn) {
                voiceBtn.title = 'Click and hold to record';
            }

            return true;
        } catch (error) {
            console.error('[VOICE] Microphone access denied:', error);
            voiceEnabled = false;

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
            if (voiceBtn) {
                voiceBtn.disabled = true;
                voiceBtn.title = tooltipMessage;
            }

            return false;
        }
    }

    /**
     * Set voice status message
     */
    function setVoiceStatus(message) {
        if (voiceStatus) {
            voiceStatus.textContent = message;
        }
    }

    /**
     * Start recording audio
     */
    async function startRecording() {
        if (!currentCaseId || !currentOrganismKey) {
            setStatus('Please start a case first before using voice', true);
            return;
        }

        try {
            console.log('[VOICE] 🎙️ Starting recording...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log('[VOICE] ✅ Got media stream');

            // Try formats in order of OpenAI compatibility
            // MP4/M4A works best, then WebM with opus
            const preferredFormats = [
                'audio/mp4',  // Best for OpenAI, works in Safari
                'audio/webm;codecs=opus',  // Good quality, works in Chrome/Firefox
                'audio/webm',  // Fallback for older browsers
                ''  // Browser default
            ];

            let mimeType = '';
            for (const format of preferredFormats) {
                if (format === '' || MediaRecorder.isTypeSupported(format)) {
                    mimeType = format;
                    break;
                }
            }

            console.log('[VOICE] Using mimeType:', mimeType || 'browser default');
            console.log('[VOICE] Supported formats check:');
            preferredFormats.forEach(fmt => {
                if (fmt) console.log(`  - ${fmt}: ${MediaRecorder.isTypeSupported(fmt) ? '✅' : '❌'}`);
            });

            const options = mimeType ? { mimeType } : {};
            mediaRecorder = new MediaRecorder(stream, options);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                    console.log('[VOICE] 📊 Data chunk received:', event.data.size, 'bytes');
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: mimeType || 'audio/webm' });
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

            mediaRecorder.start();
            isRecording = true;
            recordingStartTime = Date.now();
            setVoiceStatus('🔴 RECORDING - Speak now!');
            setStatus('🎙️ Recording in progress... Release to send');

            // Visual feedback on button
            if (voiceBtn) {
                voiceBtn.style.background = '#dc3545';
                voiceBtn.style.animation = 'pulse 1s infinite';
            }

            console.log('[VOICE] ✅ Recording started successfully at', new Date(recordingStartTime).toISOString());
            console.log('[VOICE] 💡 Speak now! Release button or click again to stop.');

        } catch (error) {
            console.error('[VOICE] ❌ Recording error:', error);
            setStatus('Error accessing microphone: ' + error.message, true);
            setVoiceStatus('❌ Recording failed');
            isRecording = false;
        }
    }

    /**
     * Stop recording audio
     */
    function stopRecording() {
        if (mediaRecorder && isRecording) {
            // Check recording duration
            const duration = Date.now() - recordingStartTime;
            console.log('[VOICE] ⏹️ Stopping recording... Duration:', duration, 'ms');

            if (duration < 500) {
                console.warn('[VOICE] ⚠️ Recording too short:', duration, 'ms (minimum 500ms recommended)');
                setStatus('Recording too short - please hold longer', true);
                setVoiceStatus('⚠️ Too short');

                // Stop and reset
                mediaRecorder.stop();
                isRecording = false;

                // Reset button
                if (voiceBtn) {
                    voiceBtn.style.background = '';
                    voiceBtn.style.animation = '';
                }

                // Reset status after delay
                setTimeout(() => {
                    setVoiceStatus('🎤 Voice ready');
                    setStatus('');
                }, 2000);

                return;
            }

            mediaRecorder.stop();
            isRecording = false;
            setVoiceStatus('⏸️ Processing...');
            setStatus('Processing audio...');

            // Reset button appearance
            if (voiceBtn) {
                voiceBtn.style.background = '';
                voiceBtn.style.animation = '';
            }

            console.log('[VOICE] ✅ Recording stopped after', duration, 'ms, processing...');
        } else {
            console.warn('[VOICE] ⚠️ Stop called but not recording');
        }
    }

    /**
     * Send voice message to API
     */
    async function sendVoiceMessage(audioBlob) {
        console.log('[VOICE] Sending audio to API...');
        console.log('[VOICE] Audio blob type:', audioBlob.type);
        console.log('[VOICE] Audio blob size:', audioBlob.size, 'bytes');

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
            console.log('[VOICE] Sending as:', filename);

            // Create form data
            const formData = new FormData();
            formData.append('audio', audioBlob, filename);
            formData.append('case_id', currentCaseId);
            formData.append('organism_key', currentOrganismKey);
            formData.append('history', JSON.stringify(chatHistory));

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
            chatHistory.push({ role: 'user', content: data.transcribed_text });

            // Add assistant response
            const speakerIcon = data.speaker === 'patient' ? '🤒' : '👨‍⚕️';
            addMessage('assistant', `${speakerIcon} ${data.response_text}`, true);
            chatHistory.push({ role: 'assistant', content: data.response_text });

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

            if (responseAudio) {
                responseAudio.src = audioUrl;
                responseAudio.play();
                console.log('[VOICE] Playing audio response');

                // Clean up URL after playing
                responseAudio.onended = () => {
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
        if (!voiceInitialized) {
            const granted = await requestMicrophonePermission();
            if (!granted) {
                setStatus('Microphone access denied. Check permissions.', true);
                return;
            }
        }

        if (!voiceEnabled) {
            setStatus('Voice is not available. Check microphone permissions.', true);
            return;
        }

        if (!currentCaseId || !currentOrganismKey) {
            setStatus('Please start a case first before using voice', true);
            return;
        }

        // Toggle recording
        if (isRecording) {
            console.log('[VOICE] 🛑 Stopping recording (user clicked button)');
            stopRecording();
            if (voiceBtn) {
                voiceBtn.classList.remove('recording');
                voiceBtn.textContent = '🎤';
            }
        } else {
            console.log('[VOICE] ▶️ Starting recording (user clicked button)');
            startRecording();
            if (voiceBtn) {
                voiceBtn.classList.add('recording');
                voiceBtn.textContent = '⏹️';
            }
        }
    }

    // Voice button event listener - simple toggle on click
    if (voiceBtn) {
        voiceBtn.addEventListener('click', handleVoiceButton);
        voiceBtn.title = 'Click to start/stop voice recording';
    }

    // Check voice availability on load (doesn't request permission yet)
    if (voiceBtn) {
        console.log('[VOICE] Voice button found:', voiceBtn);
        console.log('[VOICE] Voice button disabled state BEFORE check:', voiceBtn.disabled);
        checkVoiceAvailability();
        console.log('[VOICE] Voice button disabled state AFTER check:', voiceBtn.disabled);
    } else {
        console.error('[VOICE] Voice button element not found!');
    }

    // ============================================================
    // END VOICE FUNCTIONALITY
    // ============================================================

    // Initialize
    console.log('[INIT] MicroTutor V4 Frontend initialized');
    if (!loadConversationState()) {
        disableInput(true);
        finishBtn.disabled = true;
    }
});

