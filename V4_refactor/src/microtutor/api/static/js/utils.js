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
 * Convert markdown links and formatting to HTML
 * @param {string} text - Markdown text to convert
 * @returns {string} HTML formatted text
 */
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
