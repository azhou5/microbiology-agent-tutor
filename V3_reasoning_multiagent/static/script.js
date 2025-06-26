document.addEventListener('DOMContentLoaded', () => {
    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const startCaseBtn = document.getElementById('start-case-btn');
    const organismSelect = document.getElementById('organism-select');
    const randomOrganismBtn = document.getElementById('random-organism-btn');
    const statusMessage = document.getElementById('status-message');
    const finishBtn = document.getElementById('finish-btn');
    const feedbackModal = document.getElementById('feedback-modal');
    const closeFeedbackBtn = document.getElementById('close-feedback-btn');
    const submitFeedbackBtn = document.getElementById('submit-feedback-btn');
    const correctOrganismSpan = document.getElementById('correct-organism');

    // --- Temporary Debugging: Monitor feedbackModal.style.display changes ---
    if (feedbackModal) {
        let currentDisplay = feedbackModal.style.display;
        Object.defineProperty(feedbackModal.style, 'display', {
            get: function () {
                return currentDisplay;
            },
            set: function (value) {
                console.log('[DEBUG_MODAL_STYLE] feedbackModal.style.display is being set to:', value);
                if (value === 'block' || value === 'flex') {
                    console.error('[DEBUG_MODAL_STYLE] ATTENTION: feedbackModal.style.display is being set to \'block\' or \'flex\'. Call stack:');
                    console.log(new Error().stack);
                    // debugger; // Temporarily comment out debugger for smoother testing of this fix
                }
                currentDisplay = value;
            },
            configurable: true
        });
    } else {
        console.error('[DEBUG_MODAL_STYLE] feedbackModal element not found!');
    }
    // --- End Temporary Debugging ---

    let chatHistory = []; // Store the conversation history [{role: 'user'/'assistant', content: '...'}, ...]
    let currentCaseId = null; // Store the current case ID
    let currentOrganismKey = null;
    let cachedOrganisms = []; // To store the list of organisms with cached cases

    const LOCAL_STORAGE_HISTORY_KEY = 'microbiologyTutorChatHistory';
    const LOCAL_STORAGE_CASE_ID_KEY = 'microbiologyTutorCaseId';
    const LOCAL_STORAGE_ORGANISM_KEY = 'microbiologyTutorOrganismKey';

    function saveConversationState() {
        try {
            console.log("    [SAVE_STATE] >>> Saving state to localStorage:", { historyLength: chatHistory.length, caseId: currentCaseId, organismKey: currentOrganismKey });
            localStorage.setItem(LOCAL_STORAGE_HISTORY_KEY, JSON.stringify(chatHistory));
            localStorage.setItem(LOCAL_STORAGE_CASE_ID_KEY, currentCaseId);
            if (currentOrganismKey) { // Only save if not null
                localStorage.setItem(LOCAL_STORAGE_ORGANISM_KEY, currentOrganismKey);
            }
        } catch (e) {
            console.error("Error saving conversation state to localStorage:", e);
            setStatus("Could not save conversation. Your browser might be blocking localStorage or it's full.", true);
        }
    }

    function loadConversationState() {
        console.log("[DEBUG_RENDER] Attempting to load conversation state from localStorage.");
        try {
            const savedHistory = localStorage.getItem(LOCAL_STORAGE_HISTORY_KEY);
            const savedCaseId = localStorage.getItem(LOCAL_STORAGE_CASE_ID_KEY);
            const savedOrganismKey = localStorage.getItem(LOCAL_STORAGE_ORGANISM_KEY);

            console.log("[DEBUG_RENDER] Loaded from localStorage:",
                { savedHistoryJSON: savedHistory, savedCaseId, savedOrganismKey });

            if (savedHistory && savedCaseId && savedOrganismKey) {
                chatHistory = JSON.parse(savedHistory);
                currentCaseId = savedCaseId;
                currentOrganismKey = savedOrganismKey;
                console.log("[DEBUG_RENDER] Parsed history and set caseId/organismKey:",
                    { chatHistoryLength: chatHistory.length, currentCaseId, currentOrganismKey });

                if (chatHistory.length > 0) {
                    chatbox.innerHTML = '';
                    chatHistory.forEach(msg => {
                        if (msg.role !== 'system') {
                            addMessage(msg.role, msg.content, false);
                        }
                    });
                    disableInput(false);
                    finishBtn.disabled = false;
                    console.log("[DEBUG_RENDER] UI enabled, finishBtn enabled.");
                    setStatus(`Resumed case. Case ID: ${currentCaseId}`);
                    if (organismSelect) {
                        if (organismSelect.value === 'random' && currentOrganismKey !== 'random') {
                            const allOptions = getAllOptions();
                            const matchedOption = allOptions.find(opt => opt.value === currentOrganismKey);
                            if (matchedOption) {
                                organismSelect.value = currentOrganismKey;
                                if (randomOrganismBtn && randomOrganismBtn.classList.contains('active')) {
                                    randomOrganismBtn.classList.remove('active');
                                    organismSelect.classList.remove('random-selected');
                                }
                            }
                        } else if (organismSelect.value !== currentOrganismKey) {
                            organismSelect.value = currentOrganismKey;
                        }
                    }
                    console.log("[DEBUG_RENDER] loadConversationState successfully loaded and applied state.");
                    return true;
                } else {
                    console.log("[DEBUG_RENDER] Saved history was empty after parsing or not enough data to resume.");
                }
            } else {
                console.log("[DEBUG_RENDER] No complete saved state found in localStorage (history, caseId, or organismKey missing).");
            }
        } catch (e) {
            console.error("[DEBUG_RENDER] Error loading conversation state from localStorage:", e);
            setStatus("Could not load previous conversation. Starting fresh.", true);
            clearConversationState();
        }
        console.log("[DEBUG_RENDER] loadConversationState did NOT load or apply a previous state.");
        return false;
    }

    function clearConversationState() {
        try {
            console.log("  [CLEAR_STATE] >>> Clearing conversation state from localStorage.");
            localStorage.removeItem(LOCAL_STORAGE_HISTORY_KEY);
            localStorage.removeItem(LOCAL_STORAGE_CASE_ID_KEY);
            localStorage.removeItem(LOCAL_STORAGE_ORGANISM_KEY);
            console.log("  [CLEAR_STATE] <<< Conversation state cleared.");
        } catch (e) {
            console.error("Error clearing conversation state from localStorage:", e);
        }
    }

    // Function to generate a unique case ID
    function generateCaseId() {
        return 'case_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    async function fetchCachedOrganisms() {
        try {
            const response = await fetch('/get_cached_organisms');
            if (!response.ok) {
                throw new Error('Failed to fetch cached organisms');
            }
            const data = await response.json();
            if (data && Array.isArray(data)) {
                cachedOrganisms = data;
                console.log('Successfully fetched cached organisms:', cachedOrganisms);
                // Enable the random button only if there are cached organisms
                if (randomOrganismBtn) {
                    randomOrganismBtn.disabled = cachedOrganisms.length === 0;
                }
            }
        } catch (error) {
            console.error('Error fetching cached organisms:', error);
            if (randomOrganismBtn) randomOrganismBtn.disabled = true; // Disable on error
        }
    }

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
                const ratingElement = ratingButtonsDiv.querySelector('.rated');

                if (!ratingElement) {
                    setStatus('Please select a rating first.', true);
                    return;
                }
                const rating = ratingElement.dataset.rating;

                // Allow empty feedback text
                // if (!feedbackText.trim()) {
                //     setStatus('Please provide feedback for your rating.', true);
                //     return;
                // }

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
                            replacement_text: replacementText,
                            case_id: currentCaseId,
                            organism: currentOrganismKey
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
                            ${feedbackText.trim() ? `<div class="feedback-section">
                                <div class="feedback-label">Why this score:</div>
                                <div class="feedback-text">${feedbackText}</div>
                            </div>` : ''}
                            ${replacementText.trim() ? `<div class="feedback-section">
                                <div class="feedback-label">Preferred response:</div>
                                <div class="feedback-text">${replacementText}</div>
                            </div>` : ''}
                        </div>
                    `;

                    // If user provided a replacement, show it
                    if (replacementText.trim()) {

                        if (in_context_learning) {

                            // integrate feedback into the chat history so that the LLM can adjust in real time!
                            const feedbackContextMessage = {
                                role: 'system', // Using 'system' to provide strong context/correction
                                content: `Context: The user provided feedback on the assistant's immediately preceding response.\nRating: ${rating}/4.\nUser's reason: "${feedbackText}"\nThe user suggested the following as a better response, which will follow as the new assistant turn: "${replacementText}"`
                            };
                            chatHistory.push(feedbackContextMessage);
                        }
                        // add the replacement text to the UI and chat history

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
        if (disabled && !statusMessage.textContent.includes("Error")) { // only show processing if not an error
            setStatus('Processing...');
        } else if (!disabled && statusMessage.textContent === 'Processing...') {
            setStatus('');
        }
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
        console.log("    [RANDOM_SELECT] >>> Function started.");
        const optionsToUse = cachedOrganisms.length > 0 ? cachedOrganisms : getAllOptions().map(opt => opt.value);
        console.log("    [RANDOM_SELECT] Using this list for selection:", optionsToUse);
        if (optionsToUse.length === 0) {
            console.log("    [RANDOM_SELECT] No options available to select from. Aborting.");
            return;
        }

        // Clear any visual indication of a specific selection
        organismSelect.value = 'random'; // Set dropdown to "Random Selection"
        organismSelect.classList.add('random-selected'); // Style for random
        randomOrganismBtn.classList.add('active'); // Style button as active

        const randomIndex = Math.floor(Math.random() * optionsToUse.length);
        const randomOrganismValue = optionsToUse[randomIndex];
        console.log(`    [RANDOM_SELECT] Selected random index ${randomIndex}, which is value: ${randomOrganismValue}`);


        // Find the corresponding display text from the dropdown options
        const allOptions = getAllOptions();
        const matchedOption = allOptions.find(opt => opt.value === randomOrganismValue);
        const randomOrganismText = matchedOption ? matchedOption.textContent : randomOrganismValue;
        console.log("    [RANDOM_SELECT] Display text for selected organism:", randomOrganismText);


        // Store the random selection in a data attribute
        organismSelect.dataset.randomlySelectedValue = randomOrganismValue;
        organismSelect.dataset.randomlySelectedText = randomOrganismText;
        console.log("    [RANDOM_SELECT] Stored in dataset:", { value: randomOrganismValue, text: randomOrganismText });


        // Update the button text to show the randomly selected organism
        randomOrganismBtn.textContent = `Random: ${randomOrganismText}`;
        console.log("    [RANDOM_SELECT] <<< Function finished.");
    }

    if (randomOrganismBtn) {
        randomOrganismBtn.addEventListener('click', selectRandomOrganism);
    }

    // Event listener for organism select change
    if (organismSelect) {
        organismSelect.addEventListener('change', () => {
            if (organismSelect.value !== 'random') {
                // If a specific organism is chosen, deselect the random button
                if (randomOrganismBtn) {
                    randomOrganismBtn.classList.remove('active');
                    randomOrganismBtn.textContent = 'Random Selection'; // Reset button text
                }
                organismSelect.classList.remove('random-selected');
                delete organismSelect.dataset.randomlySelectedValue; // Clear stored random value
                delete organismSelect.dataset.randomlySelectedText;
            } else {
                // If "Random Selection" is chosen again, trigger random selection
                selectRandomOrganism();
            }
        });
    }

    async function handleStartCase() {
        console.log("[START_CASE] >>> 'Start New Case' clicked. Beginning process.");
        console.log("[START_CASE] 1. Clearing previous state.");
        clearConversationState(); // Clear any previous persisted state when starting a new case.

        console.log("[START_CASE] 2. Resetting local variables (history, UI).");
        chatHistory = [];
        chatbox.innerHTML = ''; // Clear chatbox
        currentCaseId = generateCaseId(); // Generate a new case ID for each new case
        console.log("[START_CASE] New Case ID:", currentCaseId);

        console.log("[START_CASE] 3. Determining selected organism.");
        let selectedOrganism;

        // Prioritize the 'active' state of the random button as the user's true intent.
        if (randomOrganismBtn.classList.contains('active')) {
            console.log("[START_CASE]   - Random button is active. This is the user's intent. Calling selectRandomOrganism().");
            selectRandomOrganism(); // Pick a new random organism
            selectedOrganism = organismSelect.dataset.randomlySelectedValue;
            console.log(`[START_CASE]   - Value after random selection: '${selectedOrganism}'`);
        } else {
            console.log("[START_CASE]   - Random button is not active. Using dropdown's value.");
            selectedOrganism = organismSelect.value;
            console.log(`[START_CASE]   - Initial dropdown value: '${selectedOrganism}'`);
            // If the dropdown is for some reason still 'random', select a random one.
            if (selectedOrganism === 'random') {
                console.log("[START_CASE]   - Dropdown was 'random'. Calling selectRandomOrganism().");
                selectRandomOrganism();
                selectedOrganism = organismSelect.dataset.randomlySelectedValue;
                console.log(`[START_CASE]   - Value after random selection: '${selectedOrganism}'`);
            }
        }

        // Check if we have a valid organism to proceed with
        console.log("[START_CASE] 4. Validating final organism choice.");
        if (!selectedOrganism || selectedOrganism === 'random') {
            setStatus('Please select an organism or click the "Random Selection" button.', true);
            console.log("[START_CASE] <<< Aborting: No valid organism selected.");
            return;
        }
        console.log(`[START_CASE]    - Validation passed. Using organism: '${selectedOrganism}'`);

        currentOrganismKey = selectedOrganism; // Set the global currentOrganismKey
        console.log(`[START_CASE] 5. Set global organism key to: '${currentOrganismKey}' and updating UI status.`);
        setStatus(`Starting new case...`);

        disableInput(true);
        finishBtn.disabled = true; // Disable finish button until case starts

        try {
            console.log("[START_CASE] 6. Sending request to backend /start_case endpoint.");
            console.log("[START_CASE]   - Payload:", { organism: currentOrganismKey, case_id: currentCaseId });
            const response = await fetch('/start_case', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ organism: currentOrganismKey, case_id: currentCaseId }),
            });

            console.log("[START_CASE] 7. Received response from backend.");
            if (!response.ok) {
                const err = await response.json();
                console.error("[START_CASE] <<< Error from backend:", err);
                throw new Error(err.error || `HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log("[START_CASE]   - Response data:", data);
            if (data.error) {
                throw new Error(data.error);
            }

            console.log("[START_CASE] 8. Populating chat history and UI from response.");
            chatHistory = data.history || []; // Initialize with history from server (includes system prompt)

            // The initial message is already part of the history from the server
            // So, we just need to render the history
            chatbox.innerHTML = ''; // Clear previous messages if any (e.g. "Processing...")
            chatHistory.forEach(msg => {
                if (msg.role !== 'system') {
                    addMessage(msg.role, msg.content, msg.role === 'assistant');
                }
            });

            setStatus(`Case started. Case ID: ${currentCaseId}`);
            disableInput(false);
            finishBtn.disabled = false; // Enable finish button now
            console.log("[START_CASE] 9. Saving new conversation state.");
            saveConversationState(); // Save state after successful start
            console.log("[START_CASE] <<< Process finished successfully.");
        } catch (error) {
            console.error("[START_CASE] <<< Error during start case process:", error);
            setStatus(`Error: ${error.message}`, true);
            disableInput(false); // Re-enable input if start fails
            currentOrganismKey = null; // Reset organism key on failure
            currentCaseId = null; // Reset case ID
        }
    }

    async function handleSendMessage() {
        const messageText = userInput.value.trim();
        if (!messageText) return;

        addMessage('user', messageText);
        chatHistory.push({ role: 'user', content: messageText });
        userInput.value = '';
        disableInput(true);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: messageText,
                    history: chatHistory,
                    organism_key: currentOrganismKey,
                    case_id: currentCaseId
                }),
            });

            if (!response.ok) {
                const errData = await response.json();
                if (errData.needs_new_case) {
                    setStatus("Session expired or case mismatch. Please start a new case.", true);
                    disableInput(true); // Keep disabled
                    finishBtn.disabled = true;
                    clearConversationState(); // Clear invalid state
                } else {
                    throw new Error(errData.error || `HTTP ${response.status}`);
                }
                return; // Stop processing if needs_new_case or other error
            }

            const data = await response.json();
            if (data.error) { // Handle application-specific errors from /chat
                throw new Error(data.error);
            }

            addMessage('assistant', data.response, true); // Add feedback UI for assistant messages
            chatHistory = data.history; // Update history with the full history from server

            disableInput(false);
            setStatus(''); // Clear "Processing..."
            saveConversationState(); // Save state after successful message exchange
        } catch (error) {
            console.error(error);
            setStatus(`Error: ${error.message}`, true);
            disableInput(false); // Keep disabled on error to prevent further input until resolved or new case.
            // Or, re-enable if you want user to be able to try again: enableInput(false);
        }
    }

    if (startCaseBtn) {
        startCaseBtn.addEventListener('click', handleStartCase);
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', handleSendMessage);
    }

    if (userInput) {
        // Modified for <textarea>: Enter to send, Shift+Enter for newline
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !sendBtn.disabled) {
                e.preventDefault(); // Prevent adding a newline character in the textarea
                handleSendMessage();
            }
            // If only Enter is pressed (without Shift), and sendBtn is disabled, 
            // or if Shift+Enter is pressed, the default textarea behavior (newline) will occur.
        });
    }

    // --- Finish Case and Feedback Modal Logic ---
    if (finishBtn) {
        finishBtn.addEventListener('click', () => {
            console.log("[DEBUG_RENDER] finishBtn clicked. Current Organism Key:", currentOrganismKey);
            if (currentOrganismKey) {
                correctOrganismSpan.textContent = currentOrganismKey;
            } else {
                correctOrganismSpan.textContent = "Unknown (case not fully started or error occurred)";
            }
            console.log("[DEBUG_RENDER] Displaying feedback modal via finishBtn click.");
            feedbackModal.style.display = 'flex';
        });
    }

    if (closeFeedbackBtn) {
        closeFeedbackBtn.addEventListener('click', () => {
            console.log("[DEBUG_MODAL_CLOSE] closeFeedbackBtn clicked!");
            if (feedbackModal) {
                feedbackModal.style.display = 'none';
                console.log("[DEBUG_MODAL_CLOSE] feedbackModal.style.display set to 'none'.");
            } else {
                console.error("[DEBUG_MODAL_CLOSE] feedbackModal element not found when trying to close!");
            }
        });
    } else {
        console.error("[DEBUG_MODAL_CLOSE] closeFeedbackBtn element not found to attach listener!");
    }

    if (submitFeedbackBtn) {
        submitFeedbackBtn.addEventListener('click', async () => {
            const detailRating = document.querySelector('input[name="detail"]:checked');
            const helpfulnessRating = document.querySelector('input[name="helpfulness"]:checked');
            const accuracyRating = document.querySelector('input[name="accuracy"]:checked');
            const comments = document.getElementById('feedback-comments').value;

            if (!detailRating || !helpfulnessRating || !accuracyRating) {
                alert('Please provide a rating for all categories (detail, helpfulness, accuracy) or use skip.');
                return;
            }

            const feedbackData = {
                detail: detailRating.value,
                helpfulness: helpfulnessRating.value,
                accuracy: accuracyRating.value,
                comments: comments,
                case_id: currentCaseId, // Use the current case ID
                organism: currentOrganismKey // Log the organism for this case
            };

            setStatus('Submitting case feedback...');
            try {
                const response = await fetch('/case_feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(feedbackData),
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || `HTTP ${response.status}`);
                }

                setStatus('Case feedback submitted! Thank you. You can start a new case.');
                feedbackModal.style.display = 'none';

                // Reset UI for a new case
                chatbox.innerHTML = '<p class="status">Case finished. Select an organism and start a new case.</p>';
                disableInput(true); // Disable main chat input
                finishBtn.disabled = true; // Disable finish button
                userInput.value = '';

                // Clear the stored conversation state
                clearConversationState();
                chatHistory = [];
                currentCaseId = null;
                currentOrganismKey = null;

                // Reset feedback form for next time
                document.querySelectorAll('input[type="radio"]').forEach(radio => radio.checked = false);
                document.getElementById('feedback-comments').value = '';
                document.querySelectorAll('.skip-btn').forEach(btn => btn.disabled = false);

            } catch (error) {
                console.error('Error submitting case feedback:', error);
                setStatus(`Error submitting case feedback: ${error.message}`, true);
            }
        });
    }

    // Skip buttons for feedback
    document.querySelectorAll('.skip-btn').forEach(button => {
        button.addEventListener('click', function () {
            const questionName = this.dataset.question;
            const radioButtons = document.querySelectorAll(`input[name="${questionName}"]`);
            let isAnyChecked = false;
            radioButtons.forEach(radio => {
                if (radio.checked) {
                    isAnyChecked = true;
                }
                radio.checked = false; // Uncheck all
                radio.disabled = true; // Disable them
            });

            // Find the "not applicable" or a default value if you add one, e.g., 0 or "skipped"
            // For now, we'll just disable and uncheck.
            // If you have a specific "skipped" value, check that radio button.

            this.textContent = isAnyChecked ? 'Skipped (Reset)' : 'Skipped';
            this.disabled = true; // Disable skip button after skipping or allow re-enable?
            // For now, let's allow one skip.
        });
    });

    // Load any saved conversation state when the page loads
    if (!loadConversationState()) {
        // If no state was loaded, ensure input is disabled until a case is started
        console.log("[DEBUG_RENDER] No state loaded on initial page setup. Disabling input and finishBtn.");
        disableInput(true);
        finishBtn.disabled = true;
    } else {
        console.log("[DEBUG_RENDER] State WAS loaded on initial page setup. Input and finishBtn should be active.");
    }

    // Fetch cached organisms on page load
    fetchCachedOrganisms();
});

// Make the in_context_learning flag available (assuming it's set by your template)
// This line should be outside DOMContentLoaded if it's set by Flask template directly in a <script> tag
// window.in_context_learning = window.in_context_learning || false;
// It's already in your HTML, so it should be fine. 