/**
 * LocalStorage operations for MicroTutor V4
 */

/**
 * Save conversation state to localStorage
 */
function saveConversationState() {
    try {
        localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(State.chatHistory));
        localStorage.setItem(STORAGE_KEYS.CASE_ID, State.currentCaseId || '');
        localStorage.setItem(STORAGE_KEYS.ORGANISM, State.currentOrganismKey || '');
        localStorage.setItem(STORAGE_KEYS.PHASE, State.currentPhase);
        localStorage.setItem(STORAGE_KEYS.PHASE_HISTORY, JSON.stringify(State.phaseHistory));
        console.log('[SAVE] State saved:', {
            historyLength: State.chatHistory.length,
            caseId: State.currentCaseId,
            phase: State.currentPhase
        });
    } catch (e) {
        console.error('[SAVE] Error saving state:', e);
        if (typeof setStatus === 'function') {
            setStatus('Could not save conversation state', true);
        }
    }
}

/**
 * Load conversation state from localStorage
 * @returns {boolean} True if state was loaded successfully
 */
function loadConversationState() {
    try {
        const savedHistory = localStorage.getItem(STORAGE_KEYS.HISTORY);
        const savedCaseId = localStorage.getItem(STORAGE_KEYS.CASE_ID);
        const savedOrganism = localStorage.getItem(STORAGE_KEYS.ORGANISM);
        const savedPhase = localStorage.getItem(STORAGE_KEYS.PHASE);
        const savedPhaseHistory = localStorage.getItem(STORAGE_KEYS.PHASE_HISTORY);

        if (savedHistory && savedCaseId && savedOrganism) {
            State.chatHistory = JSON.parse(savedHistory);
            State.currentCaseId = savedCaseId;
            State.currentOrganismKey = savedOrganism;
            State.currentPhase = savedPhase || 'information_gathering';
            State.phaseHistory = savedPhaseHistory ? JSON.parse(savedPhaseHistory) : [];

            if (State.chatHistory.length > 0 && DOM.chatbox) {
                DOM.chatbox.innerHTML = '';
                State.chatHistory.forEach(msg => {
                    if (msg.role !== 'system') {
                        if (typeof addMessage === 'function') {
                            addMessage(msg.role, msg.content, false);
                        }
                    }
                });

                if (typeof disableInput === 'function') {
                    disableInput(false);
                }
                if (DOM.finishBtn) {
                    DOM.finishBtn.disabled = false;
                }
                if (DOM.organismSelect) {
                    DOM.organismSelect.value = State.currentOrganismKey;
                }
                if (typeof showPhaseProgression === 'function') {
                    showPhaseProgression();
                }
                if (typeof updatePhaseUI === 'function') {
                    updatePhaseUI();
                }
                if (typeof setStatus === 'function') {
                    setStatus(`Resumed case. Case ID: ${State.currentCaseId}`);
                }
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
 * Clear conversation state from localStorage
 */
function clearConversationState() {
    try {
        localStorage.removeItem(STORAGE_KEYS.HISTORY);
        localStorage.removeItem(STORAGE_KEYS.CASE_ID);
        localStorage.removeItem(STORAGE_KEYS.ORGANISM);
        localStorage.removeItem(STORAGE_KEYS.PHASE);
        localStorage.removeItem(STORAGE_KEYS.PHASE_HISTORY);
        console.log('[CLEAR] State cleared');
    } catch (e) {
        console.error('[CLEAR] Error clearing state:', e);
    }
}

/**
 * Get seen organisms from localStorage
 * @returns {Array<string>} Array of seen organism keys
 */
function getSeenOrganisms() {
    try {
        const savedSeen = localStorage.getItem(STORAGE_KEYS.SEEN_ORGANISMS);
        return savedSeen ? JSON.parse(savedSeen) : [];
    } catch (e) {
        console.error('[STORAGE] Error parsing seen organisms:', e);
        return [];
    }
}

/**
 * Add organism to seen list
 * @param {string} organismKey - Organism key to add
 */
function addSeenOrganism(organismKey) {
    try {
        const seenOrganisms = getSeenOrganisms();
        if (!seenOrganisms.includes(organismKey)) {
            seenOrganisms.push(organismKey);
            localStorage.setItem(STORAGE_KEYS.SEEN_ORGANISMS, JSON.stringify(seenOrganisms));
            console.log('[STORAGE] Updated seen organisms list:', seenOrganisms);
        }
    } catch (e) {
        console.error('[STORAGE] Error updating seen organisms list:', e);
    }
}

/**
 * Clear seen organisms list
 */
function clearSeenOrganisms() {
    try {
        localStorage.removeItem(STORAGE_KEYS.SEEN_ORGANISMS);
        console.log('[STORAGE] Cleared seen organisms list');
    } catch (e) {
        console.error('[STORAGE] Error clearing seen organisms:', e);
    }
}

/**
 * Load feedback settings from localStorage
 */
function loadFeedbackSettings() {
    try {
        const savedEnabled = localStorage.getItem('microtutor_feedback_enabled');
        const savedThreshold = localStorage.getItem('microtutor_feedback_threshold');

        if (savedEnabled !== null) {
            State.feedbackEnabled = savedEnabled === 'true';
        } else {
            State.feedbackEnabled = true; // Default to enabled
        }

        if (DOM.feedbackToggle) {
            DOM.feedbackToggle.checked = State.feedbackEnabled;
        }

        if (savedThreshold !== null) {
            State.feedbackThreshold = parseFloat(savedThreshold);
            if (DOM.thresholdSlider) {
                DOM.thresholdSlider.value = State.feedbackThreshold;
            }
            if (DOM.thresholdValue) {
                DOM.thresholdValue.textContent = State.feedbackThreshold.toFixed(1);
            }
        }
    } catch (e) {
        console.error('[FEEDBACK] Error loading settings:', e);
    }
}

/**
 * Save feedback settings to localStorage
 */
function saveFeedbackSettings() {
    try {
        localStorage.setItem('microtutor_feedback_enabled', State.feedbackEnabled.toString());
        localStorage.setItem('microtutor_feedback_threshold', State.feedbackThreshold.toString());
    } catch (e) {
        console.error('[FEEDBACK] Error saving settings:', e);
    }
}
