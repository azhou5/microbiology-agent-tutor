/**
 * Configuration constants for MicroTutor V4.
 */

const API_BASE = '/api/v1';

const STORAGE_KEYS = {
    HISTORY: 'microtutor_v4_chat_history',
    CASE_ID: 'microtutor_v4_case_id',
    ORGANISM: 'microtutor_v4_organism',
    SEEN_ORGANISMS: 'microtutor_v4_seen_organisms',
    MODULE: 'microtutor_v4_current_module',
    MODULE_QUEUE: 'microtutor_v4_module_queue',
    SELECTED_MODULES: 'microtutor_v4_selected_modules',
    ENABLE_MCQS: 'microtutor_v4_enable_mcqs',
    ASSESSMENT_RESULTS: 'microtutor_v4_assessment_results',
};

// Module definitions used by the progress sidebar and guidance text.
const MODULE_DEFINITIONS = {
    history_taking: {
        name: 'History Taking',
        icon: '📋',
        guidance: 'Gather key history and examination findings from the patient.',
    },
    ddx_deep_dive: {
        name: 'DDx Deep Dive',
        icon: '🔍',
        guidance: 'Work through the differential diagnosis by comparing clinical features and investigations.',
    },
    tx_deep_dive: {
        name: 'Management Deep Dive',
        icon: '💊',
        guidance: 'Reason through treatment choices, guidelines, and monitoring.',
    },
    pathophys_epi: {
        name: 'Pathophys & Epi',
        icon: '🧬',
        guidance: 'Connect pathophysiology to the clinical picture, investigations, treatment, and epi context.',
    },
    feedback: {
        name: 'Feedback',
        icon: '✅',
        guidance: 'Receive feedback on your performance and clinical reasoning.',
    },
};

const MCQ_CONFIG = {
    defaultNumQuestions: 5,
    showExplanationsOnReveal: true,
    enableScoring: true,
};

// A/B-testable feature flags for background LLMs during history-taking.
const EMR_FLAGS = {
    enableEmrNotes: true,   // LLM that extracts structured notes for the EMR panel
    enableChecklist: true,  // LLM that ticks off progress-bar items
};

// Maps backend tool/speaker names → module IDs for progress updates.
const TOOL_TO_MODULE = {
    patient: 'history_taking',
    ddx_tutor: 'ddx_deep_dive',
    tx_tutor: 'tx_deep_dive',
    pathophys_epi_tutor: 'pathophys_epi',
    feedback: 'feedback',
};
