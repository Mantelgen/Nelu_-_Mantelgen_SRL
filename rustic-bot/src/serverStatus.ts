import type { RCONManager } from './rcon';

export type ServerStatus = 'active' | 'stopped';

export interface ServerStatusSnapshot {
    status: ServerStatus;
    checkedAt: Date;
}

type HealthChecker = Pick<RCONManager, 'checkHealth'>;
type StatusChangeHandler = (current: ServerStatusSnapshot, previous?: ServerStatus) => Promise<void> | void;

export class ServerStatusMonitor {
    private snapshot: ServerStatusSnapshot | null = null;
    private checkPromise: Promise<ServerStatusSnapshot> | null = null;
    private interval: ReturnType<typeof setInterval> | null = null;
    private stoppedAnnouncementPending = false;
    private consecutiveFailures = 0;

    constructor(
        private readonly healthChecker: HealthChecker,
        private readonly onStatusChange: StatusChangeHandler,
        private readonly intervalMs = 30_000,
        private readonly timeoutMs = 5_000,
        private readonly failureThreshold = 3,
    ) {}

    async start(): Promise<void> {
        if (this.interval) return;

        // Announce an initial offline state too. Otherwise an outage that starts
        // before the bot restarts is never reported.
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
        this.consecutiveFailures = isHealthy ? 0 : this.consecutiveFailures + 1;

        const next: ServerStatusSnapshot = {
            status: isHealthy ? 'active' : 'stopped',
            checkedAt: new Date(),
        };
        const previous = this.snapshot?.status;

        this.snapshot = next;

        const changed = previous !== undefined && previous !== next.status;

        if (
            next.status === 'stopped'
            && this.consecutiveFailures === this.failureThreshold
            && !this.stoppedAnnouncementPending
        ) {
            this.stoppedAnnouncementPending = true;
        } else if (next.status === 'active') {
            this.stoppedAnnouncementPending = false;
        }

        // Retry a failed outage announcement on the next check, without
        // duplicating an alert that was delivered successfully.
        if (next.status === 'stopped' && this.stoppedAnnouncementPending) {
            try {
                await this.onStatusChange(next, previous);
                this.stoppedAnnouncementPending = false;
            } catch (err) {
                console.error('Failed to announce server status change:', err);
            }
        } else if (changed && next.status === 'active') {
            try {
                await this.onStatusChange(next, previous);
            } catch (err) {
                console.error('Failed to announce server status change:', err);
            }
        }

        return next;
    }
}
