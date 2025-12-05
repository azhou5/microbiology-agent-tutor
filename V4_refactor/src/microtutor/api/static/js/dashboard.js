/**
 * Dashboard functionality for MicroTutor V4
 */

/**
 * Initialize dashboard functionality
 */
function initDashboard() {
    console.log('[DASHBOARD] Initializing dashboard...');

    // Load initial data
    loadDashboardData();

    // Set up event listeners
    if (DOM.refreshStatsBtn) {
        DOM.refreshStatsBtn.addEventListener('click', loadDashboardData);
    }

    if (DOM.autoRefreshToggle) {
        DOM.autoRefreshToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
    }

    if (DOM.toggleChartBtn) {
        DOM.toggleChartBtn.addEventListener('click', toggleChart);
        // Set initial button text
        DOM.toggleChartBtn.textContent = '📊 Hide Chart';
    }

    // Start auto-refresh if enabled
    if (DOM.autoRefreshToggle && DOM.autoRefreshToggle.checked) {
        startAutoRefresh();
    }

    console.log('[DASHBOARD] Dashboard initialized');
}

/**
 * Load dashboard data (stats, trends)
 */
async function loadDashboardData() {
    try {
        console.log('[DASHBOARD] Loading dashboard data...');

        // Load stats and trends in parallel
        const [statsResponse, trendsResponse] = await Promise.all([
            fetch(`${API_BASE}/analytics/feedback/stats`),
            fetch(`${API_BASE}/analytics/feedback/trends?time_range=all`)
        ]);

        if (statsResponse.ok) {
            const statsData = await statsResponse.json();
            updateStatsDisplay(statsData.data);
        }

        if (trendsResponse.ok) {
            const trendsData = await trendsResponse.json();
            updateTrendsChart(trendsData.data);
        }

        console.log('[DASHBOARD] Dashboard data loaded successfully');

    } catch (error) {
        console.error('[DASHBOARD] Error loading dashboard data:', error);
    }
}

/**
 * Load only trends data (for time range changes)
 */
async function loadTrendsData() {
    try {
        const timeRangeSelect = document.getElementById('time-range-select');
        const timeRange = timeRangeSelect ? timeRangeSelect.value : 'all';
        const response = await fetch(`${API_BASE}/analytics/feedback/trends?time_range=${timeRange}`);
        if (response.ok) {
            const data = await response.json();
            updateTrendsChart(data.data);
        }
    } catch (error) {
        console.error('[DASHBOARD] Error loading trends data:', error);
    }
}

/**
 * Update statistics display
 * @param {Object} data - Statistics data
 */
function updateStatsDisplay(data) {
    // Message feedback
    if (DOM.messageFeedbackCount) {
        DOM.messageFeedbackCount.textContent = data.message_feedback.total;
    }
    if (DOM.messageTrend) {
        const trend = data.message_feedback.trend;
        DOM.messageTrend.textContent = trend > 0 ? `+${trend} today` : trend < 0 ? `${trend} today` : 'No change today';
        DOM.messageTrend.className = `stat-trend ${trend > 0 ? '' : trend < 0 ? 'negative' : 'neutral'}`;
    }

    // Case feedback
    if (DOM.caseFeedbackCount) {
        DOM.caseFeedbackCount.textContent = data.case_feedback.total;
    }
    if (DOM.caseTrend) {
        const trend = data.case_feedback.trend;
        DOM.caseTrend.textContent = trend > 0 ? `+${trend} today` : trend < 0 ? `${trend} today` : 'No change today';
        DOM.caseTrend.className = `stat-trend ${trend > 0 ? '' : trend < 0 ? 'negative' : 'neutral'}`;
    }

    // Average rating
    if (DOM.avgRating) {
        DOM.avgRating.textContent = data.overall.avg_rating;
    }
    if (DOM.ratingTrend) {
        DOM.ratingTrend.textContent = `Avg: ${data.overall.avg_rating}/5`;
    }

    // Last updated
    if (DOM.lastUpdated && data.overall.last_update) {
        const updateTime = new Date(data.overall.last_update);
        DOM.lastUpdated.textContent = updateTime.toLocaleString('en-US', {
            timeZone: 'America/New_York',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        }) + ' EST';
    }
    if (DOM.updateTrend) {
        DOM.updateTrend.textContent = 'System active';
    }
}

/**
 * Update FAISS status display
 * @param {Object} data - FAISS status data
 */
