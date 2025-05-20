document.addEventListener('DOMContentLoaded', () => {
    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const startCaseBtn = document.getElementById('start-case-btn');
    const organismSelect = document.getElementById('organism-select');
    const statusMessage = document.getElementById('status-message');
    const finishBtn = document.getElementById('finish-btn');

    let chatHistory = []; // Store the conversation history [{role: 'user'/'assistant', content: '...'}, ...]

    function addMessage(sender, messageContent, addFeedbackUI = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'assistant-message');

        // Use innerHTML to allow basic formatting later if needed, but be cautious
        const messageTextSpan = document.createElement('span');
        messageTextSpan.textContent = messageContent;
        messageDiv.appendChild(messageTextSpan);

        // Store the raw message content for feedback
        messageDiv.dataset.messageContent = messageContent;

        if (sender === 'assistant') {
            const feedbackContainer = document.createElement('div');
            feedbackContainer.classList.add('feedback-container');

            // Create rating prompt
            const ratingPrompt = document.createElement('span');
            ratingPrompt.textContent = "Rate this response (1-5):";
            ratingPrompt.classList.add('feedback-prompt');
            feedbackContainer.appendChild(ratingPrompt);

            // Create rating buttons container
            const ratingButtonsDiv = document.createElement('div');
            ratingButtonsDiv.classList.add('feedback-buttons');

            // Create rating buttons
            for (let i = 1; i <= 5; i++) {
                const ratingBtn = document.createElement('button');
                ratingBtn.textContent = i;
                ratingBtn.title = `Rate ${i} out of 5`;
                ratingBtn.classList.add('feedback-btn', 'rating-btn');
                ratingBtn.dataset.rating = i;
                ratingButtonsDiv.appendChild(ratingBtn);
            }
            feedbackContainer.appendChild(ratingButtonsDiv);

            // Add click handler for popup feedback
            ratingButtonsDiv.addEventListener('click', async (event) => {
                const ratingBtn = event.target.closest('.rating-btn');
                if (!ratingBtn) return;

                const rating = ratingBtn.dataset.rating;
                const buttonsInDiv = ratingButtonsDiv.querySelectorAll('.rating-btn');
                buttonsInDiv.forEach(btn => btn.disabled = true);
                ratingBtn.classList.add('rated');

                let feedbackText = prompt(`You rated this response ${rating}/5. Why this score?`, "");
                if (feedbackText === null) {
                    buttonsInDiv.forEach(btn => btn.disabled = false);
                    ratingBtn.classList.remove('rated');
                    setStatus('Feedback cancelled.');
                    return;
                }

                let replacementText = prompt('Please enter your preferred response to replace the tutor output:', '');
                if (replacementText === null) {
                    buttonsInDiv.forEach(btn => btn.disabled = false);
                    ratingBtn.classList.remove('rated');
                    setStatus('Feedback cancelled.');
                    return;
                }

                setStatus('Sending feedback...');
                try {
                    const response = await fetch('/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            rating,
                            message: messageContent,
                            history: chatHistory,
                            feedback_text: feedbackText || '',
                            replacement_text: replacementText || ''
                        }),
                    });

                    if (!response.ok) {
                        const err = await response.json();
                        throw new Error(err.error || `HTTP ${response.status}`);
                    }

                    setStatus('Feedback submitted — thank you!');

                    // Instead of showing "thanks" message, show the rating and feedback
                    feedbackContainer.innerHTML = `
                        <div class="feedback-submitted">
                            <div class="feedback-rating">Rating: ${rating}/5</div>
                            ${feedbackText ? `<div class="feedback-section">
                                <div class="feedback-label">Why this score:</div>
                                <div class="feedback-text">${feedbackText}</div>
                            </div>` : ''}
                            ${replacementText ? `<div class="feedback-section">
                                <div class="feedback-label">Preferred response:</div>
                                <div class="feedback-text">${replacementText}</div>
                            </div>` : ''}
                        </div>
                    `;

                    // If user provided a replacement, show it
                    if (replacementText) {
                        addMessage('assistant', replacementText, true);
                        chatHistory.push({ role: 'assistant', content: replacementText });
                    }
                } catch (error) {
                    console.error(error);
                    setStatus(`Error: ${error.message}`, true);
                    buttonsInDiv.forEach(btn => btn.disabled = false);
                    ratingBtn.classList.remove('rated');
                }
            });

            messageDiv.appendChild(feedbackContainer);
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
        // Don't disable the finish button here, as we want to control it separately
        statusMessage.textContent = disabled ? 'Processing...' : '';
    }

    async function handleStartCase() {
        const selectedOrganism = organismSelect.value;
        const selectedModel = document.getElementById('model-select').value;
        if (!selectedOrganism) {
            setStatus('Please select an organism.', true);
            return;
        }

        setStatus('Starting new case...');
        startCaseBtn.disabled = true;
        organismSelect.disabled = true;
        document.getElementById('model-select').disabled = true;
        chatbox.innerHTML = ''; // Clear previous chat
        chatHistory = []; // Reset history

        try {
            const response = await fetch('/start_case', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    organism: selectedOrganism,
                    model: selectedModel
                }),
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
            finishBtn.disabled = false; // Enable the finish button
            setStatus('Case started. You can now chat.');

        } catch (error) {
            console.error('Error starting case:', error);
            setStatus(`Error starting case: ${error.message}`, true);
            // Keep input disabled if start fails
            disableInput(true);
            finishBtn.disabled = true; // Keep finish button disabled on error
        } finally {
            // Re-enable start button regardless of success/failure to allow retries/new cases
            startCaseBtn.disabled = false;
            organismSelect.disabled = false;
            document.getElementById('model-select').disabled = false;
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

    // --- Event Listeners ---
    startCaseBtn.addEventListener('click', handleStartCase);
    sendBtn.addEventListener('click', handleSendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !sendBtn.disabled) {
            handleSendMessage();
        }
    });

    // Initial state
    setStatus('Select an organism and click "Start New Case".');

    // Feedback modal elements
    const feedbackModal = document.getElementById('feedback-modal');
    const submitFeedbackBtn = document.getElementById('submit-feedback-btn');
    const closeFeedbackBtn = document.getElementById('close-feedback-btn');

    // Finish Case button
    finishBtn.addEventListener('click', function () {
        // Show the feedback modal
        feedbackModal.style.display = 'block';
    });

    // Submit case feedback
    submitFeedbackBtn.addEventListener('click', function () {
        // Get selected ratings
        const detailRating = document.querySelector('input[name="detail"]:checked')?.value;
        const helpfulnessRating = document.querySelector('input[name="helpfulness"]:checked')?.value;
        const accuracyRating = document.querySelector('input[name="accuracy"]:checked')?.value;
        const comments = document.getElementById('feedback-comments').value;

        // Validate that all ratings are selected
        if (!detailRating || !helpfulnessRating || !accuracyRating) {
            alert('Please select a rating for all three questions.');
            return;
        }

        // Submit the feedback
        fetch('/case_feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                detail: detailRating,
                helpfulness: helpfulnessRating,
                accuracy: accuracyRating,
                comments: comments
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    statusMessage.textContent = 'Error submitting case feedback: ' + data.error;
                } else {
                    // Close the modal
                    feedbackModal.style.display = 'none';

                    // Reset the form
                    document.querySelectorAll('input[type="radio"]').forEach(radio => {
                        radio.checked = false;
                    });
                    document.getElementById('feedback-comments').value = '';

                    // Show thank you message
                    statusMessage.textContent = 'Thank you for your feedback! You can start a new case.';

                    // Reset the chat
                    chatbox.innerHTML = '';
                    userInput.disabled = true;
                    sendBtn.disabled = true;
                    finishBtn.disabled = true;
                }
            })
            .catch(error => {
                statusMessage.textContent = 'Error submitting case feedback: ' + error;
                console.error('Error submitting case feedback:', error);
            });
    });

    // Close feedback modal
    closeFeedbackBtn.addEventListener('click', function () {
        feedbackModal.style.display = 'none';
    });

    // Close modal when clicking outside
    window.addEventListener('click', function (event) {
        if (event.target === feedbackModal) {
            feedbackModal.style.display = 'none';
        }
    });
}); 