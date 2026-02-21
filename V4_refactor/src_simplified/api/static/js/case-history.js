/**
 * Case History Management
 * Stores and retrieves user-specific case history using localStorage
 */

const CASE_HISTORY_KEY = 'microtutor_case_history';

/**
 * Get all case history
 * @returns {Array} Array of case history objects
 */
function getCaseHistory() {
    try {
        const history = localStorage.getItem(CASE_HISTORY_KEY);
        return history ? JSON.parse(history) : [];
    } catch (error) {
        console.error('[CASE_HISTORY] Error reading history:', error);
        return [];
    }
}

/**
 * Save a case to history
 * @param {Object} caseData - Case data to save
 */
function saveCaseToHistory(caseData) {
    try {
        const history = getCaseHistory();

        // Add timestamp if not present
        if (!caseData.timestamp) {
            caseData.timestamp = new Date().toISOString();
        }

        // Add case ID if not present
        if (!caseData.id) {
            caseData.id = `case_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        }

        // Add to beginning of array (most recent first)
        history.unshift(caseData);

        // Limit to last 50 cases
        if (history.length > 50) {
            history.splice(50);
        }

        localStorage.setItem(CASE_HISTORY_KEY, JSON.stringify(history));
        console.log('[CASE_HISTORY] Case saved to history:', caseData.id);

        // Update UI if history panel exists
        if (typeof updateCaseHistoryUI === 'function') {
            updateCaseHistoryUI();
        }
    } catch (error) {
        console.error('[CASE_HISTORY] Error saving case:', error);
    }
}

/**
 * Get a specific case by ID
 * @param {string} caseId - Case ID
 * @returns {Object|null} Case data or null
 */
function getCaseById(caseId) {
    const history = getCaseHistory();
    return history.find(c => c.id === caseId) || null;
}

/**
 * Extract learning points from MCQs
 * @param {Array} mcqs - Array of MCQ objects
 * @returns {Array} Array of learning points
 */
function extractLearningPoints(mcqs) {
    if (!mcqs || !Array.isArray(mcqs)) return [];

    const learningPoints = [];
    mcqs.forEach(mcq => {
        if (mcq.learning_point) {
            learningPoints.push(mcq.learning_point);
        }
        // Also extract from explanations
        if (mcq.options && Array.isArray(mcq.options)) {
            mcq.options.forEach(opt => {
                if (opt.explanation && opt.is_correct) {
                    // Extract key points from correct answer explanations
                    learningPoints.push(opt.explanation);
                }
            });
        }
    });

    // Remove duplicates and return
    return [...new Set(learningPoints)];
}

/**
 * Calculate MCQ performance summary
 * @param {Object} assessmentScore - Score object with correct/total
 * @param {Object} assessmentAnswers - Object mapping question IDs to answers
 * @param {Array} mcqs - Array of MCQ objects
 * @returns {Object} Performance summary
 */
function calculateMCQPerformance(assessmentScore, assessmentAnswers, mcqs) {
    if (!mcqs || !Array.isArray(mcqs)) {
        return {
            total: 0,
            correct: 0,
            incorrect: 0,
            percentage: 0,
            correctTopics: [],
            incorrectTopics: []
        };
    }

    const correctTopics = [];
    const incorrectTopics = [];

    mcqs.forEach(mcq => {
        const userAnswer = assessmentAnswers[mcq.question_id];
        const correctOption = mcq.options?.find(opt => opt.is_correct);

        if (userAnswer && correctOption) {
            if (userAnswer === correctOption.letter) {
                correctTopics.push(mcq.topic || 'Unknown');
            } else {
                incorrectTopics.push(mcq.topic || 'Unknown');
            }
        }
    });

    return {
        total: assessmentScore.total || mcqs.length,
        correct: assessmentScore.correct || 0,
        incorrect: (assessmentScore.total || mcqs.length) - (assessmentScore.correct || 0),
        percentage: assessmentScore.total > 0
            ? Math.round((assessmentScore.correct / assessmentScore.total) * 100)
            : 0,
        correctTopics: [...new Set(correctTopics)],
        incorrectTopics: [...new Set(incorrectTopics)]
    };
}

/**
 * Prepare case data for saving
 * @param {Object} options - Case data options
 * @returns {Object} Formatted case data
 */
function prepareCaseData({
    caseId,
    organism,
    chatHistory,
    mcqs,
    assessmentScore,
    assessmentAnswers,
    feedbackData,
    weakAreas
}) {
    const learningPoints = extractLearningPoints(mcqs);
    const mcqPerformance = calculateMCQPerformance(assessmentScore, assessmentAnswers, mcqs);

    return {
        id: caseId || `case_${Date.now()}`,
        organism: organism || 'Unknown',
        timestamp: new Date().toISOString(),
        chatHistory: chatHistory || [],
        mcqPerformance: mcqPerformance,
        learningPoints: learningPoints,
        weakAreas: weakAreas || [],
        feedback: feedbackData || {},
        summary: {
            totalMessages: chatHistory?.length || 0,
            mcqScore: mcqPerformance.percentage,
            topicsCovered: [...new Set([
                ...mcqPerformance.correctTopics,
                ...mcqPerformance.incorrectTopics
            ])]
        }
    };
}

/**
 * Clear all case history
 */
function clearCaseHistory() {
    try {
        localStorage.removeItem(CASE_HISTORY_KEY);
        console.log('[CASE_HISTORY] History cleared');
        if (typeof updateCaseHistoryUI === 'function') {
            updateCaseHistoryUI();
        }
    } catch (error) {
        console.error('[CASE_HISTORY] Error clearing history:', error);
    }
}

/**
 * Initialize case history UI
 */
function initializeCaseHistory() {
    const toggleBtn = document.getElementById('toggle-case-history');
    const clearBtn = document.getElementById('clear-case-history');
    const closeModalBtn = document.getElementById('close-case-history-modal');

    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const panel = document.getElementById('case-history-panel');
            const content = document.getElementById('case-history-content');
            if (panel && content) {
                const isExpanded = content.style.display !== 'none';
                content.style.display = isExpanded ? 'none' : 'block';
                toggleBtn.textContent = isExpanded ? '▶' : '▼';
            }
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to clear all case history? This cannot be undone.')) {
                clearCaseHistory();
            }
        });
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            const modal = document.getElementById('case-history-modal');
            if (modal) {
                modal.classList.remove('is-active');
            }
        });
    }

    // Show panel by default
    const panel = document.getElementById('case-history-panel');
    if (panel) {
        panel.style.display = 'block';
    }

    // Initial UI update
    updateCaseHistoryUI();
}

/**
 * Update case history UI
 */
function updateCaseHistoryUI() {
    const historyList = document.getElementById('case-history-list');
    const emptyState = document.getElementById('case-history-empty');

    if (!historyList || !emptyState) return;

    const history = getCaseHistory();

    if (history.length === 0) {
        historyList.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';
    historyList.style.display = 'block';
    historyList.innerHTML = '';

    history.forEach(caseData => {
        const caseItem = createCaseHistoryItem(caseData);
        historyList.appendChild(caseItem);
    });
}

/**
 * Create a case history item element
 * @param {Object} caseData - Case data
 * @returns {HTMLElement} Case item element
 */
function createCaseHistoryItem(caseData) {
    const item = document.createElement('div');
    item.className = 'case-history-item';
    item.dataset.caseId = caseData.id;

    const date = new Date(caseData.timestamp);
    const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const score = caseData.mcqPerformance?.percentage || 0;
    const scoreClass = score >= 80 ? 'score-excellent' : score >= 60 ? 'score-good' : 'score-needs-improvement';

    item.innerHTML = `
        <div class="case-history-item-header">
            <div class="case-history-item-title">
                <strong>${caseData.organism || 'Unknown Organism'}</strong>
                <span class="case-history-date">${dateStr}</span>
            </div>
            <div class="case-history-item-score ${scoreClass}">
                ${score}%
            </div>
        </div>
        <div class="case-history-item-summary">
            <span class="case-history-stat">📝 ${caseData.summary?.totalMessages || 0} messages</span>
            <span class="case-history-stat">📚 ${caseData.learningPoints?.length || 0} learning points</span>
            <span class="case-history-stat">✅ ${caseData.mcqPerformance?.correct || 0}/${caseData.mcqPerformance?.total || 0} correct</span>
        </div>
        <button class="btn btn-small btn-primary view-case-btn">View Details</button>
    `;

    const viewBtn = item.querySelector('.view-case-btn');
    if (viewBtn) {
        viewBtn.addEventListener('click', () => {
            showCaseDetails(caseData);
        });
    }

    return item;
}

/**
 * Show case details in modal
 * @param {Object} caseData - Case data
 */
function showCaseDetails(caseData) {
    const modal = document.getElementById('case-history-modal');
    const detailDiv = document.getElementById('case-history-detail');

    if (!modal || !detailDiv) return;

    const date = new Date(caseData.timestamp);
    const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();

    const score = caseData.mcqPerformance?.percentage || 0;
    const scoreClass = score >= 80 ? 'score-excellent' : score >= 60 ? 'score-good' : 'score-needs-improvement';

    let detailHTML = `
        <div class="case-detail-header">
            <h3>${caseData.organism || 'Unknown Organism'}</h3>
            <p class="case-detail-date">Completed: ${dateStr}</p>
        </div>
        
        <div class="case-detail-section">
            <h4>📊 Performance Summary</h4>
            <div class="case-detail-stats">
                <div class="case-detail-stat">
                    <span class="stat-label">MCQ Score:</span>
                    <span class="stat-value ${scoreClass}">${score}%</span>
                </div>
                <div class="case-detail-stat">
                    <span class="stat-label">Correct:</span>
                    <span class="stat-value">${caseData.mcqPerformance?.correct || 0}/${caseData.mcqPerformance?.total || 0}</span>
                </div>
                <div class="case-detail-stat">
                    <span class="stat-label">Total Messages:</span>
                    <span class="stat-value">${caseData.summary?.totalMessages || 0}</span>
                </div>
            </div>
        </div>
    `;

    // Learning Points
    if (caseData.learningPoints && caseData.learningPoints.length > 0) {
        detailHTML += `
            <div class="case-detail-section">
                <h4>💡 Key Learning Points</h4>
                <ul class="learning-points-list">
                    ${caseData.learningPoints.map(point => `<li>${point}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    // Topics - Correct vs Incorrect
    if (caseData.mcqPerformance) {
        if (caseData.mcqPerformance.correctTopics.length > 0) {
            detailHTML += `
                <div class="case-detail-section">
                    <h4>✅ Topics You Got Right</h4>
                    <div class="topics-list">
                        ${caseData.mcqPerformance.correctTopics.map(topic => `<span class="topic-tag topic-correct">${topic}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        if (caseData.mcqPerformance.incorrectTopics.length > 0) {
            detailHTML += `
                <div class="case-detail-section">
                    <h4>❌ Topics to Review</h4>
                    <div class="topics-list">
                        ${caseData.mcqPerformance.incorrectTopics.map(topic => `<span class="topic-tag topic-incorrect">${topic}</span>`).join('')}
                    </div>
                </div>
            `;
        }
    }

    // Weak Areas
    if (caseData.weakAreas && caseData.weakAreas.length > 0) {
        detailHTML += `
            <div class="case-detail-section">
                <h4>📚 Areas to Review</h4>
                <ul class="weak-areas-list">
                    ${caseData.weakAreas.map(area => `<li>${area}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    // Chat History Preview (first few messages)
    if (caseData.chatHistory && caseData.chatHistory.length > 0) {
        const previewMessages = caseData.chatHistory.slice(0, 5);
        detailHTML += `
            <div class="case-detail-section">
                <h4>💬 Conversation Preview</h4>
                <div class="chat-preview">
                    ${previewMessages.map(msg => `
                        <div class="chat-preview-message ${msg.role}">
                            <strong>${msg.role === 'user' ? 'You' : 'Tutor'}:</strong> ${msg.content.substring(0, 100)}${msg.content.length > 100 ? '...' : ''}
                        </div>
                    `).join('')}
                    ${caseData.chatHistory.length > 5 ? `<p class="chat-preview-more">... and ${caseData.chatHistory.length - 5} more messages</p>` : ''}
                </div>
            </div>
        `;
    }

    detailDiv.innerHTML = detailHTML;
    modal.classList.add('is-active');
}

// Export functions globally
window.getCaseHistory = getCaseHistory;
window.saveCaseToHistory = saveCaseToHistory;
window.getCaseById = getCaseById;
window.prepareCaseData = prepareCaseData;
window.clearCaseHistory = clearCaseHistory;
window.updateCaseHistoryUI = updateCaseHistoryUI;
window.initializeCaseHistory = initializeCaseHistory;
window.showCaseDetails = showCaseDetails;

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCaseHistory);
} else {
    initializeCaseHistory();
}
