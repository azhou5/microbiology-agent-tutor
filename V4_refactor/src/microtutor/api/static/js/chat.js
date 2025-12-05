/**
 * Chat functionality for MicroTutor V4
 */

/**
 * Safely add a message to chat history with validation
 * @param {string} role - Message role (user, assistant, system)
 * @param {string} content - Message content
 */
function addMessageToHistory(role, content) {
    if (!role || !content || typeof content !== 'string' || content.trim().length === 0) {
        console.warn('[CHAT_HISTORY] Skipping invalid message:', { role, content });
        return;
    }

    if (!['user', 'assistant', 'system'].includes(role)) {
        console.warn('[CHAT_HISTORY] Invalid role:', role);
        return;
    }

    State.chatHistory.push({ role, content: content.trim() });
}

/**
 * Set the last tool used (called when processing tool responses)
 * @param {string} toolName - Name of the tool used
 */
function setLastToolUsed(toolName) {
    State.lastToolUsed = toolName;
}

/**
 * Detect speaker type based on tool usage flow
 * @param {string} messageContent - Message content (not used but kept for compatibility)
 * @returns {string} Speaker type
 */
function detectSpeakerType(messageContent) {
    // If we know the last tool used, determine speaker based on that
    if (State.lastToolUsed) {
        switch (State.lastToolUsed) {
            case 'patient':
                return 'patient';
            case 'socratic':
                return 'socratic';
            case 'tests_management':
                return 'tests_management';
            case 'feedback':
                return 'feedback';
            case 'hint':
                return 'hint';
            case 'update_phase':
                return 'tutor'; // Phase updates are from tutor
            default:
                return 'tutor';
        }
    }

    // Fallback: if no tool info, assume tutor
    return 'tutor';
}

/**
 * Get avatar for speaker type
 * @param {string} speakerType - Type of speaker
 * @returns {string} Avatar emoji
 */
function getSpeakerAvatar(speakerType) {
    const avatars = {
        'patient': '🏥',              // Hospital emoji for patient
        'tutor': '👨‍🏫',              // Teacher emoji for tutor
        'socratic': '🤔',             // Thinking emoji for socratic agent
        'tests_management': '🧪',     // Test tube emoji for tests & management
        'feedback': '📋',             // Clipboard emoji for feedback
        'hint': '💡'                  // Lightbulb emoji for hints
    };
    return avatars[speakerType] || '👨‍🏫';
}

/**
 * Create audio player for respiratory sounds
 * @param {Object} audioData - Audio data object
 * @returns {HTMLElement} Audio player container
 */
function createAudioPlayer(audioData) {
    const audioContainer = document.createElement('div');
    audioContainer.classList.add('audio-player-container');

    // Create description
    const description = document.createElement('div');
    description.classList.add('audio-description');
    description.textContent = audioData.description || 'Lung sounds';
    audioContainer.appendChild(description);

    // Create audio element
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.preload = 'metadata';
    audio.classList.add('respiratory-audio');

    // Set audio source
    const audioUrl = `${API_BASE}/audio/respiratory/${audioData.filename}`;
    audio.src = audioUrl;

    // Add error handling
    audio.addEventListener('error', function (e) {
        console.error('Audio loading error:', e);
        const errorDiv = document.createElement('div');
        errorDiv.classList.add('audio-error');
        errorDiv.textContent = 'Audio file could not be loaded';
        audioContainer.appendChild(errorDiv);
    });

    // Add loading indicator
    const loadingDiv = document.createElement('div');
    loadingDiv.classList.add('audio-loading');
    loadingDiv.textContent = 'Loading audio...';
    audioContainer.appendChild(loadingDiv);

    audio.addEventListener('canplay', function () {
        loadingDiv.style.display = 'none';
    });

    audioContainer.appendChild(audio);

    // Add play/pause button for better UX
    const playButton = document.createElement('button');
    playButton.classList.add('audio-play-button');
    playButton.innerHTML = '▶️ Play Lung Sounds';
    playButton.addEventListener('click', function () {
        if (audio.paused) {
            audio.play();
            playButton.innerHTML = '⏸️ Pause';
        } else {
            audio.pause();
            playButton.innerHTML = '▶️ Play Lung Sounds';
        }
    });

    audio.addEventListener('play', function () {
        playButton.innerHTML = '⏸️ Pause';
    });

    audio.addEventListener('pause', function () {
        playButton.innerHTML = '▶️ Play Lung Sounds';
    });

    audioContainer.appendChild(playButton);

    return audioContainer;
}

