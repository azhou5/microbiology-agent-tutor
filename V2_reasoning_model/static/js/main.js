var sessionId = "";
var isStreaming = false;
var revealedInfo = {
    history: {},
    exam: {},
    labs: {}
};
var currentOrganism = null;

// Initialize the all prompts collection for downloading
window.allPrompts = {
    "tutor": [],
    "case_presenter": [],
    "patient": []
};

// Initialize the debug panel on page load
window.onload = function () {
    // Make sure the debug content is visible
    const debugContent = document.getElementById('agentTabContent');
    if (debugContent) {
        debugContent.style.display = 'block';
    }

    // Add a welcome message to each debug panel
    const panels = ['tutor-debug', 'case-presenter-debug', 'patient-debug'];
    panels.forEach(panelId => {
        const panel = document.getElementById(panelId);
        if (panel && panel.childNodes.length === 0) {
            updateAgentDebug(panelId, {
                title: "Debug Panel Ready",
                input: "Waiting for messages...",
                timestamp: new Date().toISOString()
            });
        }
    });
};

function setProcessing(processing) {
    isStreaming = processing;

    // Add null checks for all DOM elements
    const userInput = document.getElementById('user-input');
    if (userInput) userInput.disabled = processing;

    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) sendBtn.disabled = processing;

    const startCaseBtn = document.getElementById('start-case-btn');
    if (startCaseBtn) startCaseBtn.disabled = processing;

    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) resetBtn.disabled = processing;

    const testCaseBtn = document.getElementById('test-case-btn');
    if (testCaseBtn) testCaseBtn.disabled = processing;

    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) typingIndicator.style.display = processing ? 'block' : 'none';

    console.log(`Set processing state to: ${processing}`);
}

