/**
 * HA Entity Explorer - Main JavaScript
 * Handles entity search, chart rendering, and date range selection.
 */

// =============================================================================
// Global State
// =============================================================================

let entities = [];              // All available entities
let currentEntityId = null;     // Currently selected entity
let currentHistoryData = null;  // Current history data for the chart
let dateRange = {
    start: null,
    end: null
};
let appConfig = null;           // App configuration from server

// DOM References
const entitySearch = document.getElementById('entity-search');
const entityDropdown = document.getElementById('entity-dropdown');
const selectedEntityContainer = document.getElementById('selected-entity-container');
const selectedEntityName = document.getElementById('selected-entity-name');
const chartDom = document.getElementById('main-chart');
const chartPlaceholder = document.getElementById('chart-placeholder');
const dateRangeBtn = document.getElementById('date-range-btn');
const dateRangeDisplay = document.getElementById('date-range-display');
const refreshBtn = document.getElementById('refresh-btn');
const detailsContent = document.getElementById('details-content');
const cursorTimeDisplay = document.getElementById('cursor-time');

// Modals
const dateRangeModal = new bootstrap.Modal(document.getElementById('dateRangeModal'));
const historyModal = new bootstrap.Modal(document.getElementById('historyModal'));
const historyModalEl = document.getElementById('historyModal');
const historyTitle = document.getElementById('historyModalLabel');
const historyChartDom = document.getElementById('history-chart');
const historyListDom = document.getElementById('history-list');
const historyLoading = document.getElementById('history-loading');

// Date pickers
let startPicker = null;
let endPicker = null;

// ECharts instances
let myChart = null;
let historyChart = null;

// =============================================================================
// Initialization
// =============================================================================

async function init() {
    // Load app configuration
    await loadConfig();

    // Initialize date pickers
    initDatePickers();

    // Set default date range
    setDefaultDateRange();

    // Load entities
    await loadEntities();

    // Setup event listeners
    setupEventListeners();

    // Initialize main chart
    initMainChart();
}

async function loadConfig() {
    try {
        const response = await axios.get('/api/config');
        appConfig = response.data;
        console.log('Config loaded:', appConfig);

        // Set language from config
        if (appConfig.language && window.i18n) {
            window.i18n.setLanguage(appConfig.language);
        }
    } catch (error) {
        console.error('Failed to load config:', error);
        appConfig = { language: 'en', defaultHistoryDays: 4 };
    }
}

function setDefaultDateRange() {
    const days = appConfig?.defaultHistoryDays || 4;
    dateRange.end = new Date();
    dateRange.start = new Date();
    dateRange.start.setDate(dateRange.start.getDate() - days);
}

function initDatePickers() {
    const commonOptions = {
        enableTime: true,
        dateFormat: 'Y-m-d H:i',
        time_24hr: true,
        theme: 'dark'
    };

    startPicker = flatpickr('#date-start', {
        ...commonOptions,
        defaultDate: dateRange.start
    });

    endPicker = flatpickr('#date-end', {
        ...commonOptions,
        defaultDate: dateRange.end
    });
}

function initMainChart() {
    myChart = echarts.init(chartDom, 'dark');

    // Handle resize
    window.addEventListener('resize', () => {
        if (myChart) myChart.resize();
    });
}

// =============================================================================
// Entity Search & Selection
// =============================================================================

async function loadEntities() {
    try {
        const loadingText = window.i18n ? window.i18n.t('loadingEntities') : 'Loading entities...';
        entityDropdown.innerHTML = `<div class="loading">${loadingText}</div>`;

        const response = await axios.get('/api/entities');
        entities = response.data;

        console.log(`Loaded ${entities.length} entities`);
        entityDropdown.classList.add('d-none');

    } catch (error) {
        console.error('Failed to load entities:', error);
        const errorText = window.i18n ? window.i18n.t('failedToLoadEntities') : 'Failed to load entities';
        entityDropdown.innerHTML = `<div class="no-results">${errorText}</div>`;
    }
}