/**
 * Add a message to the chatbox
 * @param {string} sender - Message sender (user or assistant)
 * @param {string} messageContent - Message content
 * @param {boolean} addFeedbackUI - Whether to add feedback UI
 * @param {string|null} speakerType - Speaker type override
 * @param {Object|null} audioData - Audio data if available
 * @returns {string} Message ID
 */
function addMessage(sender, messageContent, addFeedbackUI = false, speakerType = null, audioData = null) {
    if (!DOM.chatbox) return null;

    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'assistant-message');
    const messageId = 'msg-' + Date.now();
    messageDiv.id = messageId;

    // Create message content wrapper
    const messageContentDiv = document.createElement('div');
    messageContentDiv.classList.add('message-content');

    // Add avatar for assistant messages
    if (sender === 'assistant') {
        const detectedSpeakerType = speakerType || detectSpeakerType(messageContent);
        const avatar = getSpeakerAvatar(detectedSpeakerType);

        const avatarSpan = document.createElement('span');
        avatarSpan.textContent = avatar;
        avatarSpan.classList.add('message-avatar');
        messageContentDiv.appendChild(avatarSpan);
    }

    const messageTextSpan = document.createElement('span');
    messageTextSpan.textContent = messageContent;
    messageContentDiv.appendChild(messageTextSpan);

    messageDiv.appendChild(messageContentDiv);

    // Add audio player if audio data is provided
    if (audioData && audioData.has_audio) {
        const audioPlayer = createAudioPlayer(audioData.audio_data);
        messageDiv.appendChild(audioPlayer);
    }

    // Add feedback UI for assistant messages
    if (sender === 'assistant' && addFeedbackUI) {
        const feedbackContainer = createFeedbackUI(messageId, messageContent);
        messageDiv.appendChild(feedbackContainer);
    }

    DOM.chatbox.appendChild(messageDiv);
    DOM.chatbox.scrollTop = DOM.chatbox.scrollHeight;

    return messageId;
}

/**
 * Set status message
 * @param {string} message - Status message
 * @param {boolean} isError - Whether it's an error message
 */
function setStatus(message, isError = false) {
    if (!DOM.statusMessage) return;
    DOM.statusMessage.textContent = message;
    DOM.statusMessage.className = isError ? 'status error' : 'status';
}

/**
 * Show typing indicator in the chatbox
 */
function showTypingIndicator() {
    if (!DOM.chatbox) return;

    // Remove existing typing indicator if present
    hideTypingIndicator();

    const typingDiv = document.createElement('div');
    typingDiv.id = 'typing-indicator';
    typingDiv.classList.add('message', 'assistant-message', 'typing-indicator');

    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');

    const avatar = document.createElement('span');
    avatar.classList.add('message-avatar');
    avatar.textContent = '🤔';
    contentDiv.appendChild(avatar);

    const dotsContainer = document.createElement('span');
    dotsContainer.classList.add('typing-dots');
    dotsContainer.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    contentDiv.appendChild(dotsContainer);

    typingDiv.appendChild(contentDiv);
    DOM.chatbox.appendChild(typingDiv);
    DOM.chatbox.scrollTop = DOM.chatbox.scrollHeight;
}

/**
 * Hide typing indicator from the chatbox
 */
function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

/**
 * Enable/disable input controls
 * @param {boolean} disabled - Whether to disable inputs
 */
function disableInput(disabled = true) {
    if (DOM.userInput) DOM.userInput.disabled = disabled;
    if (DOM.sendBtn) DOM.sendBtn.disabled = disabled;

    if (disabled) {
        showTypingIndicator();
        if (DOM.statusMessage && !DOM.statusMessage.textContent.includes("Error")) {
            setStatus('Processing...');
        }
    } else {
        hideTypingIndicator();
        if (DOM.statusMessage && DOM.statusMessage.textContent === 'Processing...') {
            setStatus('');
        }
    }
}
