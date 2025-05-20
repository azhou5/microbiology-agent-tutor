document.addEventListener('DOMContentLoaded', () => {
    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const startCaseBtn = document.getElementById('start-case-btn');
    const organismSelect = document.getElementById('organism-select');
    const statusMessage = document.getElementById('status-message');
    const finishBtn = document.getElementById('finish-btn');

    // --- Feedback mode toggle ---
    const inlineFeedbackToggle = document.getElementById('inline-feedback-toggle');
    let inlineFeedback = false;          // default: old prompt style

    inlineFeedbackToggle.addEventListener('change', () => {
        inlineFeedback = inlineFeedbackToggle.checked;
        setStatus(`Feedback mode: ${inlineFeedback ? 'inline' : 'popup'}.`);
    });

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
            // If inline feedback mode is active, add description and replacement textareas + submit button
            if (inlineFeedback) {
                const feedbackInputDiv = document.createElement('div');
                feedbackInputDiv.classList.add('feedback-input');

                // 1) Description textarea
                const descriptionLabel = document.createElement('label');
                descriptionLabel.textContent = 'What could be better?';
                feedbackInputDiv.appendChild(descriptionLabel);

                const descriptionTextArea = document.createElement('textarea');
                descriptionTextArea.placeholder = 'Describe improvements...';
                descriptionTextArea.rows = 2;
                descriptionTextArea.classList.add('feedback-description');
                feedbackInputDiv.appendChild(descriptionTextArea);

                // 2) Replacement textarea
                const replacementLabel = document.createElement('label');
                replacementLabel.textContent = 'Your preferred response';
                feedbackInputDiv.appendChild(replacementLabel);

                const replacementTextArea = document.createElement('textarea');
                replacementTextArea.placeholder = 'Enter replacement output...';
                replacementTextArea.rows = 3;
                replacementTextArea.classList.add('feedback-replacement');
                feedbackInputDiv.appendChild(replacementTextArea);

                // 3) Submit button
                const submitFeedbackBtn = document.createElement('button');
                submitFeedbackBtn.textContent = 'Submit';
                submitFeedbackBtn.classList.add('feedback-btn', 'submit-feedback-btn');
                feedbackInputDiv.appendChild(submitFeedbackBtn);

                feedbackContainer.appendChild(feedbackInputDiv);
            }
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
        // Don't disable the finish button here, as we want to control it separately
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
        if (inlineFeedback) {
            // === Inline feedback workflow ===
            const ratingBtn = event.target.closest('.rating-btn');
            const submitBtn = event.target.closest('.submit-feedback-btn');

            // Handle rating selection
            if (ratingBtn && !ratingBtn.disabled) {
                const feedbackContainer = ratingBtn.closest('.feedback-container');
                const rating = ratingBtn.dataset.rating;
                feedbackContainer.dataset.rating = rating;
                feedbackContainer.querySelectorAll('.rating-btn').forEach(btn => {
                    btn.disabled = true;
                    if (btn === ratingBtn) btn.classList.add('rated');
                });
                // Focus the first textarea (description)
                const textarea = feedbackContainer.querySelector('.feedback-description');
                if (textarea) textarea.focus();
                setStatus(`You selected ${rating}/5. Add comments and hit Submit.`);
                return;
            }

            // Submit feedback
            if (submitBtn) {
                const feedbackContainer = submitBtn.closest('.feedback-container');
                const messageDiv       = submitBtn.closest('.assistant-message');
                const rating           = feedbackContainer.dataset.rating;

                if (!rating) {
                    setStatus('Please select a rating first.', true);
                    return;
                }

                const messageContent = messageDiv.dataset.messageContent;
                const feedbackText = feedbackContainer.querySelector('.feedback-description').value.trim();
                const replacementText = feedbackContainer.querySelector('.feedback-replacement').value.trim();

                submitBtn.disabled = true;
                setStatus('Sending feedback…');

                try {
                    const response = await fetch('/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            rating,
                            message: messageContent,
                            history: chatHistory,
                            feedback_text: feedbackText,
                            replacement_text: replacementText
                        }),
                    });

                    if (!response.ok) {
                        const err = await response.json();
                        throw new Error(err.error || `HTTP ${response.status}`);
                    }

                    setStatus('Feedback submitted — thank you!');
                    // If user provided a replacement, inject it into the chat as the tutor
                    if (replacementText) {
                        addMessage('assistant', replacementText, true);
                        chatHistory.push({ role: 'assistant', content: replacementText });
                    }
                    feedbackContainer.querySelectorAll('textarea').forEach(t => t.disabled = true);
                } catch (error) {
                    console.error(error);
                    setStatus(`Error: ${error.message}`, true);
                    submitBtn.disabled = false;
                }
            }
        } else {
            // === Popup feedback workflow (legacy) ===
            const ratingBtn = event.target.closest('.rating-btn');
            if (!ratingBtn) return;

            const messageDiv = ratingBtn.closest('.assistant-message');
            const messageContent = messageDiv.dataset.messageContent;
            const rating = ratingBtn.dataset.rating;

            const buttonsInDiv = messageDiv.querySelectorAll('.rating-btn');
            buttonsInDiv.forEach(btn => btn.disabled = true);
            ratingBtn.classList.add('rated');

            let feedbackText = prompt(`You rated this response ${rating}/5. What could be better?`, "");
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
                // If the user provided a replacement in the prompt, show it
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

    // Feedback modal elements
    const feedbackModal = document.getElementById('feedback-modal');
    const submitFeedbackBtn = document.getElementById('submit-feedback-btn');
    const closeFeedbackBtn = document.getElementById('close-feedback-btn');

    // Finish Case button
    finishBtn.addEventListener('click', function() {
        // Show the feedback modal
        feedbackModal.style.display = 'block';
    });

    // Submit case feedback
    submitFeedbackBtn.addEventListener('click', function() {
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
    closeFeedbackBtn.addEventListener('click', function() {
        feedbackModal.style.display = 'none';
    });

    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === feedbackModal) {
            feedbackModal.style.display = 'none';
        }
    });
}); 