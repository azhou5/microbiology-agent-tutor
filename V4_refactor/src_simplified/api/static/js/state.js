/**
 * Centralised application state for MicroTutor V4.
 */

const State = {
    // Chat
    chatHistory: [],

    // Case
    currentCaseId: null,
    currentOrganismKey: null,
    displayOrganism: null,
    caseComplete: false,

    // Module pipeline
    selectedModules: [],
    enableMcqs: false,
    moduleQueue: [],
    currentModule: 'history_taking',

    // Model
    currentModelProvider: 'azure',
    currentModel: 'gpt-5-mini',
    moduleModels: {},

    // Guidelines (disabled in simplified mode)
    guidelinesEnabled: false,
    currentGuidelines: null,

    // Feedback
    feedbackEnabled: true,
    feedbackThreshold: 0.7,

    // Dashboard
    chartInstance: null,
    chartVisible: true,

    // Voice (unused in simplified but kept for compat)
    mediaRecorder: null,
    audioChunks: [],
    isRecording: false,
    voiceEnabled: false,
    voiceInitialized: false,
    recordingStartTime: null,

    // Feedback counter
    autoRefreshInterval: null,
    isRefreshing: false,

    // Assessment MCQ state
    assessmentMCQs: [],
    assessmentAnswers: {},
    assessmentScore: { correct: 0, total: 0 },
    assessmentComplete: false,
    assessmentWeakAreas: [],

    // Legacy MCQ state
    currentMCQ: null,
    currentSessionId: null,

    // Pinned images (URLs already displayed, shown persistently)
    pinnedImages: [],

    // Findings checklist (history-taking progress tracker)
    findingsProgress: { history_exam: { checked: 0, total: 0 }, investigations: { checked: 0, total: 0 } },
    gatheredFindings: {},

    // EMR notes display tracking
    emrNotesDisplayed: 0,

    // Tool tracking
    lastToolUsed: null,


    reset() {
        this.chatHistory = [];
        this.currentCaseId = null;
        this.currentOrganismKey = null;
        this.displayOrganism = null;
        this.caseComplete = false;
        this.selectedModules = [];
        this.enableMcqs = false;
        this.moduleQueue = [];
        this.currentModule = 'history_taking';
        this.currentModelProvider = 'azure';
        this.currentModel = 'gpt-5-mini';
        this.moduleModels = {};
        this.guidelinesEnabled = false;
        this.currentGuidelines = null;
        this.feedbackEnabled = true;
        this.feedbackThreshold = 0.7;
        this.chartInstance = null;
        this.chartVisible = true;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.voiceEnabled = false;
        this.voiceInitialized = false;
        this.recordingStartTime = null;
        this.autoRefreshInterval = null;
        this.isRefreshing = false;
        this.assessmentMCQs = [];
        this.assessmentAnswers = {};
        this.assessmentScore = { correct: 0, total: 0 };
        this.assessmentComplete = false;
        this.assessmentWeakAreas = [];
        this.currentMCQ = null;
        this.currentSessionId = null;
        this.pinnedImages = [];
        this.findingsProgress = { history_exam: { checked: 0, total: 0 }, investigations: { checked: 0, total: 0 } };
        this.gatheredFindings = {};
        this.emrNotesDisplayed = 0;
        this.lastToolUsed = null;
    },

    resetAssessment() {
        this.assessmentMCQs = [];
        this.assessmentAnswers = {};
        this.assessmentScore = { correct: 0, total: 0 };
        this.assessmentComplete = false;
    }
};
