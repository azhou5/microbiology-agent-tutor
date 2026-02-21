# MicroTutor V4 Frontend JavaScript Modules

This directory contains the modular JavaScript codebase for MicroTutor V4. The original monolithic `script.js` file (3090 lines) has been refactored into 14 focused modules, each handling a specific aspect of the application.

## Module Overview

### Core Modules (Load First)

#### `config.js`

**Purpose**: Centralized configuration constants  
**Dependencies**: None  
**Exports**: `API_BASE`, `STORAGE_KEYS`, `PHASE_DEFINITIONS`, `MCQ_KEYWORDS`, `MCQ_TOPIC_PATTERNS`  
**Description**: Contains all global configuration constants including API endpoints, LocalStorage keys, phase definitions, and MCQ detection patterns. This ensures consistent configuration across the entire application.

#### `utils.js`

**Purpose**: Reusable utility functions  
**Dependencies**: None  
**Exports**: `escapeHtml()`, `markdownToHtml()`, `truncateText()`, `generateCaseId()`, `generateSessionId()`, `validateChatHistory()`  
**Description**: Provides common helper functions used throughout the application, such as HTML escaping for security, markdown-to-HTML conversion, text truncation, and ID generation.

#### `state.js`

**Purpose**: Global application state management  
**Dependencies**: None  
**Exports**: `State` object with properties and `reset()` method  
**Description**: Centralizes all application state variables including chat history, current case ID, organism selection, phase tracking, feedback settings, voice recording state, and more. Provides a single source of truth for application state.

#### `dom.js`

**Purpose**: DOM element references  
**Dependencies**: None  
**Exports**: `DOM` object with element references and `init()` method  
**Description**: Centralizes all DOM element references, avoiding repeated `document.getElementById()` calls. Initializes once when DOM is loaded, providing clean and efficient access to HTML elements throughout the application.

### Storage Module

#### `storage.js`

**Purpose**: LocalStorage operations  
**Dependencies**: `config.js` (STORAGE_KEYS), `state.js` (State)  
**Exports**: `saveConversationState()`, `loadConversationState()`, `clearConversationState()`, `getSeenOrganisms()`, `addSeenOrganism()`, `clearSeenOrganisms()`, `loadFeedbackSettings()`, `saveFeedbackSettings()`  
**Description**: Encapsulates all interactions with browser LocalStorage. Handles saving/loading conversation state, tracking seen organisms, and persisting feedback settings. Provides a clean API for data persistence.

### Feature Modules

#### `chat.js`

**Purpose**: Chat messaging functionality  
**Dependencies**: `dom.js`, `state.js`, `utils.js`  
**Exports**: `addMessageToHistory()`, `setLastToolUsed()`, `detectSpeakerType()`, `getSpeakerAvatar()`, `createAudioPlayer()`, `addMessage()`, `setStatus()`, `disableInput()`  
**Description**: Handles core chat message display, including adding messages to the chat UI, managing message history, detecting speaker types (patient/doctor), creating audio players for voice responses, and managing input state.

#### `guidelines.js`

**Purpose**: Clinical guidelines fetching and display  
**Dependencies**: `dom.js`, `state.js`, `utils.js`, `config.js`  
**Exports**: `updateGuidelinesStatus()`, `displayGuidelines()`, `window.toggleGuidelineText()`, `showGuidelinesResults()`, `hideGuidelinesResults()`, `fetchGuidelines()`  
**Description**: Manages fetching and displaying clinical guidelines from the backend. Handles markdown rendering, text truncation/expansion, and updating the guidelines UI based on the selected organism.

#### `phase.js`

**Purpose**: Case study phase management  
**Dependencies**: `dom.js`, `state.js`, `config.js`  
**Exports**: `showPhaseProgression()`, `hidePhaseProgression()`, `resetPhaseToInformationGathering()`, `updatePhaseUI()`, `transitionToPhase()`, `updatePhaseLocking()`, `updatePhaseProgress()`, `updatePhaseGuidance()`, `updateCompletionCriteria()`  
**Description**: Manages the progression of microbiology case studies through defined phases (Information Gathering → Differential Diagnosis → Tests & Management → Feedback). Handles phase transitions, UI updates, locking/unlocking phases, and progress tracking.

#### `api.js`

**Purpose**: Backend API interactions  
**Dependencies**: `dom.js`, `state.js`, `config.js`, `chat.js`, `storage.js`  
**Exports**: `getAllOrganisms()`, `selectRandomOrganism()`, `handleStartCase()`, `handleSendMessage()`, `updateModelSelection()`, `updateCurrentModel()`, `syncWithBackendConfig()`  
**Description**: Contains all functions that make HTTP requests to the FastAPI backend. Handles starting new cases, sending chat messages, fetching organisms, model/provider selection, and syncing configuration with the backend.

#### `feedback.js`

**Purpose**: User feedback system  
**Dependencies**: `dom.js`, `state.js`, `api.js`, `chat.js`, `storage.js`  
**Exports**: `createFeedbackUI()`, `submitFeedback()`, `displayFeedbackExamples()`, `initializeFeedbackControls()`, `showThresholdNotification()`, `updateFeedbackControlsUI()`, `handleFinishCase()`, `closeFeedbackModal()`, `submitCaseFeedback()`  
**Description**: Manages the feedback system for both individual messages and complete cases. Handles creating feedback UI elements, submitting feedback to the API, displaying feedback examples, and managing feedback controls and thresholds.

