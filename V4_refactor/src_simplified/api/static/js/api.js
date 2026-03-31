/**
 * API call functions for MicroTutor V4.
 */

// ── helpers ──────────────────────────────────────────────────────────────

function updateCaseSummaryHeader(data) {
    const caseSummaryHeader = document.getElementById('case-summary-header');
    const caseOneLiner = document.getElementById('case-one-liner');
    const toggleBtn = document.getElementById('toggle-case-summary');
    if (!caseSummaryHeader || !caseOneLiner) return;

    let text = '';
    if (data.history && Array.isArray(data.history)) {
        const first = data.history.find(m => m.role === 'assistant');
        if (first) {
            const parts = first.content.split('\n\n');
            text = parts.length >= 2
                ? parts[1].trim()
                : (first.content.match(/\d{1,3}-year-old\s+(?:man|woman|male|female|patient)[^.]*\./i) || [first.content])[0];
        }
    }
    caseOneLiner.textContent = text || 'Case in progress...';
    caseSummaryHeader.style.display = 'flex';
    State.casePresentation = text;

    if (toggleBtn) {
        toggleBtn.onclick = () => {
            toggleBtn.classList.toggle('collapsed');
            caseSummaryHeader.classList.toggle('collapsed');
        };
    }
}

function hideCaseSummaryHeader() {
    const el = document.getElementById('case-summary-header');
    if (el) el.style.display = 'none';
}

function getAllOrganisms() {
    if (!DOM.organismSelect) return [];
    const orgs = [];
    for (const group of DOM.organismSelect.getElementsByTagName('optgroup')) {
        for (const opt of group.getElementsByTagName('option')) {
            if (opt.value && opt.value !== 'random') orgs.push(opt.value);
        }
    }
    return orgs;
}

// ── module selection helpers ─────────────────────────────────────────────

function getSelectedModules() {
    const boxes = document.querySelectorAll('input[name="selected_modules"]:checked');
    return Array.from(boxes).map(b => b.value);
}

function getEnableMcqs() {
    const cb = document.getElementById('mod-mcqs');
    return cb ? cb.checked : false;
}

function getModuleModels() {
    const models = {};
    document.querySelectorAll('.module-model-select').forEach(sel => {
        if (sel.value && sel.dataset.module) {
            models[sel.dataset.module] = sel.value;
        }
    });
    return models;
}

// ── case presentation image lightbox ─────────────────────────────────────

/**
 * Open full-screen lightbox for a case presentation thumbnail.
 * @param {string} src - Image URL
 * @param {string} [alt] - Alt text
 */
function openCaseImageLightbox(src, alt) {
    const root = document.getElementById('case-image-lightbox');
    const img = document.getElementById('case-image-lightbox-img');
    if (!root || !img || !src) return;
    img.src = src;
    img.alt = alt || 'Case image';
    root.classList.add('is-active');
    root.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
}

/**
 * Close the case image lightbox and restore page scroll.
 */
function closeCaseImageLightbox() {
    const root = document.getElementById('case-image-lightbox');
    const img = document.getElementById('case-image-lightbox-img');
    if (!root) return;
    root.classList.remove('is-active');
    root.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (img) {
        img.removeAttribute('src');
        img.alt = '';
    }
}

/**
 * Wire backdrop, close control, and Escape (once). Thumbnails call openCaseImageLightbox directly
 * when they are created in showCasePresentation so clicks work even if this runs late.
 */
function initCaseImageLightbox() {
    const root = document.getElementById('case-image-lightbox');
    if (!root || root.dataset.lightboxBound === '1') return;
    root.dataset.lightboxBound = '1';

    root.addEventListener('click', (e) => {
        if (e.target === root || e.target.classList.contains('case-image-lightbox-close')) {
            closeCaseImageLightbox();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && root.classList.contains('is-active')) {
            closeCaseImageLightbox();
        }
    });
}

// ── case presentation panel ──────────────────────────────────────────────

/**
 * Show or hide the case presentation panel based on first_module.
 * For history_taking the panel stays hidden (patient gives info interactively).
 * For all other modules the full case text + images are rendered.
 */
