/**
 * Post-Case Assessment MCQ functionality for MicroTutor V4
 * 
 * Handles:
 * - Generating targeted MCQs after case completion
 * - Displaying MCQs interactively
 * - Tracking answers and scores
 * - Revealing explanations
 */

/**
 * Initialize MCQ assessment functionality
 */
function initializeMCQ() {
    console.log('[MCQ] Initializing post-case assessment functionality');

    // Generate MCQs button
    const generateBtn = document.getElementById('generate-mcqs-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', handleGenerateAssessment);
    }

    // Retry assessment button
    const retryBtn = document.getElementById('retry-assessment-btn');
    if (retryBtn) {
        retryBtn.addEventListener('click', handleRetryAssessment);
    }

    // Start new case button
    const newCaseBtn = document.getElementById('start-new-case-btn');
    if (newCaseBtn) {
        newCaseBtn.addEventListener('click', () => {
            hideAssessmentSection();
            // Reset and show case setup (handled by main.js)
            if (typeof resetForNewCase === 'function') {
                resetForNewCase();
            }
        });
    }

    // Finish case and give feedback button
    const finishCaseFeedbackBtn = document.getElementById('finish-case-feedback-btn');
    if (finishCaseFeedbackBtn) {
        finishCaseFeedbackBtn.addEventListener('click', () => {
            // Mark case as complete
            State.caseComplete = true;

            // Disable the finish button in input area if it exists
            if (DOM.finishBtn) {
                DOM.finishBtn.disabled = true;
                DOM.finishBtn.textContent = '✅ Case Complete';
            }

            // Show the feedback modal
            if (typeof showCaseFeedbackModal === 'function') {
                showCaseFeedbackModal();
            } else if (DOM.feedbackModal) {
                DOM.feedbackModal.classList.add('is-active');
            }
        });
    }

    // Assessment phase button in sidebar - always available
    const assessmentPhaseBtn = document.querySelector('[data-phase="assessment"]');
    if (assessmentPhaseBtn) {
        assessmentPhaseBtn.addEventListener('click', () => {
            showAssessmentSection(false); // false = show generate button (not auto-generating)
        });
    }
}

/**
 * Show the assessment section (called after feedback phase)
 * @param {boolean} autoGenerate - If true, hide the generate button (auto-generating)
 */
