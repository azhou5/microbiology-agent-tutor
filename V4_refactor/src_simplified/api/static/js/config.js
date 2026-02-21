/**
 * Configuration constants for MicroTutor V4
 */

// API Configuration
const API_BASE = '/api/v1';

// LocalStorage keys
const STORAGE_KEYS = {
    HISTORY: 'microtutor_v4_chat_history',
    CASE_ID: 'microtutor_v4_case_id',
    ORGANISM: 'microtutor_v4_organism',
    SEEN_ORGANISMS: 'microtutor_v4_seen_organisms',
    PHASE: 'microtutor_v4_current_phase',
    PHASE_HISTORY: 'microtutor_v4_phase_history',
    ASSESSMENT_RESULTS: 'microtutor_v4_assessment_results'
};

// Phase definitions and guidance
const PHASE_DEFINITIONS = {
    information_gathering: {
        name: 'Information Gathering',
        icon: '📋',
        guidance: 'Gather key history and examination findings from the patient. Ask about symptoms, duration, and physical exam.',
        nextPhase: 'differential_diagnosis'
    },
    differential_diagnosis: {
        name: 'Differential Diagnosis',
        icon: '🔍',
        guidance: 'Organize clinical information and develop differential diagnoses. Consider the most likely causes based on your findings.',
        nextPhase: 'tests_management'
    },
    tests_management: {
        name: 'Tests & Management',
        icon: '🧪',
        guidance: 'Order relevant investigations and propose treatments. Consider what would confirm or rule out each diagnosis and develop a management plan.',
        nextPhase: 'deeper_dive'
    },
    deeper_dive: {
        name: 'Deeper Dive',
        icon: '🔬',
        guidance: 'Explore mechanisms, virulence factors, and guidelines in depth.',
        nextPhase: 'post_case_mcq'
    },
    post_case_mcq: {
        name: 'Post-Case MCQ',
        icon: '📝',
        guidance: 'Test your understanding with targeted MCQs based on areas you struggled with during the case.',
        nextPhase: 'feedback'
    },
    assessment: {
        name: 'Assessment MCQs',
        icon: '📝',
        guidance: 'Complete post-case MCQs to consolidate learning before final feedback.',
        nextPhase: 'feedback'
    },
    feedback: {
        name: 'Feedback',
        icon: '✅',
        guidance: 'Receive feedback on the case. Review your performance and clinical reasoning.',
        nextPhase: null
    }
};

// MCQ Configuration
const MCQ_CONFIG = {
    defaultNumQuestions: 5,
    showExplanationsOnReveal: true,
    enableScoring: true
};

// Tool to Phase mapping - maps tool names to corresponding phases
const TOOL_TO_PHASE = {
    'patient': 'information_gathering',
    'maintutor_differential': 'differential_diagnosis',
    'tests_management': 'tests_management',
    'deeper_dive_tutor': 'deeper_dive',
    'post_case_assessment': 'post_case_mcq',
    'feedback': 'feedback'
};
