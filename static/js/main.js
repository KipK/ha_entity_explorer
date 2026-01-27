
// Références DOM
const chartDom = document.getElementById('main-chart');
const fileSelector = document.getElementById('file-selector');
const detailsContent = document.getElementById('details-content');
const cursorTimeDisplay = document.getElementById('cursor-time');

// Initialisation ECharts
const myChart = echarts.init(chartDom, 'dark');
let currentFilename = null;

// Gestion du redimensionnement
window.addEventListener('resize', function () {
    myChart.resize();
});

// Chargement de la liste des fichiers
async function loadFiles() {
    try {
        const response = await axios.get('/api/files');
        const files = response.data;

        fileSelector.innerHTML = '<option selected disabled>Choisir un fichier...</option>';
        files.forEach(file => {
            const option = document.createElement('option');
            option.value = file;
            option.text = file;
            // Auto-select history.json if present
            if (file === 'history.json') option.selected = true;
            fileSelector.appendChild(option);
        });

        // Chargement automatique si history.json est présent
        if (files.includes('history.json')) {
            loadChartData('history.json');
        }

        fileSelector.addEventListener('change', (e) => {
            loadChartData(e.target.value);
        });
    } catch (error) {
        console.error("Erreur chargement fichiers:", error);
    }
}

// Chargement des données du graphique
async function loadChartData(filename) {
    if (!filename) return;
    currentFilename = filename;

    myChart.showLoading();
    try {
        const response = await axios.get(`/api/chart-data/${filename}`);
        const data = response.data;

        renderChart(data);
    } catch (error) {
        console.error("Erreur chargement données:", error);
        alert("Erreur lors du chargement des données: " + error.message);
    } finally {
        myChart.hideLoading();
    }
}

// Rendu du graphique
function renderChart(data) {
    // Préparation des données pour la série de chauffage (Area sous la courbe de temp)
    const heatingData = data.timestamps.map((ts, index) => {
        const isHeating = data.is_heating[index];
        const currentTemp = data.current_temperature[index];

        // Si chauffe: on prend la température actuelle (ou 0 si inconnue)
        // Si pas chauffe: 0
        if (isHeating === 1 && currentTemp != null) {
            return currentTemp;
        }
        return null; // Allows auto-scale to ignore 'off' values (don't force to 0)
    });

    const option = {
        animation: false, // Disable animation for instant updates
        backgroundColor: '#1e1e1e', // Match CSS
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            }
        },
        legend: {
            data: ['Intérieure', 'Consigne', 'Extérieure', 'Chauffe'],
            top: 10,
            selected: {
                'Extérieure': false
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '15%', // Place pour le slider
            containLabel: true
        },
        toolbox: {
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {},
                saveAsImage: {}
            }
        },
        dataZoom: [
            {
                type: 'inside',
                start: 0,
                end: 100,
                filterMode: 'filter'
            },
            {
                start: 0,
                end: 100,
                filterMode: 'filter'
            }
        ],
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: data.timestamps,
            axisLabel: {
                formatter: function (value) {
                    return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                }
            }
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: {
                show: true,
                lineStyle: { color: '#333' }
            },
            // Force tight scaling
            min: function (value) {
                return Math.floor(value.min * 10) / 10 - 0.1;
            },
            max: function (value) {
                return Math.ceil(value.max * 10) / 10 + 0.1;
            },
            axisLabel: {
                formatter: function (value) {
                    return value.toFixed(1) + ' °C';
                }
            }
        },
        series: [
            {
                name: 'Chauffe',
                type: 'line',
                step: 'start', // Important: le changement d'état s'applique dès le timestamp
                data: heatingData,
                lineStyle: { width: 0 }, // Pas de ligne au sommet
                areaStyle: {
                    color: 'rgba(255, 140, 0, 0.4)', // Orange transparent
                    origin: 'start'
                },
                symbol: 'none'
            },
            {
                name: 'Consigne',
                type: 'line',
                step: 'start',
                data: data.temperature,
                lineStyle: { color: '#FFD700', width: 2 }, // Gold
                symbol: 'none'
            },
            {
                name: 'Intérieure',
                type: 'line',
                step: 'start',
                data: data.current_temperature,
                lineStyle: { color: '#4169E1', width: 2 }, // RoyalBlue
                areaStyle: {
                    // Petit dégradé bleu sous la courbe de temp, mais plus léger que la chauffe
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(65, 105, 225, 0.1)' },
                        { offset: 1, color: 'rgba(65, 105, 225, 0.0)' }
                    ])
                },
                symbol: 'none'
            },
            {
                name: 'Extérieure',
                type: 'line',
                step: 'start',
                data: data.ext_current_temperature,
                lineStyle: { color: '#A9A9A9', width: 1, type: 'dashed' }, // DarkGray
                symbol: 'none',
                smooth: true
            }
        ]
    };

    myChart.setOption(option, true); // true = not merge (reset)

    // Variable pour stocker le timestamp sous la souris
    let currentHoverTimestamp = null;

    // Tracker la position de la souris
    myChart.on('updateAxisPointer', function (event) {
        const xAxisInfo = event.axesInfo[0];
        if (xAxisInfo) {
            const index = xAxisInfo.value;
            currentHoverTimestamp = data.timestamps[index];
            // On met à jour l'heure affichée pour aider à viser
            cursorTimeDisplay.textContent = new Date(currentHoverTimestamp).toLocaleTimeString();
        }
    });

    // Déclencher l'affichage des détails au click
    myChart.getZr().on('click', function () {
        if (currentHoverTimestamp) {
            fetchDetails(currentHoverTimestamp);
        }
    });
}