function filterEntities(query) {
    if (!query || query.length < 2) {
        return [];
    }

    const lowerQuery = query.toLowerCase();

    return entities.filter(e =>
        e.friendly_name.toLowerCase().includes(lowerQuery) ||
        e.entity_id.toLowerCase().includes(lowerQuery)
    ).slice(0, 20); // Limit to 20 results
}

function renderEntityDropdown(filteredEntities) {
    if (filteredEntities.length === 0) {
        const noResultsText = window.i18n ? window.i18n.t('noEntitiesFound') : 'No entities found';
        entityDropdown.innerHTML = `<div class="no-results">${noResultsText}</div>`;
        return;
    }

    entityDropdown.innerHTML = filteredEntities.map(entity => `
        <div class="entity-item" data-entity-id="${entity.entity_id}">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <span class="entity-domain ${entity.domain}">${entity.domain}</span>
                    <span class="entity-name">${escapeHtml(entity.friendly_name)}</span>
                </div>
                <span class="entity-state">${escapeHtml(entity.state)}</span>
            </div>
            <div class="entity-id">${entity.entity_id}</div>
        </div>
    `).join('');

    // Add click handlers
    entityDropdown.querySelectorAll('.entity-item').forEach(item => {
        item.addEventListener('click', () => {
            selectEntity(item.dataset.entityId);
        });
    });
}

function selectEntity(entityId) {
    const entity = entities.find(e => e.entity_id === entityId);
    if (!entity) return;

    currentEntityId = entityId;

    // Update UI
    entitySearch.value = '';
    entityDropdown.classList.add('d-none');
    selectedEntityName.textContent = entity.friendly_name;
    selectedEntityContainer.classList.remove('d-none');
    dateRangeBtn.disabled = false;
    refreshBtn.classList.remove('d-none');

    // Load history
    loadEntityHistory();
}

function clearSelectedEntity() {
    currentEntityId = null;
    currentHistoryData = null;

    selectedEntityContainer.classList.add('d-none');
    dateRangeBtn.disabled = true;
    refreshBtn.classList.add('d-none');
    dateRangeDisplay.textContent = '';

    // Clear chart
    if (myChart) {
        myChart.clear();
    }
    chartPlaceholder.classList.remove('d-none');

    // Clear details
    const clickText = window.i18n ? window.i18n.t('clickToSeeDetails') : 'Click on the chart to see details.';
    detailsContent.innerHTML = `<p class="text-muted">${clickText}</p>`;
    cursorTimeDisplay.textContent = '--:--';
}

// =============================================================================
// History Loading & Chart Rendering
// =============================================================================

async function loadEntityHistory() {
    if (!currentEntityId) return;

    // Show loading
    chartPlaceholder.classList.add('d-none');
    myChart.showLoading();

    try {
        const params = new URLSearchParams({
            start: dateRange.start.toISOString(),
            end: dateRange.end.toISOString()
        });

        const response = await axios.get(`/api/history/${currentEntityId}?${params}`);
        currentHistoryData = response.data;

        // Update date display
        updateDateRangeDisplay();

        // Render chart based on entity type
        if (currentHistoryData.type === 'climate') {
            renderClimateChart(currentHistoryData);
        } else if (currentHistoryData.type === 'numeric') {
            renderNumericChart(currentHistoryData);
        } else {
            renderTextChart(currentHistoryData);
        }

    } catch (error) {
        console.error('Failed to load history:', error);
        const errorText = window.i18n ? window.i18n.t('failedToLoadHistory') : 'Failed to load entity history';
        alert(errorText + ': ' + (error.response?.data?.error || error.message));
    } finally {
        myChart.hideLoading();
    }
}

