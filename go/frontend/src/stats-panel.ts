interface StatItem {
    label: string;
    key: string;
    format: 'price' | 'number' | 'large' | 'percent' | 'plain';
}

const STATS: StatItem[] = [
    { label: 'Open', key: 'open', format: 'price' },
    { label: 'High', key: 'dayHigh', format: 'price' },
    { label: 'Low', key: 'dayLow', format: 'price' },
    { label: 'Volume', key: 'volume', format: 'large' },
    { label: 'P/E', key: 'trailingPE', format: 'plain' },
    { label: 'Mkt Cap', key: 'marketCap', format: 'large' },
    { label: '52W High', key: 'fiftyTwoWeekHigh', format: 'price' },
    { label: '52W Low', key: 'fiftyTwoWeekLow', format: 'price' },
    { label: 'Avg Vol', key: 'averageVolume', format: 'large' },
    { label: 'Yield', key: 'dividendYield', format: 'percent' },
    { label: 'Beta', key: 'beta', format: 'plain' },
    { label: 'EPS', key: 'trailingEps', format: 'price' },
];

export class StatsPanel {
    private container: HTMLElement;
    private currency: string = 'USD';

    constructor(container: HTMLElement) {
        this.container = container;
        this.render();
    }

    private render() {
        this.container.innerHTML = '';
        this.container.className = 'stats-panel';
        for (const stat of STATS) {
            const cell = document.createElement('div');
            cell.className = 'stats-cell';
            cell.dataset.key = stat.key;
            cell.innerHTML = `
                <span class="stats-label">${stat.label}</span>
                <span class="stats-value">—</span>
            `;
            this.container.appendChild(cell);
        }
    }

    update(info: Record<string, any>, currency?: string) {
        if (currency) this.currency = currency;

        for (const stat of STATS) {
            const cell = this.container.querySelector(`[data-key="${stat.key}"]`);
            if (!cell) continue;
            const valueEl = cell.querySelector('.stats-value')!;
            const raw = info[stat.key];
            valueEl.textContent = this.formatValue(raw, stat.format);
        }
    }

    private formatValue(value: any, format: string): string {
        if (value == null || value === 0) return '—';
        const num = Number(value);
        if (isNaN(num)) return '—';

        switch (format) {
            case 'price':
                return this.formatPrice(num);
            case 'number':
                return num.toLocaleString();
            case 'large':
                return this.formatLarge(num);
            case 'percent':
                return (num * 100).toFixed(2) + '%';
            case 'plain':
                return num.toFixed(2);
            default:
                return String(value);
        }
    }

    private formatPrice(num: number): string {
        const symbol = CURRENCY_SYMBOLS[this.currency] || '$';
        const suffix = SUFFIX_CURRENCIES.has(this.currency);
        const formatted = num.toFixed(2);
        return suffix ? `${formatted} ${symbol}` : `${symbol}${formatted}`;
    }

    private formatLarge(num: number): string {
        if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T';
        if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
        if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
        if (num >= 1e3) return (num / 1e3).toFixed(1) + 'K';
        return num.toLocaleString();
    }
}

const CURRENCY_SYMBOLS: Record<string, string> = {
    USD: '$', EUR: '€', GBP: '£', JPY: '¥', CNY: '¥',
    CHF: 'CHF', CAD: 'C$', AUD: 'A$', HKD: 'HK$', KRW: '₩',
    INR: '₹', BRL: 'R$', SEK: 'kr', NOK: 'kr', DKK: 'kr',
    ILS: '₪', SGD: 'S$', TWD: 'NT$', ZAR: 'R',
};

const SUFFIX_CURRENCIES = new Set(['SEK', 'NOK', 'DKK', 'CHF']);
