import type { RCONManager } from './rcon';

export type ServerStatus = 'active' | 'stopped';

export interface ServerStatusSnapshot {
    status: ServerStatus;
    checkedAt: Date;
}

type HealthChecker = Pick<RCONManager, 'checkHealth'>;
type StatusChangeHandler = (current: ServerStatusSnapshot, previous: ServerStatus) => Promise<void> | void;

export class ServerStatusMonitor {
    private snapshot: ServerStatusSnapshot | null = null;
    private checkPromise: Promise<ServerStatusSnapshot> | null = null;
    private interval: ReturnType<typeof setInterval> | null = null;

    constructor(
        private readonly healthChecker: HealthChecker,
        private readonly onStatusChange: StatusChangeHandler,
        private readonly intervalMs = 30_000,
        private readonly timeoutMs = 5_000,
    ) {}

    async start(): Promise<void> {
        if (this.interval) return;

        // Establish a baseline without announcing an outage that happened before
        // the bot started observing the server.
        await this.checkNow();
        this.interval = setInterval(() => {
            this.checkNow().catch((err) => console.error('Server status check failed:', err));
        }, this.intervalMs);
    }

    stop(): void {
        if (!this.interval) return;
        clearInterval(this.interval);
        this.interval = null;
    }

    async checkNow(): Promise<ServerStatusSnapshot> {
        if (this.checkPromise) return this.checkPromise;

        this.checkPromise = this.performCheck();
        try {
            return await this.checkPromise;
        } finally {
            this.checkPromise = null;
        }
    }

    getLastSnapshot(): ServerStatusSnapshot | null {
        return this.snapshot;
    }

    private async performCheck(): Promise<ServerStatusSnapshot> {
        const isHealthy = await this.healthChecker.checkHealth(this.timeoutMs);
        const next: ServerStatusSnapshot = {
            status: isHealthy ? 'active' : 'stopped',
            checkedAt: new Date(),
        };
        const previous = this.snapshot?.status;

        this.snapshot = next;

        if (previous && previous !== next.status) {
            try {
                await this.onStatusChange(next, previous);
            } catch (err) {
                console.error('Failed to announce server status change:', err);
            }
        }

        return next;
    }
}