function updateDateRangeDisplay() {
    if (window.i18n) {
        dateRangeDisplay.textContent = window.i18n.formatDateRange(dateRange.start, dateRange.end);
    } else {
        const formatDate = (d) => {
            return d.toLocaleString('en-US', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        };
        dateRangeDisplay.textContent = `from ${formatDate(dateRange.start)} to ${formatDate(dateRange.end)}`;
    }
}

function renderClimateChart(data) {
    // Get translated labels
    const t = window.i18n ? window.i18n.t : (k) => k;
    const labels = {
        interior: t('interior'),
        setpoint: t('setpoint'),
        exterior: t('exterior'),
        heating: t('heating')
    };

    // Prepare heating area data
    const heatingData = data.timestamps.map((ts, index) => {
        const isHeating = data.is_heating[index];
        const currentTemp = data.current_temperature[index];

        if (isHeating === 1 && currentTemp != null) {
            return currentTemp;
        }
        return null;
    });

    const option = {
        animation: false,
        backgroundColor: '#1e1e1e',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' }
        },
        legend: {
            data: [labels.interior, labels.setpoint, labels.exterior, labels.heating],
            top: 10,
            selected: { [labels.exterior]: false }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '15%',
            containLabel: true
        },
        toolbox: {
            feature: {
                dataZoom: { yAxisIndex: 'none' },
                restore: {},
                saveAsImage: {}
            }
        },
        dataZoom: [
            { type: 'inside', start: 0, end: 100, filterMode: 'filter' },
            { start: 0, end: 100, filterMode: 'filter' }
        ],
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: data.timestamps,
            axisLabel: {
                formatter: (value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { show: true, lineStyle: { color: '#333' } },
            min: (value) => Math.floor(value.min * 10) / 10 - 0.1,
            max: (value) => Math.ceil(value.max * 10) / 10 + 0.1,
            axisLabel: { formatter: (value) => value.toFixed(1) + ' °C' }
        },
        series: [
            {
                name: labels.heating,
                type: 'line',
                step: 'start',
                data: heatingData,
                lineStyle: { width: 0 },
                areaStyle: { color: 'rgba(255, 140, 0, 0.4)', origin: 'start' },
                symbol: 'none'
            },
            {
                name: labels.setpoint,
                type: 'line',
                step: 'start',
                data: data.temperature,
                lineStyle: { color: '#FFD700', width: 2 },
                symbol: 'none'
            },
            {
                name: labels.interior,
                type: 'line',
                step: 'start',
                data: data.current_temperature,
                lineStyle: { color: '#4169E1', width: 2 },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(65, 105, 225, 0.1)' },
                        { offset: 1, color: 'rgba(65, 105, 225, 0.0)' }
                    ])
                },
                symbol: 'none'
            },
            {
                name: labels.exterior,
                type: 'line',
                step: 'start',
                data: data.ext_current_temperature,
                lineStyle: { color: '#A9A9A9', width: 1, type: 'dashed' },
                symbol: 'none',
                smooth: true
            }
        ]
    };

    myChart.setOption(option, true);
    setupChartClickHandler(data);
}

function renderNumericChart(data) {
    const option = {
        animation: false,
        backgroundColor: '#1e1e1e',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '15%',
            containLabel: true
        },
        toolbox: {
            feature: {
                dataZoom: { yAxisIndex: 'none' },
                restore: {},
                saveAsImage: {}
            }
        },
        dataZoom: [
            { type: 'inside', start: 0, end: 100 },
            { start: 0, end: 100 }
        ],
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: data.timestamps,
            axisLabel: {
                formatter: (value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { show: true, lineStyle: { color: '#333' } }
        },
        series: [{
            name: 'Value',
            type: 'line',
            step: 'start',
            data: data.states,
            lineStyle: { color: '#00d2ff', width: 2 },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(0, 210, 255, 0.3)' },
                    { offset: 1, color: 'rgba(0, 210, 255, 0)' }
                ])
            },
            symbol: 'none'
        }]
    };

    myChart.setOption(option, true);
    setupChartClickHandler(data);
}

