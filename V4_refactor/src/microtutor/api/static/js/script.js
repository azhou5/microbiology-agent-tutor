/**
 * MicroTutor V4 Frontend JavaScript
 * Modern frontend adapted for FastAPI backend
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const startCaseBtn = document.getElementById('start-case-btn');
    const organismSelect = document.getElementById('organism-select');
    const statusMessage = document.getElementById('status-message');
    const finishBtn = document.getElementById('finish-btn');
    const feedbackModal = document.getElementById('feedback-modal');
    const closeFeedbackBtn = document.getElementById('close-feedback-btn');
    const submitFeedbackBtn = document.getElementById('submit-feedback-btn');
    const correctOrganismSpan = document.getElementById('correct-organism');

    // Voice elements
    const voiceBtn = document.getElementById('voice-btn');
    const voiceStatus = document.getElementById('voice-status');
    const responseAudio = document.getElementById('response-audio');

    // Guidelines control elements
    const guidelinesToggle = document.getElementById('guidelines-toggle');
    const guidelinesResults = document.getElementById('guidelines-results');
    const guidelinesStatus = document.getElementById('guidelines-status');
    const guidelinesCount = document.getElementById('guidelines-count');
    const guidelinesContent = document.getElementById('guidelines-content');

    // Feedback control elements
    const feedbackToggle = document.getElementById('feedback-toggle');
    const thresholdSlider = document.getElementById('threshold-slider');
    const thresholdValue = document.getElementById('threshold-value');

    // Dashboard elements
    const messageFeedbackCount = document.getElementById('message-feedback-count');
    const caseFeedbackCount = document.getElementById('case-feedback-count');
    const avgRating = document.getElementById('avg-rating');
    const lastUpdated = document.getElementById('last-updated');
    const refreshStatsBtn = document.getElementById('refresh-stats-btn');
    const autoRefreshToggle = document.getElementById('auto-refresh-toggle');

    // Chart elements
    const trendsCanvas = document.getElementById('trends-canvas');
    const toggleChartBtn = document.getElementById('toggle-chart-btn');

    // Trend elements
    const messageTrend = document.getElementById('message-trend');
    const caseTrend = document.getElementById('case-trend');
    const ratingTrend = document.getElementById('rating-trend');
    const updateTrend = document.getElementById('update-trend');

    // FAISS status elements
    const faissStatus = document.getElementById('faiss-status');
    const faissTrend = document.getElementById('faiss-trend');
    const faissIcon = document.getElementById('faiss-icon');
    const faissLoading = document.getElementById('faiss-loading');

    // API Configuration
    const API_BASE = '/api/v1';

    // MCQ functionality
    let currentMCQ = null;
    let currentSessionId = null;

    // State
    let chatHistory = [];
    let currentCaseId = null;
    let currentOrganismKey = null;
    let currentPhase = 'information_gathering';
    let currentModelProvider = 'azure';
    let currentModel = 'gpt-4.1';  // Default to gpt-4.1
    let guidelinesEnabled = true;
    let currentGuidelines = null;

    /**
     * Validate and filter chat history messages
     */
    function validateChatHistory(history) {
        if (!Array.isArray(history)) {
            return [];
        }

        return history.filter(msg => {
            return msg &&
                typeof msg === 'object' &&
                msg.role &&
                typeof msg.role === 'string' &&
                msg.content &&
                typeof msg.content === 'string' &&
                msg.content.trim().length > 0 &&
                ['user', 'assistant', 'system'].includes(msg.role);
        });
    }

    /**
     * Safely add a message to chat history with validation
     */
    function addMessageToHistory(role, content) {
        if (!role || !content || typeof content !== 'string' || content.trim().length === 0) {
            console.warn('[CHAT_HISTORY] Skipping invalid message:', { role, content });
            return;
        }

        if (!['user', 'assistant', 'system'].includes(role)) {
            console.warn('[CHAT_HISTORY] Invalid role:', role);
            return;
        }

        chatHistory.push({ role, content: content.trim() });
    }
    let phaseHistory = [];

    // Feedback state - enabled by default
    let feedbackEnabled = true;
    let feedbackThreshold = 0.7;

    // Dashboard state
    let chartInstance = null;
    let chartVisible = true;

    // Voice state
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    let voiceEnabled = false;
    let voiceInitialized = false; // Track if we've attempted initialization
    let recordingStartTime = null; // Track when recording started

    // Feedback counter state
    let autoRefreshInterval = null;
    let isRefreshing = false;

    // LocalStorage keys
    const STORAGE_KEYS = {
        HISTORY: 'microtutor_v4_chat_history',
        CASE_ID: 'microtutor_v4_case_id',
        ORGANISM: 'microtutor_v4_organism',
        SEEN_ORGANISMS: 'microtutor_v4_seen_organisms',
        PHASE: 'microtutor_v4_current_phase',
        PHASE_HISTORY: 'microtutor_v4_phase_history'
    };

    // Phase definitions and guidance
    const PHASE_DEFINITIONS = {
        information_gathering: {
            name: 'Information Gathering',
            icon: '📋',
            guidance: 'Gather key history and examination findings from the patient. Ask about symptoms, duration, and physical exam.',
            nextPhase: 'differential_diagnosis'
        },
        differential_diagnosis: {
            name: 'Differential Diagnosis & Clinical Reasoning',
            icon: '🔍',
            guidance: 'Organize clinical information and develop differential diagnoses. Consider the most likely causes based on your findings.',
            nextPhase: 'tests_management'
        },
        tests_management: {
            name: 'Tests & Management',
            icon: '🧪',
            guidance: 'Order relevant investigations and propose treatments. Consider what would confirm or rule out each diagnosis and develop a management plan.',
            nextPhase: 'feedback'
        },
        feedback: {
            name: 'Feedback',
            icon: '✅',
            guidance: 'Receive feedback on the case. Review your performance and clinical reasoning.',
            nextPhase: null
        }
    };

    /**
     * Save conversation state to localStorage
     */
    function saveConversationState() {
        try {
            localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(chatHistory));
            localStorage.setItem(STORAGE_KEYS.CASE_ID, currentCaseId || '');
            localStorage.setItem(STORAGE_KEYS.ORGANISM, currentOrganismKey || '');
            localStorage.setItem(STORAGE_KEYS.PHASE, currentPhase);
            localStorage.setItem(STORAGE_KEYS.PHASE_HISTORY, JSON.stringify(phaseHistory));
            console.log('[SAVE] State saved:', {
                historyLength: chatHistory.length,
                caseId: currentCaseId,
                phase: currentPhase
            });
        } catch (e) {
            console.error('[SAVE] Error saving state:', e);
            setStatus('Could not save conversation state', true);
        }
    }

    /**
     * Load conversation state from localStorage
     */
    function loadConversationState() {
        try {
            const savedHistory = localStorage.getItem(STORAGE_KEYS.HISTORY);
            const savedCaseId = localStorage.getItem(STORAGE_KEYS.CASE_ID);
            const savedOrganism = localStorage.getItem(STORAGE_KEYS.ORGANISM);
            const savedPhase = localStorage.getItem(STORAGE_KEYS.PHASE);
            const savedPhaseHistory = localStorage.getItem(STORAGE_KEYS.PHASE_HISTORY);

            if (savedHistory && savedCaseId && savedOrganism) {
                chatHistory = JSON.parse(savedHistory);
                currentCaseId = savedCaseId;
                currentOrganismKey = savedOrganism;
                currentPhase = savedPhase || 'information_gathering';
                phaseHistory = savedPhaseHistory ? JSON.parse(savedPhaseHistory) : [];

                if (chatHistory.length > 0) {
                    chatbox.innerHTML = '';
                    chatHistory.forEach(msg => {
                        if (msg.role !== 'system') {
                            addMessage(msg.role, msg.content, false);
                        }
                    });

                    disableInput(false);
                    finishBtn.disabled = false;
                    organismSelect.value = currentOrganismKey;
                    showPhaseProgression();
                    updatePhaseUI();
                    setStatus(`Resumed case. Case ID: ${currentCaseId}`);
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
     * Clear conversation state
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
        currentPhase = 'information_gathering';
        updatePhaseUI();
        console.log('[PHASE] Reset to Information Gathering');
    }

    /**
     * Guidelines functionality
     */
    function updateGuidelinesStatus(status, count = 0) {
        guidelinesStatus.textContent = status;
        guidelinesCount.textContent = `${count} results`;

        if (status.includes('Loading') || status.includes('⏳')) {
            guidelinesStatus.className = 'status-indicator loading';
        } else if (status.includes('Error') || status.includes('❌')) {
            guidelinesStatus.className = 'status-indicator error';
        } else if (status.includes('Success') || status.includes('✅')) {
            guidelinesStatus.className = 'status-indicator success';
        } else {
            guidelinesStatus.className = 'status-indicator';
        }
    }

    function displayGuidelines(guidelines) {
        if (!guidelines || !guidelines.organism) {
            guidelinesContent.innerHTML = '<div class="guidelines-loading">No guidelines available</div>';
            return;
        }

        let html = '';

        // Clinical Guidelines
        if (guidelines.clinical_guidelines) {
            const fullText = guidelines.clinical_guidelines;
            const truncated = truncateText(fullText, 300);
            const displayText = markdownToHtml(truncated.isTruncated ? truncated.text : fullText);

            html += `
                <div class="guideline-section">
                    <h5>🏥 Clinical Guidelines</h5>
                    <div class="guideline-item">
                        <div class="guideline-abstract">
                            <div class="guideline-text" data-full="${escapeHtml(fullText)}">${displayText}</div>
                            ${truncated.isTruncated ? `
                                <button class="expand-btn" onclick="toggleGuidelineText(this)">+ Show More</button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }

        // Diagnostic Approach
        if (guidelines.diagnostic_approach) {
            const fullText = guidelines.diagnostic_approach;
            const truncated = truncateText(fullText, 300);
            const displayText = markdownToHtml(truncated.isTruncated ? truncated.text : fullText);

            html += `
                <div class="guideline-section">
                    <h5>🔍 Diagnostic Approach</h5>
                    <div class="guideline-item">
                        <div class="guideline-abstract">
                            <div class="guideline-text" data-full="${escapeHtml(fullText)}">${displayText}</div>
                            ${truncated.isTruncated ? `
                                <button class="expand-btn" onclick="toggleGuidelineText(this)">+ Show More</button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }

        // Treatment Protocols
        if (guidelines.treatment_protocols) {
            const fullText = guidelines.treatment_protocols;
            const truncated = truncateText(fullText, 300);
            const displayText = markdownToHtml(truncated.isTruncated ? truncated.text : fullText);

            html += `
                <div class="guideline-section">
                    <h5>💊 Treatment Protocols</h5>
                    <div class="guideline-item">
                        <div class="guideline-abstract">
                            <div class="guideline-text" data-full="${escapeHtml(fullText)}">${displayText}</div>
                            ${truncated.isTruncated ? `
                                <button class="expand-btn" onclick="toggleGuidelineText(this)">+ Show More</button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }

        // Recent Evidence
        if (guidelines.recent_evidence && guidelines.recent_evidence.length > 0) {
            html += `
                <div class="guideline-section">
                    <h5>📚 Recent Evidence</h5>
            `;

            guidelines.recent_evidence.forEach((evidence, index) => {
                const title = evidence.title || 'Research Evidence';
                const fullText = evidence.abstract || evidence.content || 'No abstract available';
                const truncated = truncateText(fullText, 150);
                const displayText = truncated.isTruncated ? truncated.text : fullText;
                const doi = evidence.doi || evidence.url;
                const journal = evidence.journal || evidence.source || 'Research';
                const year = evidence.year || new Date().getFullYear();

                html += `
                    <div class="guideline-item">
                        <div class="guideline-title">${title}</div>
                        <div class="guideline-abstract">
                            <div class="guideline-text" data-full="${escapeHtml(fullText)}">${displayText}</div>
                            ${truncated.isTruncated ? `
                                <button class="expand-btn" onclick="toggleGuidelineText(this)">+ Show More</button>
                            ` : ''}
                        </div>
                        <div class="guideline-meta">
                            <span class="guideline-source">${journal}</span>
                            <span class="guideline-year">${year}</span>
                            <a href="${doi || 'https://pubmed.ncbi.nlm.nih.gov/'}" target="_blank" class="guideline-link">🔗 View Source</a>
                        </div>
                    </div>
                `;
            });

            html += '</div>';
        }

        if (!html) {
            html = '<div class="guidelines-loading">No guidelines found for this organism</div>';
        }

        guidelinesContent.innerHTML = html;
    }

    function truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) {
            return { text: text || '', isTruncated: false };
        }

        const truncated = text.substring(0, maxLength);
        const lastSpace = truncated.lastIndexOf(' ');
        const finalText = lastSpace > maxLength * 0.8 ? truncated.substring(0, lastSpace) : truncated;

        return {
            text: finalText + '...',
            isTruncated: true
        };
    }

    // Helper function to escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Helper function to convert markdown links and formatting to HTML
    function markdownToHtml(text) {
        if (!text) return '';

        // Convert markdown links [text](url) to HTML links
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="guideline-inline-link">$1</a>');

        // Convert bold **text** to <strong>
        text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Convert italic *text* to <em>
        text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Convert line breaks to <br>
        text = text.replace(/\n/g, '<br>');

        // Convert --- separators to <hr>
        text = text.replace(/---/g, '<hr class="guideline-separator">');

        return text;
    }

    // Global function for expand/collapse inline text (accessible from onclick)
    window.toggleGuidelineText = function (button) {
        const textDiv = button.previousElementSibling; // The .guideline-text div
        const fullText = textDiv.getAttribute('data-full');
        const isExpanded = button.classList.contains('expanded');

        if (isExpanded) {
            // Collapse - show truncated version
            const truncated = truncateText(fullText, 300);
            textDiv.innerHTML = markdownToHtml(truncated.text);
            button.textContent = '+ Show More';
            button.classList.remove('expanded');
        } else {
            // Expand - show full text with markdown formatting
            textDiv.innerHTML = markdownToHtml(fullText);
            button.textContent = '− Show Less';
            button.classList.add('expanded');
        }
    };

    function showGuidelinesResults() {
        guidelinesResults.style.display = 'block';
    }

    function hideGuidelinesResults() {
        guidelinesResults.style.display = 'none';
    }

    async function fetchGuidelines(organism) {
        if (!guidelinesEnabled) {
            hideGuidelinesResults();
            return;
        }

        showGuidelinesResults();
        updateGuidelinesStatus('⏳ Loading guidelines...', 0);

        try {
            const response = await fetch(`${API_BASE}/guidelines/fetch`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    organism: organism
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            currentGuidelines = data;

            // Count actual guideline sections found
            let count = 0;
            if (data.clinical_guidelines) count++;
            if (data.diagnostic_approach) count++;
            if (data.treatment_protocols) count++;
            if (data.recent_evidence && data.recent_evidence.length > 0) count += data.recent_evidence.length;

            updateGuidelinesStatus('✅ Guidelines loaded', count);
            displayGuidelines(data);

        } catch (error) {
            console.error('Error fetching guidelines:', error);
            updateGuidelinesStatus('❌ Error loading guidelines', 0);
            guidelinesContent.innerHTML = '<div class="guidelines-loading">Failed to load guidelines. Please try again.</div>';
        }
    }

    /**
     * Update model selection based on provider
     */
    function updateModelSelection() {
        const azureProvider = document.getElementById('azure-provider');
        const personalProvider = document.getElementById('personal-provider');
        const modelSelect = document.getElementById('model-select');

        if (!azureProvider || !personalProvider || !modelSelect) {
            return;
        }

        // Clear all options first
        modelSelect.innerHTML = '';

        // Update current provider
        if (azureProvider.checked) {
            const previousProvider = currentModelProvider;
            currentModelProvider = 'azure';
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
                    currentModel = 'gpt-4.1';
                }
                modelSelect.appendChild(optionElement);
            });

        } else {
            const previousProvider = currentModelProvider;
            currentModelProvider = 'personal';
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
                    currentModel = 'o4';
                }
                modelSelect.appendChild(optionElement);
            });
        }

        console.log(`[MODEL] Provider: ${currentModelProvider}, Model: ${currentModel}`);
        console.log(`🔧 [FRONTEND] System: ${currentModelProvider.toUpperCase()}`);
        console.log(`🤖 [FRONTEND] Model: ${currentModel}`);
    }

    /**
     * Update current model when selection changes
     */
    function updateCurrentModel() {
        const modelSelect = document.getElementById('model-select');
        if (modelSelect && modelSelect.value) {
            const previousModel = currentModel;
            currentModel = modelSelect.value;
            console.log(`[MODEL] Selected model: ${currentModel}`);
            console.log(`🔄 [FRONTEND] Model Changed: ${previousModel} → ${currentModel}`);
            console.log(`🔧 [FRONTEND] Current System: ${currentModelProvider.toUpperCase()}`);
            console.log(`🤖 [FRONTEND] Current Model: ${currentModel}`);
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
            const azureProvider = document.getElementById('azure-provider');
            const personalProvider = document.getElementById('personal-provider');

            if (config.use_azure) {
                if (azureProvider) azureProvider.checked = true;
                if (personalProvider) personalProvider.checked = false;
                currentModelProvider = 'azure';
            } else {
                if (azureProvider) azureProvider.checked = false;
                if (personalProvider) personalProvider.checked = true;
                currentModelProvider = 'personal';
            }

            // Update model selection
            currentModel = config.current_model;

            // Refresh model selection UI
            updateModelSelection();

            // Set the correct model in the dropdown
            const modelSelect = document.getElementById('model-select');
            if (modelSelect) {
                modelSelect.value = currentModel;
            }

            console.log(`[CONFIG] Synced - Provider: ${currentModelProvider}, Model: ${currentModel}`);
            console.log(`✅ [FRONTEND] Configuration Synced with Backend`);
            console.log(`🔧 [FRONTEND] System: ${currentModelProvider.toUpperCase()}`);
            console.log(`🤖 [FRONTEND] Model: ${currentModel}`);

        } catch (error) {
            console.warn('[CONFIG] Failed to sync with backend, using defaults:', error);
            // Continue with default configuration
        }
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

            if (phase === currentPhase) {
                btn.classList.add('active');
            }
        });

        // Update guidance text
        const phaseDef = PHASE_DEFINITIONS[currentPhase];
        if (phaseDef) {
            guidanceText.textContent = phaseDef.guidance;
        }
    }

    /**
     * Transition to a new phase
     */
    function transitionToPhase(newPhase) {
        if (!currentCaseId || !currentOrganismKey) {
            setStatus('Please start a case first', true);
            return;
        }

        const phaseDef = PHASE_DEFINITIONS[newPhase];
        if (!phaseDef) {
            console.error('[PHASE] Unknown phase:', newPhase);
            return;
        }

        // Update UI state
        currentPhase = newPhase;
        updatePhaseUI();
        saveConversationState();

        // Simply write the phase message to the input textbox and trigger send
        const transitionMessage = `Let's move onto phase: ${phaseDef.name}`;
        userInput.value = transitionMessage;

        // Trigger the normal send flow
        handleSendMessage();
    }

    /**
     * Update phase locking state
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
     */
    function updatePhaseGuidance(guidance) {
        const guidanceText = document.getElementById('phase-guidance-text');
        if (guidanceText && guidance) {
            guidanceText.textContent = guidance;
        }
    }

    /**
     * Update completion criteria
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

    /**
     * Get all available organisms from the select element
     */
    function getAllOrganisms() {
        const organisms = [];
        const optgroups = organismSelect.getElementsByTagName('optgroup');

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
        let seenOrganisms = [];
        try {
            const savedSeen = localStorage.getItem(STORAGE_KEYS.SEEN_ORGANISMS);
            if (savedSeen) {
                seenOrganisms = JSON.parse(savedSeen);
            }
        } catch (e) {
            console.error('[RANDOM] Error parsing seen organisms:', e);
            seenOrganisms = [];
        }

        console.log('[RANDOM] Previously seen organisms:', seenOrganisms);

        // Determine unseen organisms
        let unseenOrganisms = allAvailableOrganisms.filter(o => !seenOrganisms.includes(o));
        console.log('[RANDOM] Unseen organisms:', unseenOrganisms);

        // Check if we need to reset
        if (unseenOrganisms.length === 0 && allAvailableOrganisms.length > 0) {
            console.log('[RANDOM] All organisms have been seen. Resetting the list.');
            localStorage.removeItem(STORAGE_KEYS.SEEN_ORGANISMS);
            seenOrganisms = [];
            unseenOrganisms = allAvailableOrganisms;
            setStatus('You have completed all available organisms! The cycle will now repeat.');

            // Try to avoid the very last organism from the previous cycle
            if (unseenOrganisms.length > 1 && currentOrganismKey) {
                const finalPool = unseenOrganisms.filter(o => o !== currentOrganismKey);
                if (finalPool.length > 0) {
                    unseenOrganisms = finalPool;
                    console.log(`[RANDOM] Starting new cycle, avoiding last organism '${currentOrganismKey}'`);
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
        organismSelect.value = 'random';
        organismSelect.dataset.randomlySelectedValue = randomOrganismValue;

        // Find the display text for the selected organism
        const allOptions = getAllOrganisms();
        const matchedOption = Array.from(organismSelect.options).find(opt => opt.value === randomOrganismValue);
        const randomOrganismText = matchedOption ? matchedOption.textContent : randomOrganismValue;
        organismSelect.dataset.randomlySelectedText = randomOrganismText;

        console.log(`[RANDOM] Random selection complete: ${randomOrganismValue} (${randomOrganismText})`);
        return randomOrganismValue;
    }

    /**
     * Generate unique case ID
     */
    function generateCaseId() {
        return 'case_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Track the last tool used to determine speaker
    let lastToolUsed = null;

    /**
     * Set the last tool used (called when processing tool responses)
     */
    function setLastToolUsed(toolName) {
        lastToolUsed = toolName;
    }

    /**
     * Detect speaker type based on tool usage flow
     */
    function detectSpeakerType(messageContent) {
        // If we know the last tool used, determine speaker based on that
        if (lastToolUsed) {
            switch (lastToolUsed) {
                case 'patient':
                    return 'patient';
                case 'socratic':
                    return 'socratic';
                case 'tests_management':
                    return 'tests_management';
                case 'feedback':
                    return 'feedback';
                case 'hint':
                    return 'hint';
                case 'update_phase':
                    return 'tutor'; // Phase updates are from tutor
                default:
                    return 'tutor';
            }
        }

        // Fallback: if no tool info, assume tutor
        return 'tutor';
    }

    /**
     * Get avatar for speaker type
     */
    function getSpeakerAvatar(speakerType) {
        const avatars = {
            'patient': '🏥',              // Hospital emoji for patient
            'tutor': '👨‍🏫',              // Teacher emoji for tutor
            'socratic': '🤔',             // Thinking emoji for socratic agent
            'tests_management': '🧪',     // Test tube emoji for tests & management
            'feedback': '📋',             // Clipboard emoji for feedback
            'hint': '💡'                  // Lightbulb emoji for hints
        };
        return avatars[speakerType] || '👨‍🏫';
    }

    /**
     * Create audio player for respiratory sounds
     */
    function createAudioPlayer(audioData) {
        const audioContainer = document.createElement('div');
        audioContainer.classList.add('audio-player-container');

        // Create description
        const description = document.createElement('div');
        description.classList.add('audio-description');
        description.textContent = audioData.description || 'Lung sounds';
        audioContainer.appendChild(description);

        // Create audio element
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.preload = 'metadata';
        audio.classList.add('respiratory-audio');

        // Set audio source
        const audioUrl = `${API_BASE}/audio/respiratory/${audioData.filename}`;
        audio.src = audioUrl;

        // Add error handling
        audio.addEventListener('error', function (e) {
            console.error('Audio loading error:', e);
            const errorDiv = document.createElement('div');
            errorDiv.classList.add('audio-error');
            errorDiv.textContent = 'Audio file could not be loaded';
            audioContainer.appendChild(errorDiv);
        });

        // Add loading indicator
        const loadingDiv = document.createElement('div');
        loadingDiv.classList.add('audio-loading');
        loadingDiv.textContent = 'Loading audio...';
        audioContainer.appendChild(loadingDiv);

        audio.addEventListener('canplay', function () {
            loadingDiv.style.display = 'none';
        });

        audioContainer.appendChild(audio);

        // Add play/pause button for better UX
        const playButton = document.createElement('button');
        playButton.classList.add('audio-play-button');
        playButton.innerHTML = '▶️ Play Lung Sounds';
        playButton.addEventListener('click', function () {
            if (audio.paused) {
                audio.play();
                playButton.innerHTML = '⏸️ Pause';
            } else {
                audio.pause();
                playButton.innerHTML = '▶️ Play Lung Sounds';
            }
        });

        audio.addEventListener('play', function () {
            playButton.innerHTML = '⏸️ Pause';
        });

        audio.addEventListener('pause', function () {
            playButton.innerHTML = '▶️ Play Lung Sounds';
        });

        audioContainer.appendChild(playButton);

        return audioContainer;
    }

    /**
     * Add a message to the chatbox
     */
    function addMessage(sender, messageContent, addFeedbackUI = false, speakerType = null, audioData = null) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'assistant-message');
        const messageId = 'msg-' + Date.now();
        messageDiv.id = messageId;

        // Create message content wrapper
        const messageContentDiv = document.createElement('div');
        messageContentDiv.classList.add('message-content');

        // Add avatar for assistant messages
        if (sender === 'assistant') {
            const detectedSpeakerType = speakerType || detectSpeakerType(messageContent);
            const avatar = getSpeakerAvatar(detectedSpeakerType);

            const avatarSpan = document.createElement('span');
            avatarSpan.textContent = avatar;
            avatarSpan.classList.add('message-avatar');
            messageContentDiv.appendChild(avatarSpan);
        }

        const messageTextSpan = document.createElement('span');
        messageTextSpan.textContent = messageContent;
        messageContentDiv.appendChild(messageTextSpan);

        messageDiv.appendChild(messageContentDiv);

        // Add audio player if audio data is provided
        if (audioData && audioData.has_audio) {
            const audioPlayer = createAudioPlayer(audioData.audio_data);
            messageDiv.appendChild(audioPlayer);
        }

        // Add feedback UI for assistant messages
        if (sender === 'assistant' && addFeedbackUI) {
            const feedbackContainer = createFeedbackUI(messageId, messageContent);
            messageDiv.appendChild(feedbackContainer);
        }

        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight;

        return messageId;
    }

    /**
     * Create feedback UI for assistant messages
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
                    history: chatHistory,
                    feedback_text: feedbackText,
                    replacement_text: replacementText,
                    case_id: currentCaseId,
                    organism: currentOrganismKey
                }),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || err.error || `HTTP ${response.status}`);
            }

            setStatus('Feedback submitted — thank you!');

            // Refresh dashboard data
            loadDashboardData();
        } catch (error) {
            console.error('[FEEDBACK] Error:', error);
            setStatus(`Error: ${error.message}`, true);
        }
    }

    /**
     * Set status message
     */
    function setStatus(message, isError = false) {
        statusMessage.textContent = message;
        statusMessage.className = isError ? 'status error' : 'status';
    }

    /**
     * Enable/disable input controls
     */
    function disableInput(disabled = true) {
        userInput.disabled = disabled;
        sendBtn.disabled = disabled;
        if (disabled && !statusMessage.textContent.includes("Error")) {
            setStatus('Processing...');
        } else if (!disabled && statusMessage.textContent === 'Processing...') {
            setStatus('');
        }
    }

    /**
     * Start a new case
     */
    async function handleStartCase() {
        console.log('[START_CASE] Starting new case...');

        let selectedOrganism = organismSelect.value;

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
        chatHistory = [];
        chatbox.innerHTML = '';
        currentCaseId = generateCaseId();
        currentOrganismKey = selectedOrganism;

        // Reset phase to Information Gathering
        currentPhase = 'information_gathering';

        setStatus('Starting new case...');
        disableInput(true);
        finishBtn.disabled = true;

        try {
            const response = await fetch(`${API_BASE}/start_case`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    organism: currentOrganismKey,
                    case_id: currentCaseId,
                    model_name: currentModel,
                    model_provider: currentModelProvider
                }),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || err.error || `HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('[START_CASE] Response:', data);

            // Initialize history from response with validation
            chatHistory = validateChatHistory(data.history);

            // Display messages
            chatbox.innerHTML = '';
            chatHistory.forEach(msg => {
                if (msg.role !== 'system') {
                    addMessage(msg.role, msg.content, msg.role === 'assistant');
                }
            });

            setStatus(`Case started. Case ID: ${currentCaseId}`);
            disableInput(false);
            finishBtn.disabled = false;
            showPhaseProgression();
            updatePhaseUI();
            saveConversationState();

            // Fetch guidelines if enabled
            if (guidelinesEnabled) {
                await fetchGuidelines(currentOrganismKey);
            }

            // Update seen organisms list for random selection
            try {
                const savedSeen = localStorage.getItem(STORAGE_KEYS.SEEN_ORGANISMS);
                let seenOrganisms = savedSeen ? JSON.parse(savedSeen) : [];
                if (!seenOrganisms.includes(currentOrganismKey)) {
                    seenOrganisms.push(currentOrganismKey);
                    localStorage.setItem(STORAGE_KEYS.SEEN_ORGANISMS, JSON.stringify(seenOrganisms));
                    console.log('[START_CASE] Updated seen organisms list:', seenOrganisms);
                }
            } catch (e) {
                console.error('[START_CASE] Error updating seen organisms list:', e);
            }

            console.log('[START_CASE] Success!');
        } catch (error) {
            console.error('[START_CASE] Error:', error);
            setStatus(`Error: ${error.message}`, true);
            disableInput(false);
            currentOrganismKey = null;
            currentCaseId = null;
        }
    }

    /**
     * Send a chat message
     */
    async function handleSendMessage() {
        const messageText = userInput.value.trim();
        if (!messageText) return;

        // Validate that a case is active
        if (!currentCaseId || !currentOrganismKey) {
            setStatus('Please start a case first before sending messages.', true);
            return;
        }

        console.log('[CHAT] Sending message...');

        addMessage('user', messageText);
        addMessageToHistory('user', messageText);
        userInput.value = '';
        disableInput(true);

        try {
            // Filter out malformed messages before sending
            const validHistory = validateChatHistory(chatHistory);

            // Log feedback settings being sent
            console.log(`🎯 [CHAT] Sending Request with Feedback Settings:`);
            console.log(`🔧 [CHAT] Feedback Enabled: ${feedbackEnabled}`);
            console.log(`📊 [CHAT] Threshold: ${feedbackThreshold.toFixed(1)}`);
            console.log(`🤖 [CHAT] Model: ${currentModel} (${currentModelProvider})`);

            const response = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: messageText,
                    history: validHistory,
                    organism_key: currentOrganismKey,
                    case_id: currentCaseId,
                    model_name: currentModel,
                    model_provider: currentModelProvider,
                    feedback_enabled: feedbackEnabled,
                    feedback_threshold: feedbackThreshold
                }),
            });

            if (!response.ok) {
                const errData = await response.json();

                if (errData.detail && errData.detail.includes('case')) {
                    setStatus("Session expired. Please start a new case.", true);
                    disableInput(true);
                    finishBtn.disabled = true;
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
                lastToolUsed = null;
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
                chatHistory = validateChatHistory(data.history);
            }
            addMessageToHistory('assistant', data.response);

            // Update phase information from backend metadata
            if (data.metadata) {
                // Update current phase
                if (data.metadata.current_phase && data.metadata.current_phase !== currentPhase) {
                    currentPhase = data.metadata.current_phase;
                    updatePhaseUI();
                    console.log('[PHASE] Backend phase update:', data.metadata.current_phase);
                }

                // Handle socratic mode phase updates
                if (data.metadata.socratic_mode && data.metadata.current_phase === 'differential_diagnosis') {
                    currentPhase = 'differential_diagnosis';
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
                displayFeedbackExamples(data.feedback_examples, messageId);
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
     * Finish case and show feedback modal
     */
    function handleFinishCase() {
        console.log('[FINISH] Finishing case...');
        if (currentOrganismKey) {
            correctOrganismSpan.textContent = currentOrganismKey;
        } else {
            correctOrganismSpan.textContent = "Unknown";
        }
        feedbackModal.classList.add('is-active');
    }

    /**
     * Close feedback modal
     */
    function closeFeedbackModal() {
        feedbackModal.classList.remove('is-active');
    }

    /**
     * Submit case feedback
     */
    async function submitCaseFeedback() {
        const detailRating = document.querySelector('input[name="detail"]:checked');
        const helpfulnessRating = document.querySelector('input[name="helpfulness"]:checked');
        const accuracyRating = document.querySelector('input[name="accuracy"]:checked');
        const comments = document.getElementById('feedback-comments').value;

        if (!detailRating || !helpfulnessRating || !accuracyRating) {
            alert('Please provide a rating for all categories or use skip.');
            return;
        }

        const feedbackData = {
            detail: parseInt(detailRating.value),
            helpfulness: parseInt(helpfulnessRating.value),
            accuracy: parseInt(accuracyRating.value),
            comments: comments,
            case_id: currentCaseId,
            organism: currentOrganismKey
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

            setStatus('Case feedback submitted! Thank you. You can start a new case.');
            closeFeedbackModal();

            // Refresh dashboard data
            loadDashboardData();

            // Reset UI
            chatbox.innerHTML = '<div class="welcome-message"><p>👋 Case completed!</p><p>Select an organism and start a new case.</p></div>';
            disableInput(true);
            finishBtn.disabled = true;
            userInput.value = '';

            // Clear state
            clearConversationState();
            chatHistory = [];
            currentCaseId = null;
            currentOrganismKey = null;

            // Reset feedback form
            document.querySelectorAll('input[type="radio"]').forEach(radio => radio.checked = false);
            document.getElementById('feedback-comments').value = '';
            document.querySelectorAll('.skip-btn').forEach(btn => btn.disabled = false);

        } catch (error) {
            console.error('[CASE_FEEDBACK] Error:', error);
            setStatus(`Error submitting feedback: ${error.message}`, true);
        }
    }

    // Event Listeners
    if (startCaseBtn) {
        startCaseBtn.addEventListener('click', handleStartCase);
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', enhancedSendMessage);
    }

    if (userInput) {
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !sendBtn.disabled) {
                e.preventDefault();
                handleSendMessage();
            }
        });
    }

    if (finishBtn) {
        finishBtn.addEventListener('click', handleFinishCase);
    }

    if (closeFeedbackBtn) {
        closeFeedbackBtn.addEventListener('click', closeFeedbackModal);
    }

    if (submitFeedbackBtn) {
        submitFeedbackBtn.addEventListener('click', submitCaseFeedback);
    }

    // Guidelines toggle handler
    if (guidelinesToggle) {
        guidelinesToggle.addEventListener('change', (e) => {
            guidelinesEnabled = e.target.checked;
            if (!guidelinesEnabled) {
                // Completely hide guidelines results when disabled
                hideGuidelinesResults();
            } else if (currentOrganismKey) {
                // Re-fetch and show guidelines if organism is selected
                fetchGuidelines(currentOrganismKey);
            }
        });
    }

    // Organism select change handler
    if (organismSelect) {
        organismSelect.addEventListener('change', () => {
            // Reset phase to Information Gathering whenever organism selection changes
            resetPhaseToInformationGathering();

            if (organismSelect.value === 'random') {
                // If random is selected, immediately trigger random selection
                selectRandomOrganism();
            }
        });
    }

    // Model provider toggle handlers
    const azureProvider = document.getElementById('azure-provider');
    const personalProvider = document.getElementById('personal-provider');
    const modelSelect = document.getElementById('model-select');

    if (azureProvider) {
        azureProvider.addEventListener('change', updateModelSelection);
    }

    if (personalProvider) {
        personalProvider.addEventListener('change', updateModelSelection);
    }

    if (modelSelect) {
        modelSelect.addEventListener('change', updateCurrentModel);
    }

    // Initialize model selection on page load
    updateModelSelection();

    // Log initial configuration
    console.log(`🚀 [FRONTEND] Initializing MicroTutor V4`);
    console.log(`🔧 [FRONTEND] Initial System: ${currentModelProvider.toUpperCase()}`);
    console.log(`🤖 [FRONTEND] Initial Model: ${currentModel}`);

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

    // ============================================================
    // VOICE FUNCTIONALITY
    // ============================================================

    /**
     * Check if the current context is secure for getUserMedia
     */
    function isSecureContext() {
        const hostname = window.location.hostname;
        const protocol = window.location.protocol;

        // Secure contexts: HTTPS, localhost, 127.0.0.1, or file://
        return (
            protocol === 'https:' ||
            hostname === 'localhost' ||
            hostname === '127.0.0.1' ||
            hostname === '[::1]' ||
            protocol === 'file:'
        );
    }

    /**
     * Check if voice is available (without requesting permission)
     */
    function checkVoiceAvailability() {
        console.log('[VOICE] Checking voice availability...');
        console.log('[VOICE] navigator:', typeof navigator);
        console.log('[VOICE] navigator.mediaDevices:', typeof navigator.mediaDevices);
        console.log('[VOICE] window.location.href:', window.location.href);
        console.log('[VOICE] window.isSecureContext:', window.isSecureContext);
        console.log('[VOICE] window.location.protocol:', window.location.protocol);
        console.log('[VOICE] window.location.hostname:', window.location.hostname);

        // Check if we're in a secure context first (this we can determine for sure)
        if (!isSecureContext()) {
            const currentUrl = window.location.href;
            const localhostUrl = currentUrl.replace(window.location.hostname, 'localhost');
            const errorMessage = '❌ Use localhost';
            const tooltipMessage = `Microphone requires HTTPS or localhost. Try: ${localhostUrl}`;

            setVoiceStatus(errorMessage);
            if (voiceBtn) {
                voiceBtn.disabled = true;
                voiceBtn.title = tooltipMessage;
            }

            console.warn(
                '%c[VOICE] Security Warning',
                'color: orange; font-weight: bold; font-size: 14px;',
                `\nMicrophone requires HTTPS or localhost.\nCurrent: ${window.location.hostname}\nTry: ${localhostUrl}`
            );
            return false;
        }

        // If we're in a secure context, ALWAYS enable the button
        // Let the actual getUserMedia call fail with a proper error if there's an issue
        if (voiceBtn) {
            voiceBtn.disabled = false;
            voiceBtn.title = 'Click to request microphone access';
        }

        // Check if the browser supports getUserMedia (but don't disable button)
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            let statusMessage = '🎤 Click to try';
            let warning = 'Voice API not detected, but click to try anyway';

            if (!navigator.mediaDevices) {
                console.warn('[VOICE] navigator.mediaDevices is undefined - this is unusual on localhost');
                warning = 'navigator.mediaDevices is undefined. Click to attempt access anyway.';
            } else if (!navigator.mediaDevices.getUserMedia) {
                console.warn('[VOICE] getUserMedia is undefined');
                warning = 'getUserMedia is undefined. Click to attempt access anyway.';
            }

            setVoiceStatus(statusMessage);
            if (voiceBtn) {
                voiceBtn.title = warning;
            }
            console.warn('[VOICE] Voice API not detected. Browser:', navigator.userAgent);
            console.warn('[VOICE] Button enabled anyway - will attempt on click');
            return false;
        }

        // Voice API is available
        setVoiceStatus('🎤 Click to start');
        console.log('[VOICE] ✅ Voice API available, waiting for user interaction');
        return true;
    }

    /**
     * Request microphone permission (called on first user interaction)
     */
    async function requestMicrophonePermission() {
        if (voiceInitialized) {
            return voiceEnabled; // Already attempted
        }

        voiceInitialized = true;
        setVoiceStatus('⏳ Requesting...');

        try {
            console.log('[VOICE] Requesting microphone permission...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            voiceEnabled = true;
            setVoiceStatus('🎤 Voice ready');
            console.log('[VOICE] Microphone access granted');

            // Stop the stream immediately (we'll request again when actually recording)
            stream.getTracks().forEach(track => track.stop());

            if (voiceBtn) {
                voiceBtn.title = 'Click and hold to record';
            }

            return true;
        } catch (error) {
            console.error('[VOICE] Microphone access denied:', error);
            voiceEnabled = false;

            let errorMessage = '❌ Mic unavailable';
            let tooltipMessage = 'Microphone access denied';

            if (error.name === 'NotAllowedError') {
                errorMessage = '❌ Permission denied';
                tooltipMessage = 'You denied microphone access. Click 🔒 in address bar to change permissions.';
            } else if (error.name === 'NotFoundError') {
                errorMessage = '❌ No microphone';
                tooltipMessage = 'No microphone found on this device';
            } else if (error.name === 'NotReadableError') {
                errorMessage = '❌ Mic in use';
                tooltipMessage = 'Microphone is already in use by another application';
            } else {
                tooltipMessage = error.message || 'Could not access microphone';
            }

            setVoiceStatus(errorMessage);
            if (voiceBtn) {
                voiceBtn.disabled = true;
                voiceBtn.title = tooltipMessage;
            }

            return false;
        }
    }

    /**
     * Set voice status message
     */
    function setVoiceStatus(message) {
        if (voiceStatus) {
            voiceStatus.textContent = message;
        }
    }

    /**
     * Start recording audio
     */
    async function startRecording() {
        if (!currentCaseId || !currentOrganismKey) {
            setStatus('Please start a case first before using voice', true);
            return;
        }

        try {
            console.log('[VOICE] 🎙️ Starting recording...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log('[VOICE] ✅ Got media stream');

            // Try formats in order of OpenAI compatibility
            // MP4/M4A works best, then WebM with opus
            const preferredFormats = [
                'audio/mp4',  // Best for OpenAI, works in Safari
                'audio/webm;codecs=opus',  // Good quality, works in Chrome/Firefox
                'audio/webm',  // Fallback for older browsers
                ''  // Browser default
            ];

            let mimeType = '';
            for (const format of preferredFormats) {
                if (format === '' || MediaRecorder.isTypeSupported(format)) {
                    mimeType = format;
                    break;
                }
            }

            console.log('[VOICE] Using mimeType:', mimeType || 'browser default');
            console.log('[VOICE] Supported formats check:');
            preferredFormats.forEach(fmt => {
                if (fmt) console.log(`  - ${fmt}: ${MediaRecorder.isTypeSupported(fmt) ? '✅' : '❌'}`);
            });

            const options = mimeType ? { mimeType } : {};
            mediaRecorder = new MediaRecorder(stream, options);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                    console.log('[VOICE] 📊 Data chunk received:', event.data.size, 'bytes');
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: mimeType || 'audio/webm' });
                console.log('[VOICE] ⏹️ Recording stopped, total size:', audioBlob.size, 'bytes');

                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());

                // Send to API
                if (audioBlob.size > 0) {
                    await sendVoiceMessage(audioBlob);
                } else {
                    console.error('[VOICE] Recording is empty (0 bytes)');
                    setStatus('Recording failed - no audio captured', true);
                    setVoiceStatus('🎤 Voice ready');
                }
            };

            mediaRecorder.start();
            isRecording = true;
            recordingStartTime = Date.now();
            setVoiceStatus('🔴 RECORDING - Speak now!');
            setStatus('🎙️ Recording in progress... Release to send');

            // Visual feedback on button
            if (voiceBtn) {
                voiceBtn.style.background = '#dc3545';
                voiceBtn.style.animation = 'pulse 1s infinite';
            }

            console.log('[VOICE] ✅ Recording started successfully at', new Date(recordingStartTime).toISOString());
            console.log('[VOICE] 💡 Speak now! Release button or click again to stop.');

        } catch (error) {
            console.error('[VOICE] ❌ Recording error:', error);
            setStatus('Error accessing microphone: ' + error.message, true);
            setVoiceStatus('❌ Recording failed');
            isRecording = false;
        }
    }

    /**
     * Stop recording audio
     */
    function stopRecording() {
        if (mediaRecorder && isRecording) {
            // Check recording duration
            const duration = Date.now() - recordingStartTime;
            console.log('[VOICE] ⏹️ Stopping recording... Duration:', duration, 'ms');

            if (duration < 500) {
                console.warn('[VOICE] ⚠️ Recording too short:', duration, 'ms (minimum 500ms recommended)');
                setStatus('Recording too short - please hold longer', true);
                setVoiceStatus('⚠️ Too short');

                // Stop and reset
                mediaRecorder.stop();
                isRecording = false;

                // Reset button
                if (voiceBtn) {
                    voiceBtn.style.background = '';
                    voiceBtn.style.animation = '';
                }

                // Reset status after delay
                setTimeout(() => {
                    setVoiceStatus('🎤 Voice ready');
                    setStatus('');
                }, 2000);

                return;
            }

            mediaRecorder.stop();
            isRecording = false;
            setVoiceStatus('⏸️ Processing...');
            setStatus('Processing audio...');

            // Reset button appearance
            if (voiceBtn) {
                voiceBtn.style.background = '';
                voiceBtn.style.animation = '';
            }

            console.log('[VOICE] ✅ Recording stopped after', duration, 'ms, processing...');
        } else {
            console.warn('[VOICE] ⚠️ Stop called but not recording');
        }
    }

    /**
     * Send voice message to API
     */
    async function sendVoiceMessage(audioBlob) {
        console.log('[VOICE] Sending audio to API...');
        console.log('[VOICE] Audio blob type:', audioBlob.type);
        console.log('[VOICE] Audio blob size:', audioBlob.size, 'bytes');

        disableInput(true);
        setStatus('Transcribing and processing...');

        try {
            // Determine file extension from MIME type
            let extension = 'webm';
            if (audioBlob.type.includes('mp4')) {
                extension = 'mp4';
            } else if (audioBlob.type.includes('ogg')) {
                extension = 'ogg';
            } else if (audioBlob.type.includes('wav')) {
                extension = 'wav';
            }

            const filename = `recording.${extension}`;
            console.log('[VOICE] Sending as:', filename);

            // Create form data
            const formData = new FormData();
            formData.append('audio', audioBlob, filename);
            formData.append('case_id', currentCaseId);
            formData.append('organism_key', currentOrganismKey);
            formData.append('history', JSON.stringify(chatHistory));

            // Send to voice chat endpoint
            const response = await fetch(`${API_BASE}/voice/chat`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || errData.error || `HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('[VOICE] Response received:', data);

            // Add transcribed user message
            addMessage('user', data.transcribed_text);
            addMessageToHistory('user', data.transcribed_text);

            // Add assistant response
            const speakerIcon = data.speaker === 'patient' ? '🤒' : '👨‍⚕️';
            addMessage('assistant', `${speakerIcon} ${data.response_text}`, true);
            addMessageToHistory('assistant', data.response_text);

            // Play audio response
            if (data.audio_base64) {
                playAudioResponse(data.audio_base64);
            }

            setStatus('');
            setVoiceStatus('🎤 Voice ready');
            disableInput(false);
            saveConversationState();

        } catch (error) {
            console.error('[VOICE] Error:', error);
            setStatus(`Voice error: ${error.message}`, true);
            setVoiceStatus('❌ Error');
            disableInput(false);
        }
    }

    /**
     * Play audio response from base64
     */
    function playAudioResponse(audioBase64) {
        try {
            // Convert base64 to blob
            const byteCharacters = atob(audioBase64);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const audioBlob = new Blob([byteArray], { type: 'audio/mpeg' });

            // Create URL and play
            const audioUrl = URL.createObjectURL(audioBlob);

            if (responseAudio) {
                responseAudio.src = audioUrl;
                responseAudio.play();
                console.log('[VOICE] Playing audio response');

                // Clean up URL after playing
                responseAudio.onended = () => {
                    URL.revokeObjectURL(audioUrl);
                };
            }
        } catch (error) {
            console.error('[VOICE] Error playing audio:', error);
        }
    }

    /**
     * Handle voice button click (toggle recording on/off)
     */
    async function handleVoiceButton() {
        // First-time setup: request permission
        if (!voiceInitialized) {
            const granted = await requestMicrophonePermission();
            if (!granted) {
                setStatus('Microphone access denied. Check permissions.', true);
                return;
            }
        }

        if (!voiceEnabled) {
            setStatus('Voice is not available. Check microphone permissions.', true);
            return;
        }

        if (!currentCaseId || !currentOrganismKey) {
            setStatus('Please start a case first before using voice', true);
            return;
        }

        // Toggle recording
        if (isRecording) {
            console.log('[VOICE] 🛑 Stopping recording (user clicked button)');
            stopRecording();
            if (voiceBtn) {
                voiceBtn.classList.remove('recording');
                voiceBtn.textContent = '🎤';
            }
        } else {
            console.log('[VOICE] ▶️ Starting recording (user clicked button)');
            startRecording();
            if (voiceBtn) {
                voiceBtn.classList.add('recording');
                voiceBtn.textContent = '⏹️';
            }
        }
    }

    // Voice button event listener - simple toggle on click
    if (voiceBtn) {
        voiceBtn.addEventListener('click', handleVoiceButton);
        voiceBtn.title = 'Click to start/stop voice recording';
    }

    // Check voice availability on load (doesn't request permission yet)
    if (voiceBtn) {
        console.log('[VOICE] Voice button found:', voiceBtn);
        console.log('[VOICE] Voice button disabled state BEFORE check:', voiceBtn.disabled);
        checkVoiceAvailability();
        console.log('[VOICE] Voice button disabled state AFTER check:', voiceBtn.disabled);
    } else {
        console.error('[VOICE] Voice button element not found!');
    }

    // ============================================================
    // END VOICE FUNCTIONALITY
    // ============================================================

    // ============================================================
    // FEEDBACK CONTROL FUNCTIONALITY
    // ============================================================

    /**
     * Initialize feedback controls
     */
    function initializeFeedbackControls() {
        if (feedbackToggle) {
            feedbackToggle.addEventListener('change', (e) => {
                feedbackEnabled = e.target.checked;
                console.log('[FEEDBACK] Feedback enabled:', feedbackEnabled);
                console.log('🎯 [FEEDBACK] Threshold slider remains adjustable at all times');
                updateFeedbackControlsUI();
                saveFeedbackSettings();
            });
        }

        if (thresholdSlider) {
            thresholdSlider.addEventListener('input', (e) => {
                const previousThreshold = feedbackThreshold;
                feedbackThreshold = parseFloat(e.target.value);
                thresholdValue.textContent = feedbackThreshold.toFixed(1);

                // Enhanced logging
                console.log(`🎯 [FEEDBACK] Threshold Changed: ${previousThreshold.toFixed(1)} → ${feedbackThreshold.toFixed(1)}`);
                console.log(`🔧 [FEEDBACK] Current Threshold: ${feedbackThreshold.toFixed(1)}`);
                console.log(`📊 [FEEDBACK] Threshold Mode: ${feedbackThreshold >= 0.8 ? 'Strict (Exact Matches)' : feedbackThreshold >= 0.5 ? 'Balanced' : 'Loose (More Examples)'}`);

                // Visual feedback
                thresholdValue.style.color = feedbackThreshold >= 0.8 ? '#e74c3c' : feedbackThreshold >= 0.5 ? '#f39c12' : '#27ae60';

                // Show temporary notification
                showThresholdNotification(feedbackThreshold);

                saveFeedbackSettings();
            });
        }

        // Load saved settings
        loadFeedbackSettings();
        updateFeedbackControlsUI();

        // Confirm slider is enabled
        console.log('✅ [FEEDBACK] Threshold slider initialized and enabled');
        console.log(`🎯 [FEEDBACK] Current threshold: ${feedbackThreshold.toFixed(1)}`);
        console.log(`🔧 [FEEDBACK] Feedback system: ${feedbackEnabled ? 'Enabled (Default)' : 'Disabled'}`);
        console.log('💡 [FEEDBACK] AI Feedback is enabled by default for optimal learning experience');
    }

    /**
     * Load feedback settings from localStorage
     */
    function loadFeedbackSettings() {
        try {
            const savedEnabled = localStorage.getItem('microtutor_feedback_enabled');
            const savedThreshold = localStorage.getItem('microtutor_feedback_threshold');

            if (savedEnabled !== null) {
                feedbackEnabled = savedEnabled === 'true';
            } else {
                // Default to enabled if no saved setting
                feedbackEnabled = true;
            }

            if (feedbackToggle) {
                feedbackToggle.checked = feedbackEnabled;
            }

            if (savedThreshold !== null) {
                feedbackThreshold = parseFloat(savedThreshold);
                if (thresholdSlider) {
                    thresholdSlider.value = feedbackThreshold;
                }
                if (thresholdValue) {
                    thresholdValue.textContent = feedbackThreshold.toFixed(1);
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
            localStorage.setItem('microtutor_feedback_enabled', feedbackEnabled.toString());
            localStorage.setItem('microtutor_feedback_threshold', feedbackThreshold.toString());
        } catch (e) {
            console.error('[FEEDBACK] Error saving settings:', e);
        }
    }

    /**
     * Show threshold change notification
     */
    function showThresholdNotification(threshold) {
        const statusMessage = document.getElementById('status-message');
        if (statusMessage) {
            const mode = threshold >= 0.8 ? 'Strict (Exact Matches)' :
                threshold >= 0.5 ? 'Balanced' : 'Loose (More Examples)';
            const color = threshold >= 0.8 ? '#e74c3c' :
                threshold >= 0.5 ? '#f39c12' : '#27ae60';

            statusMessage.innerHTML = `🎯 Threshold: ${threshold.toFixed(1)} - ${mode}`;
            statusMessage.style.color = color;
            statusMessage.style.display = 'block';

            // Hide after 3 seconds
            setTimeout(() => {
                statusMessage.style.display = 'none';
            }, 3000);
        }
    }

    /**
     * Update feedback controls UI state
     */
    function updateFeedbackControlsUI() {
        // Keep threshold slider always enabled so users can adjust it anytime
        // They might want to set it before enabling feedback
        if (thresholdSlider) {
            thresholdSlider.disabled = false;  // Always keep enabled for adjustability
        }
        if (thresholdValue) {
            // Keep full opacity so it's always visible and adjustable
            thresholdValue.style.opacity = '1';
            // Set color based on threshold value
            thresholdValue.style.color = feedbackThreshold >= 0.8 ? '#e74c3c' : feedbackThreshold >= 0.5 ? '#f39c12' : '#27ae60';
        }
    }

    /**
     * Display feedback examples in the chat
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

        examples.forEach((example, index) => {
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

    // Initialize feedback controls
    initializeFeedbackControls();

    // ============================================================
    // END FEEDBACK CONTROL FUNCTIONALITY
    // ============================================================

    // ============================================================
    // FEEDBACK COUNTER FUNCTIONALITY
    // ============================================================

    /**
     * Fetch feedback statistics from the API
     */
    async function fetchFeedbackStats() {
        if (isRefreshing) return;

        isRefreshing = true;
        console.log('[FEEDBACK_STATS] Fetching feedback statistics...');

        try {
            // Add loading animation
            if (caseFeedbackCount) caseFeedbackCount.classList.add('loading');
            if (messageFeedbackCount) messageFeedbackCount.classList.add('loading');

            // Fetch database stats
            const statsResponse = await fetch(`${API_BASE}/db/stats`);
            if (!statsResponse.ok) {
                throw new Error(`Stats API error: ${statsResponse.status}`);
            }
            const statsData = await statsResponse.json();

            // Fetch feedback data for message feedback count
            const feedbackResponse = await fetch(`${API_BASE}/db/feedback?limit=1`);
            let messageFeedbackCountValue = 0;
            if (feedbackResponse.ok) {
                const feedbackData = await feedbackResponse.json();
                messageFeedbackCountValue = feedbackData.count || 0;
            }

            // Update the display
            updateFeedbackStatsDisplay({
                totalFeedback: (statsData.stats?.case_feedback || 0) + messageFeedbackCountValue,
                caseFeedback: statsData.stats?.case_feedback || 0,
                messageFeedback: messageFeedbackCountValue,
                lastUpdated: new Date().toLocaleTimeString()
            });

            console.log('[FEEDBACK_STATS] Successfully updated stats:', {
                total: (statsData.stats?.case_feedback || 0) + messageFeedbackCountValue,
                case: statsData.stats?.case_feedback || 0,
                message: messageFeedbackCountValue
            });

        } catch (error) {
            console.error('[FEEDBACK_STATS] Error fetching stats:', error);
            updateFeedbackStatsDisplay({
                totalFeedback: 'Error',
                caseFeedback: 'Error',
                messageFeedback: 'Error',
                lastUpdated: 'Error'
            });
        } finally {
            isRefreshing = false;
            // Remove loading animation
            if (caseFeedbackCount) caseFeedbackCount.classList.remove('loading');
            if (messageFeedbackCount) messageFeedbackCount.classList.remove('loading');
        }
    }

    /**
     * Update the feedback statistics display
     */
    function updateFeedbackStatsDisplay(stats) {
        if (caseFeedbackCount) {
            caseFeedbackCount.textContent = stats.caseFeedback;
        }
        if (messageFeedbackCount) {
            messageFeedbackCount.textContent = stats.messageFeedback;
        }
        if (lastUpdated) {
            lastUpdated.textContent = stats.lastUpdated;
        }
    }

    /**
     * Start auto-refresh for feedback stats
     */
    function startAutoRefresh() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
        }

        autoRefreshInterval = setInterval(() => {
            if (autoRefreshToggle && autoRefreshToggle.checked) {
                fetchFeedbackStats();
                fetchFAISSStatus(); // Also poll FAISS status
            }
        }, 30000); // 30 seconds

        console.log('[FEEDBACK_STATS] Auto-refresh started (30s interval)');
    }

    /**
     * Stop auto-refresh for feedback stats
     */
    function stopAutoRefresh() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
        console.log('[FEEDBACK_STATS] Auto-refresh stopped');
    }

    /**
     * Initialize feedback counter functionality
     */
    function initializeFeedbackCounter() {
        // Event listeners
        if (refreshStatsBtn) {
            refreshStatsBtn.addEventListener('click', () => {
                console.log('[FEEDBACK_STATS] Manual refresh triggered');
                fetchFeedbackStats();
            });
        }

        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    startAutoRefresh();
                } else {
                    stopAutoRefresh();
                }
            });
        }

        // Initial load
        fetchFeedbackStats();
        fetchFAISSStatus();

        // Start auto-refresh if enabled
        if (autoRefreshToggle && autoRefreshToggle.checked) {
            startAutoRefresh();
        }

        console.log('[FEEDBACK_STATS] Feedback counter initialized');
    }

    // ============================================================
    // END FEEDBACK COUNTER FUNCTIONALITY
    // ============================================================

    // ============================================================
    // DASHBOARD FUNCTIONALITY
    // ============================================================

    /**
     * Initialize dashboard functionality
     */
    function initDashboard() {
        console.log('[DASHBOARD] Initializing dashboard...');

        // Load initial data
        loadDashboardData();

        // Set up event listeners
        if (refreshStatsBtn) {
            refreshStatsBtn.addEventListener('click', loadDashboardData);
        }

        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    startAutoRefresh();
                } else {
                    stopAutoRefresh();
                }
            });
        }


        if (toggleChartBtn) {
            toggleChartBtn.addEventListener('click', toggleChart);
            // Set initial button text
            toggleChartBtn.textContent = '📊 Hide Chart';
        }

        // Start auto-refresh if enabled
        if (autoRefreshToggle && autoRefreshToggle.checked) {
            startAutoRefresh();
        }

        console.log('[DASHBOARD] Dashboard initialized');
    }

    /**
     * Load dashboard data (stats, trends)
     */
    async function loadDashboardData() {
        try {
            console.log('[DASHBOARD] Loading dashboard data...');

            // Load stats and trends in parallel
            const [statsResponse, trendsResponse] = await Promise.all([
                fetch(`${API_BASE}/analytics/feedback/stats`),
                fetch(`${API_BASE}/analytics/feedback/trends?time_range=all`)
            ]);

            if (statsResponse.ok) {
                const statsData = await statsResponse.json();
                updateStatsDisplay(statsData.data);
            }

            if (trendsResponse.ok) {
                const trendsData = await trendsResponse.json();
                updateTrendsChart(trendsData.data);
            }

            console.log('[DASHBOARD] Dashboard data loaded successfully');

        } catch (error) {
            console.error('[DASHBOARD] Error loading dashboard data:', error);
        }
    }

    /**
     * Load only trends data (for time range changes)
     */
    async function loadTrendsData() {
        try {
            const response = await fetch(`${API_BASE}/analytics/feedback/trends?time_range=${timeRangeSelect.value}`);
            if (response.ok) {
                const data = await response.json();
                updateTrendsChart(data.data);
            }
        } catch (error) {
            console.error('[DASHBOARD] Error loading trends data:', error);
        }
    }

    /**
     * Update statistics display
     */
    function updateStatsDisplay(data) {
        // Message feedback
        if (messageFeedbackCount) {
            messageFeedbackCount.textContent = data.message_feedback.total;
        }
        if (messageTrend) {
            const trend = data.message_feedback.trend;
            messageTrend.textContent = trend > 0 ? `+${trend} today` : trend < 0 ? `${trend} today` : 'No change today';
            messageTrend.className = `stat-trend ${trend > 0 ? '' : trend < 0 ? 'negative' : 'neutral'}`;
        }

        // Case feedback
        if (caseFeedbackCount) {
            caseFeedbackCount.textContent = data.case_feedback.total;
        }
        if (caseTrend) {
            const trend = data.case_feedback.trend;
            caseTrend.textContent = trend > 0 ? `+${trend} today` : trend < 0 ? `${trend} today` : 'No change today';
            caseTrend.className = `stat-trend ${trend > 0 ? '' : trend < 0 ? 'negative' : 'neutral'}`;
        }

        // Average rating
        if (avgRating) {
            avgRating.textContent = data.overall.avg_rating;
        }
        if (ratingTrend) {
            ratingTrend.textContent = `Avg: ${data.overall.avg_rating}/5`;
        }

        // Last updated
        if (lastUpdated && data.overall.last_update) {
            const updateTime = new Date(data.overall.last_update);
            lastUpdated.textContent = updateTime.toLocaleString('en-US', {
                timeZone: 'America/New_York',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            }) + ' EST';
        }
        if (updateTrend) {
            updateTrend.textContent = 'System active';
        }
    }

    /**
     * Update FAISS status display
     */
    function updateFAISSStatus(data) {
        if (!data) return;

        const isReindexing = data.is_reindexing;
        const lastComplete = data.last_reindex_complete;
        const currentDuration = data.current_duration;
        const reindexCount = data.reindex_count;
        const lastError = data.last_error;

        // Update status text
        if (faissStatus) {
            if (isReindexing) {
                faissStatus.textContent = 'Re-indexing...';
                faissStatus.className = 'stat-value reindexing';
            } else if (lastError) {
                faissStatus.textContent = 'Error';
                faissStatus.className = 'stat-value error';
            } else {
                faissStatus.textContent = 'Ready';
                faissStatus.className = 'stat-value ready';
            }
        }

        // Update trend text
        if (faissTrend) {
            if (isReindexing) {
                const duration = currentDuration ? Math.round(currentDuration) : 0;
                faissTrend.textContent = `Re-indexing for ${duration}s...`;
            } else if (lastComplete) {
                const completeTime = new Date(lastComplete);
                const timeStr = completeTime.toLocaleString('en-US', {
                    timeZone: 'America/New_York',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                });
                faissTrend.textContent = `Last update: ${timeStr} (${reindexCount} total)`;
            } else {
                faissTrend.textContent = 'Never updated';
            }
        }

        // Update icon and loading animation
        if (faissIcon) {
            if (isReindexing) {
                faissIcon.textContent = '🔄';
                faissIcon.className = 'stat-icon spinning';
            } else if (lastError) {
                faissIcon.textContent = '⚠️';
                faissIcon.className = 'stat-icon error';
            } else {
                faissIcon.textContent = '✅';
                faissIcon.className = 'stat-icon ready';
            }
        }

        // Show/hide loading animation
        if (faissLoading) {
            faissLoading.style.display = isReindexing ? 'flex' : 'none';
        }
    }

    /**
     * Fetch FAISS re-indexing status
     */
    async function fetchFAISSStatus() {
        try {
            const response = await fetch(`${API_BASE}/faiss/reindex-status`);
            if (response.ok) {
                const data = await response.json();
                updateFAISSStatus(data);
            } else {
                console.warn('Failed to fetch FAISS status:', response.status);
            }
        } catch (error) {
            console.warn('Error fetching FAISS status:', error);
        }
    }

    /**
     * Update trends chart
     */
    function updateTrendsChart(data) {
        if (!trendsCanvas || !chartVisible) return;

        const ctx = trendsCanvas.getContext('2d');

        // Destroy existing chart
        if (chartInstance) {
            chartInstance.destroy();
        }

        // Create new chart
        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: data.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Cumulative Feedback Over Time'
                    },
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Cumulative Feedback Entries'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }


    /**
     * Toggle chart visibility
     */
    function toggleChart() {
        chartVisible = !chartVisible;
        const chartContainer = document.getElementById('feedback-chart');

        if (chartVisible) {
            chartContainer.style.display = 'block';
            toggleChartBtn.textContent = '📊 Hide Chart';
            loadTrendsData(); // Reload data when showing
        } else {
            chartContainer.style.display = 'none';
            toggleChartBtn.textContent = '📊 Show Chart';
        }
    }

    /**
     * Start auto-refresh
     */
    function startAutoRefresh() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
        }

        autoRefreshInterval = setInterval(() => {
            loadDashboardData();
        }, 30000); // 30 seconds

        console.log('[DASHBOARD] Auto-refresh started');
    }

    /**
     * Stop auto-refresh
     */
    function stopAutoRefresh() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }

        console.log('[DASHBOARD] Auto-refresh stopped');
    }

    // ============================================================
    // END DASHBOARD FUNCTIONALITY
    // ============================================================

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
        finishBtn.disabled = true;
    }

    // Initialize dashboard
    initDashboard();

    // Initialize feedback counter
    initializeFeedbackCounter();

    // Initialize MCQ functionality
    initializeMCQ();
});

