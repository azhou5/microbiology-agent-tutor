/**
 * API call functions for MicroTutor V4
 */

/**
 * Get all available organisms from the select element
 * @returns {Array<string>} Array of organism values
 */
function getAllOrganisms() {
    if (!DOM.organismSelect) return [];

    const organisms = [];
    const optgroups = DOM.organismSelect.getElementsByTagName('optgroup');

    for (let group of optgroups) {
        const groupOptions = group.getElementsByTagName('option');
        for (let option of groupOptions) {
            if (option.value && option.value !== 'random') {
                organisms.push(option.value);
            }
        }
    }
    return organisms;
}

/**
 * Select a random organism using sampling without replacement
 * @returns {string|null} Selected organism key or null
 */
function selectRandomOrganism() {
    console.log('[RANDOM] Starting random organism selection');

    const allAvailableOrganisms = getAllOrganisms();

    if (allAvailableOrganisms.length === 0) {
        console.log('[RANDOM] No organisms available');
        setStatus('No organisms available to start a case.', true);
        return null;
    }

    // Get seen organisms from localStorage
    const seenOrganisms = getSeenOrganisms();
    console.log('[RANDOM] Previously seen organisms:', seenOrganisms);

    // Determine unseen organisms
    let unseenOrganisms = allAvailableOrganisms.filter(o => !seenOrganisms.includes(o));
    console.log('[RANDOM] Unseen organisms:', unseenOrganisms);

    // Check if we need to reset
    if (unseenOrganisms.length === 0 && allAvailableOrganisms.length > 0) {
        console.log('[RANDOM] All organisms have been seen. Resetting the list.');
        clearSeenOrganisms();
        unseenOrganisms = allAvailableOrganisms;
        setStatus('You have completed all available organisms! The cycle will now repeat.');

        // Try to avoid the very last organism from the previous cycle
        if (unseenOrganisms.length > 1 && State.currentOrganismKey) {
            const finalPool = unseenOrganisms.filter(o => o !== State.currentOrganismKey);
            if (finalPool.length > 0) {
                unseenOrganisms = finalPool;
                console.log(`[RANDOM] Starting new cycle, avoiding last organism '${State.currentOrganismKey}'`);
            }
        }
    }

    // Select from the available pool
    const optionsToUse = unseenOrganisms;
    if (optionsToUse.length === 0) {
        console.error('[RANDOM] No options to select from');
        return null;
    }

    const randomIndex = Math.floor(Math.random() * optionsToUse.length);
    const randomOrganismValue = optionsToUse[randomIndex];
    console.log(`[RANDOM] Selected random organism: ${randomOrganismValue}`);

    // Update the select element to show the random selection
    if (DOM.organismSelect) {
        DOM.organismSelect.value = 'random';
        DOM.organismSelect.dataset.randomlySelectedValue = randomOrganismValue;

        // Find the display text for the selected organism
        const matchedOption = Array.from(DOM.organismSelect.options).find(opt => opt.value === randomOrganismValue);
        const randomOrganismText = matchedOption ? matchedOption.textContent : randomOrganismValue;
        DOM.organismSelect.dataset.randomlySelectedText = randomOrganismText;

        console.log(`[RANDOM] Random selection complete: ${randomOrganismValue} (${randomOrganismText})`);
    }

    return randomOrganismValue;
}

/**
 * Start a new case
 */