function renderTextChart(data) {
    // For text/categorical data, show a timeline-like view
    // Convert states to numeric categories for visualization
    const uniqueStates = [...new Set(data.states.filter(s => s !== null))];
    const stateToNum = {};
    uniqueStates.forEach((s, i) => stateToNum[s] = i);

    const numericStates = data.states.map(s => s !== null ? stateToNum[s] : null);

    const option = {
        animation: false,
        backgroundColor: '#1e1e1e',
        tooltip: {
            trigger: 'axis',
            formatter: (params) => {
                const idx = params[0].dataIndex;
                return `${new Date(data.timestamps[idx]).toLocaleString()}<br/>State: <b>${data.states[idx]}</b>`;
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '15%',
            containLabel: true
        },
        dataZoom: [
            { type: 'inside', start: 0, end: 100 },
            { start: 0, end: 100 }
        ],
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: data.timestamps,
            axisLabel: {
                formatter: (value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
        },
        yAxis: {
            type: 'category',
            data: uniqueStates,
            splitLine: { show: true, lineStyle: { color: '#333' } }
        },
        series: [{
            type: 'line',
            step: 'start',
            data: numericStates,
            lineStyle: { color: '#9370DB', width: 2 },
            symbol: 'circle',
            symbolSize: 6
        }]
    };

    myChart.setOption(option, true);
    setupChartClickHandler(data);
}

function setupChartClickHandler(data) {
    let currentHoverTimestamp = null;

    myChart.on('updateAxisPointer', (event) => {
        const xAxisInfo = event.axesInfo[0];
        if (xAxisInfo) {
            const index = xAxisInfo.value;
            currentHoverTimestamp = data.timestamps[index];
            cursorTimeDisplay.textContent = new Date(currentHoverTimestamp).toLocaleTimeString();
        }
    });

    myChart.getZr().off('click');
    myChart.getZr().on('click', () => {
        if (currentHoverTimestamp) {
            fetchDetails(currentHoverTimestamp);
        }
    });
}

// =============================================================================
// Details Panel
// =============================================================================

let detailsTimeout;
let currentDetailsData = null;
let attributePath = [];

async function fetchDetails(timestamp) {
    clearTimeout(detailsTimeout);
    detailsTimeout = setTimeout(async () => {
        if (!currentEntityId) return;

        try {
            const response = await axios.get(`/api/details/${currentEntityId}`, {
                params: { timestamp }
            });
            currentDetailsData = response.data;
            attributePath = [];
            displayAttributes(currentDetailsData, []);
        } catch (error) {
            console.error('Failed to fetch details:', error);
        }
    }, 50);
}

function displayAttributes(data, path) {
    const t = window.i18n ? window.i18n.t : (k) => k;

    if (!data || !data.attributes) {
        detailsContent.innerHTML = `<p class="text-muted">${t('noAttributesAvailable')}</p>`;
        return;
    }

    // Navigate to the correct level based on path
    let current = data.attributes;
    for (const key of path) {
        if (current && typeof current === 'object' && key in current) {
            current = current[key];
        } else {
            current = {};
            break;
        }
    }

    let html = '';

    // Back button if not at root
    if (path.length > 0) {
        const backText = window.i18n ? window.i18n.t('back') : 'Back';
        html += `
            <button class="btn btn-sm btn-outline-secondary mb-2" onclick="navigateAttributesBack()">
                <i class="bi bi-arrow-left"></i> ${backText}
            </button>
            <div class="attribute-path mb-2">
                <span class="path-item" onclick="navigateToPath([])">attributes</span>
                ${path.map((p, i) => `<span> / </span><span class="path-item" onclick="navigateToPath(${JSON.stringify(path.slice(0, i + 1))})">${p}</span>`).join('')}
            </div>
        `;
    }

    if (typeof current !== 'object' || current === null) {
        html += `<p class="text-muted">Value: ${current}</p>`;
        detailsContent.innerHTML = html;
        return;
    }

    html += '<table class="table table-sm table-dark table-striped text-xsmall">';

    const entries = Object.entries(current);
    for (const [key, value] of entries) {
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            // Dict - show as navigable folder
            const keyCount = Object.keys(value).length;
            const itemsText = window.i18n ? window.i18n.t('items') : 'items';
            html += `
                <tr class="clickable-row dict-row" onclick="navigateAttributesInto('${key}')">
                    <td><i class="bi bi-folder-fill text-warning me-2"></i>${key}</td>
                    <td class="text-end text-muted">${keyCount} ${itemsText} →</td>
                </tr>`;
        } else {
            // Simple value - clickable to show history
            const displayVal = formatAttributeValue(value);
            const fullPath = [...path, key].join('.');
            html += `
                <tr class="clickable-row" onclick="showAttributeHistory('${fullPath}')">
                    <td>${key}</td>
                    <td class="text-end">${displayVal}</td>
                </tr>`;
        }
    }

    html += '</table>';
    detailsContent.innerHTML = html;
}

function formatAttributeValue(value) {
    if (value === null || value === undefined) {
        return '<span class="text-muted">null</span>';
    }
    if (typeof value === 'number') {
        return Math.round(value * 10000) / 10000;
    }
    if (Array.isArray(value)) {
        return `[${value.length} items]`;
    }
    if (typeof value === 'boolean') {
        return value ? '<span class="text-success">true</span>' : '<span class="text-danger">false</span>';
    }
    return escapeHtml(String(value));
}

function navigateAttributesInto(key) {
    attributePath.push(key);
    displayAttributes(currentDetailsData, attributePath);
}

function navigateAttributesBack() {
    attributePath.pop();
    displayAttributes(currentDetailsData, attributePath);
}

function navigateToPath(path) {
    attributePath = path;
    displayAttributes(currentDetailsData, attributePath);
}

// =============================================================================
// Attribute History Modal
// =============================================================================

historyModalEl.addEventListener('hidden.bs.modal', () => {
    if (historyChart) {
        historyChart.dispose();
        historyChart = null;
    }
    historyChartDom.innerHTML = '';
    historyListDom.innerHTML = '';
});

historyModalEl.addEventListener('shown.bs.modal', () => {
    if (historyChart) {
        historyChart.resize();
    }
});

async function showAttributeHistory(key) {
    if (!currentEntityId) return;

    const t = window.i18n ? window.i18n.t : (k) => k;
    historyTitle.textContent = `${t('history')}: ${key}`;
    historyChartDom.classList.add('d-none');
    historyListDom.classList.add('d-none');
    historyLoading.classList.remove('d-none');

    historyModal.show();

    try {
        const params = new URLSearchParams({
            key,
            start: dateRange.start.toISOString(),
            end: dateRange.end.toISOString()
        });

        const response = await axios.get(`/api/attribute-history/${currentEntityId}?${params}`);
        const data = response.data;

        historyLoading.classList.add('d-none');

        if (data.type === 'numeric') {
            renderHistoryChart(data);
        } else {
            renderHistoryList(data);
        }

    } catch (error) {
        console.error('Failed to load attribute history:', error);
        const errorText = window.i18n ? window.i18n.t('failedToLoadAttributeHistory') : 'Failed to load attribute history';
        alert(errorText);
        historyLoading.classList.add('d-none');
    }
}

function renderHistoryChart(data) {
    historyChartDom.classList.remove('d-none');

    if (historyChart) historyChart.dispose();
    historyChart = echarts.init(historyChartDom, 'dark');

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' }
        },
        grid: {
            left: '3%', right: '4%', bottom: '15%', containLabel: true
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: data.timestamps,
            axisLabel: {
                formatter: (value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { show: true, lineStyle: { color: '#333' } }
        },
        dataZoom: [
            { type: 'inside', start: 0, end: 100 },
            { start: 0, end: 100 }
        ],
        series: [{
            name: data.key,
            type: 'line',
            step: 'start',
            data: data.values,
            symbol: 'none',
            lineStyle: { width: 2, color: '#00d2ff' },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(0, 210, 255, 0.3)' },
                    { offset: 1, color: 'rgba(0, 210, 255, 0)' }
                ])
            }
        }]
    };

    historyChart.setOption(option);
}

