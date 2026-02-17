/**
 * Main Application Controller
 * Orchestrates live data fetching and UI updates
 */
class App {
    constructor() {
        this.dataFetcher = new LiveDataFetcher();
        this.chart = new LiveChart('priceChart');

        this.previousUpPrice = 0.50;
        this.previousDownPrice = 0.50;
        this.recentTicks = [];
        this.maxRecentTicks = 20;

        this.bindOverlayEvents();
        this.startClock();
        this.start();
    }

    bindOverlayEvents() {
        // Re-render chart when overlay settings change
        const rerenderChart = () => this.chart.render();

        document.getElementById('showMA')?.addEventListener('change', rerenderChart);
        document.getElementById('showBB')?.addEventListener('change', rerenderChart);
        document.getElementById('bbStdDev')?.addEventListener('change', rerenderChart);
    }

    start() {
        this.dataFetcher.start(
            (data) => this.onDataUpdate(data),
            (error) => this.onError(error),
            (url, start, end) => this.onNewWindow(url, start, end),
            (ranges) => this.onRangesUpdate(ranges)
        );
    }

    onRangesUpdate(ranges) {
        this.updateHistoricalRanges(ranges);
    }

    updateHistoricalRanges(ranges) {
        const formatPrice = (price) => {
            if (!price || price === 0 || price === Infinity) return '--';
            return '$' + price.toLocaleString(undefined, { maximumFractionDigits: 0 });
        };

        const formatSpread = (spread) => {
            if (!spread || spread === 0) return '--';
            return '$' + spread.toFixed(0);
        };

        // 15m
        document.getElementById('range15mHigh').textContent = formatPrice(ranges['15m']?.high);
        document.getElementById('range15mLow').textContent = formatPrice(ranges['15m']?.low);
        document.getElementById('range15mSpread').textContent = formatSpread(ranges['15m']?.spread);

        // 1h
        document.getElementById('range1hHigh').textContent = formatPrice(ranges['1h']?.high);
        document.getElementById('range1hLow').textContent = formatPrice(ranges['1h']?.low);
        document.getElementById('range1hSpread').textContent = formatSpread(ranges['1h']?.spread);

        // 6h
        document.getElementById('range6hHigh').textContent = formatPrice(ranges['6h']?.high);
        document.getElementById('range6hLow').textContent = formatPrice(ranges['6h']?.low);
        document.getElementById('range6hSpread').textContent = formatSpread(ranges['6h']?.spread);

        // 24h
        document.getElementById('range24hHigh').textContent = formatPrice(ranges['24h']?.high);
        document.getElementById('range24hLow').textContent = formatPrice(ranges['24h']?.low);
        document.getElementById('range24hSpread').textContent = formatSpread(ranges['24h']?.spread);

        // Last update
        if (ranges.lastUpdate) {
            document.getElementById('rangeLastUpdate').textContent =
                'Updated: ' + ranges.lastUpdate.toLocaleTimeString();
        }
    }

    startClock() {
        const updateClock = () => {
            const now = new Date();
            document.getElementById('currentTime').textContent = now.toLocaleTimeString();
        };
        updateClock();
        setInterval(updateClock, 1000);
    }

    onDataUpdate(data) {
        this.updateConnectionStatus(true, data.lastUpdate);
        this.updateWindowInfo(data.window);
        this.updateBTCStats(data.btc);
        this.updatePolymarketPrices(data.polymarket, data.leading);
        this.updateWinnerBanner(data);
        this.addRecentTick(data.btc.current, data.lastUpdate);
        if (data.signals) {
            this.updateSignals(data.signals);
        }
        this.chart.update(data.history, data.btc.open);
    }

    onError(error) {
        console.error('Data fetch error:', error);
        this.updateConnectionStatus(false);
    }

    updateSignals(signals) {
        // N-Pattern
        const nPattern = signals.n_pattern || 'WAIT';
        const el = document.getElementById('algo-n-pattern');
        if (el) {
            const stateEl = el.querySelector('.algo-state');

            // Reset classes
            el.classList.remove('active', 'invalid');

            if (nPattern === 'BET_UP_CONFIRMED') {
                el.classList.add('active');
                stateEl.textContent = 'BUY SIGNAL';
                stateEl.style.color = '#00ff88';
            } else if (nPattern === 'PATTERN_INVALID') {
                el.classList.add('invalid');
                stateEl.textContent = 'INVALID';
                stateEl.style.color = '#ff4444';
            } else {
                stateEl.textContent = 'WAITING';
                stateEl.style.color = '#888';
            }
        }
    }

    onNewWindow(url, startTs, endTs) {
        console.log('New window:', url);
        document.getElementById('polymarketLink').href = url;
        this.recentTicks = [];
        this.updateRecentTicks();
        this.chart.clear();
    }

    updateConnectionStatus(connected, lastUpdate) {
        const badge = document.getElementById('connectionStatus');
        const lastEl = document.getElementById('lastUpdate');

        if (connected) {
            badge.className = 'status-badge connected';
            badge.textContent = '● Connected';
            if (lastUpdate) {
                lastEl.textContent = 'Last: ' + lastUpdate.toLocaleTimeString();
            }
        } else {
            badge.className = 'status-badge disconnected';
            badge.textContent = '● Disconnected';
        }
    }

