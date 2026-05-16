import './style.css';
import { Watchlist } from './watchlist';
import { EventsOn } from '../wailsjs/runtime/runtime';

const app = document.querySelector<HTMLDivElement>('#app')!;

app.innerHTML = `
    <div class="sidebar" id="sidebar"></div>
    <div class="main-content" id="main-content">
        <div class="empty-state">
            <div class="empty-state-icon">📈</div>
            <div class="empty-state-title">No ticker selected</div>
            <div class="empty-state-desc">Search for a stock and add it to your watchlist</div>
        </div>
    </div>
`;

const sidebar = document.getElementById('sidebar')!;
const watchlist = new Watchlist(sidebar);

watchlist.onTickerSelected = (_ticker: string) => {
    // Chart, detail, and news views will be wired up in later commits
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

watchlist.init();