function createMessageDiv(isUser = false) {
    const chatContainer = document.getElementById('chat-container');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'tutor-message streaming'}`;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return messageDiv;
}

function addMessage(message, isUser = false) {
    const messageDiv = createMessageDiv(isUser);
    messageDiv.classList.remove('streaming');
    messageDiv.textContent = message;
    return messageDiv;
}

function updateRevealedInfo(newInfo) {
    if (!newInfo) {
        console.log("updateRevealedInfo called with no data");
        return;
    }

    console.log("Updating revealed info with:", newInfo);

    // Merge new info with existing info
    if (newInfo.history) {
        console.log("Merging history info:", newInfo.history);
        revealedInfo.history = { ...revealedInfo.history, ...newInfo.history };
    }
    if (newInfo.exam) {
        console.log("Merging exam info:", newInfo.exam);
        revealedInfo.exam = { ...revealedInfo.exam, ...newInfo.exam };
    }
    if (newInfo.labs) {
        console.log("Merging labs info:", newInfo.labs);
        revealedInfo.labs = { ...revealedInfo.labs, ...newInfo.labs };
    }

    // Log the updated info
    console.log("Updated revealed info:", revealedInfo);

    // Update the UI
    updateRevealedInfoUI();
}

function updateRevealedInfoUI() {
    console.log("Updating revealed info UI with:", revealedInfo);

    // Helper function to truncate long text
    const truncateText = (text, maxLength = 60) => {
        if (text && text.length > maxLength) {
            return text.substring(0, maxLength) + '...';
        }
        return text;
    };

    // Update history info
    const historyList = document.getElementById('history-info');
    historyList.innerHTML = '';
    for (const [key, value] of Object.entries(revealedInfo.history)) {
        console.log(`Adding history item: ${key} = ${value}`);
        const li = document.createElement('li');
        li.className = 'list-group-item history-item compact-item';
        li.innerHTML = `<strong class="history-header">${truncateText(key, 30)}</strong><div class="info-content">${truncateText(value, 60)}</div>`;
        historyList.appendChild(li);
    }

    // Update exam info
    const examList = document.getElementById('exam-info');
    examList.innerHTML = '';
    for (const [key, value] of Object.entries(revealedInfo.exam)) {
        console.log(`Adding exam item: ${key} = ${value}`);
        const li = document.createElement('li');
        li.className = 'list-group-item exam-item compact-item';
        li.innerHTML = `<strong class="exam-header">${truncateText(key, 30)}</strong><div class="info-content">${truncateText(value, 60)}</div>`;
        examList.appendChild(li);
    }

    // Update labs info
    const labsList = document.getElementById('labs-info');
    labsList.innerHTML = '';
    for (const [key, value] of Object.entries(revealedInfo.labs)) {
        console.log(`Adding labs item: ${key} = ${value}`);
        const li = document.createElement('li');
        li.className = 'list-group-item labs-item compact-item';
        li.innerHTML = `<strong class="labs-header">${truncateText(key, 30)}</strong><div class="info-content">${truncateText(value, 60)}</div>`;
        labsList.appendChild(li);
    }

    // If an organism is set, display it
    if (currentOrganism) {
        // Update the badge
        const organismBadge = document.getElementById('organism-badge');
        const currentOrganismBadge = document.getElementById('current-organism-badge');

        organismBadge.style.display = 'inline-block';
        currentOrganismBadge.textContent = currentOrganism;

        // Check if organism element already exists
        let organismElement = document.getElementById('current-organism');
        if (!organismElement) {
            // Create a new element for the organism
            const revealedInfoDiv = document.getElementById('revealed-info');
            const heading = document.createElement('h5');
            heading.className = 'mt-2 mb-1';
            heading.textContent = 'Current Organism';
            revealedInfoDiv.appendChild(heading);

            organismElement = document.createElement('p');
            organismElement.id = 'current-organism';
            organismElement.className = 'text-center fw-bold text-primary small mb-0';
            revealedInfoDiv.appendChild(organismElement);
        }

        // Update the organism text
        organismElement.textContent = currentOrganism;
    } else {
        // Hide the badge if no organism
        const organismBadge = document.getElementById('organism-badge');
        organismBadge.style.display = 'none';
    }
}

function sendMessage() {
    const messageInput = document.getElementById('user-input');
    const message = messageInput.value.trim();

    if (!message) return;

    const messagesContainer = document.getElementById('chat-container');

    // Add user message to the chat
    const userDiv = document.createElement('div');
    userDiv.className = 'message user-message';
    userDiv.textContent = message;
    messagesContainer.appendChild(userDiv);

    // Clear the input field
    messageInput.value = '';

    // Disable the input while waiting for a response
    setProcessing(true);

    // Scroll to the bottom of the messages
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Update URL to include session ID if available
    let url = `/chat_alt?message=${encodeURIComponent(message)}`;
    if (sessionId) {
        url += `&session_id=${sessionId}`;
    }

    // Send the request
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Response data:", data);

            // Check if we have valid data
            if (!data) {
                throw new Error("Empty response received from server");
            }

            // Only try to process if there's a chunk in the response
            if (data.chunk) {
                // Display the response message
                const tutorDiv = document.createElement('div');
                tutorDiv.className = 'message tutor-message';
                tutorDiv.innerHTML = data.chunk.replace(/\n/g, '<br>');
                messagesContainer.appendChild(tutorDiv);

                // Scroll to the bottom of the messages
                messagesContainer.scrollTop = messagesContainer.scrollHeight;

                // Update the debug panels with agent inputs and llm prompts
                updateAgentDebugPanels(data, message);

                // Check if revealed info is being processed asynchronously
                if (data.revealed_info_status === "processing" && sessionId) {
                    console.log("Revealed info is being processed asynchronously");
                    // Start polling for revealed info updates
                    pollForRevealedInfo(sessionId);
                } else if (data.revealed_info) {
                    // If revealed info was returned synchronously (backward compatibility)
                    updateRevealedInfo(data.revealed_info);
                }

                // Re-enable the input only after successful response
                setProcessing(false);

                // Return early to prevent error handling code from running
                return;
            }

            // If error occurred, show it
            if (data.error) {
                console.error("Error:", data.error);
                // Display error message
                const errorDiv = document.createElement('div');
                errorDiv.className = 'message error-message';
                errorDiv.textContent = data.error;
                messagesContainer.appendChild(errorDiv);
            }

            // Re-enable the input
            setProcessing(false);
        })
        .catch(error => {
            console.error("Error sending message:", error);

            // Only display error message if we haven't already shown a valid response
            // Check if we've already added a tutorDiv message in this response cycle
            const lastMessage = messagesContainer.lastElementChild;
            const alreadyDisplayedResponse = lastMessage && lastMessage.classList.contains('tutor-message') &&
                lastMessage.textContent && lastMessage.textContent.trim() !== '';

            if (!alreadyDisplayedResponse) {
                // Display error message
                const errorDiv = document.createElement('div');
                errorDiv.className = 'message error-message';
                errorDiv.textContent = "Error sending message. Please try again later.";
                messagesContainer.appendChild(errorDiv);
            }

            // Re-enable the input
            setProcessing(false);
        });
}

function pollForRevealedInfo(sessionId, maxAttempts = 10, attempt = 1) {
    // Don't poll too many times
    if (attempt > maxAttempts) {
        console.log("Max polling attempts reached for revealed info");
        return;
    }

    // Calculate delay: exponential backoff with a base of 1 second
    const delay = 1000 * Math.pow(1.5, attempt - 1);

    // Schedule the poll after the delay
    setTimeout(() => {
        console.log(`Polling for revealed info, attempt ${attempt} of ${maxAttempts}`);

        fetch(`/get_revealed_info?session_id=${sessionId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("Revealed info poll result:", data);

                if (data.status === "success" && data.revealed_info) {
                    // Successfully got revealed info, update the UI
                    updateRevealedInfo(data.revealed_info);
                    console.log("Successfully updated revealed info");

                    // Show a subtle indicator that the info was updated
                    const revealedInfoDiv = document.getElementById('revealed-info');
                    if (revealedInfoDiv) {
                        revealedInfoDiv.classList.add('flash-update');
                        // Remove the flash effect after animation completes
                        setTimeout(() => {
                            revealedInfoDiv.classList.remove('flash-update');
                        }, 1000);
                    }

                } else if (data.status === "processing") {
                    // Still processing, poll again
                    pollForRevealedInfo(sessionId, maxAttempts, attempt + 1);

                } else if (data.status === "error") {
                    console.error("Error retrieving revealed info:", data.error);
                    // Don't need to show an error to the user as this is just supplementary info
                }
            })
            .catch(error => {
                console.error("Error polling for revealed info:", error);
                // Try again with backoff if there was a network error
                pollForRevealedInfo(sessionId, maxAttempts, attempt + 1);
            });
    }, delay);
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

