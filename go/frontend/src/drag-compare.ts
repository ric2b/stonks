import { IChartApi, ISeriesApi, Time, AreaData } from 'lightweight-charts';

interface DragState {
    active: boolean;
    startX: number;
    startTime: Time | null;
    startPrice: number | null;
}

export class DragCompare {
    private chart: IChartApi;
    private series: ISeriesApi<'Area', Time>;
    private container: HTMLElement;
    private hoverLabel: HTMLElement;
    private state: DragState = { active: false, startX: 0, startTime: null, startPrice: null };
    private overlay: HTMLElement | null = null;

    constructor(chart: IChartApi, series: ISeriesApi<'Area', Time>, container: HTMLElement, hoverLabel: HTMLElement) {
        this.chart = chart;
        this.series = series;
        this.container = container;
        this.hoverLabel = hoverLabel;
        this.setupEvents();
    }

    private setupEvents() {
        this.container.addEventListener('mousedown', (e: MouseEvent) => {
            if (e.button !== 0) return;
            const coord = this.chart.timeScale().coordinateToTime(e.offsetX);
            if (!coord) return;

            const data = this.getDataAtTime(coord);
            if (data === null) return;

            this.state = {
                active: true,
                startX: e.offsetX,
                startTime: coord,
                startPrice: data,
            };

            this.createOverlay(e.offsetX);
        });

        this.container.addEventListener('mousemove', (e: MouseEvent) => {
            if (!this.state.active) return;

            const coord = this.chart.timeScale().coordinateToTime(e.offsetX);
            if (!coord) return;

            const currentPrice = this.getDataAtTime(coord);
            if (currentPrice === null || this.state.startPrice === null) return;

            this.updateOverlay(e.offsetX);

            const diff = currentPrice - this.state.startPrice;
            const pct = (diff / this.state.startPrice) * 100;
            const sign = diff >= 0 ? '+' : '';
            const color = diff >= 0 ? 'var(--green)' : 'var(--red)';

            const startDate = this.formatTime(this.state.startTime!);
            const endDate = this.formatTime(coord);

            this.hoverLabel.innerHTML = `${startDate} – ${endDate} &nbsp;&nbsp; <span style="color:${color}">${sign}${diff.toFixed(2)} (${sign}${pct.toFixed(2)}%)</span>`;
        });

        const endDrag = () => {
            if (!this.state.active) return;
            this.state.active = false;
            this.removeOverlay();
            this.hoverLabel.textContent = '';
        };

        this.container.addEventListener('mouseup', endDrag);
        this.container.addEventListener('mouseleave', endDrag);
    }

    private getDataAtTime(time: Time): number | null {
        const coord = this.chart.timeScale().timeToCoordinate(time);
        if (coord === null) return null;

        const data = this.series.dataByIndex(
            Math.round(this.chart.timeScale().coordinateToLogical(coord) ?? 0)
        ) as AreaData<Time> | null;

        if (data && 'value' in data) {
            return data.value;
        }
        return null;
    }

    private createOverlay(x: number) {
        this.removeOverlay();
        this.overlay = document.createElement('div');
        this.overlay.className = 'drag-overlay';
        this.overlay.style.left = `${x}px`;
        this.overlay.style.width = '0px';
        this.container.appendChild(this.overlay);
    }

    private updateOverlay(currentX: number) {
        if (!this.overlay) return;
        const left = Math.min(this.state.startX, currentX);
        const width = Math.abs(currentX - this.state.startX);
        this.overlay.style.left = `${left}px`;
        this.overlay.style.width = `${width}px`;
    }

    private removeOverlay() {
        if (this.overlay) {
            this.overlay.remove();
            this.overlay = null;
        }
    }

    private formatTime(time: Time): string {
        const t = time as number;
        const date = new Date(t * 1000);
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
    }
}
