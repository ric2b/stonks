import { FetchNewsItems } from '../wailsjs/go/app/App';
import { BrowserOpenURL } from '../wailsjs/runtime/runtime';

interface NewsItem {
    title: string;
    url: string;
    provider: string;
    pubDate: number;
}

export class NewsPanel {
    private container: HTMLElement;

    constructor(container: HTMLElement) {
        this.container = container;
        this.container.className = 'news-panel';
        this.container.innerHTML = '<div class="news-list"></div>';
    }

    async loadNews(ticker: string) {
        const list = this.container.querySelector('.news-list')!;
        list.innerHTML = '';

        const items: NewsItem[] = await FetchNewsItems(ticker);
        if (!items || items.length === 0) {
            list.innerHTML = '<div class="news-empty">No recent news</div>';
            return;
        }

        for (const item of items) {
            const el = document.createElement('div');
            el.className = 'news-item';
            el.innerHTML = `
                <div class="news-title">${this.escapeHtml(item.title)}</div>
                <div class="news-meta">
                    <span class="news-provider">${this.escapeHtml(item.provider)}</span>
                    <span class="news-time">${this.relativeTime(item.pubDate)}</span>
                </div>
            `;
            el.addEventListener('click', () => BrowserOpenURL(item.url));
            list.appendChild(el);
        }
    }

    private relativeTime(timestamp: number): string {
        const now = Math.floor(Date.now() / 1000);
        const diff = now - timestamp;

        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
        const date = new Date(timestamp * 1000);
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return `${months[date.getMonth()]} ${date.getDate()}`;
    }

    private escapeHtml(str: string): string {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}