function renderHistoryList(data) {
    historyListDom.classList.remove('d-none');

    const t = window.i18n ? window.i18n.t : (k) => k;
    let html = '<table class="table table-dark table-sm table-striped">';
    html += `<thead><tr><th>${t('time')}</th><th>${t('value')}</th></tr></thead><tbody>`;

    data.timestamps.forEach((ts, index) => {
        const val = data.values[index];
        const dateStr = new Date(ts).toLocaleString();
        html += `<tr><td>${dateStr}</td><td>${escapeHtml(String(val))}</td></tr>`;
    });

    html += '</tbody></table>';
    historyListDom.innerHTML = html;
}

// =============================================================================
// Date Range Selection
// =============================================================================

function openDateRangeModal() {
    startPicker.setDate(dateRange.start);
    endPicker.setDate(dateRange.end);
    dateRangeModal.show();
}

function applyDateRange() {
    const startDate = startPicker.selectedDates[0];
    const endDate = endPicker.selectedDates[0];
    const t = window.i18n ? window.i18n.t : (k) => k;

    if (!startDate || !endDate) {
        alert(t('errorDateRange'));
        return;
    }

    if (startDate >= endDate) {
        alert(t('errorDateOrder'));
        return;
    }

    dateRange.start = startDate;
    dateRange.end = endDate;

    dateRangeModal.hide();

    // Reload history with new date range
    if (currentEntityId) {
        loadEntityHistory();
    }
}

