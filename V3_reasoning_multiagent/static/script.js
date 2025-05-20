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
                descriptionLabel.textContent = 'Please provide feedback on the strengths and weaknesses of this response.';
                feedbackInputDiv.appendChild(descriptionLabel);

                const descriptionTextArea = document.createElement('textarea');
                descriptionTextArea.placeholder = 'Share your thoughts on what worked well and what could be improved...';
                descriptionTextArea.rows = 2;
                descriptionTextArea.classList.add('feedback-description');
                feedbackInputDiv.appendChild(descriptionTextArea);

                // Add skip button for feedback text
                const skipFeedbackBtn = document.createElement('button');
                skipFeedbackBtn.textContent = 'Skip Feedback';
                skipFeedbackBtn.classList.add('skip-feedback-btn');
                skipFeedbackBtn.onclick = () => {
                    descriptionTextArea.value = '';
                    descriptionTextArea.disabled = true;
                    skipFeedbackBtn.disabled = true;
                    skipFeedbackBtn.textContent = 'Skipped';
                };
                feedbackInputDiv.appendChild(skipFeedbackBtn);

                // 2) Replacement textarea
                const replacementLabel = document.createElement('label');
                replacementLabel.textContent = 'Your preferred response';
                feedbackInputDiv.appendChild(replacementLabel);

                const replacementTextArea = document.createElement('textarea');
                replacementTextArea.placeholder = 'Enter replacement output...';
                replacementTextArea.rows = 3;
                replacementTextArea.classList.add('feedback-replacement');
                feedbackInputDiv.appendChild(replacementTextArea);

                // Add skip button for preferred response
                const skipReplacementBtn = document.createElement('button');
                skipReplacementBtn.textContent = 'Skip Preferred Response';
                skipReplacementBtn.classList.add('skip-replacement-btn');
                skipReplacementBtn.onclick = () => {
                    replacementTextArea.value = '';
                    replacementTextArea.disabled = true;
                    skipReplacementBtn.disabled = true;
                    skipReplacementBtn.textContent = 'Skipped';
                };
                feedbackInputDiv.appendChild(skipReplacementBtn);

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

            // Create custom dialog for feedback
            const feedbackDialog = document.createElement('div');
            feedbackDialog.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                z-index: 1000;
                width: 80%;
                max-width: 500px;
            `;

            // Add feedback text input
            const feedbackLabel = document.createElement('label');
            feedbackLabel.textContent = 'Please provide feedback on the strengths and weaknesses of this response:';
            feedbackLabel.style.display = 'block';
            feedbackLabel.style.marginBottom = '10px';
            feedbackDialog.appendChild(feedbackLabel);

            const feedbackTextarea = document.createElement('textarea');
            feedbackTextarea.style.width = '100%';
            feedbackTextarea.style.marginBottom = '10px';
            feedbackTextarea.style.padding = '8px';
            feedbackTextarea.rows = 4;
            feedbackDialog.appendChild(feedbackTextarea);

            // Add skip button for feedback
            const skipFeedbackBtn = document.createElement('button');
            skipFeedbackBtn.textContent = 'Skip Feedback';
            skipFeedbackBtn.style.marginRight = '10px';
            skipFeedbackBtn.onclick = () => {
                feedbackTextarea.value = '';
                feedbackTextarea.disabled = true;
                skipFeedbackBtn.disabled = true;
                skipFeedbackBtn.textContent = 'Skipped';
            };
            feedbackDialog.appendChild(skipFeedbackBtn);

            // Add buttons container
            const buttonsContainer = document.createElement('div');
            buttonsContainer.style.marginTop = '20px';
            buttonsContainer.style.textAlign = 'right';

            // Add continue button
            const continueBtn = document.createElement('button');
            continueBtn.textContent = 'Continue';
            continueBtn.style.marginRight = '10px';
            continueBtn.onclick = () => {
                const feedbackText = feedbackTextarea.value;
                feedbackDialog.remove();
                overlay.remove();
                
                // Show preferred response dialog
                const replacementDialog = document.createElement('div');
                replacementDialog.style.cssText = feedbackDialog.style.cssText;

                const replacementLabel = document.createElement('label');
                replacementLabel.textContent = 'Your preferred response:';
                replacementLabel.style.display = 'block';
                replacementLabel.style.marginBottom = '10px';
                replacementDialog.appendChild(replacementLabel);

                const replacementTextarea = document.createElement('textarea');
                replacementTextarea.style.width = '100%';
                replacementTextarea.style.marginBottom = '10px';
                replacementTextarea.style.padding = '8px';
                replacementTextarea.rows = 4;
                replacementDialog.appendChild(replacementTextarea);

                // Add skip button for preferred response
                const skipReplacementBtn = document.createElement('button');
                skipReplacementBtn.textContent = 'Skip Preferred Response';
                skipReplacementBtn.style.marginRight = '10px';
                skipReplacementBtn.onclick = () => {
                    replacementTextarea.value = '';
                    replacementTextarea.disabled = true;
                    skipReplacementBtn.disabled = true;
                    skipReplacementBtn.textContent = 'Skipped';
                };
                replacementDialog.appendChild(skipReplacementBtn);

                const replacementButtonsContainer = document.createElement('div');
                replacementButtonsContainer.style.marginTop = '20px';
                replacementButtonsContainer.style.textAlign = 'right';

                const submitBtn = document.createElement('button');
                submitBtn.textContent = 'Submit';
                submitBtn.style.marginRight = '10px';
                submitBtn.onclick = () => {
                    replacementDialog.remove();
                    overlay.remove();
                    handleFeedbackSubmission(rating, messageContent, feedbackText, replacementTextarea.value);
                };
                replacementButtonsContainer.appendChild(submitBtn);

                const cancelBtn = document.createElement('button');
                cancelBtn.textContent = 'Cancel';
                cancelBtn.onclick = () => {
                    replacementDialog.remove();
                    overlay.remove();
                    buttonsInDiv.forEach(btn => btn.disabled = false);
                    ratingBtn.classList.remove('rated');
                    setStatus('Feedback cancelled.');
                };
                replacementButtonsContainer.appendChild(cancelBtn);

                replacementDialog.appendChild(replacementButtonsContainer);
                document.body.appendChild(replacementDialog);
                replacementTextarea.focus();
            };
            buttonsContainer.appendChild(continueBtn);

            // Add cancel button
            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = 'Cancel';
            cancelBtn.onclick = () => {
                feedbackDialog.remove();
                overlay.remove();
                buttonsInDiv.forEach(btn => btn.disabled = false);
                ratingBtn.classList.remove('rated');
                setStatus('Feedback cancelled.');
            };
            buttonsContainer.appendChild(cancelBtn);

            feedbackDialog.appendChild(buttonsContainer);

            // Add overlay
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                z-index: 999;
            `;

            document.body.appendChild(overlay);
            document.body.appendChild(feedbackDialog);
            feedbackTextarea.focus();
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
        const detailRating = document.querySelector('input[name="detail"]:checked')?.value;
        const helpfulnessRating = document.querySelector('input[name="helpfulness"]:checked')?.value;
        const accuracyRating = document.querySelector('input[name="accuracy"]:checked')?.value;
        const comments = document.getElementById('feedback-comments').value;

        // Check if at least one question is answered
        if (!detailRating && !helpfulnessRating && !accuracyRating) {
            alert('Please provide at least one rating or skip all questions.');
            return;
        }

        const feedbackData = {
            detail: detailRating || 'skipped',
            helpfulness: helpfulnessRating || 'skipped',
            accuracy: accuracyRating || 'skipped',
            comments: comments
        };

        // Send feedback to server
        fetch('/case_feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(feedbackData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error submitting feedback: ' + data.error);
            } else {
                alert('Thank you for your feedback!');
                document.getElementById('feedback-modal').style.display = 'none';
                // Reset the form
                document.querySelectorAll('input[type="radio"]').forEach(radio => radio.checked = false);
                document.getElementById('feedback-comments').value = '';
                document.querySelectorAll('.skip-btn').forEach(btn => {
                    btn.disabled = false;
                    btn.textContent = 'Skip';
                });
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error submitting feedback. Please try again.');
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

    // Add event listeners for skip buttons
    document.querySelectorAll('.skip-btn').forEach(button => {
        button.addEventListener('click', function() {
            const questionName = this.getAttribute('data-question');
            // Uncheck all radio buttons for this question
            document.querySelectorAll(`input[name="${questionName}"]`).forEach(radio => {
                radio.checked = false;
            });
            // Disable the skip button
            this.disabled = true;
            // Add a visual indicator that this question was skipped
            this.textContent = 'Skipped';
        });
    });
}); 