document.addEventListener('DOMContentLoaded', () => {
    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const startCaseBtn = document.getElementById('start-case-btn');
    const organismSelect = document.getElementById('organism-select');
    const randomOrganismBtn = document.getElementById('random-organism-btn');
    const statusMessage = document.getElementById('status-message');
    const finishBtn = document.getElementById('finish-btn');

    let chatHistory = []; // Store the conversation history [{role: 'user'/'assistant', content: '...'}, ...]

    function addMessage(sender, messageContent, addFeedbackUI = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'assistant-message');
        messageDiv.id = 'msg-' + Date.now(); // Add unique ID for the message

        const messageTextSpan = document.createElement('span');
        messageTextSpan.textContent = messageContent;
        messageDiv.appendChild(messageTextSpan);

        messageDiv.dataset.messageContent = messageContent;

        if (sender === 'assistant') {
            const feedbackContainer = document.createElement('div');
            feedbackContainer.classList.add('feedback-container');

            // Create rating prompt
            const ratingPrompt = document.createElement('span');
            ratingPrompt.textContent = "Rate this response (1-4):";
            ratingPrompt.classList.add('feedback-prompt');
            feedbackContainer.appendChild(ratingPrompt);

            // Create rating buttons container
            const ratingButtonsDiv = document.createElement('div');
            ratingButtonsDiv.classList.add('feedback-buttons');

            // Create rating buttons
            for (let i = 1; i <= 4; i++) {
                const ratingBtn = document.createElement('button');
                ratingBtn.textContent = i;
                ratingBtn.title = `Rate ${i} out of 4`;
                ratingBtn.classList.add('feedback-btn', 'rating-btn');
                ratingBtn.dataset.rating = i;
                ratingButtonsDiv.appendChild(ratingBtn);
            }

            // Add cancel button
            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = 'Cancel';
            cancelBtn.title = 'Cancel rating';
            cancelBtn.classList.add('feedback-btn', 'cancel-btn');
            ratingButtonsDiv.appendChild(cancelBtn);

            feedbackContainer.appendChild(ratingButtonsDiv);

            // Create feedback textboxes container
            const feedbackTextboxes = document.createElement('div');
            feedbackTextboxes.classList.add('feedback-textboxes');

            // Create "Why this score" textbox
            const whyScoreBox = document.createElement('div');
            whyScoreBox.classList.add('feedback-textbox');
            whyScoreBox.innerHTML = `
                <label for="feedback-text-${messageDiv.id}">Why this score?</label>
                <textarea id="feedback-text-${messageDiv.id}" placeholder="Please explain your rating..."></textarea>
            `;

            // Create "Preferred response" textbox
            const preferredResponseBox = document.createElement('div');
            preferredResponseBox.classList.add('feedback-textbox');
            preferredResponseBox.innerHTML = `
                <label for="replacement-text-${messageDiv.id}">Preferred response (optional):</label>
                <textarea id="replacement-text-${messageDiv.id}" placeholder="Enter your preferred response..."></textarea>
            `;

            // Create submit button
            const submitButton = document.createElement('button');
            submitButton.classList.add('feedback-submit');
            submitButton.textContent = 'Submit Feedback';
            submitButton.disabled = true;

            feedbackTextboxes.appendChild(whyScoreBox);
            feedbackTextboxes.appendChild(preferredResponseBox);
            feedbackTextboxes.appendChild(submitButton);
            feedbackContainer.appendChild(feedbackTextboxes);

            // Add click handler for rating buttons
            ratingButtonsDiv.addEventListener('click', (event) => {
                const ratingBtn = event.target.closest('.rating-btn');
                const cancelBtn = event.target.closest('.cancel-btn');

                if (cancelBtn) {
                    // Reset all buttons
                    ratingButtonsDiv.querySelectorAll('.rating-btn').forEach(btn => {
                        btn.classList.remove('rated');
                        btn.disabled = false;
                    });
                    // Hide feedback textboxes
                    feedbackTextboxes.classList.remove('visible');
                    submitButton.disabled = true;
                    return;
                }

                if (!ratingBtn) return;

                // Reset all buttons
                ratingButtonsDiv.querySelectorAll('.rating-btn').forEach(btn => {
                    btn.classList.remove('rated');
                    btn.disabled = false;
                });

                // Set the clicked button as rated
                ratingBtn.classList.add('rated');
                ratingBtn.disabled = true;

                // Show feedback textboxes
                feedbackTextboxes.classList.add('visible');
                submitButton.disabled = false;
            });

            // Add submit handler
            submitButton.addEventListener('click', async () => {
                const feedbackText = document.getElementById(`feedback-text-${messageDiv.id}`).value;
                const replacementText = document.getElementById(`replacement-text-${messageDiv.id}`).value;
                const rating = ratingButtonsDiv.querySelector('.rated').dataset.rating;

                if (!feedbackText.trim()) {
                    setStatus('Please provide feedback for your rating.', true);
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
                            feedback_text: feedbackText,
                            replacement_text: replacementText
                        }),
                    });

                    if (!response.ok) {
                        const err = await response.json();
                        throw new Error(err.error || `HTTP ${response.status}`);
                    }

                    setStatus('Feedback submitted — thank you!');

                    // Show feedback summary
                    feedbackContainer.innerHTML = `
                        <div class="feedback-submitted">
                            <div class="feedback-rating">Rating: ${rating}/4</div>
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
                    // Reset the rating buttons
                    ratingButtonsDiv.querySelectorAll('.rating-btn').forEach(btn => {
                        btn.classList.remove('rated');
                        btn.disabled = false;
                    });
                    feedbackTextboxes.classList.remove('visible');
                    submitButton.disabled = true;
                }
            });

            messageDiv.appendChild(feedbackContainer);
        }

        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight;
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

    // Function to get all options from the select element (excluding the random option)
    function getAllOptions() {
        const options = [];
        const optgroups = organismSelect.getElementsByTagName('optgroup');

        for (let group of optgroups) {
            const groupOptions = group.getElementsByTagName('option');
            for (let option of groupOptions) {
                options.push(option);
            }
        }
        return options;
    }

    // Function to select a random organism
    function selectRandomOrganism() {
        const options = getAllOptions();
        if (options.length === 0) return;

        const randomIndex = Math.floor(Math.random() * options.length);
        const randomOption = options[randomIndex];

        // Store the random selection in a data attribute
        organismSelect.dataset.randomSelection = randomOption.value;

        // Set the dropdown to show "Random Selection"
        organismSelect.value = "random";

        // Show a generic message
        setStatus("Random organism selected. Click 'Start New Case' to begin.", false);
    }

    // Modify the start case handler to use the random selection if needed
    async function handleStartCase() {
        // Always select a random organism
        selectRandomOrganism();
        let selectedOrganism = organismSelect.dataset.randomSelection;

        if (!selectedOrganism) {
            setStatus('Error selecting random organism. Please try again.', true);
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
                body: JSON.stringify({
                    organism: selectedOrganism,
                    model: 'o3-mini'  // Always use o3-mini
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
        // Get the current organism from the select element
        const correctOrganism = organismSelect.dataset.randomSelection;

        // Update the organism display in the modal
        const organismDisplay = document.getElementById('correct-organism');
        if (organismDisplay && correctOrganism) {
            // Format the organism name (capitalize first letter of each word)
            const formattedOrganism = correctOrganism.split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
            organismDisplay.textContent = formattedOrganism;
        }

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
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(feedbackData)
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

    // Add event listeners for skip buttons
    document.querySelectorAll('.skip-btn').forEach(button => {
        button.addEventListener('click', function () {
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

    // Add click handler for random selection button
    randomOrganismBtn.addEventListener('click', selectRandomOrganism);
}); 