import { GetWatchlist, AddTicker, RemoveTicker, ReorderWatchlist, SearchTickers, ValidateTicker } from '../wailsjs/go/app/App';

interface WatchlistEntry {
    ticker: string;
    position: number;
    name: string;
    currency: string;
}

interface SearchResult {
    symbol: string;
    name: string;
    exchange: string;
}

export class Watchlist {
    private container: HTMLElement;
    private entries: WatchlistEntry[] = [];
    private selectedTicker: string = '';
    private searchTimeout: number | null = null;
    private searchInput!: HTMLInputElement;
    private searchResults!: HTMLElement;
    private listContainer!: HTMLElement;
    private headerLabel!: HTMLElement;

    onTickerSelected: ((ticker: string) => void) | null = null;

    constructor(container: HTMLElement) {
        this.container = container;
    }

    async init() {
        this.render();
        await this.loadWatchlist();
    }

    private render() {
        this.container.innerHTML = `
            <div class="watchlist-search">
                <input type="text" class="watchlist-search-input" placeholder="Search or add ticker..." />
            </div>
            <div class="watchlist-search-results hidden"></div>
            <div class="watchlist-header">
                <span class="watchlist-header-label">Watchlist · 0</span>
            </div>
            <div class="watchlist-list"></div>
        `;

        this.searchInput = this.container.querySelector('.watchlist-search-input')!;
        this.searchResults = this.container.querySelector('.watchlist-search-results')!;
        this.listContainer = this.container.querySelector('.watchlist-list')!;
        this.headerLabel = this.container.querySelector('.watchlist-header-label')!;

        this.searchInput.addEventListener('input', () => this.onSearchInput());
        this.searchInput.addEventListener('keydown', (e) => this.onSearchKeydown(e));
    }

    private async loadWatchlist() {
        this.entries = await GetWatchlist();
        this.updateHeader();
        this.renderList();
    }

    private updateHeader() {
        this.headerLabel.textContent = `Watchlist · ${this.entries.length}`;
    }

    private renderList() {
        this.listContainer.innerHTML = '';
        for (const entry of this.entries) {
            const item = this.createListItem(entry);
            this.listContainer.appendChild(item);
        }
    }

