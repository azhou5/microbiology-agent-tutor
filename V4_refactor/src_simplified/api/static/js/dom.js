/**
 * DOM element references for MicroTutor V4
 * Centralized DOM element access
 */

const DOM = {
    // Chat elements
    chatbox: null,
    userInput: null,
    sendBtn: null,
    finishBtn: null,
    statusMessage: null,

    // Case setup elements
    startCaseBtn: null,
    organismSelect: null,

    // Modal elements
    feedbackModal: null,
    closeFeedbackBtn: null,
    submitFeedbackBtn: null,
    correctOrganismSpan: null,

    // Voice elements
    voiceBtn: null,
    voiceStatus: null,
    responseAudio: null,

    // Guidelines elements
    guidelinesToggle: null,
    guidelinesResults: null,
    guidelinesStatus: null,
    guidelinesCount: null,
    guidelinesContent: null,

    // Feedback control elements
    feedbackToggle: null,
    thresholdSlider: null,
    thresholdValue: null,

    // Dashboard elements
    messageFeedbackCount: null,
    caseFeedbackCount: null,
    avgRating: null,
    lastUpdated: null,
    refreshStatsBtn: null,
    autoRefreshToggle: null,

    // Chart elements
    trendsCanvas: null,
    toggleChartBtn: null,

    // Trend elements
    messageTrend: null,
    caseTrend: null,
    ratingTrend: null,
    updateTrend: null,

    // FAISS status elements
    faissStatus: null,
    faissTrend: null,
    faissIcon: null,
    faissLoading: null,

    // Model selection elements
    azureProvider: null,
    personalProvider: null,
    modelSelect: null,

    /**
     * Initialize all DOM element references
     */
    init() {
        this.chatbox = document.getElementById('chatbox');
        this.userInput = document.getElementById('user-input');
        this.sendBtn = document.getElementById('send-btn');
        this.finishBtn = document.getElementById('finish-btn');
        this.statusMessage = document.getElementById('status-message');

        this.startCaseBtn = document.getElementById('start-case-btn');
        this.startRandomCaseBtn = document.getElementById('start-random-case-btn');
        this.organismSelect = document.getElementById('organism-select');

        this.feedbackModal = document.getElementById('feedback-modal');
        this.closeFeedbackBtn = document.getElementById('close-feedback-btn');
        this.submitFeedbackBtn = document.getElementById('submit-feedback-btn');
        this.correctOrganismSpan = document.getElementById('correct-organism');

        this.voiceBtn = document.getElementById('voice-btn');
        this.voiceStatus = document.getElementById('voice-status');
        this.responseAudio = document.getElementById('response-audio');

        this.guidelinesToggle = document.getElementById('guidelines-toggle');
        this.guidelinesResults = document.getElementById('guidelines-results');
        this.guidelinesStatus = document.getElementById('guidelines-status');
        this.guidelinesCount = document.getElementById('guidelines-count');
        this.guidelinesContent = document.getElementById('guidelines-content');

        this.feedbackToggle = document.getElementById('feedback-toggle');
        this.thresholdSlider = document.getElementById('threshold-slider');
        this.thresholdValue = document.getElementById('threshold-value');

        this.messageFeedbackCount = document.getElementById('message-feedback-count');
        this.caseFeedbackCount = document.getElementById('case-feedback-count');
        this.avgRating = document.getElementById('avg-rating');
        this.lastUpdated = document.getElementById('last-updated');
        this.refreshStatsBtn = document.getElementById('refresh-stats-btn');
        this.autoRefreshToggle = document.getElementById('auto-refresh-toggle');

        this.trendsCanvas = document.getElementById('trends-canvas');
        this.toggleChartBtn = document.getElementById('toggle-chart-btn');

        this.messageTrend = document.getElementById('message-trend');
        this.caseTrend = document.getElementById('case-trend');
        this.ratingTrend = document.getElementById('rating-trend');
        this.updateTrend = document.getElementById('update-trend');

        this.faissStatus = document.getElementById('faiss-status');
        this.faissTrend = document.getElementById('faiss-trend');
        this.faissIcon = document.getElementById('faiss-icon');
        this.faissLoading = document.getElementById('faiss-loading');

        this.azureProvider = document.getElementById('azure-provider');
        this.personalProvider = document.getElementById('personal-provider');
        this.modelSelect = document.getElementById('model-select');
    }
};