function processUserMessage(message) {
    // Log the message going to the tutor
    updateAgentDebug('tutor-debug', {
        message: message,
        sessionId: sessionId || 'none',
        timestamp: new Date().toISOString()
    });

    console.log(`Processing message: '${message}' with session ID: '${sessionId}'`);

    // Create a new event source for the response
    if (!sessionId) {
        // If no session exists, create one
        sessionId = "test_session"; // In a real app, generate a unique session ID
        console.log(`No session ID found, using default: ${sessionId}`);
    }

    // Check if the message is a new case request
    if (message.toLowerCase().startsWith('new case')) {
        // Extract organism if specified
        let organism = null;
        if (message.toLowerCase().includes('with')) {
            const parts = message.toLowerCase().split('with');
            if (parts.length > 1 && parts[1].trim()) {
                organism = parts[1].trim();
            }
        }

        // If organism specified, use it, otherwise direct to organism selection page
        if (organism) {
            currentMessageDiv = createMessageDiv();
            fetchWithOrganism(organism);
        } else {
            window.location.href = '/organisms';
            return;
        }
    } else {
        // Regular message processing
        currentMessageDiv = createMessageDiv();

        // Add progress indicator for chat
        let timeoutCount = 0;
        let progressIndicator;

        function updateProgress() {
            timeoutCount++;
            if (currentMessageDiv) {
                if (!progressIndicator) {
                    progressIndicator = document.createElement('div');
                    progressIndicator.className = 'progress-indicator';
                    progressIndicator.style.fontStyle = 'italic';
                    progressIndicator.style.marginTop = '10px';
                    progressIndicator.style.color = '#666';
                    currentMessageDiv.parentNode.insertBefore(progressIndicator, currentMessageDiv.nextSibling);
                }
                progressIndicator.textContent = `Thinking${'.'.repeat(timeoutCount % 4)}`;
            }
        }

        // Start the progress indicator
        const progressInterval = setInterval(updateProgress, 1000);

        // Prepare request URL with proper encoding
        const requestUrl = `/chat_alt?message=${encodeURIComponent(message)}&session_id=${encodeURIComponent(sessionId)}`;
        console.log(`Sending request to: ${requestUrl}`);

        // Use the new GET endpoint instead of POST with form data
        fetch(requestUrl, {
            method: 'GET'
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                // Clear the progress indicator
                clearInterval(progressInterval);
                if (progressIndicator) {
                    progressIndicator.remove();
                }

                console.log("Chat response data:", data);

                // Check if we have valid data
                if (!data) {
                    throw new Error("Empty response received from server");
                }

                // Update all agent debug panels with available input information
                updateAgentDebugPanels(data, message);

                if (data.error) {
                    console.error(`Error in response: ${data.error}`);
                    currentMessageDiv.textContent = `Error: ${data.error}`;
                } else if (data.chunk) {
                    console.log(`Received response chunk: ${data.chunk.substring(0, 50)}...`);
                    // Update the response text
                    currentMessageDiv.textContent = data.chunk;

                    // Update revealed info if provided
                    if (data.revealed_info) {
                        updateRevealedInfo(data.revealed_info);
                    }

                    // Update organism if provided
                    if (data.organism) {
                        currentOrganism = data.organism;
                        updateRevealedInfoUI();
                    }
                } else {
                    // Fallback response if no chunk is provided
                    console.error("No chunk in response");
                    currentMessageDiv.textContent = "The tutor did not provide a response. Please try again.";
                }
            })
            .catch(error => {
                console.error('Error:', error);
                // Clear the progress indicator
                clearInterval(progressInterval);
                if (progressIndicator) {
                    progressIndicator.remove();
                }
                currentMessageDiv.textContent = "Error: Failed to get response from server. Please check your connection and try again.";
            })
            .finally(() => {
                // Remove streaming class and set processing to false
                currentMessageDiv.classList.remove('streaming');
                setProcessing(false);
                console.log("Message processing complete");
            });
    }
}

