/**
 * Real-Time Chart Module
 */
class LiveChart {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.dataPoints = [];
        this.openPrice = 0;

        this.colors = {
            background: '#111827',
            grid: 'rgba(75, 85, 99, 0.3)',
            openLine: '#f59e0b',
            priceUp: '#10b981',
            priceDown: '#ef4444',
            text: '#9ca3af',
            ma: '#8b5cf6',
            bbUpper: 'rgba(59, 130, 246, 0.8)',
            bbLower: 'rgba(59, 130, 246, 0.8)',
            bbFill: 'rgba(59, 130, 246, 0.1)'
        };

        this.padding = { top: 60, right: 90, bottom: 10, left: 10 };

        this.resizeObserver = new ResizeObserver(() => this.resize());
        this.resizeObserver.observe(this.canvas.parentElement);
        this.resize();
    }

    getOverlaySettings() {
        const showMA = document.getElementById('showMA')?.checked ?? true;
        const showBB = document.getElementById('showBB')?.checked ?? true;
        const bbStdDev = parseInt(document.getElementById('bbStdDev')?.value) || 2;
        return { showMA, showBB, bbStdDev };
    }

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.ctx.scale(dpr, dpr);
        this.width = rect.width;
        this.height = rect.height;
        this.chartWidth = this.width - this.padding.left - this.padding.right;
        this.chartHeight = this.height - this.padding.top - this.padding.bottom;
        this.render();
    }

    update(priceHistory, openPrice) {
        this.dataPoints = priceHistory;
        this.openPrice = openPrice;
        this.render();
    }

    render() {
        if (!this.ctx) return;
        this.ctx.fillStyle = this.colors.background;
        this.ctx.fillRect(0, 0, this.width, this.height);

        if (this.dataPoints.length === 0) {
            this.ctx.fillStyle = this.colors.text;
            this.ctx.font = '16px Inter, sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('Waiting for live data...', this.width / 2, this.height / 2);
            return;
        }

        // SHRINK TO FIT with OPEN as CENTER MIDLINE
        const prices = this.dataPoints.map(p => p.price);
        const openPrice = this.openPrice > 0 ? this.openPrice : prices[0];

        // Calculate max deviation from open price (either direction)
        let maxDeviation = 0;
        for (const price of prices) {
            const deviation = Math.abs(price - openPrice);
            if (deviation > maxDeviation) maxDeviation = deviation;
        }

        // Add padding to deviation (min $30 for visibility)
        maxDeviation = Math.max(maxDeviation * 1.3, 30);

        // Set symmetric range around open price (open is always center)
        const minPrice = openPrice - maxDeviation;
        const maxPrice = openPrice + maxDeviation;

        // Get overlay settings
        const overlays = this.getOverlaySettings();

        // Draw layers in order
        this.drawGrid(minPrice, maxPrice);

        // Draw Bollinger Bands (behind price line)
        if (overlays.showBB && this.dataPoints.length >= 5) {
            this.drawBollingerBands(minPrice, maxPrice, overlays.bbStdDev);
        }

        // Draw Moving Average
        if (overlays.showMA && this.dataPoints.length >= 3) {
            this.drawMovingAverage(minPrice, maxPrice);
        }

        this.drawOpenLine(minPrice, maxPrice);
        this.drawPriceLine(minPrice, maxPrice);
        this.drawCurrentPrice(minPrice, maxPrice);
        this.updateAxes(minPrice, maxPrice);
    }

    /**
     * Calculate rolling MA and standard deviation at each point
     * Returns arrays of {x, ma, upper, lower} for each point
     */
    calculateRollingStats(period, stdDevMultiplier) {
        const prices = this.dataPoints.map(p => p.price);
        const result = [];

        for (let i = 0; i < prices.length; i++) {
            // Use all points up to current point (cumulative)
            // Or use last 'period' points if we have enough
            const start = Math.max(0, i - period + 1);
            const window = prices.slice(start, i + 1);

            if (window.length < 3) continue; // Need at least 3 points

            // Calculate mean
            const mean = window.reduce((a, b) => a + b, 0) / window.length;

            // Calculate std dev
            const variance = window.reduce((sum, p) => sum + Math.pow(p - mean, 2), 0) / window.length;
            const stdDev = Math.sqrt(variance);

            result.push({
                idx: i,
                elapsed: this.dataPoints[i].elapsed,
                ma: mean,
                upper: mean + (stdDev * stdDevMultiplier),
                lower: mean - (stdDev * stdDevMultiplier)
            });
        }

        return result;
    }

    /**
     * Draw Bollinger Bands as dynamic curved lines
     */
    drawBollingerBands(minPrice, maxPrice, stdDevMultiplier) {
        const ctx = this.ctx;
        const period = 20; // Rolling period (20 points = ~20 seconds)
        const stats = this.calculateRollingStats(period, stdDevMultiplier);

        if (stats.length < 2) return;

        // Draw fill between bands
        ctx.fillStyle = this.colors.bbFill;
        ctx.beginPath();

        // Upper line (left to right)
        for (let i = 0; i < stats.length; i++) {
            const x = this.elapsedToX(stats[i].elapsed);
            const y = this.priceToY(stats[i].upper, minPrice, maxPrice);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }

        // Lower line (right to left) to close the shape
        for (let i = stats.length - 1; i >= 0; i--) {
            const x = this.elapsedToX(stats[i].elapsed);
            const y = this.priceToY(stats[i].lower, minPrice, maxPrice);
            ctx.lineTo(x, y);
        }

        ctx.closePath();
        ctx.fill();

        // Draw upper band line
        ctx.strokeStyle = this.colors.bbUpper;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 2]);
        ctx.beginPath();
        for (let i = 0; i < stats.length; i++) {
            const x = this.elapsedToX(stats[i].elapsed);
            const y = this.priceToY(stats[i].upper, minPrice, maxPrice);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Draw lower band line
        ctx.strokeStyle = this.colors.bbLower;
        ctx.beginPath();
        for (let i = 0; i < stats.length; i++) {
            const x = this.elapsedToX(stats[i].elapsed);
            const y = this.priceToY(stats[i].lower, minPrice, maxPrice);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // Label at the end
        if (stats.length > 0) {
            const last = stats[stats.length - 1];
            const endX = this.elapsedToX(last.elapsed);
            ctx.fillStyle = this.colors.bbUpper;
            ctx.font = '10px Inter';
            ctx.textAlign = 'left';
            ctx.fillText(`+${stdDevMultiplier}σ`, endX + 5, this.priceToY(last.upper, minPrice, maxPrice) + 4);
            ctx.fillText(`-${stdDevMultiplier}σ`, endX + 5, this.priceToY(last.lower, minPrice, maxPrice) + 4);
        }
    }

    /**
     * Draw Moving Average as a dynamic curved line
     */
    drawMovingAverage(minPrice, maxPrice) {
        const ctx = this.ctx;
        const period = 20; // Rolling period
        const stats = this.calculateRollingStats(period, 0);

        if (stats.length < 2) return;

        ctx.strokeStyle = this.colors.ma;
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        ctx.lineJoin = 'round';
        ctx.beginPath();

        for (let i = 0; i < stats.length; i++) {
            const x = this.elapsedToX(stats[i].elapsed);
            const y = this.priceToY(stats[i].ma, minPrice, maxPrice);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Label at the end
        if (stats.length > 0) {
            const last = stats[stats.length - 1];
            ctx.fillStyle = this.colors.ma;
            ctx.font = 'bold 10px Inter';
            ctx.textAlign = 'left';
            ctx.fillText('MA', this.elapsedToX(last.elapsed) + 5, this.priceToY(last.ma, minPrice, maxPrice) + 4);
        }
    }


    drawGrid(minPrice, maxPrice) {
        const ctx = this.ctx;
        ctx.strokeStyle = this.colors.grid;
        ctx.lineWidth = 1;

        for (let i = 0; i <= 8; i++) {
            const y = this.priceToY(minPrice + ((maxPrice - minPrice) / 8) * i, minPrice, maxPrice);
            ctx.beginPath();
            ctx.moveTo(this.padding.left, y);
            ctx.lineTo(this.width - this.padding.right, y);
            ctx.stroke();
        }

        for (let min = 0; min <= 15; min += 3) {
            const x = this.elapsedToX(min * 60);
            ctx.beginPath();
            ctx.setLineDash([4, 4]);
            ctx.moveTo(x, this.padding.top);
            ctx.lineTo(x, this.height - this.padding.bottom);
            ctx.stroke();
        }
        ctx.setLineDash([]);
    }

    drawOpenLine(minPrice, maxPrice) {
        if (this.openPrice === 0) return;
        const ctx = this.ctx;
        const y = this.priceToY(this.openPrice, minPrice, maxPrice);
        ctx.strokeStyle = this.colors.openLine;
        ctx.lineWidth = 2;
        ctx.setLineDash([8, 4]);
        ctx.beginPath();
        ctx.moveTo(this.padding.left, y);
        ctx.lineTo(this.width - this.padding.right, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = this.colors.openLine;
        ctx.font = 'bold 11px Inter';
        ctx.textAlign = 'left';
        ctx.fillText('OPEN', this.padding.left + 5, y - 5);
    }

    drawPriceLine(minPrice, maxPrice) {
        if (this.dataPoints.length < 2) return;
        const ctx = this.ctx;
        const lastPrice = this.dataPoints[this.dataPoints.length - 1].price;
        const isUp = lastPrice >= this.openPrice;

        ctx.strokeStyle = isUp ? this.colors.priceUp : this.colors.priceDown;
        ctx.lineWidth = 2.5;
        ctx.lineJoin = 'round';
        ctx.beginPath();

        for (let i = 0; i < this.dataPoints.length; i++) {
            const x = this.elapsedToX(this.dataPoints[i].elapsed);
            const y = this.priceToY(this.dataPoints[i].price, minPrice, maxPrice);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();

        const lastX = this.elapsedToX(this.dataPoints[this.dataPoints.length - 1].elapsed);
        const firstX = this.elapsedToX(this.dataPoints[0].elapsed);
        const openY = this.priceToY(this.openPrice, minPrice, maxPrice);
        ctx.lineTo(lastX, openY);
        ctx.lineTo(firstX, openY);
        ctx.closePath();
        ctx.fillStyle = isUp ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)';
        ctx.fill();
    }

    drawCurrentPrice(minPrice, maxPrice) {
        if (this.dataPoints.length === 0) return;
        const ctx = this.ctx;
        const p = this.dataPoints[this.dataPoints.length - 1];
        const x = this.elapsedToX(p.elapsed);
        const y = this.priceToY(p.price, minPrice, maxPrice);
        const isUp = p.price >= this.openPrice;
        const color = isUp ? this.colors.priceUp : this.colors.priceDown;

        ctx.beginPath();
        ctx.arc(x, y, 12, 0, Math.PI * 2);
        ctx.fillStyle = isUp ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        ctx.fillStyle = color;
        ctx.font = 'bold 12px Inter';
        ctx.textAlign = 'left';
        ctx.fillText('$' + p.price.toLocaleString(undefined, { minimumFractionDigits: 2 }), x + 15, y + 4);
    }

    updateAxes(minPrice, maxPrice) {
        const priceAxis = document.getElementById('priceAxis');
        if (priceAxis) {
            let html = '';
            for (let i = 6; i >= 0; i--) {
                const price = minPrice + ((maxPrice - minPrice) / 6) * i;
                html += `<span>$${price.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>`;
            }
            priceAxis.innerHTML = html;
        }

        const timeAxis = document.getElementById('timeAxis');
        if (timeAxis) {
            let html = '';
            for (let min = 0; min <= 15; min += 3) html += `<span>${min}:00</span>`;
            timeAxis.innerHTML = html;
        }
    }

    elapsedToX(elapsed) {
        return this.padding.left + ((elapsed / 900) * this.chartWidth);
    }

    priceToY(price, minPrice, maxPrice) {
        return this.height - this.padding.bottom - (((price - minPrice) / (maxPrice - minPrice)) * this.chartHeight);
    }

    clear() {
        this.dataPoints = [];
        this.openPrice = 0;
        this.render();
    }
}

window.LiveChart = LiveChart;
