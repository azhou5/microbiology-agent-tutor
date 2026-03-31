/**
 * Utility functions for MicroTutor V4
 */

/**
 * Escape HTML to prevent XSS attacks
 * @param {string} text - Text to escape
 * @returns {string} Escaped HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Remove internal LLM figure markers from visible assistant/patient text.
 * @param {string} text - Raw message
 * @returns {string} Text without [[display_figure:N]] tokens
 */
function stripDisplayFigureMarkers(text) {
    if (!text || typeof text !== 'string') return text;
    return text
        .replace(/\[\[\s*display_figure\s*:\s*\d+\s*\]\]/gi, '')
        .replace(/\bdisplay_figure\s*\(\s*\d+\s*\)/gi, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

/**
 * Convert markdown links and formatting to HTML
 * @param {string} text - Markdown text to convert
 * @returns {string} HTML formatted text
 */
function markdownToHtml(text) {
    if (!text) return '';

    // Escape HTML first to prevent XSS (basic)
    let html = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

    // Headers (### Header)
    html = html.replace(/^### (.*$)/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gm, '<h1>$1</h1>');

    // Bold (**text**)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Italic (*text*)
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Links [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="guideline-inline-link">$1</a>');

    // Lists - convert "- item" to "<li>item</li>"
    html = html.replace(/^\s*-\s+(.*$)/gm, '<li>$1</li>');
    
    // Wrap lists in <ul>
    // This regex looks for consecutive <li> lines (separated by newlines)
    // Note: JS regex multiline mode doesn't easily support spanning multiple lines for replacement 
    // unless we process the whole string carefully.
    // Simpler approach: Process paragraph blocks.

    let sections = html.split(/\n\n+/);
    
    let formattedSections = sections.map(section => {
        // If the section contains list items, wrap them
        if (section.includes('<li>')) {
            // Check if it's purely a list section (ignoring whitespace)
            if (section.trim().startsWith('<li>')) {
                return '<ul>' + section.replace(/\n/g, '') + '</ul>';
            }
            // Mixed content? Just wrap the li parts? 
            // For now, let's assume lists are their own blocks mostly.
            // If we have mixed content, we might leave <li> hanging without <ul> which browsers usually handle okay-ish but is bad HTML.
            // Let's force wrap any block of <li>s
            return section.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
        }
        
        // Headers already formatted
        if (section.match(/^<h/)) {
            return section;
        }
        
        if (section.trim().length === 0) return '';
        
        // Regular paragraph - handle internal line breaks as <br>
        return '<p>' + section.replace(/\n/g, '<br>') + '</p>';
    });
    
    return formattedSections.join('');
}

/**
 * Truncate text to a maximum length
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {{text: string, isTruncated: boolean}} Truncated text and flag
 */
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

/**
 * Generate unique case ID
 * @returns {string} Unique case ID
 */
function generateCaseId() {
    return 'case_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

/**
 * Generate unique session ID
 * @returns {string} Unique session ID
 */
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

/**
 * Validate chat history messages
 * @param {Array} history - Chat history array
 * @returns {Array} Validated chat history
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
