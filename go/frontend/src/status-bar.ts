export class StatusBar {
    private container: HTMLElement;
    private dotEl!: HTMLElement;
    private stateEl!: HTMLElement;
    private timeEl!: HTMLElement;

    constructor(container: HTMLElement) {
        this.container = container;
        this.render();
    }

    private render() {
        this.container.className = 'status-bar';
        this.container.innerHTML = `
            <div class="status-left">
                <span class="status-dot"></span>
                <span class="status-state">—</span>
                <span class="status-time"></span>
            </div>
            <div class="status-right">Data from Yahoo Finance</div>
        `;
        this.dotEl = this.container.querySelector('.status-dot')!;
        this.stateEl = this.container.querySelector('.status-state')!;
        this.timeEl = this.container.querySelector('.status-time')!;
    }

    updateMarketState(state: string) {
        const { label, color } = STATE_MAP[state] || STATE_MAP['CLOSED'];
        this.stateEl.textContent = label;
        this.dotEl.style.background = color;
        this.timeEl.textContent = `Updated ${this.formatNow()}`;
    }

    private formatNow(): string {
        const d = new Date();
        const h = d.getHours().toString().padStart(2, '0');
        const m = d.getMinutes().toString().padStart(2, '0');
        return `${h}:${m}`;
    }
}

const STATE_MAP: Record<string, { label: string; color: string }> = {
    REGULAR: { label: 'Market Open', color: 'var(--green)' },
    PRE: { label: 'Pre-Market', color: 'var(--yellow)' },
    POST: { label: 'After Hours', color: 'var(--blue)' },
    POSTPOST: { label: 'After Hours', color: 'var(--blue)' },
    CLOSED: { label: 'Market Closed', color: 'var(--text-muted)' },
};