function fetchWithOrganism(organism) {
    const eventSource = new EventSource(`/start_case?organism=${encodeURIComponent(organism)}`);
    let fullResponse = '';
    let timeoutCount = 0;
    let progressIndicator;
    let isRandomCase = organism === "RANDOM_CASE";

    // Add a progress/waiting indicator
    function updateProgress() {
        timeoutCount++;
        if (currentMessageDiv) {
            if (!progressIndicator) {
                progressIndicator = document.createElement('div');
                progressIndicator.className = 'progress-indicator';
                progressIndicator.style.fontStyle = 'italic';
                progressIndicator.style.marginTop = '10px';
                progressIndicator.style.color = '#666';
                currentMessageDiv.parentNode.insertBefore(progressIndicator, currentMessageDiv.nextSibling);
            }
            progressIndicator.textContent = `Generating case${'.'.repeat(timeoutCount % 4)}`;
        }
    }

    // Start the progress indicator
    const progressInterval = setInterval(updateProgress, 1000);

    // Handle 'start' event
    eventSource.addEventListener('start', function (event) {
        console.log("Received start event:", event.data);
        if (currentMessageDiv) {
            currentMessageDiv.textContent = event.data;
        }
    });

    // Handle 'update' event
    eventSource.addEventListener('update', function (event) {
        console.log("Received update event:", event.data);
        if (currentMessageDiv) {
            currentMessageDiv.textContent = event.data;
        }
    });

    // Handle 'complete' event (for GitHub workflow)
    eventSource.addEventListener('complete', function (event) {
        console.log("Received complete event");

        var data = JSON.parse(event.data);
        console.log("Complete data:", data);

        // Update UI with the generated case
        addMessage(data.message, false);

        // Store session ID
        sessionId = data.session_id;

        // Check if revealed info is being processed asynchronously
        if (data.revealed_info_status === "processing" && sessionId) {
            console.log("Revealed info for case start is being processed asynchronously");
            // Start polling for revealed info updates
            pollForRevealedInfo(sessionId);
        } else if (data.revealed_info) {
            // Backward compatibility: if revealed info was returned directly
            revealedInfo = data.revealed_info;
            updateRevealedInfoUI();
        }

        // If this is a case with a specific organism, show the badge
        if (data.is_random_case || data.organism) {
            currentOrganism = data.organism || organism;
            $("#current-organism-badge").text(currentOrganism);
            $("#organism-badge").show();
            updateRevealedInfoUI(); // Update organism in revealed info panel
        }

        // Re-enable buttons
        $("#start-case-btn").prop("disabled", false);
        $("#reset-btn").prop("disabled", false);
        $("#test-case-btn").prop("disabled", false);

        // Hide typing indicator
        $(".typing-indicator").hide();

        // Close the event source
        eventSource.close();
    });

    // Handle 'error' event
    eventSource.addEventListener('error', function (event) {
        console.error("Received error event:", event);

        // Clear the progress indicator
        clearInterval(progressInterval);
        if (progressIndicator) {
            progressIndicator.remove();
        }

        // Try to extract error message from event data
        let errorMsg = "Error getting response from server";
        if (event.data) {
            try {
                const data = JSON.parse(event.data);
                errorMsg = data.error || errorMsg;
            } catch (e) {
                // If parsing fails, use the event data directly
                errorMsg = event.data || errorMsg;
            }
        }

        // Display error message
        if (currentMessageDiv) {
            currentMessageDiv.textContent = "Error: " + errorMsg;
            currentMessageDiv.classList.remove('streaming');
        }

        setProcessing(false);
        eventSource.close();
    });

    // Add a general onerror handler as a fallback for any other errors
    eventSource.onerror = function (error) {
        console.error("EventSource general error:", error);

        // Clear the progress indicator
        clearInterval(progressInterval);
        if (progressIndicator) {
            progressIndicator.remove();
        }

        if (currentMessageDiv) {
            currentMessageDiv.textContent = "Error: Connection to server failed. Please try again.";
            currentMessageDiv.classList.remove('streaming');
        }

        setProcessing(false);
        eventSource.close();
    };

    // Set timeout to close connection if no response
    setTimeout(function () {
        // Clear the progress indicator
        clearInterval(progressInterval);
        if (progressIndicator) {
            progressIndicator.remove();
        }

        if (eventSource.readyState !== 2) { // 2 = CLOSED
            console.log("Closing EventSource due to timeout");
            eventSource.close();
            if (currentMessageDiv) {
                currentMessageDiv.textContent = "Error: Request timed out. This might be due to a connection issue or the case generation taking too long. Please try again or choose a different organism.";
                currentMessageDiv.classList.remove('streaming');
            }
            setProcessing(false);
        }
    }, 60000); // 60 second timeout
}

