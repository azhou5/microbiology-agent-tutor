/**
 * Main initialization for MicroTutor V4
 * This file ties all modules together and initializes the application
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize DOM references
    DOM.init();

    // Event Listeners
    if (DOM.startCaseBtn) {
        DOM.startCaseBtn.addEventListener('click', handleStartCase);
    }

    if (DOM.sendBtn) {
        DOM.sendBtn.addEventListener('click', enhancedSendMessage);
    }

    if (DOM.userInput) {
        DOM.userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !DOM.sendBtn.disabled) {
                e.preventDefault();
                handleSendMessage();
            }
        });
    }

    if (DOM.finishBtn) {
        DOM.finishBtn.addEventListener('click', handleFinishCase);
    }

    if (DOM.closeFeedbackBtn) {
        DOM.closeFeedbackBtn.addEventListener('click', closeFeedbackModal);
    }

    if (DOM.submitFeedbackBtn) {
        DOM.submitFeedbackBtn.addEventListener('click', submitCaseFeedback);
    }

    // Guidelines toggle handler
    if (DOM.guidelinesToggle) {
        DOM.guidelinesToggle.addEventListener('change', (e) => {
            State.guidelinesEnabled = e.target.checked;
            if (!State.guidelinesEnabled) {
                // Completely hide guidelines results when disabled
                hideGuidelinesResults();
            } else if (State.currentOrganismKey) {
                // Re-fetch and show guidelines if organism is selected
                fetchGuidelines(State.currentOrganismKey);
            }
        });
    }

    // Organism select change handler
    if (DOM.organismSelect) {
        DOM.organismSelect.addEventListener('change', () => {
            // Reset phase to Information Gathering whenever organism selection changes
            resetPhaseToInformationGathering();

            if (DOM.organismSelect.value === 'random') {
                // If random is selected, immediately trigger random selection
                selectRandomOrganism();
            }
        });
    }

    // Model provider toggle handlers
    if (DOM.azureProvider) {
        DOM.azureProvider.addEventListener('change', updateModelSelection);
    }

    if (DOM.personalProvider) {
        DOM.personalProvider.addEventListener('change', updateModelSelection);
    }

    if (DOM.modelSelect) {
        DOM.modelSelect.addEventListener('change', updateCurrentModel);
    }

    // Initialize model selection on page load
    updateModelSelection();

    // Log initial configuration
    console.log(`🚀 [FRONTEND] Initializing MicroTutor V4`);
    console.log(`🔧 [FRONTEND] Initial System: ${State.currentModelProvider.toUpperCase()}`);
    console.log(`🤖 [FRONTEND] Initial Model: ${State.currentModel}`);

    // Sync with backend configuration
    syncWithBackendConfig();

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

    // Voice button event listener
    if (DOM.voiceBtn) {
        DOM.voiceBtn.addEventListener('click', handleVoiceButton);
        DOM.voiceBtn.title = 'Click to start/stop voice recording';
    }

    // Check voice availability on load (doesn't request permission yet)
    if (DOM.voiceBtn) {
        console.log('[VOICE] Voice button found:', DOM.voiceBtn);
        checkVoiceAvailability();
    } else {
        console.error('[VOICE] Voice button element not found!');
    }

    // Phase button event listeners
    document.addEventListener('click', (e) => {
        if (e.target.closest('.phase-btn')) {
            const btn = e.target.closest('.phase-btn');
            const phase = btn.dataset.phase;
            if (phase && !btn.disabled) {
                transitionToPhase(phase);
            }
        }
    });

    // Initialize
    console.log('[INIT] MicroTutor V4 Frontend initialized');
    if (!loadConversationState()) {
        disableInput(true);
        if (DOM.finishBtn) DOM.finishBtn.disabled = true;
    }

    // Initialize dashboard
    initDashboard();

    // Initialize feedback counter
    initializeFeedbackCounter();

    // Initialize feedback controls
    initializeFeedbackControls();

    // Initialize MCQ functionality
    initializeMCQ();
});