function applyQuickRange(days) {
    dateRange.end = new Date();
    dateRange.start = new Date();
    dateRange.start.setDate(dateRange.start.getDate() - days);

    startPicker.setDate(dateRange.start);
    endPicker.setDate(dateRange.end);

    // Update button states
    document.querySelectorAll('.quick-range').forEach(btn => {
        btn.classList.remove('active');
        if (parseInt(btn.dataset.days) === days) {
            btn.classList.add('active');
        }
    });
}

// =============================================================================
// Event Listeners Setup
// =============================================================================

function setupEventListeners() {
    // Entity search input
    entitySearch.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        if (query.length >= 2) {
            const filtered = filterEntities(query);
            renderEntityDropdown(filtered);
            entityDropdown.classList.remove('d-none');
        } else {
            entityDropdown.classList.add('d-none');
        }
    });

    // Hide dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!entitySearch.contains(e.target) && !entityDropdown.contains(e.target)) {
            entityDropdown.classList.add('d-none');
        }
    });

    // Focus on search shows dropdown if has content
    entitySearch.addEventListener('focus', () => {
        if (entitySearch.value.length >= 2) {
            entityDropdown.classList.remove('d-none');
        }
    });

    // Keyboard navigation
    entitySearch.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            entityDropdown.classList.add('d-none');
        }
    });

    // Date range button
    dateRangeBtn.addEventListener('click', openDateRangeModal);

    // Apply date range
    document.getElementById('apply-date-range').addEventListener('click', applyDateRange);

    // Quick range buttons
    document.querySelectorAll('.quick-range').forEach(btn => {
        btn.addEventListener('click', () => {
            applyQuickRange(parseInt(btn.dataset.days));
        });
    });

    // Refresh button
    refreshBtn.addEventListener('click', loadEntityHistory);
}

// =============================================================================
// Utilities
// =============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make functions available globally for onclick handlers
window.clearSelectedEntity = clearSelectedEntity;
window.navigateAttributesBack = navigateAttributesBack;
window.navigateAttributesInto = navigateAttributesInto;
window.navigateToPath = navigateToPath;
window.showAttributeHistory = showAttributeHistory;

// =============================================================================
// Start
// =============================================================================

init();
