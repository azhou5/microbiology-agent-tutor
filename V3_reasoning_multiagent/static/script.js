document.addEventListener('DOMContentLoaded', () => {
    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const startCaseBtn = document.getElementById('start-case-btn');
    const organismSelect = document.getElementById('organism-select');
    const statusMessage = document.getElementById('status-message');

    let chatHistory = []; // Store the conversation history [{role: 'user'/'assistant', content: '...'}, ...]

    function addMessage(sender, messageContent, addFeedbackUI = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'assistant-message');

        // Use innerHTML to allow basic formatting later if needed, but be cautious
        // For now, just setting text content is safer
        const messageTextSpan = document.createElement('span');
        messageTextSpan.textContent = messageContent;
        messageDiv.appendChild(messageTextSpan);

        // Store the raw message content for feedback
        messageDiv.dataset.messageContent = messageContent;

        if (sender === 'assistant' && addFeedbackUI) {
            const feedbackContainer = document.createElement('div');
            feedbackContainer.classList.add('feedback-container'); // New container class

            const ratingPrompt = document.createElement('span');
            ratingPrompt.textContent = "Rate this response (1-5):";
            ratingPrompt.classList.add('feedback-prompt');
            feedbackContainer.appendChild(ratingPrompt);

            const feedbackButtonsDiv = document.createElement('div');
            feedbackButtonsDiv.classList.add('feedback-buttons'); // Keep this class for styling buttons

            for (let i = 1; i <= 5; i++) {
                const ratingBtn = document.createElement('button');
                ratingBtn.textContent = i; // Button text is the rating number
                ratingBtn.title = `Rate ${i} out of 5`;
                ratingBtn.classList.add('feedback-btn', 'rating-btn'); // Add 'rating-btn' class
                ratingBtn.dataset.rating = i; // Store rating value
                feedbackButtonsDiv.appendChild(ratingBtn);
            }
            feedbackContainer.appendChild(feedbackButtonsDiv);
            messageDiv.appendChild(feedbackContainer); // Append the whole container
        }

        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight; // Auto-scroll to bottom
    }

    function setStatus(message, isError = false) {
        statusMessage.textContent = message;
        statusMessage.style.color = isError ? '#dc3545' : '#6c757d'; // Red for errors, grey otherwise
    }

    function disableInput(disabled = true) {
        userInput.disabled = disabled;
        sendBtn.disabled = disabled;
        statusMessage.textContent = disabled ? 'Processing...' : '';
    }

    async function handleStartCase() {
        const selectedOrganism = organismSelect.value;
        if (!selectedOrganism) {
            setStatus('Please select an organism.', true);
            return;
        }

        setStatus('Starting new case...');
        startCaseBtn.disabled = true;
        organismSelect.disabled = true;
        chatbox.innerHTML = ''; // Clear previous chat
        chatHistory = []; // Reset history

        try {
            const response = await fetch('/start_case', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ organism: selectedOrganism }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            chatHistory = data.history || []; // Initialize history from server
            if (data.initial_message) {
                addMessage('assistant', data.initial_message, true);
            } else {
                 setStatus('Received empty initial message from server.', true);
            }
            disableInput(false); // Enable chat input
            setStatus('Case started. You can now chat.');

        } catch (error) {
            console.error('Error starting case:', error);
            setStatus(`Error starting case: ${error.message}`, true);
            // Keep input disabled if start fails
            disableInput(true);
        } finally {
            // Re-enable start button regardless of success/failure to allow retries/new cases
             startCaseBtn.disabled = false;
             organismSelect.disabled = false;
        }
    }


    async function handleSendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        addMessage('user', message);
        chatHistory.push({ role: 'user', content: message }); // Update local history
        userInput.value = ''; // Clear input field
        disableInput(true); // Disable input while waiting for response

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // Send only the new message, server uses its internal history
                body: JSON.stringify({ message: message }),
            });

            if (!response.ok) {
                 const errorData = await response.json();
                 throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            chatHistory = data.history || chatHistory; // Update history from server response
            addMessage('assistant', data.response, true);
            setStatus(''); // Clear status

        } catch (error) {
            console.error('Error sending message:', error);
            addMessage('system', `Error: ${error.message}`); // Show error in chat
            setStatus(`Error: ${error.message}`, true);
        } finally {
            disableInput(false); // Re-enable input
        }
    }

    async function handleFeedback(event) {
        const button = event.target.closest('.rating-btn'); // Target rating buttons specifically
        if (!button) return; // Click wasn't on a rating button

        const messageDiv = button.closest('.assistant-message');
        const messageContent = messageDiv.dataset.messageContent;
        const rating = button.dataset.rating; // Rating is now 1-5

        // Disable all rating buttons for this message immediately
        const buttonsInDiv = messageDiv.querySelectorAll('.rating-btn');
        buttonsInDiv.forEach(btn => btn.disabled = true);

        // Highlight the clicked button
        button.classList.add('rated'); // Add a general 'rated' class for styling

        // Always prompt for feedback, regardless of rating
        let feedbackText = prompt(`You rated this response ${rating}/5. Add optional feedback:`, "");
        if (feedbackText === null) { // User cancelled the prompt
             // Re-enable buttons if prompt is cancelled
             buttonsInDiv.forEach(btn => btn.disabled = false);
             button.classList.remove('rated'); // Remove highlight
             setStatus('Feedback cancelled.');
             return;
        }

        setStatus('Sending feedback...');

        try {
            const response = await fetch('/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    rating: rating, // Send the numerical rating (1-5)
                    message: messageContent,
                    history: chatHistory,
                    feedback_text: feedbackText || '' // Ensure it's not null
                }),
            });

             if (!response.ok) {
                 const errorData = await response.json();
                 throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
             }

            setStatus('Feedback submitted. Thank you!');
            // Keep buttons disabled after successful submission

        } catch (error) {
            console.error('Error sending feedback:', error);
            setStatus(`Error submitting feedback: ${error.message}`, true);
            // Optionally re-enable buttons on error to allow retry?
            // buttonsInDiv.forEach(btn => btn.disabled = false);
            // button.classList.remove('rated');
        }
    }

    // --- Event Listeners ---
    startCaseBtn.addEventListener('click', handleStartCase);
    sendBtn.addEventListener('click', handleSendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !sendBtn.disabled) {
            handleSendMessage();
        }
    });

    // Use event delegation for feedback buttons
    chatbox.addEventListener('click', handleFeedback);

    // Initial state
    setStatus('Select an organism and click "Start New Case".');
}); 