// --- Inicializar Telegram WebApp SDK ---
const tg = window.Telegram ? window.Telegram.WebApp : null;

if (tg) {
    tg.ready();
    tg.expand(); // Expandir la app a pantalla completa
    // Aplicar tema nativo
    document.body.classList.add('telegram-theme');
}

// --- Generación de Datos de Simulación (Fallback si falla API) ---
function generateSimulatedData(points = 100) {
    let price = 67350; // Precio realista por defecto para simulación
    const data = [];
    const now = new Date();
    
    for (let i = points; i > 0; i--) {
        const time = new Date(now.getTime() - i * 5 * 60 * 1000); // Intervalo de 5 min
        const change = (Math.random() - 0.48) * 100;
        price += change;
        data.push({
            time: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            close: price
        });
    }
    return data;
}

let currentSymbol = "BTCUSDT";

// --- Obtener datos reales de Binance API (Soporte Spot + Futuros) ---
async function fetchBinanceData(symbol = currentSymbol) {
    try {
        // 1. Intentar con Binance Spot
        const spotUrl = `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=5m&limit=100`;
        const response = await fetch(spotUrl);
        if (response.ok) {
            const klines = await response.json();
            return mapKlines(klines);
        }
        
        // 2. Si falla Spot, intentar con Binance Futures (Perpetuos)
        console.log(`ℹ️ Símbolo ${symbol} no encontrado en Spot. Buscando en Binance Futuros...`);
        const futuresUrl = `https://fapi.binance.com/fapi/v1/klines?symbol=${symbol}&interval=5m&limit=100`;
        const futuresResponse = await fetch(futuresUrl);
        if (futuresResponse.ok) {
            const klines = await futuresResponse.json();
            return mapKlines(klines);
        }
        
        throw new Error(`Symbol ${symbol} not found on Spot or Futures API.`);
    } catch (e) {
        console.warn(`⚠️ No se pudo obtener datos de Binance para ${symbol}:`, e);
        return null;
    }
}

function mapKlines(klines) {
    return klines.map(k => {
        const openTime = new Date(k[0]);
        return {
            time: openTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            close: parseFloat(k[4]) // Close price
        };
    });
}

// Dataset inicial
let originalDataset = [];

// --- Cálculos Matemáticos de Indicadores ---
function calculateSMA(data, period) {
    const sma = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            sma.push(null);
            continue;
        }
        let sum = 0;
        for (let j = 0; j < period; j++) {
            sum += data[i - j].close;
        }
        sma.push(sum / period);
    }
    return sma;
}

function calculateBollingerBands(data, period, stdDevMultiplier = 2) {
    const upper = [];
    const lower = [];
    const middle = calculateSMA(data, period);
    
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1 || middle[i] === null) {
            upper.push(null);
            lower.push(null);
            continue;
        }
        // Calcular desviación estándar
        let sumSqDiff = 0;
        const mean = middle[i];
        for (let j = 0; j < period; j++) {
            sumSqDiff += Math.pow(data[i - j].close - mean, 2);
        }
        const stdDev = Math.sqrt(sumSqDiff / period);
        
        upper.push(mean + stdDevMultiplier * stdDev);
        lower.push(mean - stdDevMultiplier * stdDev);
    }
    
    return { upper, lower, middle };
}

function calculateEMA(data, period) {
    const ema = [];
    if (data.length === 0) return ema;
    
    const k = 2 / (period + 1);
    let emaVal = data[0].close; // Inicializar con el primer precio
    ema.push(emaVal);
    
    for (let i = 1; i < data.length; i++) {
        emaVal = data[i].close * k + emaVal * (1 - k);
        ema.push(emaVal);
    }
    
    for (let i = 0; i < period - 1; i++) {
        ema[i] = null;
    }
    return ema;
}

function calculateMACD(data, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
    const fastEma = calculateEMA(data, fastPeriod);
    const slowEma = calculateEMA(data, slowPeriod);
    
    const macdLine = [];
    for (let i = 0; i < data.length; i++) {
        if (fastEma[i] === null || slowEma[i] === null) {
            macdLine.push(null);
        } else {
            macdLine.push(fastEma[i] - slowEma[i]);
        }
    }
    
    const validMacd = macdLine.map(val => ({ close: val === null ? 0 : val }));
    const signalEma = calculateEMA(validMacd, signalPeriod);
    
    const signalLine = [];
    const histogram = [];
    for (let i = 0; i < data.length; i++) {
        if (macdLine[i] === null || i < (slowPeriod + signalPeriod - 2)) {
            signalLine.push(null);
            histogram.push(null);
        } else {
            const sigVal = signalEma[i];
            signalLine.push(sigVal);
            histogram.push(macdLine[i] - sigVal);
        }
    }
    
    return { macdLine, signalLine, histogram };
}