function resetSession() {
    if (isStreaming) return;

    // Set processing state
    setProcessing(true);

    // Use URLSearchParams for proper form encoding
    const formData = new URLSearchParams();
    formData.append('session_id', sessionId);

    // Try POST request first
    fetch('/reset', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
    })
        .then(response => {
            if (!response.ok) {
                // If POST fails, try GET as fallback
                console.log("POST reset failed, trying GET...");
                return fetch(`/reset_alt?session_id=${sessionId}`);
            }
            return response;
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Reset response data:", data);

            // Clear the chat container
            document.getElementById('chat-container').innerHTML = '';
            document.getElementById('typing-indicator').style.display = 'none';

            // Reset revealed info
            revealedInfo = {
                history: {},
                exam: {},
                labs: {}
            };
            currentOrganism = null;
            updateRevealedInfoUI();

            // Hide the organism badge
            const organismBadge = document.getElementById('organism-badge');
            organismBadge.style.display = 'none';

            // Add system message
            if (data.chunk) {
                addMessage(data.chunk);
            } else {
                addMessage('Session reset. Click "Select Organism" to begin.');
            }

            // Unset processing state
            setProcessing(false);
        })
        .catch(error => {
            console.error('Error:', error);
            addMessage('Error resetting session. Please try again.');
            setProcessing(false);
        });
}

// Helper function to get URL parameters
function getUrlParameter(name) {
    name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
    var regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
    var results = regex.exec(location.search);
    return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
}

// Check for organism parameter and testing mode parameter in URL
$(document).ready(function () {
    var organism = getUrlParameter('organism');
    var testingMode = getUrlParameter('testing_mode') === 'true';

    if (organism) {
        // Automatically start case with the provided organism
        startCaseWithOrganism(organism, testingMode);
    }
});

