/**
 * Feedback functionality for MicroTutor V4
 */

/**
 * Create feedback UI for assistant messages
 * @param {string} messageId - Unique message ID
 * @param {string} messageContent - Message content
 * @returns {HTMLElement} Feedback container element
 */
function createFeedbackUI(messageId, messageContent) {
    const feedbackContainer = document.createElement('div');
    feedbackContainer.classList.add('feedback-container');

    // Rating prompt
    const ratingPrompt = document.createElement('span');
    ratingPrompt.textContent = "Rate this response (1-5):";
    ratingPrompt.classList.add('feedback-prompt');
    feedbackContainer.appendChild(ratingPrompt);

    // Rating buttons container
    const ratingButtonsDiv = document.createElement('div');
    ratingButtonsDiv.classList.add('feedback-buttons');

    // Create rating buttons (1-5)
    for (let i = 1; i <= 5; i++) {
        const ratingBtn = document.createElement('button');
        ratingBtn.textContent = i;
        ratingBtn.title = `Rate ${i} out of 5`;
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
                <div class="feedback-rating">✅ Rating: ${ratingElement.dataset.rating}/5</div>
                ${feedbackText.trim() ? `<div class="feedback-text">${feedbackText}</div>` : ''}
            </div>
        `;

        // If replacement provided, add it to chat
        if (replacementText.trim()) {
            addMessage('assistant', replacementText, true);
            addMessageToHistory('assistant', replacementText);
            saveConversationState();
        }
    });

    return feedbackContainer;
}

/**
 * Submit feedback for a message
 * @param {number} rating - Rating (1-5)
 * @param {string} message - Message content
 * @param {string} feedbackText - Feedback text
 * @param {string} replacementText - Replacement text
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
                history: State.chatHistory,
                feedback_text: feedbackText,
                replacement_text: replacementText,
                case_id: State.currentCaseId,
                organism: State.currentOrganismKey
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || err.error || `HTTP ${response.status}`);
        }

        setStatus('Feedback submitted — thank you!');

        // Refresh dashboard data
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }
    } catch (error) {
        console.error('[FEEDBACK] Error:', error);
        setStatus(`Error: ${error.message}`, true);
    }
}

/**
 * Display feedback examples in the chat
 * @param {Array} examples - Array of feedback examples
 * @param {string} messageId - Message ID to attach examples to
 */
function displayFeedbackExamples(examples, messageId) {
    if (!examples || examples.length === 0) return;

    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;

    const feedbackContainer = document.createElement('div');
    feedbackContainer.className = 'feedback-examples';

    const header = document.createElement('h4');
    header.textContent = `🎯 AI Feedback Examples Used (${examples.length} found)`;
    feedbackContainer.appendChild(header);

    examples.forEach((example) => {
        const exampleDiv = document.createElement('div');
        exampleDiv.className = 'feedback-example';

        // Extract the last user input from chat history
        let matchingInput = 'N/A';
        if (example.entry.chat_history && Array.isArray(example.entry.chat_history)) {
            for (let i = example.entry.chat_history.length - 1; i >= 0; i--) {
                const msg = example.entry.chat_history[i];
                if (msg.role === 'user' && msg.content) {
                    matchingInput = msg.content;
                    break;
                }
            }
        }

        // Create the feedback display in the correct format
        const feedbackContent = document.createElement('div');
        feedbackContent.className = 'feedback-content';

        // 1) Matching input that led to this feedback being picked
        const inputDiv = document.createElement('div');
        inputDiv.className = 'feedback-input';
        inputDiv.innerHTML = `<strong>1) Matching Input:</strong> "${matchingInput}"`;

        // 2) Similarity score
        const similarityDiv = document.createElement('div');
        similarityDiv.className = 'feedback-similarity';
        similarityDiv.innerHTML = `<strong>2) Similarity:</strong> ${(example.similarity_score * 100).toFixed(1)}%`;

        // 3) Quality score
        const qualityDiv = document.createElement('div');
        qualityDiv.className = 'feedback-quality-score';
        const qualityText = example.is_positive_example ? '✓ GOOD' : example.is_negative_example ? '✗ AVOID' : '~ OK';
        const qualityClass = example.is_positive_example ? 'good' : example.is_negative_example ? 'bad' : 'neutral';
        qualityDiv.innerHTML = `<strong>3) Quality:</strong> <span class="${qualityClass}">${qualityText} (${example.entry.rating}/5)</span>`;

        // 4) Answer that was given
        const givenAnswerDiv = document.createElement('div');
        givenAnswerDiv.className = 'feedback-given-answer';
        givenAnswerDiv.innerHTML = `<strong>4) Answer Given:</strong> ${example.entry.rated_message}`;

        // 5) Feedback text provided by user
        const feedbackTextDiv = document.createElement('div');
        feedbackTextDiv.className = 'feedback-text';
        const feedbackText = example.entry.feedback_text || 'No feedback text provided';
        feedbackTextDiv.innerHTML = `<strong>5) Feedback Text:</strong> ${feedbackText}`;

        // 6) Answer that was suggested (replacement text)
        const suggestedAnswerDiv = document.createElement('div');
        suggestedAnswerDiv.className = 'feedback-suggested-answer';
        const suggestedText = example.entry.replacement_text || 'No suggested answer provided';
        suggestedAnswerDiv.innerHTML = `<strong>6) Suggested Answer:</strong> ${suggestedText}`;

        feedbackContent.appendChild(inputDiv);
        feedbackContent.appendChild(similarityDiv);
        feedbackContent.appendChild(qualityDiv);
        feedbackContent.appendChild(givenAnswerDiv);
        feedbackContent.appendChild(feedbackTextDiv);
        feedbackContent.appendChild(suggestedAnswerDiv);

        exampleDiv.appendChild(feedbackContent);
        feedbackContainer.appendChild(exampleDiv);
    });

    messageDiv.appendChild(feedbackContainer);
}

/**
 * Initialize feedback controls
 */
function initializeFeedbackControls() {
    if (DOM.feedbackToggle) {
        DOM.feedbackToggle.addEventListener('change', (e) => {
            State.feedbackEnabled = e.target.checked;
            console.log('[FEEDBACK] Feedback enabled:', State.feedbackEnabled);
            console.log('🎯 [FEEDBACK] Threshold slider remains adjustable at all times');
            updateFeedbackControlsUI();
            saveFeedbackSettings();
        });
    }

    if (DOM.thresholdSlider) {
        DOM.thresholdSlider.addEventListener('input', (e) => {
            const previousThreshold = State.feedbackThreshold;
            State.feedbackThreshold = parseFloat(e.target.value);
            if (DOM.thresholdValue) {
                DOM.thresholdValue.textContent = State.feedbackThreshold.toFixed(1);
            }

            // Enhanced logging
            console.log(`🎯 [FEEDBACK] Threshold Changed: ${previousThreshold.toFixed(1)} → ${State.feedbackThreshold.toFixed(1)}`);
            console.log(`🔧 [FEEDBACK] Current Threshold: ${State.feedbackThreshold.toFixed(1)}`);
            console.log(`📊 [FEEDBACK] Threshold Mode: ${State.feedbackThreshold >= 0.8 ? 'Strict (Exact Matches)' : State.feedbackThreshold >= 0.5 ? 'Balanced' : 'Loose (More Examples)'}`);

            // Visual feedback
            if (DOM.thresholdValue) {
                DOM.thresholdValue.style.color = State.feedbackThreshold >= 0.8 ? '#e74c3c' : State.feedbackThreshold >= 0.5 ? '#f39c12' : '#27ae60';
            }

            // Show temporary notification
            showThresholdNotification(State.feedbackThreshold);

            saveFeedbackSettings();
        });
    }

    // Load saved settings
    loadFeedbackSettings();
    updateFeedbackControlsUI();

    // Confirm slider is enabled
    console.log('✅ [FEEDBACK] Threshold slider initialized and enabled');
    console.log(`🎯 [FEEDBACK] Current threshold: ${State.feedbackThreshold.toFixed(1)}`);
    console.log(`🔧 [FEEDBACK] Feedback system: ${State.feedbackEnabled ? 'Enabled (Default)' : 'Disabled'}`);
    console.log('💡 [FEEDBACK] In Context Feedback is enabled by default for optimal learning experience');
}

/**
 * Show threshold change notification
 * @param {number} threshold - Threshold value
 */
function showThresholdNotification(threshold) {
    if (!DOM.statusMessage) return;

    const mode = threshold >= 0.8 ? 'Strict (Exact Matches)' :
        threshold >= 0.5 ? 'Balanced' : 'Loose (More Examples)';
    const color = threshold >= 0.8 ? '#e74c3c' :
        threshold >= 0.5 ? '#f39c12' : '#27ae60';

    DOM.statusMessage.innerHTML = `🎯 Threshold: ${threshold.toFixed(1)} - ${mode}`;
    DOM.statusMessage.style.color = color;
    DOM.statusMessage.style.display = 'block';

    // Hide after 3 seconds
    setTimeout(() => {
        if (DOM.statusMessage) {
            DOM.statusMessage.style.display = 'none';
        }
    }, 3000);
}

/**
 * Update feedback controls UI state
 */
function updateFeedbackControlsUI() {
    // Keep threshold slider always enabled so users can adjust it anytime
    // They might want to set it before enabling feedback
    if (DOM.thresholdSlider) {
        DOM.thresholdSlider.disabled = false;  // Always keep enabled for adjustability
    }
    if (DOM.thresholdValue) {
        // Keep full opacity so it's always visible and adjustable
        DOM.thresholdValue.style.opacity = '1';
        // Set color based on threshold value
        DOM.thresholdValue.style.color = State.feedbackThreshold >= 0.8 ? '#e74c3c' : State.feedbackThreshold >= 0.5 ? '#f39c12' : '#27ae60';
    }
}

/**
 * Finish case and automatically generate MCQs
 * Case feedback modal will show AFTER MCQs are completed
 */
function handleFinishCase() {
    console.log('[FINISH] Finishing case - generating MCQs...');

    // Store organism for later use in feedback modal
    if (State.currentOrganismKey && DOM.correctOrganismSpan) {
        DOM.correctOrganismSpan.textContent = State.currentOrganismKey;
    } else if (DOM.correctOrganismSpan) {
        DOM.correctOrganismSpan.textContent = "Unknown";
    }

    // Mark case as complete
    State.caseComplete = true;

    // Disable the finish button to prevent double-clicks
    if (DOM.finishBtn) {
        DOM.finishBtn.disabled = true;
        DOM.finishBtn.textContent = '📝 Generating MCQs...';
    }

    // Show assessment section and auto-generate MCQs
    if (typeof showAssessmentSection === 'function') {
        showAssessmentSection();
    }

    // Automatically trigger MCQ generation
    setTimeout(() => {
        if (typeof handleGenerateAssessment === 'function') {
            handleGenerateAssessment();
        }
    }, 500); // Small delay to let UI update
}

/**
 * Show the case feedback modal (called after MCQs are completed)
 */
function showCaseFeedbackModal() {
    console.log('[FEEDBACK] Showing case feedback modal after MCQs');
    if (DOM.feedbackModal) {
        DOM.feedbackModal.classList.add('is-active');
    }
}

/**
 * Close feedback modal
 */
function closeFeedbackModal() {
    if (DOM.feedbackModal) {
        DOM.feedbackModal.classList.remove('is-active');
    }
}

/**
 * Submit case feedback
 */
async function submitCaseFeedback() {
    const detailRating = document.querySelector('input[name="detail"]:checked');
    const helpfulnessRating = document.querySelector('input[name="helpfulness"]:checked');
    const accuracyRating = document.querySelector('input[name="accuracy"]:checked');
    const comments = document.getElementById('feedback-comments') ? document.getElementById('feedback-comments').value : '';

    if (!detailRating || !helpfulnessRating || !accuracyRating) {
        alert('Please provide a rating for all categories or use skip.');
        return;
    }

    const feedbackData = {
        detail: parseInt(detailRating.value),
        helpfulness: parseInt(helpfulnessRating.value),
        accuracy: parseInt(accuracyRating.value),
        comments: comments,
        case_id: State.currentCaseId,
        organism: State.currentOrganismKey
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

        setStatus('Case feedback submitted! Saving case to history...');
        closeFeedbackModal();

        // Prepare and save case data to history
        if (typeof prepareCaseData === 'function' && typeof saveCaseToHistory === 'function') {
            const caseData = prepareCaseData({
                caseId: State.currentCaseId,
                organism: State.currentOrganismKey,
                chatHistory: State.chatHistory || [],
                mcqs: State.assessmentMCQs || [],
                assessmentScore: State.assessmentScore || { correct: 0, total: 0 },
                assessmentAnswers: State.assessmentAnswers || {},
                feedbackData: feedbackData,
                weakAreas: State.assessmentWeakAreas || []
            });
            saveCaseToHistory(caseData);
        }

        // Refresh dashboard data
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }

        // Reset everything after saving
        resetCaseAfterFeedback();

    } catch (error) {
        console.error('[CASE_FEEDBACK] Error:', error);
        setStatus(`Error submitting feedback: ${error.message}`, true);
    }
}

/**
 * Reset case after feedback is submitted
 */
function resetCaseAfterFeedback() {
    // Hide assessment section
    if (typeof hideAssessmentSection === 'function') {
        hideAssessmentSection();
    }

    // Reset feedback form
    document.querySelectorAll('input[type="radio"]').forEach(radio => radio.checked = false);
    const commentsField = document.getElementById('feedback-comments');
    if (commentsField) commentsField.value = '';
    document.querySelectorAll('.skip-btn').forEach(btn => btn.disabled = false);

    // Clear chat
    if (DOM.chatbox) {
        DOM.chatbox.innerHTML = '<div class="welcome-message"><p>👋 Case completed and saved!</p><p>Select an organism and start a new case.</p></div>';
    }

    // Clear input
    if (DOM.userInput) DOM.userInput.value = '';

    // Disable input
    disableInput(true);
    if (DOM.finishBtn) {
        DOM.finishBtn.disabled = true;
        DOM.finishBtn.textContent = '🏁 Finish Case';
    }

    // Clear state
    clearConversationState();
    State.reset();

    // Reset assessment state
    if (State.resetAssessment) {
        State.resetAssessment();
    }
    State.assessmentMCQs = [];
    State.assessmentAnswers = {};
    State.assessmentScore = { correct: 0, total: 0 };
    State.assessmentWeakAreas = [];
    State.assessmentComplete = false;

    // Reset phase UI
    if (typeof resetPhaseToInformationGathering === 'function') {
        resetPhaseToInformationGathering();
    }
    if (typeof hidePhaseProgression === 'function') {
        hidePhaseProgression();
    }

    // Reset assessment button
    const assessmentBtn = document.querySelector('[data-phase="assessment"]');
    if (assessmentBtn) {
        assessmentBtn.disabled = true;
        assessmentBtn.classList.remove('active');
    }

    // Reset case state
    State.currentCaseId = null;
    State.currentOrganismKey = null;
    State.caseComplete = false;

    setStatus('Case saved to history! Ready for a new case. Select an organism and click Start!');
}

/**
 * Reset for a new case (called after assessment is complete)
 */
function resetForNewCase() {
    // Hide assessment section
    if (typeof hideAssessmentSection === 'function') {
        hideAssessmentSection();
    }

    // Reset UI
    if (DOM.chatbox) {
        DOM.chatbox.innerHTML = '<div class="welcome-message"><p>👋 Case completed!</p><p>Select an organism and start a new case.</p></div>';
    }
    disableInput(true);
    if (DOM.finishBtn) DOM.finishBtn.disabled = true;
    if (DOM.userInput) DOM.userInput.value = '';

    // Clear state
    clearConversationState();
    State.reset();

    // Reset phase UI
    resetPhaseToInformationGathering();
    hidePhaseProgression();

    // Reset assessment button
    const assessmentBtn = document.querySelector('[data-phase="assessment"]');
    if (assessmentBtn) {
        assessmentBtn.disabled = true;
        assessmentBtn.classList.remove('active');
    }

    setStatus('Ready for a new case. Select an organism and click Start!');
}

// Make functions available globally for cross-module access
window.showCaseFeedbackModal = showCaseFeedbackModal;
window.handleFinishCase = handleFinishCase;
window.resetForNewCase = resetForNewCase;