function calculateRSI(data, period) {
    const rsi = [];
    let gains = 0;
    let losses = 0;
    
    // Primer período
    for (let i = 1; i < data.length; i++) {
        const diff = data[i].close - data[i - 1].close;
        const gain = diff > 0 ? diff : 0;
        const loss = diff < 0 ? -diff : 0;
        
        if (i <= period) {
            gains += gain;
            losses += loss;
            if (i === period) {
                let avgGain = gains / period;
                let avgLoss = losses / period;
                let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
                rsi.push(100 - (100 / (1 + rs)));
            } else {
                rsi.push(null);
            }
        } else {
            // Suavizado Wilder
            let lastRSI = rsi[rsi.length - 1];
            if (lastRSI === null) {
                rsi.push(null);
                continue;
            }
            gains = (gains * (period - 1) + gain) / period;
            losses = (losses * (period - 1) + loss) / period;
            let rs = losses === 0 ? 100 : gains / losses;
            rsi.push(100 - (100 / (1 + rs)));
        }
    }
    // Desplazar rsi para alinear con el dataset original (falta el primer punto)
    rsi.unshift(null);
    return rsi;
}

// --- Elementos del DOM ---
const currentPriceEl = document.getElementById('current-price');
const rsiValueEl = document.getElementById('rsi-value');
const trendStatusEl = document.getElementById('trend-status');
const volatilityStatusEl = document.getElementById('volatility-status');
const priceChangeEl = document.getElementById('price-change-percent');

const smaSlider = document.getElementById('sma-period-input');
const rsiSlider = document.getElementById('rsi-period-input');
const bbSlider = document.getElementById('bb-period-input');
const emaSlider = document.getElementById('ema-period-input');
const macdFastSlider = document.getElementById('macd-fast-input');
const macdSlowSlider = document.getElementById('macd-slow-input');

const smaBadge = document.getElementById('sma-badge-val');
const rsiBadge = document.getElementById('rsi-badge-val');
const bbBadge = document.getElementById('bb-badge-val');
const emaBadge = document.getElementById('ema-badge-val');
const macdFastBadge = document.getElementById('macd-fast-badge-val');
const macdSlowBadge = document.getElementById('macd-slow-badge-val');

const btnCalculate = document.getElementById('btn-calculate');
const btnSendAlert = document.getElementById('btn-send-alert');

// --- Renderizar Gráfico con Chart.js ---
let priceChart;
let rsiChart;
let macdChart;

function initRsiChart(data, rsi) {
    const ctx = document.getElementById('rsiChart').getContext('2d');
    
    const rsiGrad = ctx.createLinearGradient(0, 0, 0, 150);
    rsiGrad.addColorStop(0, 'rgba(255, 99, 132, 0.15)');
    rsiGrad.addColorStop(1, 'rgba(255, 99, 132, 0.0)');

    rsiChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.time),
            datasets: [
                {
                    label: 'RSI',
                    data: rsi,
                    borderColor: '#FF6384',
                    borderWidth: 2,
                    fill: true,
                    backgroundColor: rsiGrad,
                    pointRadius: 0,
                    tension: 0.1
                },
                {
                    label: 'Sobrecompra (70)',
                    data: new Array(data.length).fill(70),
                    borderColor: 'rgba(255, 82, 82, 0.3)',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    fill: false,
                    pointRadius: 0
                },
                {
                    label: 'Sobreventa (30)',
                    data: new Array(data.length).fill(30),
                    borderColor: 'rgba(0, 230, 118, 0.3)',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    fill: false,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#8E9BAE', maxTicksLimit: 6, font: { family: 'Outfit' } }
                },
                y: {
                    min: 10,
                    max: 90,
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#8E9BAE', font: { family: 'Outfit' }, stepSize: 20 }
                }
            }
        }
    });
}

function initMacdChart(data, macdLine, signalLine, histogram) {
    const ctx = document.getElementById('macdChart').getContext('2d');
    
    macdChart = new Chart(ctx, {
        data: {
            labels: data.map(d => d.time),
            datasets: [
                {
                    type: 'line',
                    label: 'MACD',
                    data: macdLine,
                    borderColor: '#F26B48',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.1
                },
                {
                    type: 'line',
                    label: 'Señal',
                    data: signalLine,
                    borderColor: '#3897F0',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.1
                },
                {
                    type: 'bar',
                    label: 'Histograma',
                    data: histogram,
                    backgroundColor: histogram.map(val => val >= 0 ? 'rgba(0, 230, 118, 0.4)' : 'rgba(255, 82, 82, 0.4)'),
                    borderColor: histogram.map(val => val >= 0 ? '#00E676' : '#FF5252'),
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.8
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#8E9BAE', maxTicksLimit: 6, font: { family: 'Outfit' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#8E9BAE', font: { family: 'Outfit' } }
                }
            }
        }
    });
}