    updateWindowInfo(window) {
        const startTime = new Date(window.start * 1000);
        const endTime = new Date(window.end * 1000);

        document.getElementById('windowStart').textContent = startTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        document.getElementById('windowEnd').textContent = endTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        const remaining = Math.max(0, window.remaining);
        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        const countdownEl = document.getElementById('countdown');
        countdownEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
        countdownEl.className = remaining < 60 ? 'countdown warning' : 'countdown';

        const elapsedMins = Math.floor(window.elapsed / 60);
        const elapsedSecs = window.elapsed % 60;
        document.getElementById('elapsedTime').textContent = `${elapsedMins}:${elapsedSecs.toString().padStart(2, '0')}`;
        document.getElementById('pointCount').textContent = this.dataFetcher.priceHistory.length;
    }

    updateBTCStats(btc) {
        document.getElementById('btcOpen').textContent = '$' + btc.open.toLocaleString(undefined, { minimumFractionDigits: 2 });
        document.getElementById('btcCurrent').textContent = '$' + btc.current.toLocaleString(undefined, { minimumFractionDigits: 2 });
        document.getElementById('btcHigh').textContent = '$' + btc.high.toLocaleString(undefined, { minimumFractionDigits: 2 });
        document.getElementById('btcLow').textContent = '$' + btc.low.toLocaleString(undefined, { minimumFractionDigits: 2 });

        const driftEl = document.getElementById('btcDrift');
        driftEl.textContent = btc.driftPct;
        driftEl.style.color = btc.current >= btc.open ? '#10b981' : '#ef4444';

        document.getElementById('btcSource').textContent = btc.source;
    }

    updatePolymarketPrices(poly, leading) {
        const upEl = document.getElementById('upPrice');
        const downEl = document.getElementById('downPrice');
        const upCard = document.getElementById('upPriceCard');
        const downCard = document.getElementById('downPriceCard');
        const upChange = document.getElementById('upChange');
        const downChange = document.getElementById('downChange');
        const badge = document.getElementById('priceSourceBadge');

        // Update source badge
        if (poly.source === 'LIVE') {
            badge.textContent = 'LIVE';
            badge.className = 'price-source-badge live';
        } else if (poly.source === 'OFFLINE') {
            badge.textContent = 'OFFLINE';
            badge.className = 'price-source-badge offline';
        } else {
            badge.textContent = poly.source || 'LOADING';
            badge.className = 'price-source-badge loading';
        }

        // Only show prices if we have valid data
        if (poly.source === 'LIVE' && poly.up > 0) {
            upEl.textContent = '$' + poly.up.toFixed(2);
            downEl.textContent = '$' + poly.down.toFixed(2);

            upCard.classList.toggle('leading', leading === 'UP');
            downCard.classList.toggle('leading', leading === 'DOWN');

            if (this.previousUpPrice > 0) {
                const upDiff = poly.up - this.previousUpPrice;
                if (Math.abs(upDiff) > 0.001) {
                    upChange.textContent = (upDiff > 0 ? '+' : '') + upDiff.toFixed(3);
                    upChange.style.color = upDiff > 0 ? '#10b981' : '#ef4444';
                }
            }

            if (this.previousDownPrice > 0) {
                const downDiff = poly.down - this.previousDownPrice;
                if (Math.abs(downDiff) > 0.001) {
                    downChange.textContent = (downDiff > 0 ? '+' : '') + downDiff.toFixed(3);
                    downChange.style.color = downDiff > 0 ? '#10b981' : '#ef4444';
                }
            }

            this.previousUpPrice = poly.up;
            this.previousDownPrice = poly.down;
        } else {
            // Offline - show dashes
            upEl.textContent = '--';
            downEl.textContent = '--';
            upChange.textContent = 'Run price_server.py';
            downChange.textContent = '';
            upChange.style.color = '#f59e0b';
        }
    }

    updateWinnerBanner(data) {
        const sideEl = document.getElementById('winnerSide');
        sideEl.textContent = data.leading;
        sideEl.className = 'winner-side ' + data.leading.toLowerCase();

        document.getElementById('openPrice').textContent = '$' + data.btc.open.toLocaleString(undefined, { minimumFractionDigits: 2 });
        document.getElementById('currentPrice').textContent = '$' + data.btc.current.toLocaleString(undefined, { minimumFractionDigits: 2 });
        document.getElementById('driftPct').textContent = data.btc.driftPct;
    }

    addRecentTick(price, time) {
        const prevPrice = this.recentTicks.length > 0 ? this.recentTicks[0].price : price;
        const change = price - prevPrice;

        this.recentTicks.unshift({ price, time, change });
        if (this.recentTicks.length > this.maxRecentTicks) {
            this.recentTicks.pop();
        }

        this.updateRecentTicks();
    }

    updateRecentTicks() {
        const container = document.getElementById('priceHistory');

        if (this.recentTicks.length === 0) {
            container.innerHTML = '<div class="history-empty">Waiting for data...</div>';
            return;
        }

        let html = '';
        for (const tick of this.recentTicks) {
            const changeClass = tick.change > 0 ? 'up' : tick.change < 0 ? 'down' : 'neutral';
            const changeText = tick.change === 0 ? '0.00' : (tick.change > 0 ? '+' : '') + tick.change.toFixed(2);

            html += `
                <div class="history-item">
                    <span class="history-time">${tick.time.toLocaleTimeString()}</span>
                    <span class="history-price">$${tick.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    <span class="history-change ${changeClass}">${changeText}</span>
                </div>
            `;
        }

        container.innerHTML = html;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