function showCasePresentation(data) {
    const panel = document.getElementById('case-presentation');
    const textEl = document.getElementById('case-presentation-text');
    const imagesEl = document.getElementById('case-presentation-images');
    const titleEl = document.getElementById('case-presentation-title');
    const toggleBtn = document.getElementById('toggle-case-presentation');

    if (!panel || !textEl) return;

    const firstModule = data.first_module || 'history_taking';

    if (firstModule === 'history_taking' && (!data.case_text || data.case_text.length === 0)) {
        panel.style.display = 'none';
        return;
    }

    // For non-history modules, always show the panel
    if (firstModule === 'history_taking') {
        panel.style.display = 'none';
        return;
    }

    // Title
    const displayOrg = data.display_organism || data.organism || 'Case';
    if (titleEl) {
        titleEl.textContent = displayOrg === 'Random' ? 'Case Presentation' : `Case: ${displayOrg}`;
    }

    // Images
    if (imagesEl) {
        imagesEl.innerHTML = '';
        if (data.case_images && data.case_images.length > 0) {
            data.case_images.forEach(url => {
                const img = document.createElement('img');
                img.src = url;
                img.className = 'case-presentation-img';
                img.alt = 'Case image';
                img.title = 'Click to enlarge';
                img.loading = 'lazy';
                img.addEventListener('click', (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    const src = img.currentSrc || img.src;
                    if (src) openCaseImageLightbox(src, img.alt || '');
                });
                imagesEl.appendChild(img);
            });
        }
    }

    // Case text -- use shared markdownToHtml from utils.js (marked is not bundled)
    if (textEl && data.case_text) {
        if (typeof markdownToHtml === 'function') {
            textEl.innerHTML = markdownToHtml(data.case_text);
        } else {
            textEl.innerHTML = '<pre style="white-space:pre-wrap;font-family:inherit;">' +
                data.case_text.replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                '</pre>';
        }
    }

    panel.style.display = 'block';

    // Toggle collapse
    if (toggleBtn) {
        toggleBtn.onclick = () => {
            panel.classList.toggle('collapsed');
            toggleBtn.textContent = panel.classList.contains('collapsed') ? '\u25B6' : '\u25BC';
        };
    }
}

function hideCasePresentation() {
    const panel = document.getElementById('case-presentation');
    if (panel) panel.style.display = 'none';
}

// ── EMR panel ────────────────────────────────────────────────────────────

function resetEMRPanel() {
    State.findingsProgress = { history_exam: { checked: 0, total: 0 }, investigations: { checked: 0, total: 0 } };
    State.gatheredFindings = {};
    State.pinnedImages = [];
    State.emrNotesDisplayed = 0;

    const placeholders = {
        'emr-patient-info-content': 'Gather history from the patient...',
        'emr-examination-content': 'No examination findings yet.',
        'emr-observations-content': 'No observations recorded.',
    };
    for (const [id, text] of Object.entries(placeholders)) {
        const el = document.getElementById(id);
        if (el) el.innerHTML = `<p class="emr-placeholder">${text}</p>`;
    }

    ['emr-ix-bedside', 'emr-ix-bloods', 'emr-ix-imaging', 'emr-ix-microbiology', 'emr-ix-special'].forEach(id => {
        const sub = document.getElementById(id);
        if (sub) {
            const content = sub.querySelector('.emr-section-content');
            if (content) content.innerHTML = '';
        }
    });

    updateEMRProgressBars({ history_exam: { checked: 0, total: 0 }, investigations: { checked: 0, total: 0 } });
}

function updateEMRProgressBars(progress) {
    if (!progress) return;
    const he = progress.history_exam || { checked: 0, total: 0 };
    const ix = progress.investigations || { checked: 0, total: 0 };

    const hePct = he.total > 0 ? Math.round((he.checked / he.total) * 100) : 0;
    const ixPct = ix.total > 0 ? Math.round((ix.checked / ix.total) * 100) : 0;

    if (DOM.historyExamBar) DOM.historyExamBar.style.width = `${hePct}%`;
    if (DOM.historyExamCount) DOM.historyExamCount.textContent = `${he.checked}/${he.total}`;
    if (DOM.investigationsBar) DOM.investigationsBar.style.width = `${ixPct}%`;
    if (DOM.investigationsBarCount) DOM.investigationsBarCount.textContent = `${ix.checked}/${ix.total}`;
}

function setEMRBusy(busy) {
    if (DOM.emrSpinner) DOM.emrSpinner.classList.toggle('active', busy);
}

function updateEMRFromChecklist(findingsData) {
    if (!findingsData) return;
    updateEMRProgressBars(findingsData.progress);
}

