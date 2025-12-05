# MicroTutor V4 Template Structure

This directory contains the Jinja2 templates for MicroTutor V4. The main `index.html` file has been modularized into reusable partials that align with the JavaScript module structure.

## Template Overview

### Main Template

#### `index.html`

**Purpose**: Main application template  
**Description**: The primary HTML template that assembles all partials using Jinja2 `{% include %}` statements. This file provides the overall structure and loads all component partials in the correct order.

### Partials (in `partials/` directory)

#### `header.html`

**Purpose**: Application header  
**Related JS modules**: None (static content)  
**Description**: Contains the main application title and subtitle. Simple static header component.

#### `instructions.html`

**Purpose**: Case flow instructions  
**Related JS modules**: None (static content)  
**Description**: Displays the four-phase case flow instructions to guide users through the application workflow.

#### `case-setup.html`

**Purpose**: Case initialization controls  
**Related JS modules**: `api.js`, `dom.js`  
**Description**: Contains organism selection dropdown, model provider toggle, model selection dropdown, and the "Start New Case" button. This is the primary interface for starting a new microbiology case study.

**Key Elements**:

- `#organism-select` - Organism selection dropdown
- `#guidelines-toggle` - Toggle for fetching guidelines
- `#azure-provider` / `#personal-provider` - Model provider radio buttons
- `#model-select` - Model selection dropdown
- `#start-case-btn` - Button to start a new case

#### `guidelines.html`

**Purpose**: Clinical guidelines display  
**Related JS modules**: `guidelines.js`  
**Description**: Container for displaying clinical guidelines fetched from the backend. Shows guidelines status, count, and content with markdown rendering support.

**Key Elements**:

- `#guidelines-results` - Main container (hidden by default)
- `#guidelines-status` - Status indicator
- `#guidelines-count` - Results count badge
- `#guidelines-content` - Content area for guidelines

#### `feedback-controls.html`

**Purpose**: Feedback system configuration  
**Related JS modules**: `feedback.js`  
**Description**: Controls for enabling/disabling AI feedback and adjusting the similarity threshold for feedback examples.

**Key Elements**:

- `#feedback-toggle` - Enable/disable feedback checkbox
- `#threshold-slider` - Similarity threshold slider
- `#threshold-value` - Display of current threshold value

#### `chat-container.html`

**Purpose**: Main chat interface  
**Related JS modules**: `chat.js`, `voice.js`, `mcq.js`  
**Description**: The primary chat interface including the chatbox, input area, voice button, send button, and finish case button. This is where all user interactions with the AI tutor occur.

**Key Elements**:

- `#chatbox` - Main chat message container
- `#user-input` - Text input area
- `#voice-btn` - Voice recording button
- `#send-btn` - Send message button
- `#finish-btn` - Finish case button
- `#voice-status` - Voice recording status display
- `#response-audio` - Audio element for playing responses

#### `phase-progression.html`

**Purpose**: Case phase navigation sidebar  
**Related JS modules**: `phase.js`  
**Description**: Sidebar showing the current case phase and allowing navigation between phases. Displays phase guidance and progress indicators.

**Key Elements**:

- `#phase-progression` - Main container (hidden by default)
- `.phase-btn` - Phase navigation buttons (data-phase attribute)
- `#phase-guidance-text` - Current phase guidance text

#### `dashboard.html`

**Purpose**: Analytics and statistics dashboard  
**Related JS modules**: `dashboard.js`  
**Description**: Displays live feedback analytics including message feedback count, case feedback count, average rating, last update time, FAISS index status, and trends chart.

**Key Elements**:

- `#feedback-dashboard` - Main dashboard container
- `#refresh-stats-btn` - Manual refresh button
- `#auto-refresh-toggle` - Auto-refresh toggle
- `#message-feedback-count` - Message feedback count
- `#case-feedback-count` - Case feedback count
- `#avg-rating` - Average rating display
- `#last-updated` - Last update timestamp
- `#faiss-status` - FAISS index status
- `#trends-canvas` - Chart.js canvas for trends

#### `feedback-modal.html`

**Purpose**: Case completion feedback form  
**Related JS modules**: `feedback.js`  
**Description**: Modal dialog that appears when a case is finished, allowing users to provide feedback on the case quality, helpfulness, accuracy, and optional comments.

**Key Elements**:

- `#feedback-modal` - Modal container
- `#close-feedback-btn` - Close button
- `#correct-organism` - Display of correct organism
- `input[name="detail"]` - Detail rating radio buttons
- `input[name="helpfulness"]` - Helpfulness rating radio buttons
- `input[name="accuracy"]` - Accuracy rating radio buttons
- `#feedback-comments` - Optional comments textarea
- `#submit-feedback-btn` - Submit feedback button

#### `scripts.html`

**Purpose**: JavaScript module loading  
**Related JS modules**: All modules  
**Description**: Loads all JavaScript modules in the correct dependency order. Includes Chart.js library and all MicroTutor V4 modules.

## Template Structure

```
templates/
├── index.html                 # Main template (assembles all partials)
├── partials/
│   ├── header.html            # Header section
│   ├── instructions.html      # Case flow instructions
│   ├── case-setup.html        # Case initialization controls
│   ├── guidelines.html        # Guidelines display
│   ├── feedback-controls.html # Feedback system controls
│   ├── chat-container.html    # Main chat interface
│   ├── phase-progression.html # Phase navigation sidebar
│   ├── dashboard.html         # Analytics dashboard
│   ├── feedback-modal.html    # Feedback form modal
│   └── scripts.html           # JavaScript includes
└── README.md                  # This file
```

## Benefits of Modular Templates

### Maintainability

- Each component is isolated, making it easier to locate and modify specific UI sections
- Changes to one component don't affect others
- Clear separation of concerns

### Reusability

- Partials can be reused across multiple templates if needed
- Consistent structure makes it easier to add new features

### Alignment with JavaScript Modules

- HTML structure mirrors the JavaScript module organization
- Makes it easier to understand which HTML elements correspond to which JS modules
- Simplifies debugging and development

### Readability

- Main `index.html` is now only ~30 lines instead of 355 lines
- Each partial focuses on a single UI component
- Clear comments indicate which JS modules interact with each partial

## Usage

### Adding a New Component

1. Create a new partial file in `partials/` directory
2. Add HTML for your component
3. Add a comment indicating related JS modules
4. Include it in `index.html` using `{% include 'partials/your-component.html' %}`

### Modifying an Existing Component

1. Locate the relevant partial file
2. Make your changes
3. The changes will automatically appear in `index.html` since it uses includes

### Template Variables

Currently, templates don't use Jinja2 variables, but you can add them if needed:

```jinja2
{% if some_condition %}
    {% include 'partials/some-component.html' %}
{% endif %}
```

## Notes

- All partials use relative paths for static assets (e.g., `/static/css/style.css`)
- IDs and classes match those referenced in the JavaScript modules
- The structure aligns with the modular JavaScript architecture for consistency
- Partials are loaded synchronously in order, ensuring proper DOM structure

## Future Improvements

Potential enhancements:

- Add template variables for dynamic content (e.g., organism list from backend)
- Create base template with common structure
- Add template inheritance for shared layouts
- Implement template caching for better performance
- Add template validation/linting