function showAssessmentSection(autoGenerate = false) {
    const assessmentSection = document.getElementById('assessment-section');
    if (assessmentSection) {
        assessmentSection.style.display = 'block';

        // Enable the assessment phase button
        const assessmentBtn = document.querySelector('[data-phase="assessment"]');
        if (assessmentBtn) {
            assessmentBtn.disabled = false;
            assessmentBtn.classList.add('active');
        }

        // Show generate button unless auto-generating (from Finish Case)
        const generateBtn = document.getElementById('generate-mcqs-btn');
        if (generateBtn) {
            if (autoGenerate) {
                generateBtn.style.display = 'none';
            } else {
                generateBtn.style.display = 'inline-flex';
                generateBtn.disabled = false;
            }
        }

        // Show loading state immediately when auto-generating
        const loadingDiv = document.getElementById('assessment-loading');
        if (loadingDiv) {
            if (autoGenerate) {
                loadingDiv.style.display = 'flex';
            } else {
                loadingDiv.style.display = 'none';
            }
        }

        // Update phase
        State.currentPhase = 'assessment';
        if (typeof updatePhaseUI === 'function') {
            updatePhaseUI();
        }

        // Scroll to assessment section
        assessmentSection.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Hide the assessment section
 */
function hideAssessmentSection() {
    const assessmentSection = document.getElementById('assessment-section');
    if (assessmentSection) {
        assessmentSection.style.display = 'none';
    }

    // Reset MCQ container
    const mcqContainer = document.getElementById('mcq-container');
    if (mcqContainer) {
        mcqContainer.style.display = 'none';
    }

    // Hide finish section
    const finishSection = document.getElementById('mcq-finish-section');
    if (finishSection) {
        finishSection.style.display = 'none';
    }

    // Hide loading
    const loadingDiv = document.getElementById('assessment-loading');
    if (loadingDiv) {
        loadingDiv.style.display = 'none';
    }
}

/**
 * Handle generate assessment button click
 */
async function handleGenerateAssessment() {
    console.log('[MCQ] Generating post-case assessment');

    // Only require a case to be started, not completed
    if (!State.currentCaseId || !State.currentOrganismKey) {
        setStatus('Please start a case first', true);
        return;
    }

    // Show loading state
    const loadingDiv = document.getElementById('assessment-loading');
    const generateBtn = document.getElementById('generate-mcqs-btn');
    const mcqContainer = document.getElementById('mcq-container');
    const resultsSummary = document.getElementById('mcq-results-summary');

    if (loadingDiv) loadingDiv.style.display = 'flex';
    if (generateBtn) generateBtn.disabled = true;
    if (mcqContainer) mcqContainer.style.display = 'none';
    if (resultsSummary) resultsSummary.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/assessment/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                case_id: State.currentCaseId,
                organism: State.currentOrganismKey,
                conversation_history: State.chatHistory,
                num_questions: MCQ_CONFIG?.defaultNumQuestions || 5
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            // Store MCQs in state
            State.assessmentMCQs = data.result.mcqs;
            State.assessmentWeakAreas = data.result.summary.weak_areas_covered;
            State.resetAssessment();

            // Display MCQs
            displayAssessmentMCQs(data.result.mcqs);

            // Hide loading, show container
            if (loadingDiv) loadingDiv.style.display = 'none';
            if (mcqContainer) mcqContainer.style.display = 'block';
            if (generateBtn) generateBtn.style.display = 'none';

            // Show finish case and feedback button
            const finishSection = document.getElementById('mcq-finish-section');
            if (finishSection) {
                finishSection.style.display = 'block';
            }

            // Reset finish button text
            if (DOM.finishBtn) {
                DOM.finishBtn.textContent = '✅ Case Complete';
                DOM.finishBtn.disabled = true;
            }

            // Add message to chat
            if (typeof addMessage === 'function') {
                addMessage('assistant', '📝 **Assessment Time!** Answer the MCQs below to test your understanding. Case feedback will follow after you complete all questions.', 'tutor');
            }

        } else {
            throw new Error(data.error?.message || 'Failed to generate assessment');
        }

    } catch (error) {
        console.error('[MCQ] Error generating assessment:', error);
        setStatus(`Failed to generate assessment: ${error.message}`, true);
        if (loadingDiv) loadingDiv.style.display = 'none';
        if (generateBtn) generateBtn.disabled = false;

        // Reset finish button on error
        if (DOM.finishBtn) {
            DOM.finishBtn.textContent = '🏁 Finish Case';
            DOM.finishBtn.disabled = false;
        }
    }
}

/**
 * Handle retry assessment button click
 */
async function handleRetryAssessment() {
    State.resetAssessment();

    // Show generate button again
    const generateBtn = document.getElementById('generate-mcqs-btn');
    const mcqContainer = document.getElementById('mcq-container');
    const resultsSummary = document.getElementById('mcq-results-summary');
    const finishSection = document.getElementById('mcq-finish-section');

    if (generateBtn) {
        generateBtn.style.display = 'inline-flex';
        generateBtn.disabled = false;
    }
    if (mcqContainer) mcqContainer.style.display = 'none';
    if (resultsSummary) resultsSummary.style.display = 'none';
    if (finishSection) finishSection.style.display = 'none';

    // Trigger new generation
    await handleGenerateAssessment();
}

/**
 * Display assessment MCQs
 * @param {Array} mcqs - Array of MCQ objects
 */
function displayAssessmentMCQs(mcqs) {
    const questionsList = document.getElementById('mcq-questions-list');
    if (!questionsList) return;

    // Clear previous questions
    questionsList.innerHTML = '';

    // Reset score
    State.assessmentScore = { correct: 0, total: mcqs.length };
    updateScoreDisplay();

    // Create each MCQ
    mcqs.forEach((mcq, index) => {
        const questionDiv = createMCQElement(mcq, index);
        questionsList.appendChild(questionDiv);
    });
}

/**
 * Create MCQ element
 * @param {Object} mcq - MCQ data
 * @param {number} index - Question index
 * @returns {HTMLElement} MCQ element
 */