function initChart(data, sma, bb, ema) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    const chartGrad = ctx.createLinearGradient(0, 0, 0, 200);
    chartGrad.addColorStop(0, 'rgba(56, 151, 240, 0.15)');
    chartGrad.addColorStop(1, 'rgba(56, 151, 240, 0.0)');

    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.time),
            datasets: [
                {
                    label: 'Precio',
                    data: data.map(d => d.close),
                    borderColor: '#3897F0',
                    borderWidth: 2,
                    fill: true,
                    backgroundColor: chartGrad,
                    pointRadius: 0,
                    tension: 0.1
                },
                {
                    label: `SMA`,
                    data: sma,
                    borderColor: '#F18F01',
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    fill: false,
                    pointRadius: 0,
                    tension: 0.1
                },
                {
                    label: 'BB Superior',
                    data: bb.upper,
                    borderColor: 'rgba(162, 59, 114, 0.3)',
                    borderWidth: 1,
                    fill: false,
                    pointRadius: 0
                },
                {
                    label: 'BB Inferior',
                    data: bb.lower,
                    borderColor: 'rgba(162, 59, 114, 0.3)',
                    borderWidth: 1,
                    fill: '-1',
                    backgroundColor: 'rgba(162, 59, 114, 0.04)',
                    pointRadius: 0
                },
                {
                    label: 'EMA',
                    data: ema,
                    borderColor: '#9C27B0',
                    borderWidth: 1.5,
                    fill: false,
                    pointRadius: 0,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#8E9BAE', maxTicksLimit: 6, font: { family: 'Outfit' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#8E9BAE', font: { family: 'Outfit' } }
                }
            }
        }
    });
}