async function handleStartCase() {
    console.log('[START_CASE] Starting new case...');

    let selectedOrganism = DOM.organismSelect ? DOM.organismSelect.value : null;

    // Handle random selection
    if (selectedOrganism === 'random') {
        selectedOrganism = selectRandomOrganism();
        if (!selectedOrganism) {
            setStatus('Failed to select random organism.', true);
            return;
        }
    }

    if (!selectedOrganism) {
        setStatus('Please select an organism first.', true);
        return;
    }

    // Clear previous state
    clearConversationState();
    State.chatHistory = [];
    if (DOM.chatbox) DOM.chatbox.innerHTML = '';
    State.currentCaseId = generateCaseId();
    State.currentOrganismKey = selectedOrganism;

    // Reset phase to Information Gathering
    State.currentPhase = 'information_gathering';

    setStatus('Starting new case...');
    disableInput(true);
    if (DOM.finishBtn) DOM.finishBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/start_case`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                organism: State.currentOrganismKey,
                case_id: State.currentCaseId,
                model_name: State.currentModel,
                model_provider: State.currentModelProvider
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || err.error || `HTTP ${response.status}`);
        }

        const data = await response.json();
        console.log('[START_CASE] Response:', data);

        // Initialize history from response with validation
        State.chatHistory = validateChatHistory(data.history);

        // Display messages
        if (DOM.chatbox) DOM.chatbox.innerHTML = '';
        State.chatHistory.forEach(msg => {
            if (msg.role !== 'system') {
                addMessage(msg.role, msg.content, msg.role === 'assistant');
            }
        });

        setStatus(`Case started. Case ID: ${State.currentCaseId}`);
        disableInput(false);
        if (DOM.finishBtn) DOM.finishBtn.disabled = false;
        showPhaseProgression();
        updatePhaseUI();
        saveConversationState();

        // Fetch guidelines if enabled
        if (State.guidelinesEnabled) {
            await fetchGuidelines(State.currentOrganismKey);
        }

        // Update seen organisms list for random selection
        addSeenOrganism(State.currentOrganismKey);

        console.log('[START_CASE] Success!');
    } catch (error) {
        console.error('[START_CASE] Error:', error);
        setStatus(`Error: ${error.message}`, true);
        disableInput(false);
        State.currentOrganismKey = null;
        State.currentCaseId = null;
    }
}

/**
 * Send a chat message
 */
async function handleSendMessage() {
    const messageText = DOM.userInput ? DOM.userInput.value.trim() : '';
    if (!messageText) return;

    // Validate that a case is active
    if (!State.currentCaseId || !State.currentOrganismKey) {
        setStatus('Please start a case first before sending messages.', true);
        return;
    }

    console.log('[CHAT] Sending message...');

    addMessage('user', messageText);
    addMessageToHistory('user', messageText);
    if (DOM.userInput) DOM.userInput.value = '';
    disableInput(true);

    try {
        // Filter out malformed messages before sending
        const validHistory = validateChatHistory(State.chatHistory);

        // Log feedback settings being sent
        console.log(`🎯 [CHAT] Sending Request with Feedback Settings:`);
        console.log(`🔧 [CHAT] Feedback Enabled: ${State.feedbackEnabled}`);
        console.log(`📊 [CHAT] Threshold: ${State.feedbackThreshold.toFixed(1)}`);
        console.log(`🤖 [CHAT] Model: ${State.currentModel} (${State.currentModelProvider})`);

        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: messageText,
                history: validHistory,
                organism_key: State.currentOrganismKey,
                case_id: State.currentCaseId,
                model_name: State.currentModel,
                model_provider: State.currentModelProvider,
                feedback_enabled: State.feedbackEnabled,
                feedback_threshold: State.feedbackThreshold
            }),
        });

        if (!response.ok) {
            const errData = await response.json();

            if (errData.detail && errData.detail.includes('case')) {
                setStatus("Session expired. Please start a new case.", true);
                disableInput(true);
                if (DOM.finishBtn) DOM.finishBtn.disabled = true;
                clearConversationState();
                return;
            }

            throw new Error(errData.detail || errData.error || `HTTP ${response.status}`);
        }

        const data = await response.json();
        console.log('[CHAT] Response:', data);

        // Set tool tracking based on backend response
        if (data.tools_used && data.tools_used.length > 0) {
            // Use the first tool (most relevant for speaker detection)
            setLastToolUsed(data.tools_used[0]);
        } else {
            State.lastToolUsed = null;
        }

        // Check for audio data in response
        let audioData = null;
        let responseText = data.response;

        // Try to parse JSON response for audio data
        try {
            const parsedResponse = JSON.parse(data.response);
            if (parsedResponse.has_audio && parsedResponse.audio_data) {
                audioData = parsedResponse;
                responseText = parsedResponse.response;
            }
        } catch (e) {
            // Not JSON, use as plain text
        }

        const messageId = addMessage('assistant', responseText, true, null, audioData);

        // Filter out malformed messages from server history
        if (data.history) {
            State.chatHistory = validateChatHistory(data.history);
        }
        addMessageToHistory('assistant', data.response);

        // Update phase information from backend metadata
        if (data.metadata) {
            // Update current phase
            if (data.metadata.current_phase && data.metadata.current_phase !== State.currentPhase) {
                State.currentPhase = data.metadata.current_phase;
                updatePhaseUI();
                console.log('[PHASE] Backend phase update:', data.metadata.current_phase);
            }

            // Handle socratic mode phase updates
            if (data.metadata.socratic_mode && data.metadata.current_phase === 'differential_diagnosis') {
                State.currentPhase = 'differential_diagnosis';
                updatePhaseUI();
                console.log('[SOCRATIC] Phase set to differential_diagnosis for socratic mode');
            }

            // Update phase locking
            if (data.metadata.phase_locked !== undefined) {
                updatePhaseLocking(data.metadata.phase_locked);
            }

            // Update phase progress and guidance
            if (data.metadata.phase_progress !== undefined) {
                updatePhaseProgress(data.metadata.phase_progress);
            }

            if (data.metadata.phase_guidance) {
                updatePhaseGuidance(data.metadata.phase_guidance);
            }

            if (data.metadata.completion_criteria) {
                updateCompletionCriteria(data.metadata.completion_criteria);
            }
        }

        // Display feedback examples if available
        if (data.feedback_examples && data.feedback_examples.length > 0) {
            console.log('[FEEDBACK] Displaying feedback examples:', data.feedback_examples);
            if (typeof displayFeedbackExamples === 'function') {
                displayFeedbackExamples(data.feedback_examples, messageId);
            }
        }

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
 * Update model selection based on provider
 */
function updateModelSelection() {
    if (!DOM.azureProvider || !DOM.personalProvider || !DOM.modelSelect) {
        return;
    }

    // Clear all options first
    DOM.modelSelect.innerHTML = '';

    // Update current provider
    if (DOM.azureProvider.checked) {
        const previousProvider = State.currentModelProvider;
        State.currentModelProvider = 'azure';
        if (previousProvider !== 'azure') {
            console.log(`🔄 [FRONTEND] Provider Changed: ${previousProvider.toUpperCase()} → AZURE`);
        }

        // Add Azure models (using actual deployment names)
        const azureOptions = [
            { value: 'gpt-4.1', text: 'GPT-4.1 (2025-04-14)' },
            { value: 'gpt-4o-1120', text: 'GPT-4o (2024-11-20)' },
            { value: 'o4-mini-0416', text: 'o4-mini (2025-04-16)' },
            { value: 'o3-mini-0131', text: 'o3-mini (2025-01-31)' }
        ];

        azureOptions.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.value;
            optionElement.textContent = option.text;
            if (option.value === 'gpt-4.1') {
                optionElement.selected = true;
                State.currentModel = 'gpt-4.1';
            }
            DOM.modelSelect.appendChild(optionElement);
        });

    } else {
        const previousProvider = State.currentModelProvider;
        State.currentModelProvider = 'personal';
        if (previousProvider !== 'personal') {
            console.log(`🔄 [FRONTEND] Provider Changed: ${previousProvider.toUpperCase()} → PERSONAL`);
        }

        // Add Personal models
        const personalOptions = [
            { value: 'o4', text: 'o4' },
            { value: 'gpt-5-mini-2025-08-07', text: 'GPT-5 Mini (2025-08-07)' },
            { value: 'gpt-5-2025-08-07', text: 'GPT-5 (2025-08-07)' },
            { value: 'gpt-4.1-2025-04-14', text: 'GPT-4.1 (2025-04-14)' }
        ];

        personalOptions.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.value;
            optionElement.textContent = option.text;
            if (option.value === 'o4') {
                optionElement.selected = true;
                State.currentModel = 'o4';
            }
            DOM.modelSelect.appendChild(optionElement);
        });
    }

    console.log(`[MODEL] Provider: ${State.currentModelProvider}, Model: ${State.currentModel}`);
}

/**
 * Update current model when selection changes
 */
function updateCurrentModel() {
    if (DOM.modelSelect && DOM.modelSelect.value) {
        const previousModel = State.currentModel;
        State.currentModel = DOM.modelSelect.value;
        console.log(`[MODEL] Selected model: ${State.currentModel}`);
        console.log(`🔄 [FRONTEND] Model Changed: ${previousModel} → ${State.currentModel}`);
        console.log(`🔧 [FRONTEND] Current System: ${State.currentModelProvider.toUpperCase()}`);
        console.log(`🤖 [FRONTEND] Current Model: ${State.currentModel}`);
    }
}

/**
 * Sync frontend configuration with backend
 */
async function syncWithBackendConfig() {
    try {
        console.log('[CONFIG] Syncing with backend configuration...');

        const response = await fetch('/api/v1/config', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const config = await response.json();
        console.log('[CONFIG] Backend configuration:', config);

        // Update provider selection
        if (config.use_azure) {
            if (DOM.azureProvider) DOM.azureProvider.checked = true;
            if (DOM.personalProvider) DOM.personalProvider.checked = false;
            State.currentModelProvider = 'azure';
        } else {
            if (DOM.azureProvider) DOM.azureProvider.checked = false;
            if (DOM.personalProvider) DOM.personalProvider.checked = true;
            State.currentModelProvider = 'personal';
        }

        // Update model selection
        State.currentModel = config.current_model;

        // Refresh model selection UI
        updateModelSelection();

        // Set the correct model in the dropdown
        if (DOM.modelSelect) {
            DOM.modelSelect.value = State.currentModel;
        }

        console.log(`[CONFIG] Synced - Provider: ${State.currentModelProvider}, Model: ${State.currentModel}`);
        console.log(`✅ [FRONTEND] Configuration Synced with Backend`);
        console.log(`🔧 [FRONTEND] System: ${State.currentModelProvider.toUpperCase()}`);
        console.log(`🤖 [FRONTEND] Model: ${State.currentModel}`);

    } catch (error) {
        console.warn('[CONFIG] Failed to sync with backend, using defaults:', error);
        // Continue with default configuration
    }
}
