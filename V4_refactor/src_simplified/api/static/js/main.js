/**
 * Main initialisation for MicroTutor V4.
 * Wires all modules together on DOMContentLoaded.
 */

document.addEventListener('DOMContentLoaded', () => {
    DOM.init();

    if (typeof initCaseImageLightbox === 'function') {
        initCaseImageLightbox();
    }

    // ── case start ───────────────────────────────────────────────────────
    if (DOM.startCaseBtn) {
        DOM.startCaseBtn.addEventListener('click', handleStartCase);
    }

    // ── chat ─────────────────────────────────────────────────────────────
    if (DOM.sendBtn) {
        DOM.sendBtn.addEventListener('click', () => {
            if (typeof enhancedSendMessage === 'function') {
                enhancedSendMessage();
            } else {
                handleSendMessage();
            }
        });
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

    // ── feedback modal ───────────────────────────────────────────────────
    if (DOM.closeFeedbackBtn) {
        DOM.closeFeedbackBtn.addEventListener('click', closeFeedbackModal);
    }
    if (DOM.submitFeedbackBtn) {
        DOM.submitFeedbackBtn.addEventListener('click', submitCaseFeedback);
    }

    // ── organism select change ───────────────────────────────────────────
    if (DOM.organismSelect) {
        DOM.organismSelect.addEventListener('change', () => {
            resetModuleToFirst();
        });
    }

    // ── EMR refresh button ─────────────────────────────────────────────
    if (DOM.emrRefreshBtn) {
        DOM.emrRefreshBtn.addEventListener('click', handleEMRRefresh);
    }

    // ── module progress button clicks ────────────────────────────────────
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.phase-btn');
        if (btn) {
            const mod = btn.dataset.module;
            if (mod && !btn.disabled) {
                transitionToModule(mod);
            }
        }
    });

    // ── assessment skip buttons (legacy) ─────────────────────────────────
    document.querySelectorAll('.skip-btn').forEach(button => {
        button.addEventListener('click', function () {
            const qName = this.dataset.question;
            document.querySelectorAll(`input[name="${qName}"]`).forEach(r => {
                r.checked = false;
                r.disabled = true;
            });
            this.textContent = 'Skipped';
            this.disabled = true;
        });
    });

    // ── init ─────────────────────────────────────────────────────────────
    console.log('[INIT] MicroTutor V4 Frontend initialised');

    if (!loadConversationState()) {
        disableInput(true);
        if (DOM.finishBtn) DOM.finishBtn.disabled = true;
    }

    if (typeof initializeMCQ === 'function') {
        initializeMCQ();
    }
});