function updateUI() {
    if (originalDataset.length === 0) return;

    const smaVal = parseInt(smaSlider.value);
    const rsiVal = parseInt(rsiSlider.value);
    const bbVal = parseInt(bbSlider.value);
    const emaVal = parseInt(emaSlider.value);
    const macdFastVal = parseInt(macdFastSlider.value);
    const macdSlowVal = parseInt(macdSlowSlider.value);
    
    smaBadge.textContent = smaVal;
    rsiBadge.textContent = rsiVal;
    bbBadge.textContent = bbVal;
    emaBadge.textContent = emaVal;
    macdFastBadge.textContent = macdFastVal;
    macdSlowBadge.textContent = macdSlowVal;
    
    const smaData = calculateSMA(originalDataset, smaVal);
    const bbData = calculateBollingerBands(originalDataset, bbVal);
    const rsiData = calculateRSI(originalDataset, rsiVal);
    const emaData = calculateEMA(originalDataset, emaVal);
    const macdData = calculateMACD(originalDataset, macdFastVal, macdSlowVal, 9);
    
    const currentPrice = originalDataset[originalDataset.length - 1].close;
    const initialPrice = originalDataset[0].close;
    const currentRSI = rsiData[rsiData.length - 1] || 50;
    const currentSMA = smaData[smaData.length - 1] || currentPrice;
    
    // Calcular porcentaje de cambio en la muestra
    const priceChange = ((currentPrice - initialPrice) / initialPrice) * 100;
    priceChangeEl.textContent = (priceChange >= 0 ? "+" : "") + priceChange.toFixed(2) + "%";
    priceChangeEl.className = priceChange >= 0 ? "change-badge positive" : "change-badge negative";
    if (priceChange < 0) {
        priceChangeEl.style.backgroundColor = 'rgba(255, 82, 82, 0.15)';
        priceChangeEl.style.color = '#FF5252';
    } else {
        priceChangeEl.style.backgroundColor = '';
        priceChangeEl.style.color = '';
    }

    currentPriceEl.textContent = `$${currentPrice.toLocaleString([], { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    rsiValueEl.textContent = currentRSI.toFixed(2);
    
    if (currentRSI > 70) {
        rsiValueEl.className = 'stat-value text-danger';
    } else if (currentRSI < 30) {
        rsiValueEl.className = 'stat-value text-success';
    } else {
        rsiValueEl.className = 'stat-value text-warning';
    }

    if (currentPrice > currentSMA) {
        trendStatusEl.textContent = "Alcista";
        trendStatusEl.className = "stat-value text-success";
    } else {
        trendStatusEl.textContent = "Bajista";
        trendStatusEl.className = "stat-value text-danger";
    }

    const upperBB = bbData.upper[bbData.upper.length - 1] || currentPrice;
    const lowerBB = bbData.lower[bbData.lower.length - 1] || currentPrice;
    const percentWidth = ((upperBB - lowerBB) / currentPrice) * 100;
    
    if (percentWidth > 1.5) {
        volatilityStatusEl.textContent = "Alta ⚡";
        volatilityStatusEl.className = "stat-value text-danger";
    } else if (percentWidth < 0.6) {
        volatilityStatusEl.textContent = "Baja 💤";
        volatilityStatusEl.className = "stat-value text-primary";
    } else {
        volatilityStatusEl.textContent = "Moderada";
        volatilityStatusEl.className = "stat-value text-warning";
    }

    if (priceChart) {
        priceChart.data.labels = originalDataset.map(d => d.time);
        priceChart.data.datasets[0].data = originalDataset.map(d => d.close);
        priceChart.data.datasets[1].label = `SMA (${smaVal})`;
        priceChart.data.datasets[1].data = smaData;
        priceChart.data.datasets[2].data = bbData.upper;
        priceChart.data.datasets[3].data = bbData.lower;
        priceChart.data.datasets[4].label = `EMA (${emaVal})`;
        priceChart.data.datasets[4].data = emaData;
        priceChart.update();
    } else {
        initChart(originalDataset, smaData, bbData, emaData);
    }

    // Actualizar gráfico de RSI
    const rsiStatusBadge = document.getElementById('rsi-status-badge');
    rsiStatusBadge.textContent = `RSI (${rsiVal}): ${currentRSI.toFixed(2)}`;
    if (currentRSI > 70) {
        rsiStatusBadge.style.color = '#FF5252';
        rsiStatusBadge.style.backgroundColor = 'rgba(255, 82, 82, 0.1)';
        rsiStatusBadge.style.borderColor = 'rgba(255, 82, 82, 0.2)';
    } else if (currentRSI < 30) {
        rsiStatusBadge.style.color = '#00E676';
        rsiStatusBadge.style.backgroundColor = 'rgba(0, 230, 118, 0.1)';
        rsiStatusBadge.style.borderColor = 'rgba(0, 230, 118, 0.2)';
    } else {
        rsiStatusBadge.style.color = '#FFD600';
        rsiStatusBadge.style.backgroundColor = 'rgba(255, 214, 0, 0.05)';
        rsiStatusBadge.style.borderColor = 'rgba(255, 214, 0, 0.15)';
    }

    if (rsiChart) {
        rsiChart.data.labels = originalDataset.map(d => d.time);
        rsiChart.data.datasets[0].data = rsiData;
        rsiChart.data.datasets[1].data = new Array(originalDataset.length).fill(70);
        rsiChart.data.datasets[2].data = new Array(originalDataset.length).fill(30);
        rsiChart.update();
    } else {
        initRsiChart(originalDataset, rsiData);
    }

    // Actualizar gráfico de MACD
    const macdStatusBadge = document.getElementById('macd-status-badge');
    const lastHistVal = macdData.histogram[macdData.histogram.length - 1] || 0;
    macdStatusBadge.textContent = `Hist: ${lastHistVal.toFixed(2)}`;
    
    if (lastHistVal >= 0) {
        macdStatusBadge.style.color = '#00E676';
        macdStatusBadge.style.backgroundColor = 'rgba(0, 230, 118, 0.1)';
        macdStatusBadge.style.borderColor = 'rgba(0, 230, 118, 0.2)';
    } else {
        macdStatusBadge.style.color = '#FF5252';
        macdStatusBadge.style.backgroundColor = 'rgba(255, 82, 82, 0.1)';
        macdStatusBadge.style.borderColor = 'rgba(255, 82, 82, 0.2)';
    }

    if (macdChart) {
        macdChart.data.labels = originalDataset.map(d => d.time);
        macdChart.data.datasets[0].data = macdData.macdLine;
        macdChart.data.datasets[1].data = macdData.signalLine;
        macdChart.data.datasets[2].data = macdData.histogram;
        macdChart.data.datasets[2].backgroundColor = macdData.histogram.map(val => val >= 0 ? 'rgba(0, 230, 118, 0.4)' : 'rgba(255, 82, 82, 0.4)');
        macdChart.data.datasets[2].borderColor = macdData.histogram.map(val => val >= 0 ? '#00E676' : '#FF5252');
        macdChart.update();
    } else {
        initMacdChart(originalDataset, macdData.macdLine, macdData.signalLine, macdData.histogram);
    }
}

// --- Carga asíncrona ---
let updateIntervalId;
const offlineWarningEl = document.getElementById('offline-warning');

function showOfflineWarning(show) {
    if (show) {
        offlineWarningEl.classList.remove('hidden');
    } else {
        offlineWarningEl.classList.add('hidden');
    }
}

async function startApp() {
    originalDataset = await fetchBinanceData(currentSymbol);
    if (!originalDataset || originalDataset.length === 0) {
        originalDataset = generateSimulatedData(100);
        showOfflineWarning(true);
    } else {
        showOfflineWarning(false);
    }
    updateUI();
    startUpdateInterval();
}

function startUpdateInterval() {
    if (updateIntervalId) clearInterval(updateIntervalId);
    
    updateIntervalId = setInterval(async () => {
        const freshData = await fetchBinanceData(currentSymbol);
        if (freshData && freshData.length > 0) {
            originalDataset = freshData;
            showOfflineWarning(false);
            updateUI();
        } else {
            showOfflineWarning(true);
        }
    }, 30000);
}

async function changeAsset(symbol) {
    symbol = symbol.toUpperCase().trim();
    if (!symbol) return;
    
    currentPriceEl.textContent = "Cargando...";
    
    const freshData = await fetchBinanceData(symbol);
    if (freshData && freshData.length > 0) {
        currentSymbol = symbol;
        originalDataset = freshData;
        showOfflineWarning(false);
        updateUI();
        startUpdateInterval();
    } else {
        alert(`Error de conexión: No se pudieron obtener datos reales de Binance para "${symbol}". Comprueba que el par sea correcto (ej. ETHUSDT) o tu conexión a internet.`);
        updateUI();
    }
}

// --- Event Listeners ---
smaSlider.addEventListener('input', updateUI);
rsiSlider.addEventListener('input', updateUI);
bbSlider.addEventListener('input', updateUI);
emaSlider.addEventListener('input', updateUI);
macdFastSlider.addEventListener('input', updateUI);
macdSlowSlider.addEventListener('input', updateUI);

btnCalculate.addEventListener('click', () => {
    updateUI();
    if (tg) tg.HapticFeedback.notificationOccurred('success');
    alert("¡Indicadores recalculados con Polars-Talis y datos reales de Binance!");
});

// Integración para compartir datos en Telegram
btnSendAlert.addEventListener('click', () => {
    const currentPrice = currentPriceEl.textContent;
    const rsi = rsiValueEl.textContent;
    const trend = trendStatusEl.textContent;

    const dataToSend = {
        symbol: currentSymbol,
        price: currentPrice,
        rsi: rsi,
        trend: trend,
        timestamp: new Date().toISOString()
    };

    if (tg) {
        tg.sendData(JSON.stringify(dataToSend));
    } else {
        console.log("Alerta enviada:", dataToSend);
        alert("Alerta de Mercado (Consola): \n" + JSON.stringify(dataToSend, null, 2));
    }
});

// Cambiar temporalidad (Simulado recreando consulta)
document.getElementById('btn-1d').addEventListener('click', async (e) => {
    document.querySelectorAll('.btn-time').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    const freshData = await fetchBinanceData(currentSymbol);
    if (freshData && freshData.length > 0) {
        originalDataset = freshData;
        showOfflineWarning(false);
    } else {
        showOfflineWarning(true);
    }
    updateUI();
});

// Listeners de Selección de Activos
const assetSelect = document.getElementById('asset-select');
const customSymbolWrapper = document.getElementById('custom-symbol-wrapper');
const customSymbolInput = document.getElementById('custom-symbol-input');
const btnSearchSymbol = document.getElementById('btn-search-symbol');

assetSelect.addEventListener('change', (e) => {
    const val = e.target.value;
    if (val === 'CUSTOM') {
        customSymbolWrapper.classList.remove('hidden');
    } else {
        customSymbolWrapper.classList.add('hidden');
        changeAsset(val);
    }
});

btnSearchSymbol.addEventListener('click', () => {
    const val = customSymbolInput.value;
    if (val) {
        changeAsset(val);
    } else {
        alert("Por favor introduce un símbolo (ej. DOGEUSDT)");
    }
});

customSymbolInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const val = customSymbolInput.value;
        if (val) {
            changeAsset(val);
        } else {
            alert("Por favor introduce un símbolo (ej. DOGEUSDT)");
        }
    }
});

// Inicializar la App
startApp();
