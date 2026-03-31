/**
 * LocalStorage operations for MicroTutor V4.
 */

function saveConversationState() {
    try {
        localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(State.chatHistory));
        localStorage.setItem(STORAGE_KEYS.CASE_ID, State.currentCaseId || '');
        localStorage.setItem(STORAGE_KEYS.ORGANISM, State.currentOrganismKey || '');
        localStorage.setItem(STORAGE_KEYS.MODULE, State.currentModule || '');
        localStorage.setItem(STORAGE_KEYS.MODULE_QUEUE, JSON.stringify(State.moduleQueue || []));
        localStorage.setItem(STORAGE_KEYS.SELECTED_MODULES, JSON.stringify(State.selectedModules || []));
        localStorage.setItem(STORAGE_KEYS.ENABLE_MCQS, JSON.stringify(State.enableMcqs));
    } catch (e) {
        console.error('[SAVE] Error saving state:', e);
    }
}

function loadConversationState() {
    try {
        const savedHistory = localStorage.getItem(STORAGE_KEYS.HISTORY);
        const savedCaseId = localStorage.getItem(STORAGE_KEYS.CASE_ID);
        const savedOrganism = localStorage.getItem(STORAGE_KEYS.ORGANISM);
        const savedModule = localStorage.getItem(STORAGE_KEYS.MODULE);
        const savedQueue = localStorage.getItem(STORAGE_KEYS.MODULE_QUEUE);
        const savedSelected = localStorage.getItem(STORAGE_KEYS.SELECTED_MODULES);
        const savedMcqs = localStorage.getItem(STORAGE_KEYS.ENABLE_MCQS);

        if (savedHistory && savedCaseId && savedOrganism) {
            State.chatHistory = JSON.parse(savedHistory);
            State.currentCaseId = savedCaseId;
            State.currentOrganismKey = savedOrganism;
            State.currentModule = savedModule || 'history_taking';
            State.moduleQueue = savedQueue ? JSON.parse(savedQueue) : [];
            State.selectedModules = savedSelected ? JSON.parse(savedSelected) : [];
            State.enableMcqs = savedMcqs ? JSON.parse(savedMcqs) : false;

            if (State.chatHistory.length > 0 && DOM.chatbox) {
                DOM.chatbox.innerHTML = '';
                State.chatHistory.forEach(msg => {
                    if (msg.role !== 'system' && typeof addMessage === 'function') {
                        addMessage(msg.role, msg.content, false);
                    }
                });

                if (typeof disableInput === 'function') disableInput(false);
                if (DOM.finishBtn) DOM.finishBtn.disabled = false;
                if (DOM.organismSelect) DOM.organismSelect.value = State.currentOrganismKey;

                if (State.moduleQueue.length > 0 && typeof buildModuleProgressUI === 'function') {
                    buildModuleProgressUI(State.moduleQueue);
                }
                if (typeof showPhaseProgression === 'function') showPhaseProgression();
                if (typeof updateModuleUI === 'function') updateModuleUI();
                if (typeof setStatus === 'function') {
                    setStatus(`Resumed case. Case ID: ${State.currentCaseId}`);
                }

                if (State.chatHistory.length > 0 && typeof updateCaseSummaryHeader === 'function') {
                    updateCaseSummaryHeader({ history: State.chatHistory });
                }

                console.log('[LOAD] State loaded');
                return true;
            }
        }
    } catch (e) {
        console.error('[LOAD] Error loading state:', e);
        clearConversationState();
    }
    return false;
}

function clearConversationState() {
    try {
        localStorage.removeItem(STORAGE_KEYS.HISTORY);
        localStorage.removeItem(STORAGE_KEYS.CASE_ID);
        localStorage.removeItem(STORAGE_KEYS.ORGANISM);
        localStorage.removeItem(STORAGE_KEYS.MODULE);
        localStorage.removeItem(STORAGE_KEYS.MODULE_QUEUE);
        localStorage.removeItem(STORAGE_KEYS.SELECTED_MODULES);
        localStorage.removeItem(STORAGE_KEYS.ENABLE_MCQS);

        if (typeof hideCaseSummaryHeader === 'function') hideCaseSummaryHeader();
        console.log('[CLEAR] State cleared');
    } catch (e) {
        console.error('[CLEAR] Error clearing state:', e);
    }
}

function getSeenOrganisms() {
    try {
        const saved = localStorage.getItem(STORAGE_KEYS.SEEN_ORGANISMS);
        return saved ? JSON.parse(saved) : [];
    } catch (e) {
        return [];
    }
}

function addSeenOrganism(organismKey) {
    try {
        const seen = getSeenOrganisms();
        if (!seen.includes(organismKey)) {
            seen.push(organismKey);
            localStorage.setItem(STORAGE_KEYS.SEEN_ORGANISMS, JSON.stringify(seen));
        }
    } catch (e) {
        console.error('[STORAGE] Error updating seen organisms:', e);
    }
}

function clearSeenOrganisms() {
    try {
        localStorage.removeItem(STORAGE_KEYS.SEEN_ORGANISMS);
    } catch (e) {
        console.error('[STORAGE] Error clearing seen organisms:', e);
    }
}

function loadFeedbackSettings() {
    try {
        const savedEnabled = localStorage.getItem('microtutor_feedback_enabled');
        const savedThreshold = localStorage.getItem('microtutor_feedback_threshold');

        State.feedbackEnabled = savedEnabled !== null ? savedEnabled === 'true' : true;
        if (DOM.feedbackToggle) DOM.feedbackToggle.checked = State.feedbackEnabled;

        if (savedThreshold !== null) {
            State.feedbackThreshold = parseFloat(savedThreshold);
            if (DOM.thresholdSlider) DOM.thresholdSlider.value = State.feedbackThreshold;
            if (DOM.thresholdValue) DOM.thresholdValue.textContent = State.feedbackThreshold.toFixed(1);
        }
    } catch (e) {
        console.error('[FEEDBACK] Error loading settings:', e);
    }
}

function saveFeedbackSettings() {
    try {
        localStorage.setItem('microtutor_feedback_enabled', State.feedbackEnabled.toString());
        localStorage.setItem('microtutor_feedback_threshold', State.feedbackThreshold.toString());
    } catch (e) {
        console.error('[FEEDBACK] Error saving settings:', e);
    }
}
