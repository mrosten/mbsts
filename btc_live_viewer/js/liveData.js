/**
 * Live Data Module
 * Fetches real-time BTC and Polymarket prices
 */

class LiveDataFetcher {
    constructor() {
        // State
        this.isRunning = false;
        this.intervalId = null;
        this.rangesIntervalId = null;
        this.updateInterval = 1000; // 1 second
        this.rangesUpdateInterval = 30000; // 30 seconds for historical data

        // Market Data
        this.marketData = {
            btcPrice: 0,
            btcOpen: 0,
            btcHigh: 0,
            btcLow: Infinity,
            upPrice: 0.50,
            downPrice: 0.50,
            upId: null,
            downId: null,
            windowStart: 0,
            windowEnd: 0,
            lastUpdate: null,
            source: 'Binance'
        };

        // Historical Ranges
        this.historicalRanges = {
            '15m': { high: 0, low: 0, spread: 0 },
            '1h': { high: 0, low: 0, spread: 0 },
            '6h': { high: 0, low: 0, spread: 0 },
            '24h': { high: 0, low: 0, spread: 0 },
            lastUpdate: null
        };

        // Price History (for chart)
        this.priceHistory = [];
        this.maxHistoryPoints = 900; // 15 minutes at 1 point/second

        // Callbacks
        this.onUpdate = null;
        this.onError = null;
        this.onNewWindow = null;
        this.onRangesUpdate = null;

        // Polymarket market URL
        this.currentMarketUrl = '';
    }