// Debounce pour ne pas spammer l'API details (utile si on reclique vite)
let detailsTimeout;
function fetchDetails(timestamp) {
    clearTimeout(detailsTimeout);
    detailsTimeout = setTimeout(async () => {
        if (!currentFilename) return;

        try {
            const response = await axios.get(`/api/details/${currentFilename}`, {
                params: { timestamp: timestamp }
            });
            displayDetails(response.data);
        } catch (error) {
            console.error(error);
        }
    }, 50);
}

const historyModalEl = document.getElementById('historyModal');
const historyModal = new bootstrap.Modal(historyModalEl);
const historyTitle = document.getElementById('historyModalLabel');
const historyChartDom = document.getElementById('history-chart');
const historyListDom = document.getElementById('history-list');
const historyLoading = document.getElementById('history-loading');

let historyChart = null;

// Clean up chart when modal closes
historyModalEl.addEventListener('hidden.bs.modal', function () {
    if (historyChart) {
        historyChart.dispose();
        historyChart = null;
    }
    historyChartDom.innerHTML = '';
    historyListDom.innerHTML = '';
});

// Resize chart when modal fully opens
historyModalEl.addEventListener('shown.bs.modal', function () {
    if (historyChart) {
        historyChart.resize();
    }
});


function displayDetails(data) {
    if (!data || !data.attributes) return;

    const attrs = data.attributes;
    // User indicated smart_pi is in specific_states
    const specificStates = attrs.specific_states || {};
    const smartPi = specificStates.smart_pi || attrs.smart_pi || {};

    // Construction du HTML - UNIQUEMENT Smart PI demandé
    let html = '';

    // Smart PI
    if (Object.keys(smartPi).length > 0) {
        html += `<h6 class="mt-3">Smart PI (Cliquer pour historique)</h6>`;
        html += `<table class="table table-sm table-dark table-striped text-xsmall">`;
        for (const [key, value] of Object.entries(smartPi)) {
            // Formatage des nombres
            let displayVal = value;
            if (typeof value === 'number') {
                // Arrondir si nécessaire, ou afficher tel quel
                displayVal = Math.round(value * 10000) / 10000;
            }
            // Ajout de la classe clickable-row et event onclick
            html += `<tr class="clickable-row" onclick="showAttributeHistory('${key}')">
                        <td>${key}</td><td class="text-end">${displayVal}</td>
                     </tr>`;
        }
        html += `</table>`;
    } else {
        html += `<p class="text-warning small mt-3">Pas de données Smart PI</p>`;
    }

    detailsContent.innerHTML = html;
}

// Fonction pour afficher l'historique
async function showAttributeHistory(key) {
    if (!currentFilename) return;

    historyTitle.textContent = `Historique : ${key}`;
    historyChartDom.classList.add('d-none');
    historyListDom.classList.add('d-none');
    historyLoading.classList.remove('d-none');
    
    // Use HTML element method to show modal (bootstrap 5 vanilla)
    historyModal.show();

    try {
        const response = await axios.get(`/api/smartpi-history/${currentFilename}`, {
            params: { key: key }
        });
        const data = response.data;
        
        historyLoading.classList.add('d-none');
        
        if (data.type === 'numeric') {
            renderHistoryChart(data);
        } else {
            renderHistoryList(data);
        }

    } catch (error) {
        console.error("Erreur historique:", error);
        alert("Impossible de charger l'historique.");
        historyLoading.classList.add('d-none');
    }
}

function renderHistoryChart(data) {
    historyChartDom.classList.remove('d-none');
    // Ensure container has size before init
    // (Modal 'shown' event usually handles resize, but we init here)
    
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
                formatter: function (value) {
                    return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                }
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
    
    let html = '<table class="table table-dark table-sm table-striped">';
    html += '<thead><tr><th>Heure</th><th>Valeur</th></tr></thead><tbody>';
    
    // On parcourt à l'envers pour avoir le plus récent en haut ? ou ordre chrono ?
    // Ordre chrono c'est mieux pour l'historique, mais liste souvent plus récent en haut.
    // Gardons l'ordre des données (chrono).
    
    data.timestamps.forEach((ts, index) => {
        const val = data.values[index];
        const dateStr = new Date(ts).toLocaleString();
        html += `<tr><td>${dateStr}</td><td>${val}</td></tr>`;
    });
    
    html += '</tbody></table>';
    historyListDom.innerHTML = html;
}

// Start
loadFiles();
