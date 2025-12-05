/**
 * State management for MicroTutor V4
 * Centralized application state
 */

const State = {
    // Chat state
    chatHistory: [],
    phaseHistory: [],

    // Case state
    currentCaseId: null,
    currentOrganismKey: null,
    currentPhase: 'information_gathering',
    caseComplete: false,

    // Model state
    currentModelProvider: 'azure',
    currentModel: 'gpt-4.1',

    // Guidelines state
    guidelinesEnabled: true,
    currentGuidelines: null,

    // Feedback state
    feedbackEnabled: true,
    feedbackThreshold: 0.7,

    // Dashboard state
    chartInstance: null,
    chartVisible: true,

    // Voice state
    mediaRecorder: null,
    audioChunks: [],
    isRecording: false,
    voiceEnabled: false,
    voiceInitialized: false,
    recordingStartTime: null,

    // Feedback counter state
    autoRefreshInterval: null,
    isRefreshing: false,

    // Assessment MCQ state
    assessmentMCQs: [],
    assessmentAnswers: {},
    assessmentScore: { correct: 0, total: 0 },
    assessmentComplete: false,
    assessmentWeakAreas: [],

    // Legacy MCQ state (for backward compatibility)
    currentMCQ: null,
    currentSessionId: null,

    // Tool tracking
    lastToolUsed: null,

    /**
     * Reset all state to initial values
     */
    reset() {
        this.chatHistory = [];
        this.phaseHistory = [];
        this.currentCaseId = null;
        this.currentOrganismKey = null;
        this.currentPhase = 'information_gathering';
        this.caseComplete = false;
        this.currentModelProvider = 'azure';
        this.currentModel = 'gpt-4.1';
        this.guidelinesEnabled = true;
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
        this.lastToolUsed = null;
    },

    /**
     * Reset only assessment state (for retrying)
     */
    resetAssessment() {
        this.assessmentMCQs = [];
        this.assessmentAnswers = {};
        this.assessmentScore = { correct: 0, total: 0 };
        this.assessmentComplete = false;
    }
};
