import './style.css';
import { Watchlist } from './watchlist';

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

watchlist.onTickerSelected = (ticker: string) => {
    console.log('Selected:', ticker);
    // Chart, detail, and news views will be wired up in later commits
};

watchlist.init();
