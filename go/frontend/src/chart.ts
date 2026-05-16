import { createChart, IChartApi, ISeriesApi, AreaData, HistogramData, Time, CrosshairMode, AreaSeries, HistogramSeries } from 'lightweight-charts';
import { FetchChartData, GetTimeRanges, SetSetting, IsIntradayInterval, PrefetchHistory } from '../wailsjs/go/app/App';
import { DragCompare } from './drag-compare';

interface TimeRangeInfo {
    label: string;
    period: string;
    interval: string;
}

interface ChartDataResponse {
    timestamps: number[];
    open: (number | null)[];
    high: (number | null)[];
    low: (number | null)[];
    close: (number | null)[];
    volume: (number | null)[];
    meta: Record<string, any>;
}

export class ChartView {
    private container: HTMLElement;
    private chart: IChartApi | null = null;
    private areaSeries: ISeriesApi<'Area', Time> | null = null;
    private volumeSeries: ISeriesApi<'Histogram', Time> | null = null;
    private headerEl!: HTMLElement;
    private rangeBar!: HTMLElement;
    private chartContainer!: HTMLElement;
    private hoverLabel!: HTMLElement;

    private ticker: string = '';
    private currentRange: TimeRangeInfo | null = null;
    private ranges: TimeRangeInfo[] = [];
    private refreshInterval: number | null = null;
    private isUp: boolean = true;

    onInfoReceived: ((info: { ticker: string; name: string; exchange: string; currency: string }) => void) | null = null;
    onRangeChanged: ((period: string, interval: string) => void) | null = null;

    constructor(container: HTMLElement) {
        this.container = container;
    }

    async init() {
        this.ranges = await GetTimeRanges();
        this.render();
    }

    private render() {
        this.container.innerHTML = `
            <div class="chart-header" id="chart-header">
                <div class="chart-header-top">
                    <span class="chart-ticker"></span>
                    <span class="chart-company"></span>
                </div>
                <div class="chart-header-price">
                    <span class="chart-price-value"></span>
                    <span class="chart-price-change"></span>
                </div>
                <div class="chart-header-meta"></div>
            </div>
            <div class="chart-range-bar" id="chart-range-bar"></div>
            <div class="chart-hover-label" id="chart-hover-label"></div>
            <div class="chart-container" id="chart-container"></div>
        `;

        this.headerEl = this.container.querySelector('#chart-header')!;
        this.rangeBar = this.container.querySelector('#chart-range-bar')!;
        this.chartContainer = this.container.querySelector('#chart-container')!;
        this.hoverLabel = this.container.querySelector('#chart-hover-label')!;

        this.renderRangeBar();
        this.createChart();
    }

    private renderRangeBar() {
        this.rangeBar.innerHTML = '';
        for (const range of this.ranges) {
            const btn = document.createElement('button');
            btn.className = 'range-btn';
            btn.textContent = range.label;
            btn.dataset.label = range.label;
            btn.addEventListener('click', () => this.selectRange(range));
            this.rangeBar.appendChild(btn);
        }
    }

    private createChart() {
        this.chart = createChart(this.chartContainer, {
            layout: {
                background: { color: '#242424' },
                textColor: '#6b6b6b',
            },
            grid: {
                vertLines: { color: 'rgba(255,255,255,0.04)' },
                horzLines: { color: 'rgba(255,255,255,0.04)' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: { color: '#666', style: 2, width: 1 },
                horzLine: { color: '#666', style: 2, width: 1 },
            },
            rightPriceScale: {
                borderColor: 'rgba(255,255,255,0.08)',
            },
            timeScale: {
                borderColor: 'rgba(255,255,255,0.08)',
                timeVisible: true,
                secondsVisible: false,
            },
            handleScroll: { vertTouchDrag: false },
        });

        this.areaSeries = this.chart.addSeries(AreaSeries, {
            lineColor: '#4cd278',
            topColor: 'rgba(76, 210, 120, 0.3)',
            bottomColor: 'rgba(76, 210, 120, 0.02)',
            lineWidth: 2,
            crosshairMarkerVisible: true,
            crosshairMarkerRadius: 5,
        });

        this.volumeSeries = this.chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
        });

        this.chart.priceScale('volume').applyOptions({
            scaleMargins: { top: 0.85, bottom: 0 },
        });

        this.chart.subscribeCrosshairMove((param) => {
            if (!param.time || !param.point) {
                this.hoverLabel.textContent = '';
                return;
            }
            const price = param.seriesData.get(this.areaSeries!) as AreaData<Time> | undefined;
            if (price && 'value' in price) {
                const t = param.time as number;
                const date = new Date(t * 1000);
                const dateStr = this.formatDate(date);
                this.hoverLabel.textContent = `${dateStr}    ${price.value.toFixed(2)}`;
            }
        });

        const ro = new ResizeObserver(() => {
            if (this.chart) {
                this.chart.applyOptions({
                    width: this.chartContainer.clientWidth,
                    height: this.chartContainer.clientHeight,
                });
            }
        });
        ro.observe(this.chartContainer);