function startCaseWithOrganism(organism, testingMode = false) {
    $("#chat-container").empty();
    $(".typing-indicator").show();
    $("#start-case-btn").prop("disabled", true);
    $("#reset-btn").prop("disabled", true);
    $("#test-case-btn").prop("disabled", true);

    // Create a new event source for SSE
    var source = new EventSource(`/start_case?organism=${encodeURIComponent(organism)}&testing_mode=${testingMode}`);

    // Listen for "start" events
    source.addEventListener("start", function (event) {
        console.log("Received start event:", event.data);
        // Optionally update UI to show that case generation has started
        addMessage("Tutor: " + event.data, false);
    });

    // Listen for "update" events
    source.addEventListener("update", function (event) {
        console.log("Received update event:", event.data);
        // Update UI with progress
        addMessage("Tutor: " + event.data, false);
    });

    // Listen for "complete" events (for GitHub workflow)
    source.addEventListener("complete", function (event) {
        console.log("Received complete event");

        var data = JSON.parse(event.data);
        console.log("Complete data:", data);

        // Update UI with the generated case
        addMessage(data.message, false);

        // Store session ID
        sessionId = data.session_id;

        // Check if revealed info is being processed asynchronously
        if (data.revealed_info_status === "processing" && sessionId) {
            console.log("Revealed info for case start is being processed asynchronously");
            // Start polling for revealed info updates
            pollForRevealedInfo(sessionId);
        } else if (data.revealed_info) {
            // Backward compatibility: if revealed info was returned directly
            revealedInfo = data.revealed_info;
            updateRevealedInfoUI();
        }

        // If this is a case with a specific organism, show the badge
        if (data.is_random_case || data.organism) {
            currentOrganism = data.organism || organism;
            $("#current-organism-badge").text(currentOrganism);
            $("#organism-badge").show();
            updateRevealedInfoUI(); // Update organism in revealed info panel
        }

        // Re-enable buttons
        $("#start-case-btn").prop("disabled", false);
        $("#reset-btn").prop("disabled", false);
        $("#test-case-btn").prop("disabled", false);

        // Hide typing indicator
        $(".typing-indicator").hide();

        // Close the event source
        source.close();
    });

    // Listen for "error" events
    source.addEventListener("error", function (event) {
        console.error("Error event received");

        if (event.data) {
            var errorData = JSON.parse(event.data);
            console.error("Error data:", errorData);

            // Display error in chat
            addMessage("Tutor: Error - " + (errorData.error || "Failed to generate case"), false);
        } else {
            addMessage("Tutor: An error occurred while generating the case.", false);
        }

        // Re-enable buttons
        $("#start-case-btn").prop("disabled", false);
        $("#reset-btn").prop("disabled", false);
        $("#test-case-btn").prop("disabled", false);

        // Hide typing indicator
        $(".typing-indicator").hide();

        // Close the event source
        source.close();
    });
}

// Function to show the organism badge
function showOrganismBadge(organism) {
    document.getElementById('organism-badge').style.display = 'inline-block';
    document.getElementById('current-organism-badge').textContent = organism;
}

// Function to hide the organism badge
function hideOrganismBadge() {
    document.getElementById('organism-badge').style.display = 'none';
    document.getElementById('current-organism-badge').textContent = '';
}

// Add this new function after setProcessing
function enableUserInput() {
    try {
        // Enable the input field and send button
        const userInput = document.getElementById('user-input');
        if (userInput) {
            userInput.disabled = false;
            // Focus on the input field for immediate typing
            userInput.focus();
        }

        const sendBtn = document.getElementById('send-btn');
        if (sendBtn) sendBtn.disabled = false;

        // Update UI state using the safer function
        setProcessing(false);

        console.log("User input enabled successfully");
    } catch (error) {
        console.error("Error enabling user input:", error);
    }
}