#### `dashboard.js`

**Purpose**: Dashboard and analytics  
**Dependencies**: `dom.js`, `state.js`, `config.js`  
**Exports**: `initDashboard()`, `loadDashboardData()`, `loadTrendsData()`, `updateStatsDisplay()`, `updateFAISSStatus()`, `fetchFAISSStatus()`, `updateTrendsChart()`, `toggleChart()`, `startAutoRefresh()`, `stopAutoRefresh()`, `fetchFeedbackStats()`, `updateFeedbackStatsDisplay()`, `initializeFeedbackCounter()`  
**Description**: Handles dashboard functionality including displaying feedback statistics, FAISS re-indexing status, trends charts, and auto-refresh capabilities. Provides analytics and monitoring features for administrators.

#### `voice.js`

**Purpose**: Voice recording and transcription  
**Dependencies**: `dom.js`, `state.js`, `chat.js`, `api.js`  
**Exports**: `isSecureContext()`, `checkVoiceAvailability()`, `requestMicrophonePermission()`, `setVoiceStatus()`, `startRecording()`, `stopRecording()`, `sendVoiceMessage()`, `playAudioResponse()`, `handleVoiceButton()`  
**Description**: Manages voice recording functionality using the Web Audio API. Handles microphone access permissions, recording audio, sending recordings to the backend for transcription, and playing audio responses. Includes security context checks and error handling.

#### `mcq.js`

**Purpose**: Multiple Choice Questions  
**Dependencies**: `dom.js`, `state.js`, `config.js`, `api.js`, `chat.js`  
**Exports**: `getCurrentCaseContext()`, `initializeMCQ()`, `generateMCQ()`, `displayMCQ()`, `handleMCQResponse()`, `displayMCQFeedback()`, `window.generateNextMCQ()`, `window.clearMCQ()`, `enhancedSendMessage()`  
**Description**: Handles Multiple Choice Question generation, display, and response processing. Detects MCQ requests in user messages, generates questions based on topics, displays interactive MCQ UI, processes user responses, and provides feedback. Integrates with the chat system.

### Initialization Module

#### `main.js`

**Purpose**: Application initialization and event handlers  
**Dependencies**: All other modules  
**Exports**: None (runs on DOMContentLoaded)  
**Description**: The entry point that initializes all modules and sets up event listeners. Handles DOMContentLoaded event, attaches event handlers to buttons and inputs, initializes dashboard, feedback controls, and MCQ functionality. Coordinates the startup sequence of the entire application.

## Module Loading Order

Modules must be loaded in the following order due to dependencies:

1. `config.js` - Configuration constants
2. `utils.js` - Utility functions
3. `state.js` - State management
4. `dom.js` - DOM references
5. `storage.js` - LocalStorage (depends on config, state)
6. `chat.js` - Chat functionality (depends on dom, state, utils)
7. `guidelines.js` - Guidelines (depends on dom, state, utils, config)
8. `phase.js` - Phase management (depends on dom, state, config)
9. `api.js` - API calls (depends on dom, state, config, chat, storage)
10. `feedback.js` - Feedback system (depends on dom, state, api, chat, storage)
11. `dashboard.js` - Dashboard (depends on dom, state, config)
12. `voice.js` - Voice recording (depends on dom, state, chat, api)
13. `mcq.js` - MCQ functionality (depends on dom, state, config, api, chat)
14. `main.js` - Initialization (depends on all modules)

## Architecture Principles

### Single Responsibility

Each module has a single, well-defined responsibility. For example, `chat.js` only handles message display, while `api.js` only handles HTTP requests.

### Dependency Management

Modules explicitly declare their dependencies through function calls. The loading order ensures dependencies are available when needed.

### State Centralization

All application state is managed through the `State` object in `state.js`, preventing scattered state variables and making debugging easier.

### DOM Access

All DOM element access goes through the `DOM` object in `dom.js`, avoiding repeated `getElementById` calls and making it easier to track which elements are used.

### Configuration Management

All configuration constants are centralized in `config.js`, making it easy to update API endpoints, storage keys, or phase definitions.

## Usage Examples

### Adding a New Feature Module

1. Create a new file (e.g., `newfeature.js`)
2. Add functions that follow the existing patterns
3. Use `DOM` for element access, `State` for state management
4. Add the script tag to `index.html` in the correct dependency order
5. Initialize the feature in `main.js` if needed

### Accessing State

```javascript
// Read state
const currentPhase = State.currentPhase;

// Update state
State.currentPhase = 'differential_diagnosis';

// Reset state
State.reset();
```

### Accessing DOM Elements

```javascript
// Access elements through DOM object
if (DOM.chatbox) {
    DOM.chatbox.scrollTop = DOM.chatbox.scrollHeight;
}
```

### Making API Calls

```javascript
// Use functions from api.js
const response = await handleSendMessage();
```

## Notes

- The original `script.js` file (3090 lines) has been preserved as a backup
- All modules use vanilla JavaScript (no frameworks)
- Functions are designed to be pure where possible, with side effects clearly documented
- Error handling is implemented throughout, with console logging for debugging
- The code follows consistent naming conventions and includes JSDoc-style comments

## Future Improvements

Potential enhancements for the modular structure:

- Add TypeScript for type safety
- Implement a module bundler (e.g., Webpack, Rollup) for production builds
- Add unit tests for each module
- Implement a proper event system for inter-module communication
- Add JSDoc documentation generation
- Consider using ES6 modules with import/export syntax