async function handleEMRRefresh() {
    if (!State.currentCaseId) return;
    const btn = DOM.emrRefreshBtn;
    if (btn) btn.classList.add('refreshing');
    setEMRBusy(true);

    try {
        const res = await fetch(`${API_BASE}/emr_refresh/${State.currentCaseId}`, { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // Full replacement: clear all sections then re-render
        State.emrNotesDisplayed = 0;
        _clearEMRSections();
        if (data.emr_notes) updateEMRNotes(data.emr_notes);
        if (data.findings_checklist) updateEMRFromChecklist(data.findings_checklist);
    } catch (err) {
        console.error('[EMR_REFRESH] Error:', err);
    } finally {
        if (btn) btn.classList.remove('refreshing');
        setEMRBusy(false);
    }
}

function _clearEMRSections() {
    ['emr-patient-info-content', 'emr-examination-content', 'emr-observations-content'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '';
    });
    ['emr-ix-bedside', 'emr-ix-bloods', 'emr-ix-imaging', 'emr-ix-microbiology', 'emr-ix-special'].forEach(id => {
        const sub = document.getElementById(id);
        if (sub) {
            const content = sub.querySelector('.emr-section-content');
            if (content) content.innerHTML = '';
        }
    });
}

// Maps note sections → EMR panel targets.
// Top-level sections resolve to a DOM.emr*Content element.
// Investigation sections resolve to a subsection ID whose child .emr-section-content is the target.
const EMR_NOTE_SECTION_MAP = {
    HPI: { type: 'top', key: 'patient-info' },
    PMH: { type: 'top', key: 'patient-info' },
    Medications: { type: 'top', key: 'patient-info' },
    Allergies: { type: 'top', key: 'patient-info' },
    'Social History': { type: 'top', key: 'patient-info' },
    'Family History': { type: 'top', key: 'patient-info' },
    'Epidemiological History': { type: 'top', key: 'patient-info' },
    'Physical Exam': { type: 'top', key: 'examination' },
    Vitals: { type: 'top', key: 'observations' },
    Bedside: { type: 'ix', id: 'emr-ix-bedside' },
    Bloods: { type: 'ix', id: 'emr-ix-bloods' },
    Imaging: { type: 'ix', id: 'emr-ix-imaging' },
    Microbiology: { type: 'ix', id: 'emr-ix-microbiology' },
    Special: { type: 'ix', id: 'emr-ix-special' },
};

function _resolveEMRContentEl(mapping) {
    if (mapping.type === 'top') {
        if (mapping.key === 'patient-info') return DOM.emrPatientInfoContent;
        if (mapping.key === 'examination') return DOM.emrExaminationContent;
        if (mapping.key === 'observations') return DOM.emrObservationsContent;
        return null;
    }
    const sub = document.getElementById(mapping.id);
    return sub ? sub.querySelector('.emr-section-content') : null;
}

function updateEMRNotes(notes) {
    if (!notes || !Array.isArray(notes)) return;

    const displayedCount = State.emrNotesDisplayed || 0;
    const newNotes = notes.slice(displayedCount);
    console.log(`[EMR_NOTES] total=${notes.length}, displayed=${displayedCount}, new=${newNotes.length}`);
    if (newNotes.length === 0) return;

    const grouped = {};
    newNotes.forEach(n => {
        const sec = n.section || 'HPI';
        if (!grouped[sec]) grouped[sec] = [];
        grouped[sec].push({ content: n.content, image_url: n.image_url || null });
    });

    for (const [section, items] of Object.entries(grouped)) {
        const mapping = EMR_NOTE_SECTION_MAP[section];
        if (!mapping) continue;

        const contentEl = _resolveEMRContentEl(mapping);
        if (!contentEl) continue;

        const placeholder = contentEl.querySelector('.emr-placeholder');
        if (placeholder) placeholder.remove();

        // For investigation subsections the parent <h5> already labels the category,
        // so we skip the inner header to avoid redundancy.
        const skipHeader = mapping.type === 'ix';

        let listEl = contentEl.querySelector(`.emr-note-list[data-section="${section}"]`);
        if (!listEl) {
            if (!skipHeader) {
                const headerEl = document.createElement('div');
                headerEl.className = 'emr-note-header';
                headerEl.dataset.section = section;
                headerEl.textContent = section;
                contentEl.appendChild(headerEl);
            }
            listEl = document.createElement('ul');
            listEl.className = 'emr-note-list';
            listEl.dataset.section = section;
            contentEl.appendChild(listEl);
        }

        items.forEach(item => {
            const li = document.createElement('li');
            li.className = 'emr-note-item';
            li.textContent = item.content;
            listEl.appendChild(li);

            if (item.image_url) {
                const img = document.createElement('img');
                img.src = item.image_url;
                img.className = 'emr-result-image';
                img.alt = item.content;
                img.title = 'Click to enlarge';
                img.loading = 'lazy';
                img.addEventListener('click', () => {
                    if (typeof openCaseImageLightbox === 'function') {
                        openCaseImageLightbox(img.currentSrc || img.src, img.alt);
                    }
                });
                listEl.appendChild(img);
            }
        });
    }

    State.emrNotesDisplayed = notes.length;
}

let _emrPollController = null;

function pollEMRNotes(caseId) {
    if (_emrPollController) _emrPollController.abort();
    _emrPollController = new AbortController();
    const signal = _emrPollController.signal;
    const delays = [2000, 3000, 5000, 8000];
    const startCount = State.emrNotesDisplayed || 0;

    setEMRBusy(true);

    (async () => {
        try {
            for (const delay of delays) {
                await new Promise(r => setTimeout(r, delay));
                if (signal.aborted) return;
                try {
                    const res = await fetch(`${API_BASE}/emr_notes/${caseId}`, { signal });
                    if (res.status === 404) return;
                    if (!res.ok) continue;
                    const payload = await res.json();
                    if (payload.emr_notes) updateEMRNotes(payload.emr_notes);
                    if (payload.findings_checklist) updateEMRFromChecklist(payload.findings_checklist);
                    const busy = payload.emr_busy === true;
                    setEMRBusy(busy);
                    if (!busy && (payload.emr_notes || []).length > startCount) return;
                } catch { return; }
            }
        } finally {
            setEMRBusy(false);
        }
    })();
}

// ── start case ───────────────────────────────────────────────────────────

async function handleStartCase() {
    const selectedOrganism = DOM.organismSelect ? DOM.organismSelect.value : null;
    if (!selectedOrganism) {
        setStatus('Please select a case first.', true);
        return;
    }

    const modules = getSelectedModules();
    if (modules.length === 0) {
        setStatus('Please select at least one module.', true);
        return;
    }

    await handleStartCaseWithOrganism(selectedOrganism);
}

async function handleStartCaseWithOrganism(selectedOrganism) {
    clearConversationState();
    State.chatHistory = [];
    State.pinnedImages = [];
    if (DOM.chatbox) DOM.chatbox.innerHTML = '';

    resetEMRPanel();
    hideCasePresentation();
    hideCaseSummaryHeader();

    State.currentCaseId = generateCaseId();
    State.currentOrganismKey = selectedOrganism;
    State.selectedModules = getSelectedModules();
    State.enableMcqs = getEnableMcqs();
    State.moduleModels = getModuleModels();

    setStatus('Starting new case...');
    disableInput(true);
    if (DOM.finishBtn) DOM.finishBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/start_case`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                organism: State.currentOrganismKey,
                case_id: State.currentCaseId,
                selected_modules: State.selectedModules,
                enable_mcqs: State.enableMcqs,
                model_name: State.currentModel,
                model_provider: State.currentModelProvider,
                enable_emr_notes: EMR_FLAGS.enableEmrNotes,
                enable_checklist: EMR_FLAGS.enableChecklist,
                module_models: State.moduleModels || {},
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || err.error || `HTTP ${response.status}`);
        }

        const data = await response.json();
        console.log('[START_CASE] Response:', data);

        // Store the actual organism (may differ if random)
        if (data.display_organism === 'Random') {
            State.displayOrganism = 'Random';
        } else {
            State.displayOrganism = data.organism || selectedOrganism;
        }
        State.currentOrganismKey = data.organism || selectedOrganism;

        // Module pipeline from backend
        const meta = data.metadata || {};
        State.moduleQueue = meta.module_queue || State.selectedModules;
        State.currentModule = meta.current_module || State.moduleQueue[0] || 'history_taking';
        State.enableMcqs = meta.enable_mcqs || State.enableMcqs;

        State.chatHistory = validateChatHistory(data.history);

        if (DOM.chatbox) DOM.chatbox.innerHTML = '';

        const initialSpeaker = data.initial_speaker || 'maintutor';
        const speakerLabelMap = {
            patient: 'Patient',
            ddx_tutor: 'DDx Tutor',
            tx_tutor: 'Tx Tutor',
            pathophys_epi_tutor: 'Pathophys & Epi Tutor',
            feedback: 'Feedback',
            maintutor: 'MainTutor',
        };
        const initialLabel = speakerLabelMap[initialSpeaker] || 'Tutor';
        const initialType = initialSpeaker === 'patient' ? 'patient' : (initialSpeaker === 'maintutor' ? 'maintutor' : 'tutor');

        State.chatHistory.forEach(msg => {
            if (msg.role !== 'system') {
                const spkType = msg.role === 'assistant' ? initialType : undefined;
                const spkLabel = msg.role === 'assistant' ? initialLabel : undefined;
                addMessage(msg.role, msg.content, false, spkType, null, null, spkLabel);
            }
        });

        setStatus(`Case started. Case ID: ${State.currentCaseId}`);
        disableInput(false);
        if (DOM.finishBtn) DOM.finishBtn.disabled = false;

        // Show case presentation panel for non-history modules
        showCasePresentation(data);

        buildModuleProgressUI(State.moduleQueue);
        showPhaseProgression();
        updateModuleUI();
        saveConversationState();

        // One-liner header only for history-taking first module
        if (data.first_module === 'history_taking') {
            updateCaseSummaryHeader(data);
        }

        addSeenOrganism(State.currentOrganismKey);

        // Initialize checklist progress
        if (data.findings_checklist) {
            updateEMRProgressBars(data.findings_checklist.progress);
        }
        if (data.emr_notes) {
            updateEMRNotes(data.emr_notes);
        }

        // Poll for background EMR/checklist tasks fired on the first message
        pollEMRNotes(State.currentCaseId);

        if (DOM.userInput) DOM.userInput.focus();
    } catch (error) {
        console.error('[START_CASE] Error:', error);
        setStatus(`Error: ${error.message}`, true);
        disableInput(false);
        State.currentOrganismKey = null;
        State.currentCaseId = null;
    }
}

// ── chat ─────────────────────────────────────────────────────────────────

async function handleSendMessage() {
    const messageText = DOM.userInput ? DOM.userInput.value.trim() : '';
    if (!messageText) return;

    if (!State.currentCaseId) State.currentCaseId = generateCaseId();
    if (!State.currentOrganismKey) {
        State.currentOrganismKey =
            (DOM.organismSelect && DOM.organismSelect.value) ? DOM.organismSelect.value : 'Case_07011';
    }

    addMessage('user', messageText);
    addMessageToHistory('user', messageText);
    if (DOM.userInput) DOM.userInput.value = '';
    disableInput(true);

    try {
        const validHistory = validateChatHistory(State.chatHistory);

        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: messageText,
                history: validHistory,
                organism_key: State.currentOrganismKey,
                case_id: State.currentCaseId,
                model_name: State.currentModel,
                model_provider: State.currentModelProvider,
                feedback_enabled: State.feedbackEnabled,
                feedback_threshold: State.feedbackThreshold,
                current_module: State.currentModule,
            }),
        });

        if (!response.ok) {
            const errData = await response.json();
            if (errData.detail && errData.detail.includes('case')) {
                setStatus('Session expired. Please start a new case.', true);
                disableInput(true);
                if (DOM.finishBtn) DOM.finishBtn.disabled = true;
                clearConversationState();
                return;
            }
            throw new Error(errData.detail || errData.error || `HTTP ${response.status}`);
        }

        const data = await response.json();
        console.log('[CHAT] Response:', data);

        // Tool tracking
        if (data.tools_used && data.tools_used.length > 0) {
            setLastToolUsed(data.tools_used[0]);
        } else {
            State.lastToolUsed = null;
        }

        // Update EMR panel from whatever the response already carries
        if (data.findings_checklist) {
            updateEMRFromChecklist(data.findings_checklist);
        }
        if (data.emr_notes) {
            updateEMRNotes(data.emr_notes);
        }

        // Poll for async EMR notes / checklist updates (fire-and-forget)
        pollEMRNotes(State.currentCaseId);

        const subagentText = data.subagent_response || data.response;
        const subagentSpeaker = data.subagent_speaker || State.lastToolUsed || 'tutor';
        const subagentLabelMap = {
            patient: 'Patient',
            ddx_tutor: 'DDx Tutor',
            tx_tutor: 'Management Tutor',
            pathophys_epi_tutor: 'Pathophys & Epi Tutor',
            feedback: 'Feedback',
            tutor: 'Tutor',
        };
        const subagentLabel = subagentLabelMap[subagentSpeaker] || 'Tutor';
        const chatImageUrl = data.image_url || null;

        addMessage('assistant', subagentText, false, subagentSpeaker, null, chatImageUrl, subagentLabel);

        // Sync history
        if (data.history) {
            State.chatHistory = validateChatHistory(data.history);
        }

        // Update module state from backend metadata
        if (data.metadata) {
            if (data.metadata.current_module && data.metadata.current_module !== State.currentModule) {
                State.currentModule = data.metadata.current_module;
                updateModuleUI();
                console.log('[MODULE] Updated to:', State.currentModule);
            }
            if (data.metadata.module_queue) {
                State.moduleQueue = data.metadata.module_queue;
            }
            // Auto-trigger MCQ generation when we enter the feedback module
            if (data.metadata.current_module === 'feedback' && data.metadata.enable_mcqs) {
                if (DOM.finishBtn) DOM.finishBtn.textContent = '📝 Generating MCQs...';
                if (typeof showAssessmentSection === 'function') showAssessmentSection();
                setTimeout(() => {
                    if (typeof handleGenerateAssessment === 'function') handleGenerateAssessment();
                }, 500);
            }
        }

        disableInput(false);
        setStatus('');
        saveConversationState();
        if (DOM.userInput) DOM.userInput.focus();

    } catch (error) {
        console.error('[CHAT] Error:', error);
        setStatus(`Error: ${error.message}`, true);
        disableInput(false);
        if (DOM.userInput) DOM.userInput.focus();
    }
}

// ── model selection ──────────────────────────────────────────────────────

function updateModelSelection() {
    if (!DOM.azureProvider || !DOM.personalProvider || !DOM.modelSelect) return;
    DOM.modelSelect.innerHTML = '';

    const isAzure = DOM.azureProvider.checked;
    State.currentModelProvider = isAzure ? 'azure' : 'personal';

    const options = isAzure
        ? [
            { value: 'gpt-5', text: 'GPT-5 (Preview)' },
            { value: 'gpt-5-mini', text: 'GPT-5 Mini (Preview)' },
            { value: 'gpt-4o-1120', text: 'GPT-4o (2024-11-20)' },
            { value: 'o4-mini-0416', text: 'o4-mini (2025-04-16)' },
            { value: 'o3-mini-0131', text: 'o3-mini (2025-01-31)' },
        ]
        : [
            { value: 'gpt-5', text: 'GPT-5 (Preview)' },
            { value: 'o4', text: 'o4' },
            { value: 'gpt-5-mini-2025-08-07', text: 'GPT-5 Mini (2025-08-07)' },
            { value: 'gpt-5-2025-08-07', text: 'GPT-5 (2025-08-07)' },
        ];

    const preferred = State.currentModel || (isAzure ? 'gpt-5-mini' : 'gpt-5');
    options.forEach(opt => {
        const el = document.createElement('option');
        el.value = opt.value;
        el.textContent = opt.text;
        if (opt.value === preferred) {
            el.selected = true;
            State.currentModel = opt.value;
        }
        DOM.modelSelect.appendChild(el);
    });
}

function updateCurrentModel() {
    if (DOM.modelSelect && DOM.modelSelect.value) {
        State.currentModel = DOM.modelSelect.value;
        console.log('[MODEL] Selected:', State.currentModel);
    }
}

async function syncWithBackendConfig() {
    try {
        const response = await fetch('/api/v1/config');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const cfg = await response.json();

        if (cfg.use_azure) {
            if (DOM.azureProvider) DOM.azureProvider.checked = true;
            if (DOM.personalProvider) DOM.personalProvider.checked = false;
            State.currentModelProvider = 'azure';
        } else {
            if (DOM.azureProvider) DOM.azureProvider.checked = false;
            if (DOM.personalProvider) DOM.personalProvider.checked = true;
            State.currentModelProvider = 'personal';
        }
        State.currentModel = cfg.current_model;
        updateModelSelection();
        if (DOM.modelSelect) DOM.modelSelect.value = State.currentModel;
    } catch (e) {
        console.warn('[CONFIG] Sync failed, using defaults:', e);
    }
}
