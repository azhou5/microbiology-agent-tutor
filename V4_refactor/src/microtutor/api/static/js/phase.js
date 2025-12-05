/**
 * Phase management for MicroTutor V4
 */

/**
 * Show phase progression UI
 */
function showPhaseProgression() {
    const phaseProgression = document.getElementById('phase-progression');
    if (phaseProgression) {
        phaseProgression.style.display = 'block';
    }
}

/**
 * Hide phase progression UI
 */
function hidePhaseProgression() {
    const phaseProgression = document.getElementById('phase-progression');
    if (phaseProgression) {
        phaseProgression.style.display = 'none';
    }
}

/**
 * Reset phase to information gathering
 */
function resetPhaseToInformationGathering() {
    State.currentPhase = 'information_gathering';
    updatePhaseUI();
    console.log('[PHASE] Reset to Information Gathering');
}

/**
 * Update phase UI based on current state
 */
function updatePhaseUI() {
    const phaseButtons = document.querySelectorAll('.phase-btn');
    const guidanceText = document.getElementById('phase-guidance-text');

    if (!phaseButtons.length || !guidanceText) return;

    // Reset all buttons
    phaseButtons.forEach(btn => {
        btn.classList.remove('active', 'completed');
        btn.disabled = false; // Make all buttons clickable
    });

    // Set active phase
    phaseButtons.forEach(btn => {
        const phase = btn.dataset.phase;

        if (phase === State.currentPhase) {
            btn.classList.add('active');
        }
    });

    // Update guidance text
    const phaseDef = PHASE_DEFINITIONS[State.currentPhase];
    if (phaseDef) {
        guidanceText.textContent = phaseDef.guidance;
    }
}

/**
 * Transition to a new phase
 * @param {string} newPhase - New phase identifier
 */
function transitionToPhase(newPhase) {
    // Special handling for assessment phase
    if (newPhase === 'assessment') {
        if (State.caseComplete && typeof showAssessmentSection === 'function') {
            showAssessmentSection();
        } else {
            setStatus('Complete the case first to access assessment', true);
        }
        return;
    }

    if (!State.currentCaseId || !State.currentOrganismKey) {
        setStatus('Please start a case first', true);
        return;
    }

    const phaseDef = PHASE_DEFINITIONS[newPhase];
    if (!phaseDef) {
        console.error('[PHASE] Unknown phase:', newPhase);
        return;
    }

    // Update UI state
    State.currentPhase = newPhase;
    updatePhaseUI();
    saveConversationState();

    // Simply write the phase message to the input textbox and trigger send
    const transitionMessage = `Let's move onto phase: ${phaseDef.name}`;
    if (DOM.userInput) {
        DOM.userInput.value = transitionMessage;
    }

    // Trigger the normal send flow
    handleSendMessage();
}

/**
 * Update phase locking state
 * @param {boolean} isLocked - Whether phase is locked
 */
function updatePhaseLocking(isLocked) {
    const phaseButtons = document.querySelectorAll('.phase-btn');
    phaseButtons.forEach(btn => {
        if (isLocked) {
            btn.classList.add('locked');
            btn.title = 'Phase is locked - complete current phase first';
        } else {
            btn.classList.remove('locked');
            btn.title = '';
        }
    });
}

/**
 * Update phase progress indicator
 * @param {number} progress - Progress value (0-1)
 */
function updatePhaseProgress(progress) {
    const activeBtn = document.querySelector('.phase-btn.active');
    if (activeBtn) {
        // Add progress bar or visual indicator
        let progressBar = activeBtn.querySelector('.progress-bar');
        if (!progressBar) {
            progressBar = document.createElement('div');
            progressBar.className = 'progress-bar';
            activeBtn.appendChild(progressBar);
        }
        progressBar.style.width = `${progress * 100}%`;
    }
}

/**
 * Update phase guidance text
 * @param {string} guidance - Guidance text
 */
function updatePhaseGuidance(guidance) {
    const guidanceText = document.getElementById('phase-guidance-text');
    if (guidanceText && guidance) {
        guidanceText.textContent = guidance;
    }
}

/**
 * Update completion criteria
 * @param {Array<string>} criteria - Array of completion criteria strings
 */
function updateCompletionCriteria(criteria) {
    const guidanceDiv = document.querySelector('.phase-guidance');
    if (guidanceDiv && criteria && criteria.length > 0) {
        let criteriaDiv = guidanceDiv.querySelector('.completion-criteria');
        if (!criteriaDiv) {
            criteriaDiv = document.createElement('div');
            criteriaDiv.className = 'completion-criteria';
            criteriaDiv.innerHTML = '<strong>Completion Criteria:</strong><ul></ul>';
            guidanceDiv.appendChild(criteriaDiv);
        }

        const criteriaList = criteriaDiv.querySelector('ul');
        criteriaList.innerHTML = criteria.map(c => `<li>${c}</li>`).join('');
    }
}
