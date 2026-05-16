import './style.css';
import { Watchlist } from './watchlist';
import { ChartView } from './chart';
import { StatsPanel } from './stats-panel';
import { NewsPanel } from './news-panel';
import { StatusBar } from './status-bar';
import { EventsOn } from '../wailsjs/runtime/runtime';
import { FetchTickerInfo, GetSetting } from '../wailsjs/go/app/App';

const app = document.querySelector<HTMLDivElement>('#app')!;

app.innerHTML = `
    <div class="sidebar" id="sidebar"></div>
    <div class="main-content" id="main-content">
        <div class="empty-state" id="empty-state">
            <div class="empty-state-icon">📈</div>
            <div class="empty-state-title">No ticker selected</div>
            <div class="empty-state-desc">Search for a stock and add it to your watchlist</div>
        </div>
        <div class="chart-area hidden" id="chart-area"></div>
        <div class="stats-container hidden" id="stats-container"></div>
        <div class="news-container hidden" id="news-container"></div>
        <div class="status-bar-container" id="status-bar"></div>
    </div>
`;

const sidebar = document.getElementById('sidebar')!;
const chartArea = document.getElementById('chart-area')!;
const emptyState = document.getElementById('empty-state')!;
const statsContainer = document.getElementById('stats-container')!;
const newsContainer = document.getElementById('news-container')!;
const statusBarEl = document.getElementById('status-bar')!;

const watchlist = new Watchlist(sidebar);
const chartView = new ChartView(chartArea);
const statsPanel = new StatsPanel(statsContainer);
const newsPanel = new NewsPanel(newsContainer);
const statusBar = new StatusBar(statusBarEl);

function showChart() {
    emptyState.classList.add('hidden');
    chartArea.classList.remove('hidden');
    statsContainer.classList.remove('hidden');
    newsContainer.classList.remove('hidden');
}

async function loadTicker(ticker: string) {
    showChart();

    const lastPeriod = await GetSetting('last_period');
    const range = chartView.getCurrentRange();
    let period = range?.period;
    let interval = range?.interval;

    if (lastPeriod && !range) {
        const ranges = await (await import('../wailsjs/go/app/App')).GetTimeRanges();
        const found = ranges.find((r: any) => r.label === lastPeriod);
        if (found) {
            period = found.period;
            interval = found.interval;
        }
    }

    await chartView.loadTicker(ticker, period, interval);

    const info = await FetchTickerInfo(ticker);
    if (info) {
        const name = (info['longName'] || info['shortName'] || '') as string;
        const exchange = (info['exchangeName'] || info['exchange'] || '') as string;
        const currency = (info['currency'] || '') as string;
        const price = (info['regularMarketPrice'] || 0) as number;
        const changePct = (info['regularMarketChangePercent'] || 0) as number;
        chartView.updateHeader(ticker, name, price, changePct, exchange, currency);
        statsPanel.update(info, currency);
        statusBar.updateMarketState((info['marketState'] || 'CLOSED') as string);
    }

    newsPanel.loadNews(ticker);
}

watchlist.onTickerSelected = (ticker: string) => {
    loadTicker(ticker);
};

EventsOn('prices:updated', (updates: Array<{ticker: string, price: number, changePct: number}>) => {
    for (const u of updates) {
        watchlist.updatePrice(u.ticker, u.price, u.changePct);
    }
});

EventsOn('names:updated', (updates: Array<{ticker: string, name: string}>) => {
    for (const u of updates) {
        watchlist.updateName(u.ticker, u.name);
    }
});

document.addEventListener('keydown', (e: KeyboardEvent) => {
    const target = e.target as HTMLElement;
    const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA';

    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        watchlist.focusSearch();
        return;
    }
    if (e.key === '/' && !isInput) {
        e.preventDefault();
        watchlist.focusSearch();
        return;
    }
    if (e.key === 'Delete' && !isInput) {
        watchlist.removeSelected();
        return;
    }
    if (e.key === 'Backspace' && !isInput) {
        watchlist.removeSelected();
        return;
    }

    if (!isInput && e.key >= '1' && e.key <= '9') {
        chartView.selectRangeByIndex(parseInt(e.key) - 1);
        return;
    }
    if (!isInput && e.key === '0') {
        chartView.selectRangeByIndex(9);
        return;
    }
    if (!isInput && e.key === 'ArrowLeft') {
        chartView.stepRange(-1);
        return;
    }
    if (!isInput && e.key === 'ArrowRight') {
        chartView.stepRange(1);
        return;
    }
});

chartView.init();
watchlist.init();