function createMCQElement(mcq, index) {
    const questionDiv = document.createElement('div');
    questionDiv.className = 'mcq-question-card';
    questionDiv.id = `mcq-${mcq.question_id}`;
    questionDiv.dataset.questionId = mcq.question_id;
    questionDiv.dataset.answered = 'false';

    const weaknessTag = mcq.weakness_addressed
        ? `<span class="mcq-weakness-tag">📍 ${mcq.weakness_addressed}</span>`
        : '';

    questionDiv.innerHTML = `
        <div class="mcq-question-header">
            <span class="mcq-question-number">Question ${index + 1}</span>
            <span class="mcq-topic-tag">${mcq.topic}</span>
            <span class="mcq-difficulty-tag mcq-difficulty-${mcq.difficulty}">${mcq.difficulty}</span>
            ${weaknessTag}
        </div>
        <div class="mcq-question-text">
            <p>${mcq.question_text}</p>
        </div>
        <div class="mcq-options-list">
            ${mcq.options.map(option => createOptionHTML(mcq.question_id, option)).join('')}
        </div>
        <div class="mcq-feedback-section" style="display: none;">
            <div class="mcq-result-banner"></div>
            <div class="mcq-explanations">
                <h5>Explanations:</h5>
                ${mcq.options.map(option => `
                    <div class="mcq-explanation ${option.is_correct ? 'correct' : 'incorrect'}">
                        <span class="option-indicator">${option.letter.toUpperCase()}</span>
                        <span class="explanation-text">${option.explanation}</span>
                    </div>
                `).join('')}
            </div>
            ${mcq.learning_point ? `
                <div class="mcq-learning-point">
                    <strong>💡 Key Learning:</strong> ${mcq.learning_point}
                </div>
            ` : ''}
        </div>
    `;

    // Add click handlers to options
    questionDiv.querySelectorAll('.mcq-option-btn').forEach(btn => {
        btn.addEventListener('click', () => handleOptionClick(mcq.question_id, btn.dataset.letter, mcq));
    });

    return questionDiv;
}

/**
 * Create option HTML
 * @param {string} questionId - Question ID
 * @param {Object} option - Option data
 * @returns {string} HTML string
 */
function createOptionHTML(questionId, option) {
    return `
        <button class="mcq-option-btn" 
                data-question-id="${questionId}" 
                data-letter="${option.letter}"
                data-correct="${option.is_correct}">
            <span class="option-letter">${option.letter.toUpperCase()}</span>
            <span class="option-text">${option.text}</span>
            <span class="option-result-icon"></span>
        </button>
    `;
}

/**
 * Handle option click
 * @param {string} questionId - Question ID
 * @param {string} selectedLetter - Selected option letter
 * @param {Object} mcq - MCQ data
 */