        new DragCompare(this.chart, this.areaSeries, this.chartContainer, this.hoverLabel);
    }

    async loadTicker(ticker: string, period?: string, interval?: string) {
        this.ticker = ticker;

        if (period && interval) {
            const range = this.ranges.find(r => r.period === period && r.interval === interval);
            if (range) {
                this.currentRange = range;
                this.highlightRange(range.label);
            }
        } else if (!this.currentRange && this.ranges.length > 0) {
            this.currentRange = this.ranges[2]; // Default to 1M
            this.highlightRange(this.currentRange.label);
        }

        if (this.currentRange) {
            await this.fetchAndRender();
        }
    }

    async selectRange(range: TimeRangeInfo) {
        this.currentRange = range;
        this.highlightRange(range.label);
        SetSetting('last_period', range.label);
        PrefetchHistory(range.period, range.interval);
        if (this.onRangeChanged) {
            this.onRangeChanged(range.period, range.interval);
        }
        await this.fetchAndRender();
    }

    selectRangeByIndex(index: number) {
        if (index >= 0 && index < this.ranges.length) {
            this.selectRange(this.ranges[index]);
        }
    }

    stepRange(direction: number) {
        if (!this.currentRange) return;
        const idx = this.ranges.findIndex(r => r.label === this.currentRange!.label);
        const newIdx = idx + direction;
        if (newIdx >= 0 && newIdx < this.ranges.length) {
            this.selectRange(this.ranges[newIdx]);
        }
    }

    private highlightRange(label: string) {
        this.rangeBar.querySelectorAll('.range-btn').forEach(btn => {
            btn.classList.toggle('active', (btn as HTMLElement).dataset.label === label);
        });
    }

    private async fetchAndRender() {
        if (!this.ticker || !this.currentRange) return;

        this.stopAutoRefresh();

        const data = await FetchChartData(this.ticker, this.currentRange.period, this.currentRange.interval);
        if (!data) return;

        this.renderChart(data);
        this.startAutoRefreshIfNeeded();
    }

    private renderChart(data: ChartDataResponse) {
        if (!this.areaSeries || !this.volumeSeries) return;

        const lineData: AreaData<Time>[] = [];
        const volumeData: HistogramData<Time>[] = [];

        let prevClose: number | null = null;
        let firstClose: number | null = null;

        for (let i = 0; i < data.timestamps.length; i++) {
            const close = data.close[i];
            if (close == null) continue;

            const time = data.timestamps[i] as Time;

            if (firstClose === null) firstClose = close;
            lineData.push({ time, value: close });

            const vol = data.volume[i];
            if (vol != null) {
                const color = (prevClose !== null && close >= prevClose)
                    ? 'rgba(76, 210, 120, 0.35)'
                    : 'rgba(255, 107, 122, 0.35)';
                volumeData.push({ time, value: vol, color });
            }
            prevClose = close;
        }

        if (lineData.length === 0) return;

        this.isUp = firstClose !== null && prevClose !== null && prevClose >= firstClose;

        const lineColor = this.isUp ? '#4cd278' : '#ff6b7a';
        const topColor = this.isUp ? 'rgba(76, 210, 120, 0.3)' : 'rgba(255, 107, 122, 0.3)';
        const bottomColor = this.isUp ? 'rgba(76, 210, 120, 0.02)' : 'rgba(255, 107, 122, 0.02)';

        this.areaSeries.applyOptions({ lineColor, topColor, bottomColor });
        this.areaSeries.setData(lineData);
        this.volumeSeries.setData(volumeData);
        this.chart!.timeScale().fitContent();
    }

    updateHeader(ticker: string, name: string, price: number, changePct: number, exchange: string, currency: string) {
        const tickerEl = this.headerEl.querySelector('.chart-ticker')!;
        const companyEl = this.headerEl.querySelector('.chart-company')!;
        const priceEl = this.headerEl.querySelector('.chart-price-value')!;
        const changeEl = this.headerEl.querySelector('.chart-price-change')!;
        const metaEl = this.headerEl.querySelector('.chart-header-meta')!;

        tickerEl.textContent = ticker;
        companyEl.textContent = name;
        priceEl.textContent = price.toFixed(2);

        const sign = changePct >= 0 ? '+' : '';
        changeEl.textContent = `${sign}${changePct.toFixed(2)}%`;
        changeEl.className = 'chart-price-change ' + (changePct >= 0 ? 'up' : 'down');

        metaEl.textContent = `${exchange} · ${currency}`.toUpperCase();
    }

    private startAutoRefreshIfNeeded() {
        if (!this.currentRange) return;
        IsIntradayInterval(this.currentRange.interval).then(isIntraday => {
            if (isIntraday) {
                this.refreshInterval = window.setInterval(() => this.fetchAndRender(), 5 * 60 * 1000);
            }
        });
    }

    private stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    private formatDate(date: Date): string {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const m = months[date.getMonth()];
        const d = date.getDate();
        const y = date.getFullYear();
        const h = date.getHours().toString().padStart(2, '0');
        const min = date.getMinutes().toString().padStart(2, '0');

        if (this.currentRange && ['1D', '1W'].includes(this.currentRange.label)) {
            return `${m} ${d}, ${y}  ${h}:${min}`;
        }
        return `${m} ${d}, ${y}`;
    }

    getCurrentRange(): TimeRangeInfo | null {
        return this.currentRange;
    }

    destroy() {
        this.stopAutoRefresh();
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
    }
}