// Add function to start test case
function startTestCase() {
    try {
        // Clear current chat
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) chatContainer.innerHTML = '';

        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) typingIndicator.style.display = 'block';

        // Disable buttons during loading
        setProcessing(true);

        // Create a new event source for the test case endpoint
        var source = new EventSource("/test_case");

        // Set a timeout in case the connection hangs
        const timeoutId = setTimeout(() => {
            console.error("Test case request timed out");
            source.close();
            addMessage("Tutor: The test case request timed out. Please try again.", false);
            setProcessing(false);
        }, 30000); // 30 second timeout

        // Listen for "start" events
        source.addEventListener("start", function (event) {
            console.log("Test case: Received start event:", event.data);
            addMessage("Tutor: " + event.data, false);
        });

        // Listen for "update" events
        source.addEventListener("update", function (event) {
            console.log("Test case: Received update event:", event.data);
            addMessage("Tutor: " + event.data, false);
        });

        // Listen for "complete" events
        source.addEventListener("complete", function (event) {
            // Clear timeout since we got a response
            clearTimeout(timeoutId);

            console.log("Test case: Received complete event");

            try {
                var data = JSON.parse(event.data);
                console.log("Test case complete data:", data);

                // Update UI with the test case
                addMessage(data.message, false);

                // Store session ID
                if (data.session_id) {
                    sessionId = data.session_id;
                    console.log("Set session ID from test case to:", sessionId);
                }

                // Update revealed info
                if (data.revealed_info) {
                    revealedInfo = data.revealed_info;
                    updateRevealedInfoUI();
                }

                // If organism info is available, update the organism badge
                if (data.organism) {
                    currentOrganism = data.organism;
                    showOrganismBadge(data.organism);
                }

                // Re-enable buttons and hide typing indicator
                setProcessing(false);

            } catch (error) {
                console.error("Error processing test case complete event:", error);
                addMessage("Tutor: Error loading test case. Please try again.", false);
                setProcessing(false);
            }

            // Close the event source
            source.close();
        });

        // Listen for "error" events
        source.addEventListener("error", function (event) {
            // Clear timeout since we got a response
            clearTimeout(timeoutId);

            console.error("Test case: Error event received");

            var errorMessage = "An error occurred while loading the test case.";

            if (event.data) {
                try {
                    var errorData = JSON.parse(event.data);
                    console.error("Test case error data:", errorData);
                    errorMessage = "Error: " + (errorData.error || "Failed to load test case");
                } catch (e) {
                    console.error("Failed to parse error data:", e);
                }
            }

            // Display error in chat
            addMessage("Tutor: " + errorMessage, false);

            // Re-enable buttons and hide typing indicator
            setProcessing(false);

            // Close the event source
            source.close();
        });
    } catch (error) {
        console.error("Error starting test case:", error);
        addMessage("Tutor: Error starting test case: " + error.message, false);
        setProcessing(false);
    }
}

// Escape HTML function for safely displaying prompts
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Function to download all prompts as JSON
function downloadPrompts() {
    // Create a formatted timestamp for the filename
    const now = new Date();
    const dateStr = now.toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19);

    // Create a download link
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(window.allPrompts, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `agent_prompts_${dateStr}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
}

// Function to save conversation history to a file
function downloadConversationHistory() {
    if (!sessionId) {
        alert("No active conversation to save. Please start a case first.");
        return;
    }

    // Create a GET request to fetch conversation history
    fetch(`/get_conversation?session_id=${sessionId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                alert(`Error: ${data.error}`);
                return;
            }

            // Create a formatted timestamp for the filename
            const now = new Date();
            const dateStr = now.toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19);
            const organism = currentOrganism || "unknown_organism";

            // Format the conversation history for better readability
            const formattedHistory = data.conversation_history.map(item =>
                `User: ${item.user_message}\n\nTutor: ${item.ai_response}\n\n-----------\n\n`
            ).join('');

            // Create a download link for text file
            const dataStr = "data:text/plain;charset=utf-8," + encodeURIComponent(formattedHistory);
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", dataStr);
            downloadAnchorNode.setAttribute("download", `case_${organism}_${dateStr}.txt`);
            document.body.appendChild(downloadAnchorNode);
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        })
        .catch(error => {
            console.error("Error downloading conversation:", error);
            alert("Failed to download conversation history. Please try again.");
        });
}

// Add event listener for the save case button
document.addEventListener('DOMContentLoaded', function () {
    const saveCaseBtn = document.getElementById('save-case-btn');
    if (saveCaseBtn) {
        saveCaseBtn.addEventListener('click', downloadConversationHistory);
    }
});