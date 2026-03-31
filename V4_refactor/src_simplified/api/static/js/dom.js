/**
 * Centralised DOM element references for MicroTutor V4.
 */

const DOM = {
    // Chat
    chatbox: null,
    userInput: null,
    sendBtn: null,
    finishBtn: null,
    statusMessage: null,

    // Case setup
    startCaseBtn: null,
    organismSelect: null,

    // Module checkboxes
    modHistory: null,
    modDdx: null,
    modTx: null,
    modPathophys: null,
    modMcqs: null,

    // EMR Panel
    emrPanel: null,
    emrSections: null,
    emrRefreshBtn: null,
    emrSpinner: null,
    emrPatientInfoContent: null,
    emrExaminationContent: null,
    emrObservationsContent: null,
    historyExamBar: null,
    historyExamCount: null,
    investigationsBar: null,
    investigationsBarCount: null,

    // Modal
    feedbackModal: null,
    closeFeedbackBtn: null,
    submitFeedbackBtn: null,
    correctOrganismSpan: null,

    // Voice (compat)
    voiceBtn: null,
    voiceStatus: null,
    responseAudio: null,

    // Guidelines
    guidelinesToggle: null,
    guidelinesResults: null,
    guidelinesStatus: null,
    guidelinesCount: null,
    guidelinesContent: null,

    // Feedback controls
    feedbackToggle: null,
    thresholdSlider: null,
    thresholdValue: null,

    // Dashboard
    messageFeedbackCount: null,
    caseFeedbackCount: null,
    avgRating: null,
    lastUpdated: null,
    refreshStatsBtn: null,
    autoRefreshToggle: null,

    // Chart
    trendsCanvas: null,
    toggleChartBtn: null,

    // Trends
    messageTrend: null,
    caseTrend: null,
    ratingTrend: null,
    updateTrend: null,

    // FAISS
    faissStatus: null,
    faissTrend: null,
    faissIcon: null,
    faissLoading: null,

    // Model selection (legacy — kept for backward compat, no longer in UI)
    azureProvider: null,
    personalProvider: null,
    modelSelect: null,

    init() {
        this.chatbox = document.getElementById('chatbox');
        this.userInput = document.getElementById('user-input');
        this.sendBtn = document.getElementById('send-btn');
        this.finishBtn = document.getElementById('finish-btn');
        this.statusMessage = document.getElementById('status-message');

        this.startCaseBtn = document.getElementById('start-case-btn');
        this.organismSelect = document.getElementById('organism-select');

        this.modHistory = document.getElementById('mod-history');
        this.modDdx = document.getElementById('mod-ddx');
        this.modTx = document.getElementById('mod-tx');
        this.modPathophys = document.getElementById('mod-pathophys');
        this.modMcqs = document.getElementById('mod-mcqs');

        this.emrPanel = document.getElementById('emr-panel');
        this.emrRefreshBtn = document.getElementById('emr-refresh-btn');
        this.emrSpinner = document.getElementById('emr-spinner');
        this.emrSections = document.getElementById('emr-sections');
        this.emrPatientInfoContent = document.getElementById('emr-patient-info-content');
        this.emrExaminationContent = document.getElementById('emr-examination-content');
        this.emrObservationsContent = document.getElementById('emr-observations-content');
        this.historyExamBar = document.getElementById('history-exam-bar');
        this.historyExamCount = document.getElementById('history-exam-count');
        this.investigationsBar = document.getElementById('investigations-bar');
        this.investigationsBarCount = document.getElementById('investigations-bar-count');

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
    },
};