function updateFAISSStatus(data) {
    if (!data) return;

    const isReindexing = data.is_reindexing;
    const lastComplete = data.last_reindex_complete;
    const currentDuration = data.current_duration;
    const reindexCount = data.reindex_count;
    const lastError = data.last_error;

    // Update status text
    if (DOM.faissStatus) {
        if (isReindexing) {
            DOM.faissStatus.textContent = 'Re-indexing...';
            DOM.faissStatus.className = 'stat-value reindexing';
        } else if (lastError) {
            DOM.faissStatus.textContent = 'Error';
            DOM.faissStatus.className = 'stat-value error';
        } else {
            DOM.faissStatus.textContent = 'Ready';
            DOM.faissStatus.className = 'stat-value ready';
        }
    }

    // Update trend text
    if (DOM.faissTrend) {
        if (isReindexing) {
            const duration = currentDuration ? Math.round(currentDuration) : 0;
            DOM.faissTrend.textContent = `Re-indexing for ${duration}s...`;
        } else if (lastComplete) {
            const completeTime = new Date(lastComplete);
            const timeStr = completeTime.toLocaleString('en-US', {
                timeZone: 'America/New_York',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });
            DOM.faissTrend.textContent = `Last update: ${timeStr} (${reindexCount} total)`;
        } else {
            DOM.faissTrend.textContent = 'Never updated';
        }
    }

    // Update icon and loading animation
    if (DOM.faissIcon) {
        if (isReindexing) {
            DOM.faissIcon.textContent = '🔄';
            DOM.faissIcon.className = 'stat-icon spinning';
        } else if (lastError) {
            DOM.faissIcon.textContent = '⚠️';
            DOM.faissIcon.className = 'stat-icon error';
        } else {
            DOM.faissIcon.textContent = '✅';
            DOM.faissIcon.className = 'stat-icon ready';
        }
    }

    // Show/hide loading animation
    if (DOM.faissLoading) {
        DOM.faissLoading.style.display = isReindexing ? 'flex' : 'none';
    }
}

/**
 * Fetch FAISS re-indexing status
 */
async function fetchFAISSStatus() {
    try {
        const response = await fetch(`${API_BASE}/faiss/reindex-status`);
        if (response.ok) {
            const data = await response.json();
            updateFAISSStatus(data);
        } else {
            console.warn('Failed to fetch FAISS status:', response.status);
        }
    } catch (error) {
        console.warn('Error fetching FAISS status:', error);
    }
}

/**
 * Trigger FAISS re-indexing manually
 */