function handleOptionClick(questionId, selectedLetter, mcq) {
    const questionDiv = document.getElementById(`mcq-${questionId}`);
    if (!questionDiv || questionDiv.dataset.answered === 'true') {
        return; // Already answered
    }

    // Mark as answered
    questionDiv.dataset.answered = 'true';
    State.assessmentAnswers[questionId] = selectedLetter;

    // Find the correct answer
    const correctOption = mcq.options.find(opt => opt.is_correct);
    const isCorrect = correctOption && correctOption.letter === selectedLetter;

    // Update score
    if (isCorrect) {
        State.assessmentScore.correct++;
    }
    updateScoreDisplay();

    // Update option styles
    const options = questionDiv.querySelectorAll('.mcq-option-btn');
    options.forEach(btn => {
        btn.disabled = true;
        const letter = btn.dataset.letter;
        const isOptionCorrect = btn.dataset.correct === 'true';

        if (letter === selectedLetter) {
            btn.classList.add('selected');
            btn.classList.add(isCorrect ? 'correct' : 'incorrect');
        }
        if (isOptionCorrect) {
            btn.classList.add('correct-answer');
        }
    });

    // Show feedback section
    const feedbackSection = questionDiv.querySelector('.mcq-feedback-section');
    const resultBanner = questionDiv.querySelector('.mcq-result-banner');

    if (feedbackSection) {
        feedbackSection.style.display = 'block';
    }
    if (resultBanner) {
        resultBanner.className = `mcq-result-banner ${isCorrect ? 'correct' : 'incorrect'}`;
        resultBanner.innerHTML = isCorrect
            ? '✅ Correct!'
            : `❌ Incorrect - The correct answer was ${correctOption?.letter.toUpperCase()}`;
    }

    // Scroll feedback into view
    if (feedbackSection) {
        feedbackSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Check if all questions answered
    checkAssessmentComplete();
}

/**
 * Update score display
 */
function updateScoreDisplay() {
    const scoreElement = document.getElementById('mcq-score');
    const progressBar = document.getElementById('score-progress-bar');

    const { correct, total } = State.assessmentScore;
    const answeredCount = Object.keys(State.assessmentAnswers).length;

    if (scoreElement) {
        scoreElement.textContent = `${correct} / ${total}`;
    }

    if (progressBar) {
        const percentage = total > 0 ? (correct / total) * 100 : 0;
        progressBar.style.width = `${percentage}%`;
        progressBar.className = `score-progress-fill ${percentage >= 70 ? 'good' : percentage >= 50 ? 'okay' : 'poor'}`;
    }
}

/**
 * Check if assessment is complete
 */
function checkAssessmentComplete() {
    const answeredCount = Object.keys(State.assessmentAnswers).length;
    const totalQuestions = State.assessmentMCQs.length;

    if (answeredCount >= totalQuestions && totalQuestions > 0) {
        State.assessmentComplete = true;
        showAssessmentResults();
    }
}

/**
 * Show assessment results summary
 */
function showAssessmentResults() {
    const resultsSummary = document.getElementById('mcq-results-summary');
    if (!resultsSummary) return;

    const { correct, total } = State.assessmentScore;
    const percentage = total > 0 ? Math.round((correct / total) * 100) : 0;
    const incorrect = total - correct;

    // Update stats
    document.getElementById('final-score').textContent = `${percentage}%`;
    document.getElementById('correct-count').textContent = correct;
    document.getElementById('incorrect-count').textContent = incorrect;

    // Update weak areas list
    const weakAreasList = document.getElementById('weak-areas-list');
    if (weakAreasList && State.assessmentWeakAreas.length > 0) {
        weakAreasList.innerHTML = State.assessmentWeakAreas
            .map(area => `<li>${area}</li>`)
            .join('');
    }

    // Show results summary
    resultsSummary.style.display = 'block';
    resultsSummary.scrollIntoView({ behavior: 'smooth' });

    // Add congratulations or encouragement message
    const statsDiv = resultsSummary.querySelector('.results-stats');
    if (statsDiv) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'results-message';
        if (percentage >= 80) {
            messageDiv.innerHTML = '🎉 <strong>Excellent work!</strong> You demonstrated strong understanding of this case.';
        } else if (percentage >= 60) {
            messageDiv.innerHTML = '👍 <strong>Good effort!</strong> Review the explanations above to strengthen your understanding.';
        } else {
            messageDiv.innerHTML = '📚 <strong>Keep learning!</strong> Review the case material and explanations to improve.';
        }
        statsDiv.appendChild(messageDiv);
    }

    // Add "Give Case Feedback" button to results actions
    const resultsActions = resultsSummary.querySelector('.results-actions');
    if (resultsActions) {
        // Check if feedback button already exists
        if (!document.getElementById('give-feedback-btn')) {
            const feedbackBtn = document.createElement('button');
            feedbackBtn.id = 'give-feedback-btn';
            feedbackBtn.className = 'btn btn-warning btn-large';
            feedbackBtn.innerHTML = '<span class="btn-icon">⭐</span> Give Case Feedback';
            feedbackBtn.addEventListener('click', () => {
                if (typeof showCaseFeedbackModal === 'function') {
                    showCaseFeedbackModal();
                } else if (DOM.feedbackModal) {
                    DOM.feedbackModal.classList.add('is-active');
                }
            });
            // Insert as first button
            resultsActions.insertBefore(feedbackBtn, resultsActions.firstChild);
        }
    }
}

/**
 * Enable assessment after feedback phase is complete
 */
function enableAssessmentPhase() {
    State.caseComplete = true;

    // Enable the assessment phase button
    const assessmentBtn = document.querySelector('[data-phase="assessment"]');
    if (assessmentBtn) {
        assessmentBtn.disabled = false;
        assessmentBtn.classList.remove('disabled');
    }

    // Show assessment section
    showAssessmentSection();
}

/**
 * Enhanced message handling to detect MCQ requests
 * Intercepts user messages to check if they're requesting a quiz/MCQ
 * Note: MCQ generation functionality pending full migration
 */
function enhancedSendMessage() {
    // For now, just delegate to the regular message handler
    // MCQ detection can be added once the MCQ generation is fully migrated
    handleSendMessage();
}

// Make functions available globally
window.showAssessmentSection = showAssessmentSection;
window.hideAssessmentSection = hideAssessmentSection;
window.enableAssessmentPhase = enableAssessmentPhase;
window.handleGenerateAssessment = handleGenerateAssessment;
window.enhancedSendMessage = enhancedSendMessage;
