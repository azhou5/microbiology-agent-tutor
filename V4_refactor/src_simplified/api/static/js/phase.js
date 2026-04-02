/**
 * Module progress management for MicroTutor V4.
 *
 * Dynamically builds the sidebar progress buttons based on the modules
 * the user selected at case-setup time.
 */

function showPhaseProgression() {
    const el = document.getElementById('phase-progression');
    if (el) el.style.display = 'block';
}

function hidePhaseProgression() {
    const el = document.getElementById('phase-progression');
    if (el) el.style.display = 'none';
}

/**
 * Build (or rebuild) the module progress buttons from the module queue
 * returned by the backend.
 * @param {string[]} moduleQueue - ordered list of module IDs
 */
function buildModuleProgressUI(moduleQueue) {
    const container = document.getElementById('module-buttons');
    if (!container) return;
    container.innerHTML = '';

    (moduleQueue || []).forEach(modId => {
        const def = MODULE_DEFINITIONS[modId];
        if (!def) return;

        const btn = document.createElement('button');
        btn.className = 'phase-btn';
        btn.dataset.module = modId;
        btn.innerHTML =
            `<span class="phase-icon">${def.icon}</span>` +
            `<span class="phase-text">${def.name}</span>`;
        container.appendChild(btn);
    });

    updateModuleUI();
}

/**
 * Highlight the active module and mark completed ones.
 */
function updateModuleUI() {
    const buttons = document.querySelectorAll('.phase-btn');
    const guidanceText = document.getElementById('phase-guidance-text');

    buttons.forEach(btn => {
        btn.classList.remove('active', 'completed');
        btn.disabled = false;
    });

    const activeIdx = State.moduleQueue.indexOf(State.currentModule);

    buttons.forEach((btn, idx) => {
        const modId = btn.dataset.module;
        if (modId === State.currentModule) {
            btn.classList.add('active');
        } else if (idx < activeIdx) {
            btn.classList.add('completed');
        }
    });

    const def = MODULE_DEFINITIONS[State.currentModule];
    if (def && guidanceText) {
        guidanceText.textContent = def.guidance;
    }
}

/**
 * Transition to a different module (user clicks a progress button).
 * Goes directly — no intermediate questions. Feedback lives at the end.
 */
function transitionToModule(targetModule) {
    if (!State.currentCaseId || !State.currentOrganismKey) {
        setStatus('Please start a case first', true);
        return;
    }

    const def = MODULE_DEFINITIONS[targetModule];
    if (!def) {
        console.error('[MODULE] Unknown module:', targetModule);
        return;
    }

    State.currentModule = targetModule;
    updateModuleUI();
    saveConversationState();

    const msg = `Let's move onto module: ${def.name}`;
    if (DOM.userInput) DOM.userInput.value = msg;
    handleSendMessage();
}

function resetModuleToFirst() {
    if (State.moduleQueue && State.moduleQueue.length > 0) {
        State.currentModule = State.moduleQueue[0];
    } else {
        State.currentModule = 'history_taking';
    }
    updateModuleUI();
}

function updatePhaseGuidance(guidance) {
    const el = document.getElementById('phase-guidance-text');
    if (el && guidance) el.textContent = guidance;
}