    private createListItem(entry: WatchlistEntry): HTMLElement {
        const item = document.createElement('div');
        item.className = 'watchlist-item' + (entry.ticker === this.selectedTicker ? ' selected' : '');
        item.dataset.ticker = entry.ticker;
        item.draggable = true;

        item.innerHTML = `
            <div class="watchlist-item-top">
                <span class="watchlist-item-ticker">${entry.ticker}</span>
                <span class="watchlist-item-price">--</span>
            </div>
            <div class="watchlist-item-bottom">
                <span class="watchlist-item-name">${entry.name || entry.ticker}</span>
                <span class="watchlist-item-change">--</span>
            </div>
        `;

        item.addEventListener('click', () => this.selectTicker(entry.ticker));
        item.addEventListener('contextmenu', (e) => this.showContextMenu(e, entry.ticker));

        item.addEventListener('dragstart', (e) => {
            e.dataTransfer!.setData('text/plain', entry.ticker);
            item.classList.add('dragging');
        });
        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            this.listContainer.querySelectorAll('.watchlist-item').forEach(el => el.classList.remove('drag-over'));
        });
        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            item.classList.add('drag-over');
        });
        item.addEventListener('dragleave', () => {
            item.classList.remove('drag-over');
        });
        item.addEventListener('drop', (e) => {
            e.preventDefault();
            item.classList.remove('drag-over');
            const draggedTicker = e.dataTransfer!.getData('text/plain');
            if (draggedTicker && draggedTicker !== entry.ticker) {
                this.reorder(draggedTicker, entry.ticker);
            }
        });

        return item;
    }

    private selectTicker(ticker: string) {
        this.selectedTicker = ticker;
        this.listContainer.querySelectorAll('.watchlist-item').forEach(el => {
            el.classList.toggle('selected', (el as HTMLElement).dataset.ticker === ticker);
        });
        if (this.onTickerSelected) {
            this.onTickerSelected(ticker);
        }
    }

    private showContextMenu(e: MouseEvent, ticker: string) {
        e.preventDefault();
        this.removeContextMenu();

        const menu = document.createElement('div');
        menu.className = 'context-menu';
        menu.innerHTML = `<div class="context-menu-item">Remove from watchlist</div>`;
        menu.style.left = `${e.clientX}px`;
        menu.style.top = `${e.clientY}px`;

        menu.querySelector('.context-menu-item')!.addEventListener('click', async () => {
            await this.removeTicker(ticker);
            this.removeContextMenu();
        });

        document.body.appendChild(menu);
        setTimeout(() => {
            document.addEventListener('click', () => this.removeContextMenu(), { once: true });
        }, 0);
    }

    private removeContextMenu() {
        document.querySelectorAll('.context-menu').forEach(el => el.remove());
    }

    private async removeTicker(ticker: string) {
        await RemoveTicker(ticker);
        this.entries = this.entries.filter(e => e.ticker !== ticker);
        this.updateHeader();
        this.renderList();
        if (this.selectedTicker === ticker) {
            this.selectedTicker = '';
            if (this.entries.length > 0) {
                this.selectTicker(this.entries[0].ticker);
            }
        }
    }

    private onSearchInput() {
        const query = this.searchInput.value.trim();
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        if (!query) {
            this.hideSearchResults();
            return;
        }
        this.searchTimeout = window.setTimeout(() => this.doSearch(query), 300);
    }

    private async onSearchKeydown(e: KeyboardEvent) {
        if (e.key === 'Escape') {
            this.searchInput.value = '';
            this.hideSearchResults();
            this.searchInput.blur();
            return;
        }
        if (e.key === 'ArrowDown' && !this.searchResults.classList.contains('hidden')) {
            e.preventDefault();
            const first = this.searchResults.querySelector('.search-result-item') as HTMLElement;
            if (first) first.focus();
            return;
        }
        if (e.key === 'Enter') {
            const query = this.searchInput.value.trim().toUpperCase();
            if (!query) return;
            e.preventDefault();
            // If search results visible, add first result
            const firstResult = this.searchResults.querySelector('.search-result-item');
            if (firstResult && !this.searchResults.classList.contains('hidden')) {
                const symbol = (firstResult as HTMLElement).dataset.symbol!;
                await this.addTicker(symbol);
            } else {
                // Validate and add directly
                const valid = await ValidateTicker(query);
                if (valid) {
                    await this.addTicker(query);
                }
            }
        }
    }

    private async doSearch(query: string) {
        const results: SearchResult[] = await SearchTickers(query);
        if (!results || results.length === 0) {
            this.hideSearchResults();
            return;
        }
        this.showSearchResults(results);
    }

    private showSearchResults(results: SearchResult[]) {
        this.searchResults.innerHTML = '';
        this.searchResults.classList.remove('hidden');

        for (const r of results) {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            item.tabIndex = 0;
            item.dataset.symbol = r.symbol;
            item.innerHTML = `
                <span class="search-result-symbol">${r.symbol}</span>
                <span class="search-result-name">${r.name}</span>
                <span class="search-result-exchange">${r.exchange}</span>
            `;
            item.addEventListener('click', () => this.addTicker(r.symbol));
            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') this.addTicker(r.symbol);
                if (e.key === 'Escape') {
                    this.hideSearchResults();
                    this.searchInput.focus();
                }
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    const next = item.nextElementSibling as HTMLElement;
                    if (next) next.focus();
                }
                if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    const prev = item.previousElementSibling as HTMLElement;
                    if (prev) prev.focus();
                    else this.searchInput.focus();
                }
            });
            this.searchResults.appendChild(item);
        }
    }

    private hideSearchResults() {
        this.searchResults.classList.add('hidden');
        this.searchResults.innerHTML = '';
    }

    private async addTicker(symbol: string) {
        const exists = this.entries.some(e => e.ticker === symbol);
        if (exists) {
            this.selectTicker(symbol);
            this.searchInput.value = '';
            this.hideSearchResults();
            return;
        }

        await AddTicker(symbol);
        this.searchInput.value = '';
        this.hideSearchResults();
        await this.loadWatchlist();
        this.selectTicker(symbol);
    }

    updatePrice(ticker: string, price: number, changePct: number) {
        const item = this.listContainer.querySelector(`[data-ticker="${ticker}"]`);
        if (!item) return;

        const priceEl = item.querySelector('.watchlist-item-price')!;
        const changeEl = item.querySelector('.watchlist-item-change')!;

        priceEl.textContent = price.toFixed(2);

        const sign = changePct >= 0 ? '+' : '';
        changeEl.textContent = `${sign}${changePct.toFixed(2)}%`;
        changeEl.className = 'watchlist-item-change ' + (changePct >= 0 ? 'up' : 'down');
    }

    updateName(ticker: string, name: string) {
        const entry = this.entries.find(e => e.ticker === ticker);
        if (entry) entry.name = name;

        const item = this.listContainer.querySelector(`[data-ticker="${ticker}"]`);
        if (!item) return;
        const nameEl = item.querySelector('.watchlist-item-name')!;
        nameEl.textContent = name;
    }

    private async reorder(draggedTicker: string, targetTicker: string) {
        const fromIdx = this.entries.findIndex(e => e.ticker === draggedTicker);
        const toIdx = this.entries.findIndex(e => e.ticker === targetTicker);
        if (fromIdx === -1 || toIdx === -1) return;

        const [moved] = this.entries.splice(fromIdx, 1);
        this.entries.splice(toIdx, 0, moved);
        this.renderList();

        const order = this.entries.map(e => e.ticker);
        await ReorderWatchlist(order);
    }

    focusSearch() {
        this.searchInput.focus();
    }

    removeSelected() {
        if (this.selectedTicker) {
            this.removeTicker(this.selectedTicker);
        }
    }

    getSelectedTicker(): string {
        return this.selectedTicker;
    }

    getTickers(): string[] {
        return this.entries.map(e => e.ticker);
    }
}
