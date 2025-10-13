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
     * Initialize voice recording
     */
    async function initVoice() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            voiceEnabled = true;
            setVoiceStatus('🎤 Voice ready');
            console.log('[VOICE] Microphone access granted');
            // Stop the stream immediately (we'll request again when recording)
            stream.getTracks().forEach(track => track.stop());
        } catch (error) {
            console.error('[VOICE] Microphone access denied:', error);
            voiceEnabled = false;
            setVoiceStatus('❌ Mic unavailable');
            if (voiceBtn) {
                voiceBtn.disabled = true;
                voiceBtn.title = 'Microphone access denied';
            }
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
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Try to use webm/opus if supported, fallback to default
            let mimeType = 'audio/webm;codecs=opus';
            if (!MediaRecorder.isTypeSupported(mimeType)) {
                mimeType = 'audio/webm';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = ''; // Use default
                }
            }

            const options = mimeType ? { mimeType } : {};
            mediaRecorder = new MediaRecorder(stream, options);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: mimeType || 'audio/webm' });
                console.log('[VOICE] Recording stopped, size:', audioBlob.size, 'bytes');

                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());

                // Send to API
                await sendVoiceMessage(audioBlob);
            };

            mediaRecorder.start();
            isRecording = true;
            setVoiceStatus('🔴 Recording...');
            console.log('[VOICE] Recording started');

        } catch (error) {
            console.error('[VOICE] Recording error:', error);
            setStatus('Error accessing microphone', true);
            isRecording = false;
        }
    }

    /**
     * Stop recording audio
     */
    function stopRecording() {
        if (mediaRecorder && isRecording) {
            mediaRecorder.stop();
            isRecording = false;
            setVoiceStatus('⏸️ Processing...');
            console.log('[VOICE] Stopping recording...');
        }
    }

    /**
     * Send voice message to API
     */
    async function sendVoiceMessage(audioBlob) {
        console.log('[VOICE] Sending audio to API...');
        disableInput(true);
        setStatus('Transcribing and processing...');

        try {
            // Create form data
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
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
     * Handle voice button click
     */
    function handleVoiceButton() {
        if (!voiceEnabled) {
            setStatus('Voice is not available. Check microphone permissions.', true);
            return;
        }

        if (!currentCaseId || !currentOrganismKey) {
            setStatus('Please start a case first before using voice', true);
            return;
        }

        if (isRecording) {
            stopRecording();
            if (voiceBtn) {
                voiceBtn.classList.remove('recording');
            }
        } else {
            startRecording();
            if (voiceBtn) {
                voiceBtn.classList.add('recording');
            }
        }
    }

    // Voice button event listeners
    if (voiceBtn) {
        // Click to toggle recording
        voiceBtn.addEventListener('click', handleVoiceButton);

        // Also support press and hold
        voiceBtn.addEventListener('mousedown', (e) => {
            if (!isRecording) {
                startRecording();
                voiceBtn.classList.add('recording');
            }
        });

        voiceBtn.addEventListener('mouseup', (e) => {
            if (isRecording) {
                stopRecording();
                voiceBtn.classList.remove('recording');
            }
        });

        // Touch support for mobile
        voiceBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            if (!isRecording) {
                startRecording();
                voiceBtn.classList.add('recording');
            }
        });

        voiceBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            if (isRecording) {
                stopRecording();
                voiceBtn.classList.remove('recording');
            }
        });
    }

    // Initialize voice on load
    if (voiceBtn) {
        initVoice();
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