    /**
     * Start fetching live data
     */
    start(onUpdate, onError, onNewWindow, onRangesUpdate) {
        if (this.isRunning) return;

        this.isRunning = true;
        this.onUpdate = onUpdate;
        this.onError = onError;
        this.onNewWindow = onNewWindow;
        this.onRangesUpdate = onRangesUpdate;

        // Initial fetch
        this.tick();
        this.fetchHistoricalRanges();
        this.fetchServerHistory(); // Fetch any existing point in current window

        // Start intervals
        this.intervalId = setInterval(() => this.tick(), this.updateInterval);
        this.rangesIntervalId = setInterval(() => this.fetchHistoricalRanges(), this.rangesUpdateInterval);

        // Sync when coming back to tab
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                console.log('Tab visible - syncing history...');
                this.fetchServerHistory();
            }
        });

        console.log('LiveDataFetcher started');
    }

    /**
     * Stop fetching
     */
    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        if (this.rangesIntervalId) {
            clearInterval(this.rangesIntervalId);
            this.rangesIntervalId = null;
        }
        this.isRunning = false;
        console.log('LiveDataFetcher stopped');
    }

    /**
     * Main tick - fetch all data (non-blocking)
     */
    async tick() {
        try {
            // Calculate current 15-minute window
            const now = new Date();
            const min15 = Math.floor(now.getMinutes() / 15) * 15;
            const windowStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(),
                now.getHours(), min15, 0, 0);
            const windowStartTs = Math.floor(windowStart.getTime() / 1000);
            const windowEndTs = windowStartTs + 900;

            // Check for new window
            if (windowStartTs !== this.marketData.windowStart) {
                // New window started - reset immediately, don't wait for anything
                this.handleNewWindow(windowStartTs, windowEndTs);
            }

            // Fetch BTC price FIRST (fast, reliable)
            const btcPrice = await this.fetchBTCPrice();

            // Update BTC data immediately
            if (btcPrice > 0) {
                this.marketData.btcPrice = btcPrice;

                // Set open price if not set
                if (this.marketData.btcOpen === 0) {
                    // Try to get historical open, but with timeout
                    const histOpen = await this.fetchHistoricalOpen(windowStartTs * 1000);
                    this.marketData.btcOpen = histOpen > 0 ? histOpen : btcPrice;
                }

                // Update high/low
                if (btcPrice > this.marketData.btcHigh) {
                    this.marketData.btcHigh = btcPrice;
                }
                if (btcPrice < this.marketData.btcLow) {
                    this.marketData.btcLow = btcPrice;
                }

                // Add to history
                const elapsed = Math.floor((Date.now() / 1000) - windowStartTs);
                this.priceHistory.push({
                    time: now,
                    price: btcPrice,
                    elapsed: elapsed
                });

                // Trim history
                if (this.priceHistory.length > this.maxHistoryPoints) {
                    this.priceHistory = this.priceHistory.slice(-this.maxHistoryPoints);
                }
            }

            this.marketData.lastUpdate = now;

            // Update UI IMMEDIATELY with BTC data (use estimated poly prices as fallback)
            if (this.onUpdate) {
                this.onUpdate(this.getData());
            }

            // Fetch Polymarket in BACKGROUND (fire and forget, don't block)
            this.fetchPolymarketPricesBackground();

        } catch (error) {
            console.error('LiveDataFetcher tick error:', error);
            if (this.onError) {
                this.onError(error);
            }
        }
    }

    /**
     * Fetch full price history from server (to fill gaps)
     */
    async fetchServerHistory() {
        try {
            const response = await this.fetchWithTimeout('/api/history', 3000);
            if (response.ok) {
                const data = await response.json();

                // Update history if available (ignoring timestamp mismatches to be robust)
                if (data.history && data.history.length > 0) {
                    // Map server history to client format
                    this.priceHistory = data.history.map(item => ({
                        time: new Date(item.timestamp * 1000),
                        price: item.price,
                        elapsed: item.elapsed
                    }));
                    console.log(`Synced ${this.priceHistory.length} points from server`);

                    // Update current values
                    if (this.marketData.btcOpen === 0 && data.history.length > 0) {
                        this.marketData.btcOpen = data.history[0].price;
                    }

                    // Force UI update immediately to show filled chart
                    if (this.onUpdate) {
                        this.onUpdate(this.getData());
                    }
                }
            }
        } catch (e) {
            console.log('Failed to fetch server history');
        }
    }

    /**
     * Fetch Polymarket prices in background (non-blocking)
     */
    fetchPolymarketPricesBackground() {
        // Don't await - let it run in background
        this.fetchPolymarketPrices().then(polyPrices => {
            if (polyPrices) {
                this.marketData.upPrice = polyPrices.up;
                this.marketData.downPrice = polyPrices.down;
                this.marketData.polySource = polyPrices.source;
                this.marketData.signals = polyPrices.signals || {};
                // Trigger another UI update with real prices
                if (this.onUpdate) {
                    this.onUpdate(this.getData());
                }
            }
        }).catch(e => {
            // Silent fail - we have estimated prices as fallback
            console.log('Polymarket background fetch failed, using estimates');
        });
    }

    /**
     * Handle new 15-minute window
     */
    handleNewWindow(windowStartTs, windowEndTs) {
        console.log('New 15-minute window:', new Date(windowStartTs * 1000).toLocaleTimeString());

        // Reset data
        this.marketData.windowStart = windowStartTs;
        this.marketData.windowEnd = windowEndTs;
        this.marketData.btcOpen = 0;
        this.marketData.btcHigh = 0;
        this.marketData.btcLow = Infinity;
        this.marketData.upId = null;
        this.marketData.downId = null;
        this.priceHistory = [];

        // Generate new Polymarket URL
        this.currentMarketUrl = `https://polymarket.com/event/btc-updown-15m-${windowStartTs}`;

        // Callback
        if (this.onNewWindow) {
            this.onNewWindow(this.currentMarketUrl, windowStartTs, windowEndTs);
        }
    }

    /**
     * Fetch with timeout wrapper
     */
    async fetchWithTimeout(url, timeoutMs = 2000) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const response = await fetch(url, { signal: controller.signal });
            clearTimeout(timeout);
            return response;
        } catch (e) {
            clearTimeout(timeout);
            throw e;
        }
    }

    /**
     * Fetch BTC price from Binance (with timeout)
     */
    async fetchBTCPrice() {
        try {
            const response = await this.fetchWithTimeout('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT', 2000);
            if (!response.ok) throw new Error('Binance API error');

            const data = await response.json();
            this.marketData.source = 'Binance';
            return parseFloat(data.price);
        } catch (e) {
            // Fallback to Coinbase
            try {
                const response = await this.fetchWithTimeout('https://api.coinbase.com/v2/prices/BTC-USD/spot', 2000);
                if (!response.ok) throw new Error('Coinbase API error');

                const data = await response.json();
                this.marketData.source = 'Coinbase';
                return parseFloat(data.data.amount);
            } catch (e2) {
                console.error('All BTC price sources failed');
                return 0;
            }
        }
    }

    /**
     * Fetch historical open price from Binance
     */
    async fetchHistoricalOpen(timestampMs) {
        try {
            const url = `https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=${timestampMs}&limit=1`;
            const response = await fetch(url);
            if (!response.ok) return 0;

            const data = await response.json();
            if (data && data.length > 0) {
                return parseFloat(data[0][1]); // Open price
            }
        } catch (e) {
            console.error('Historical open fetch failed:', e);
        }
        return 0;
    }

    /**
     * Fetch Polymarket prices from local price server
     * The price_server.py runs on localhost:8082 and fetches real Polymarket prices
     */
    async fetchPolymarketPrices() {
        try {
            const response = await this.fetchWithTimeout('/api/prices', 2000);

            if (response.ok) {
                const data = await response.json();

                if (data.source === 'polymarket') {
                    console.log('Polymarket LIVE prices:', data.up, data.down);
                    return {
                        up: data.up,
                        down: data.down,
                        source: 'LIVE',
                        signals: data.signals
                    };
                } else {
                    console.log('Price server status:', data.source);
                    return {
                        up: data.up || 0.50,
                        down: data.down || 0.50,
                        source: data.source || 'LOADING',
                        signals: data.signals || {}
                    };
                }
            }
        } catch (e) {
            console.log('Price server not available - make sure price_server.py is running');
        }

        // Return null to indicate no data available
        return {
            up: 0,
            down: 0,
            source: 'OFFLINE'
        };
    }

    /**
     * Estimate Polymarket prices based on BTC price drift and time remaining
     * This is a fallback when API calls fail
     * 
     * The model considers:
     * - Drift amount (larger drift = higher confidence)
     * - Time remaining (less time = prices converge toward 1.00/0.00)
     */
    estimatePricesFromDrift() {
        const btcOpen = this.marketData.btcOpen;
        const btcCurrent = this.marketData.btcPrice;
        const windowEnd = this.marketData.windowEnd;
        const now = Math.floor(Date.now() / 1000);
        const remaining = Math.max(0, windowEnd - now);
        const elapsed = 900 - remaining;

        if (btcOpen === 0 || btcCurrent === 0) {
            return { up: 0.50, down: 0.50, source: 'ESTIMATED' };
        }

        // Calculate drift percentage
        const driftPct = (btcCurrent - btcOpen) / btcOpen;
        const absDrift = Math.abs(driftPct);

        // Time factor: as time runs out, prices converge toward certainty
        // At 0 min elapsed: timeFactor = 0.3 (more uncertain)
        // At 15 min elapsed: timeFactor = 1.0 (maximum confidence)
        const timeFactor = 0.3 + (elapsed / 900) * 0.7;

        // Drift sensitivity increases with time
        // Early: small drifts don't matter much
        // Late: even small drifts drive prices toward 1.00
        const baseSensitivity = 150;
        const sensitivity = baseSensitivity * timeFactor;

        // Calculate base probability using sigmoid-like function
        let upProb = 0.5 + (Math.tanh(driftPct * sensitivity) * 0.49);

        // In final minutes, if drift is clearly one direction, push toward 1.00
        if (remaining < 180) { // Last 3 minutes
            const finalPush = (180 - remaining) / 180; // 0 to 1
            if (driftPct > 0.0005) { // Up more than 0.05%
                upProb = upProb + (1 - upProb) * finalPush * 0.5;
            } else if (driftPct < -0.0005) { // Down more than 0.05%
                upProb = upProb * (1 - finalPush * 0.5);
            }
        }

        const downProb = 1 - upProb;

        return {
            up: Math.max(0.01, Math.min(0.99, upProb)),
            down: Math.max(0.01, Math.min(0.99, downProb)),
            source: 'ESTIMATED'
        };
    }

    /**
     * Fetch market token IDs from Polymarket via CORS proxy (with timeout)
     */
    async fetchMarketTokenIds() {
        try {
            // Extract slug from URL
            const slug = this.currentMarketUrl.split('/').pop().split('?')[0];
            const apiUrl = `https://gamma-api.polymarket.com/markets/slug/${slug}`;
            const proxyUrl = `https://api.allorigins.win/raw?url=${encodeURIComponent(apiUrl)}`;

            console.log('Fetching Polymarket market:', slug);

            const response = await this.fetchWithTimeout(proxyUrl, 3000);
            if (!response.ok) {
                console.log('Polymarket API returned:', response.status);
                return;
            }

            const data = await response.json();
            console.log('Polymarket market data:', data);

            if (data.clobTokenIds) {
                let ids = data.clobTokenIds;
                if (typeof ids === 'string') {
                    ids = JSON.parse(ids);
                }

                if (ids.length >= 2) {
                    // Default assignment
                    this.marketData.upId = ids[0];
                    this.marketData.downId = ids[1];

                    // Try to map by outcome name
                    if (data.outcomes) {
                        let outcomes = data.outcomes;
                        if (typeof outcomes === 'string') {
                            outcomes = JSON.parse(outcomes);
                        }

                        for (let i = 0; i < outcomes.length; i++) {
                            const name = outcomes[i];
                            if (name.includes('Up') || name.includes('Yes')) {
                                this.marketData.upId = ids[i];
                            } else if (name.includes('Down') || name.includes('No')) {
                                this.marketData.downId = ids[i];
                            }
                        }
                    }

                    console.log('Polymarket token IDs loaded:', this.marketData.upId, this.marketData.downId);
                }
            }
        } catch (e) {
            console.error('Failed to fetch market token IDs:', e);
        }
    }

    /**
     * Get current data snapshot
     */
    getData() {
        const btcOpen = this.marketData.btcOpen;
        const btcCurrent = this.marketData.btcPrice;
        const drift = btcOpen > 0 ? Math.abs(btcCurrent - btcOpen) / btcOpen : 0;
        const leading = btcCurrent >= btcOpen ? 'UP' : 'DOWN';

        return {
            btc: {
                current: btcCurrent,
                open: btcOpen,
                high: this.marketData.btcHigh,
                low: this.marketData.btcLow === Infinity ? btcCurrent : this.marketData.btcLow,
                drift: drift,
                driftPct: (drift * 100).toFixed(4) + '%',
                source: this.marketData.source
            },
            polymarket: {
                up: this.marketData.upPrice,
                down: this.marketData.downPrice,
                source: this.marketData.polySource,
                url: this.currentMarketUrl
            },
            signals: this.marketData.signals || {},
            window: {
                start: this.marketData.windowStart,
                end: this.marketData.windowEnd,
                elapsed: Math.floor(Date.now() / 1000) - this.marketData.windowStart,
                remaining: this.marketData.windowEnd - Math.floor(Date.now() / 1000)
            },
            leading: leading,
            lastUpdate: this.marketData.lastUpdate,
            history: this.priceHistory
        };
    }

    /**
     * Get price history for chart
     */
    getPriceHistory() {
        return [...this.priceHistory];
    }

    /**
     * Fetch historical price ranges from Binance
     */
    async fetchHistoricalRanges() {
        try {
            // Fetch klines for different time periods
            const periods = [
                { key: '15m', interval: '1m', limit: 15 },
                { key: '1h', interval: '5m', limit: 12 },
                { key: '6h', interval: '15m', limit: 24 },
                { key: '24h', interval: '1h', limit: 24 }
            ];

            for (const period of periods) {
                try {
                    const url = `https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=${period.interval}&limit=${period.limit}`;
                    const response = await this.fetchWithTimeout(url, 3000);

                    if (response.ok) {
                        const data = await response.json();

                        if (data && data.length > 0) {
                            // Extract highs and lows from klines
                            // Kline format: [openTime, open, high, low, close, volume, ...]
                            let high = 0;
                            let low = Infinity;

                            for (const kline of data) {
                                const kHigh = parseFloat(kline[2]);
                                const kLow = parseFloat(kline[3]);
                                if (kHigh > high) high = kHigh;
                                if (kLow < low) low = kLow;
                            }

                            this.historicalRanges[period.key] = {
                                high: high,
                                low: low,
                                spread: high - low
                            };
                        }
                    }
                } catch (e) {
                    console.log(`Failed to fetch ${period.key} range:`, e.message);
                }
            }

            this.historicalRanges.lastUpdate = new Date();

            // Callback
            if (this.onRangesUpdate) {
                this.onRangesUpdate(this.historicalRanges);
            }

        } catch (e) {
            console.error('Historical ranges fetch error:', e);
        }
    }
}

// Export
window.LiveDataFetcher = LiveDataFetcher;
