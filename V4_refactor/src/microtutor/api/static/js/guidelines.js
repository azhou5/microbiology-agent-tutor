/**
 * Guidelines functionality for MicroTutor V4
 */

/**
 * Update guidelines status display
 * @param {string} status - Status text
 * @param {number} count - Result count
 */
function updateGuidelinesStatus(status, count = 0) {
    if (!DOM.guidelinesStatus || !DOM.guidelinesCount) return;

    DOM.guidelinesStatus.textContent = status;
    DOM.guidelinesCount.textContent = `${count} results`;

    if (status.includes('Loading') || status.includes('⏳')) {
        DOM.guidelinesStatus.className = 'status-indicator loading';
    } else if (status.includes('Error') || status.includes('❌')) {
        DOM.guidelinesStatus.className = 'status-indicator error';
    } else if (status.includes('Success') || status.includes('✅')) {
        DOM.guidelinesStatus.className = 'status-indicator success';
    } else {
        DOM.guidelinesStatus.className = 'status-indicator';
    }
}

/**
 * Display guidelines in the UI
 * @param {Object} guidelines - Guidelines data object
 */
function displayGuidelines(guidelines) {
    if (!DOM.guidelinesContent) return;

    if (!guidelines || !guidelines.organism) {
        DOM.guidelinesContent.innerHTML = '<div class="guidelines-loading">No guidelines available</div>';
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

        guidelines.recent_evidence.forEach((evidence) => {
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

    DOM.guidelinesContent.innerHTML = html;
}

/**
 * Global function for expand/collapse inline text (accessible from onclick)
 * @param {HTMLElement} button - Button element that triggered the toggle
 */
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

/**
 * Show guidelines results container
 */
function showGuidelinesResults() {
    if (DOM.guidelinesResults) {
        DOM.guidelinesResults.style.display = 'block';
    }
}

/**
 * Hide guidelines results container
 */
function hideGuidelinesResults() {
    if (DOM.guidelinesResults) {
        DOM.guidelinesResults.style.display = 'none';
    }
}

/**
 * Fetch guidelines for an organism
 * @param {string} organism - Organism name
 */
async function fetchGuidelines(organism) {
    if (!State.guidelinesEnabled) {
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
            // Handle 404 gracefully - guidelines feature not yet implemented
            if (response.status === 404) {
                updateGuidelinesStatus('📋 Guidelines coming soon', 0);
                if (DOM.guidelinesContent) {
                    DOM.guidelinesContent.innerHTML = '<div class="guidelines-loading">Guidelines feature is under development.</div>';
                }
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        State.currentGuidelines = data;

        // Check if stub mode (no real data yet)
        if (data.stub_mode) {
            updateGuidelinesStatus('📋 Guidelines coming soon', 0);
            if (DOM.guidelinesContent) {
                DOM.guidelinesContent.innerHTML = '<div class="guidelines-loading">Guidelines feature is under development.</div>';
            }
            return;
        }

        // Count actual guideline sections found
        let count = 0;
        if (data.clinical_guidelines) count++;
        if (data.diagnostic_approach) count++;
        if (data.treatment_protocols) count++;
        if (data.recent_evidence && data.recent_evidence.length > 0) count += data.recent_evidence.length;

        updateGuidelinesStatus('✅ Guidelines loaded', count);
        displayGuidelines(data);

    } catch (error) {
        // Silently handle errors for guidelines - it's an optional feature
        console.warn('Guidelines not available:', error.message);
        updateGuidelinesStatus('📋 Guidelines coming soon', 0);
        if (DOM.guidelinesContent) {
            DOM.guidelinesContent.innerHTML = '<div class="guidelines-loading">Guidelines feature is under development.</div>';
        }
    }
}
