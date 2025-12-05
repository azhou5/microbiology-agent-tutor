/**
 * Clarify Sidebar - Quick help chat that doesn't interrupt the case flow
 */

(function () {
    'use strict';

    // DOM elements
    let sidebar, toggleBtn, messagesContainer, input, sendBtn;

    // State
    let isMinimized = false;
    let conversationHistory = [];

    /**
     * Initialize the clarify sidebar
     */
    function init() {
        sidebar = document.getElementById('clarify-sidebar');
        toggleBtn = document.getElementById('toggle-clarify');
        messagesContainer = document.getElementById('clarify-messages');
        input = document.getElementById('clarify-input');
        sendBtn = document.getElementById('clarify-send');

        if (!sidebar) {
            console.log('[CLARIFY] Sidebar not found, skipping initialization');
            return;
        }

        // Event listeners
        toggleBtn?.addEventListener('click', toggleSidebar);
        sendBtn?.addEventListener('click', sendMessage);
        input?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        console.log('[CLARIFY] Initialized');
    }

    /**
     * Toggle sidebar minimized state
     */
    function toggleSidebar() {
        isMinimized = !isMinimized;
        sidebar.classList.toggle('minimized', isMinimized);
        toggleBtn.textContent = isMinimized ? '+' : '−';
    }

    /**
     * Send a clarification message
     */
    async function sendMessage() {
        const message = input.value.trim();
        if (!message) return;

        // Clear welcome message on first send
        const welcome = messagesContainer.querySelector('.clarify-welcome');
        if (welcome) {
            welcome.remove();
        }

        // Add user message
        addMessage(message, 'user');
        input.value = '';
        input.disabled = true;
        sendBtn.disabled = true;

        // Show loading indicator
        const loadingEl = addLoadingIndicator();

        try {
            const response = await fetch('/api/v1/clarify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    history: conversationHistory.slice(-6)  // Last 3 exchanges
                })
            });

            const data = await response.json();

            // Remove loading indicator
            loadingEl.remove();

            if (data.response) {
                addMessage(data.response, 'assistant');
                // Update history
                conversationHistory.push(
                    { role: 'user', content: message },
                    { role: 'assistant', content: data.response }
                );
            } else {
                addMessage('Sorry, I couldn\'t process that question.', 'assistant');
            }
        } catch (error) {
            console.error('[CLARIFY] Error:', error);
            loadingEl.remove();
            addMessage('Sorry, something went wrong. Please try again.', 'assistant');
        } finally {
            input.disabled = false;
            sendBtn.disabled = false;
            input.focus();
        }
    }

    /**
     * Add a message to the chat
     */
    function addMessage(content, role) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `clarify-msg ${role}`;

        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.textContent = content;

        msgDiv.appendChild(bubble);
        messagesContainer.appendChild(msgDiv);

        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return msgDiv;
    }

    /**
     * Add loading indicator
     */
    function addLoadingIndicator() {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'clarify-msg loading';
        msgDiv.innerHTML = `
            <div class="msg-bubble">
                <div class="clarify-typing-indicator">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </div>
            </div>
        `;
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return msgDiv;
    }

    /**
     * Clear the clarify conversation
     */
    function clearConversation() {
        conversationHistory = [];
        if (messagesContainer) {
            messagesContainer.innerHTML = `
                <div class="clarify-welcome">
                    <p>💡 <strong>Examples:</strong></p>
                    <ul>
                        <li>"How do I interpret CRP levels?"</li>
                        <li>"What's the difference between sensitivity and specificity?"</li>
                    </ul>
                </div>
            `;
        }
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose for external use if needed
    window.ClarifyChat = {
        clear: clearConversation,
        toggle: toggleSidebar
    };

})();