async function triggerFAISSReindex() {
    const reindexBtn = document.getElementById('reindex-btn');
    
    try {
        // Disable button and show loading state
        if (reindexBtn) {
            reindexBtn.disabled = true;
            reindexBtn.textContent = '⏳ Starting...';
        }
        
        console.log('[FAISS] Triggering manual re-index...');
        
        const response = await fetch(`${API_BASE}/faiss/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                min_rating: 1,
                include_regular_feedback: true,
                include_case_feedback: true
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('[FAISS] Re-index triggered:', data);
            
            if (reindexBtn) {
                reindexBtn.textContent = '✅ Queued!';
            }
            
            // Poll for status updates
            setTimeout(() => {
                fetchFAISSStatus();
                if (reindexBtn) {
                    reindexBtn.disabled = false;
                    reindexBtn.textContent = '🔄 Re-index';
                }
            }, 2000);
        } else {
            const error = await response.json();
            console.error('[FAISS] Re-index failed:', error);
            
            if (reindexBtn) {
                reindexBtn.textContent = '❌ Failed';
                setTimeout(() => {
                    reindexBtn.disabled = false;
                    reindexBtn.textContent = '🔄 Re-index';
                }, 2000);
            }
        }
    } catch (error) {
        console.error('[FAISS] Re-index error:', error);
        
        if (reindexBtn) {
            reindexBtn.textContent = '❌ Error';
            setTimeout(() => {
                reindexBtn.disabled = false;
                reindexBtn.textContent = '🔄 Re-index';
            }, 2000);
        }
    }
}

/**
 * Update trends chart
 * @param {Object} data - Chart data
 */
function updateTrendsChart(data) {
    if (!DOM.trendsCanvas || !State.chartVisible) return;

    const ctx = DOM.trendsCanvas.getContext('2d');

    // Destroy existing chart
    if (State.chartInstance) {
        State.chartInstance.destroy();
    }

    // Create new chart
    State.chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: data.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Cumulative Feedback Over Time'
                },
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Cumulative Feedback Entries'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

/**
 * Toggle chart visibility
 */
function toggleChart() {
    State.chartVisible = !State.chartVisible;
    const chartContainer = document.getElementById('feedback-chart');

    if (State.chartVisible) {
        if (chartContainer) chartContainer.style.display = 'block';
        if (DOM.toggleChartBtn) DOM.toggleChartBtn.textContent = '📊 Hide Chart';
        loadTrendsData(); // Reload data when showing
    } else {
        if (chartContainer) chartContainer.style.display = 'none';
        if (DOM.toggleChartBtn) DOM.toggleChartBtn.textContent = '📊 Show Chart';
    }
}

/**
 * Start auto-refresh
 */
function startAutoRefresh() {
    if (State.autoRefreshInterval) {
        clearInterval(State.autoRefreshInterval);
    }

    State.autoRefreshInterval = setInterval(() => {
        loadDashboardData();
        fetchFAISSStatus(); // Also poll FAISS status
    }, 30000); // 30 seconds

    console.log('[DASHBOARD] Auto-refresh started');
}

/**
 * Stop auto-refresh
 */
function stopAutoRefresh() {
    if (State.autoRefreshInterval) {
        clearInterval(State.autoRefreshInterval);
        State.autoRefreshInterval = null;
    }

    console.log('[DASHBOARD] Auto-refresh stopped');
}

/**
 * Fetch feedback statistics from the API
 */
async function fetchFeedbackStats() {
    if (State.isRefreshing) return;

    State.isRefreshing = true;
    console.log('[FEEDBACK_STATS] Fetching feedback statistics...');

    try {
        // Add loading animation
        if (DOM.caseFeedbackCount) DOM.caseFeedbackCount.classList.add('loading');
        if (DOM.messageFeedbackCount) DOM.messageFeedbackCount.classList.add('loading');

        // Fetch database stats
        const statsResponse = await fetch(`${API_BASE}/db/stats`);
        if (!statsResponse.ok) {
            throw new Error(`Stats API error: ${statsResponse.status}`);
        }
        const statsData = await statsResponse.json();

        // Fetch feedback data for message feedback count
        const feedbackResponse = await fetch(`${API_BASE}/db/feedback?limit=1`);
        let messageFeedbackCountValue = 0;
        if (feedbackResponse.ok) {
            const feedbackData = await feedbackResponse.json();
            messageFeedbackCountValue = feedbackData.count || 0;
        }

        // Update the display
        updateFeedbackStatsDisplay({
            totalFeedback: (statsData.stats?.case_feedback || 0) + messageFeedbackCountValue,
            caseFeedback: statsData.stats?.case_feedback || 0,
            messageFeedback: messageFeedbackCountValue,
            lastUpdated: new Date().toLocaleTimeString()
        });

        console.log('[FEEDBACK_STATS] Successfully updated stats:', {
            total: (statsData.stats?.case_feedback || 0) + messageFeedbackCountValue,
            case: statsData.stats?.case_feedback || 0,
            message: messageFeedbackCountValue
        });

    } catch (error) {
        console.error('[FEEDBACK_STATS] Error fetching stats:', error);
        updateFeedbackStatsDisplay({
            totalFeedback: 'Error',
            caseFeedback: 'Error',
            messageFeedback: 'Error',
            lastUpdated: 'Error'
        });
    } finally {
        State.isRefreshing = false;
        // Remove loading animation
        if (DOM.caseFeedbackCount) DOM.caseFeedbackCount.classList.remove('loading');
        if (DOM.messageFeedbackCount) DOM.messageFeedbackCount.classList.remove('loading');
    }
}

/**
 * Update the feedback statistics display
 * @param {Object} stats - Statistics object
 */
function updateFeedbackStatsDisplay(stats) {
    if (DOM.caseFeedbackCount) {
        DOM.caseFeedbackCount.textContent = stats.caseFeedback;
    }
    if (DOM.messageFeedbackCount) {
        DOM.messageFeedbackCount.textContent = stats.messageFeedback;
    }
    if (DOM.lastUpdated) {
        DOM.lastUpdated.textContent = stats.lastUpdated;
    }
}

/**
 * Initialize feedback counter functionality
 */
function initializeFeedbackCounter() {
    // Event listeners
    if (DOM.refreshStatsBtn) {
        DOM.refreshStatsBtn.addEventListener('click', () => {
            console.log('[FEEDBACK_STATS] Manual refresh triggered');
            fetchFeedbackStats();
        });
    }

    if (DOM.autoRefreshToggle) {
        DOM.autoRefreshToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
    }

    // FAISS re-index button
    const reindexBtn = document.getElementById('reindex-btn');
    if (reindexBtn) {
        reindexBtn.addEventListener('click', () => {
            console.log('[FAISS] Manual re-index triggered');
            triggerFAISSReindex();
        });
    }

    // Initial load
    fetchFeedbackStats();
    fetchFAISSStatus();

    // Start auto-refresh if enabled
    if (DOM.autoRefreshToggle && DOM.autoRefreshToggle.checked) {
        startAutoRefresh();
    }

    console.log('[FEEDBACK_STATS] Feedback counter initialized');
}