// MCQ Functions
function initializeMCQ() {
    console.log('[MCQ] Initializing MCQ functionality');

    // Add event listener for MCQ option clicks
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('mcq-option')) {
            const selectedAnswer = e.target.dataset.answer;
            const questionId = e.target.dataset.questionId;
            handleMCQResponse(selectedAnswer, questionId);
        }
    });
}

async function generateMCQ(topic, caseContext = null) {
    try {
        console.log(`[MCQ] Generating MCQ for topic: ${topic}`);

        const response = await fetch(`${API_BASE}/mcq/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                topic: topic,
                case_context: caseContext,
                difficulty: 'intermediate',
                session_id: currentSessionId || generateSessionId()
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            currentMCQ = data.mcq_data;
            currentSessionId = data.session_id;

            // Display the MCQ in the chat
            displayMCQ(data.mcq_display, data.mcq_data);

            return data;
        } else {
            throw new Error(data.error || 'Failed to generate MCQ');
        }

    } catch (error) {
        console.error('[MCQ] Error generating MCQ:', error);
        addMessage('assistant', `I apologize, but I couldn't generate a question right now. Error: ${error.message}`);
        return null;
    }
}

function displayMCQ(mcqDisplay, mcqData) {
    // Create MCQ container
    const mcqContainer = document.createElement('div');
    mcqContainer.className = 'mcq-container';
    mcqContainer.innerHTML = `
        <div class="mcq-header">
            <h4>📝 Multiple Choice Question</h4>
            <p class="mcq-topic">Topic: ${mcqData.topic}</p>
        </div>
        <div class="mcq-question">
            <p><strong>${mcqData.question_text}</strong></p>
        </div>
        <div class="mcq-options">
            ${mcqData.options.map(option => `
                <button class="mcq-option" 
                        data-answer="${option.letter}" 
                        data-question-id="${mcqData.question_id}">
                    <span class="option-letter">${option.letter.toUpperCase()}</span>
                    <span class="option-text">${option.text}</span>
                </button>
            `).join('')}
        </div>
        <div class="mcq-instructions">
            <p><em>Click on your answer choice to submit your response.</em></p>
        </div>
    `;

    // Add to chat
    addMessage('assistant', '', mcqContainer);
}

async function handleMCQResponse(selectedAnswer, questionId) {
    try {
        console.log(`[MCQ] Processing response: ${selectedAnswer} for question ${questionId}`);

        const startTime = Date.now();

        // Disable all options to prevent multiple submissions
        const options = document.querySelectorAll('.mcq-option');
        options.forEach(option => {
            option.disabled = true;
            if (option.dataset.answer === selectedAnswer) {
                option.classList.add('selected');
            }
        });

        const response = await fetch(`${API_BASE}/mcq/respond`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                selected_answer: selectedAnswer,
                response_time_ms: Date.now() - startTime
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            // Display feedback
            displayMCQFeedback(data.feedback_display, data.is_correct);

            // Clear current MCQ
            currentMCQ = null;

            return data;
        } else {
            throw new Error(data.error || 'Failed to process MCQ response');
        }

    } catch (error) {
        console.error('[MCQ] Error processing response:', error);
        addMessage('assistant', `I apologize, but I couldn't process your response. Error: ${error.message}`);
        return null;
    }
}

function displayMCQFeedback(feedbackDisplay, isCorrect) {
    // Create feedback container
    const feedbackContainer = document.createElement('div');
    feedbackContainer.className = `mcq-feedback ${isCorrect ? 'correct' : 'incorrect'}`;
    feedbackContainer.innerHTML = `
        <div class="mcq-feedback-header">
            <h4>${isCorrect ? '✅ Correct!' : '❌ Incorrect'}</h4>
        </div>
        <div class="mcq-feedback-content">
            ${feedbackDisplay.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}
        </div>
        <div class="mcq-feedback-actions">
            <button class="btn btn-primary" onclick="generateNextMCQ()">📝 Next Question</button>
            <button class="btn btn-secondary" onclick="clearMCQ()">🔄 New Topic</button>
        </div>
    `;

    // Add to chat
    addMessage('assistant', '', feedbackContainer);
}

function generateNextMCQ() {
    if (currentMCQ && currentMCQ.topic) {
        generateMCQ(currentMCQ.topic);
    } else {
        addMessage('user', 'Generate a question about treatment guidelines');
    }
}

function clearMCQ() {
    currentMCQ = null;
    addMessage('user', 'I want to discuss treatment guidelines');
}

function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Enhanced message handling to detect MCQ requests
function enhancedSendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Check if this is an MCQ request
    const mcqKeywords = [
        'generate a question', 'create a question', 'test me', 'quiz me',
        'multiple choice', 'mcq', 'question about', 'ask me about',
        'what would you ask', 'test my knowledge', 'check my understanding'
    ];

    const isMCQRequest = mcqKeywords.some(keyword =>
        message.toLowerCase().includes(keyword)
    );

    if (isMCQRequest) {
        // Extract topic from message
        let topic = 'clinical guidelines';

        // Try to extract topic from common patterns
        const topicPatterns = [
            /(?:about|on|regarding)\s+([^?]+)/i,
            /question\s+(?:about|on|regarding)\s+([^?]+)/i,
            /test\s+(?:my\s+)?(?:knowledge\s+)?(?:about|on|regarding)\s+([^?]+)/i,
            /ask\s+(?:me\s+)?(?:about|on|regarding)\s+([^?]+)/i,
        ];

        for (const pattern of topicPatterns) {
            const match = message.match(pattern);
            if (match && match[1]) {
                topic = match[1].trim().replace(/[?.,!]/g, '');
                break;
            }
        }

        // Set default topics based on keywords
        if (message.toLowerCase().includes('treatment') || message.toLowerCase().includes('therapy')) {
            topic = 'treatment guidelines';
        } else if (message.toLowerCase().includes('diagnosis') || message.toLowerCase().includes('diagnostic')) {
            topic = 'diagnostic approach';
        } else if (message.toLowerCase().includes('antibiotic') || message.toLowerCase().includes('antimicrobial')) {
            topic = 'antimicrobial selection';
        }

        // Generate MCQ
        generateMCQ(topic, getCurrentCaseContext());
        userInput.value = '';
        return;
    }

    // Regular message handling
    handleSendMessage();
}

