import { describe, expect, test } from 'bun:test';
import { ServerStatusMonitor, type ServerStatus } from '../src/serverStatus';

describe('ServerStatusMonitor', () => {
    test('announces transitions without duplicates', async () => {
        const healthResults = [true, false, false, true, false];
        const transitions: Array<[ServerStatus | undefined, ServerStatus]> = [];
        const healthChecker = {
            async checkHealth() {
                return healthResults.shift() ?? false;
            },
        };
        const monitor = new ServerStatusMonitor(
            healthChecker,
            (current, previous) => {
                transitions.push([previous, current.status]);
            },
            30_000,
            5_000,
            1,
        );

        expect((await monitor.checkNow()).status).toBe('active');
        expect(transitions).toEqual([]);

        expect((await monitor.checkNow()).status).toBe('stopped');
        expect((await monitor.checkNow()).status).toBe('stopped');
        expect((await monitor.checkNow()).status).toBe('active');
        expect((await monitor.checkNow()).status).toBe('stopped');

        expect(transitions).toEqual([
            ['active', 'stopped'],
            ['stopped', 'active'],
            ['active', 'stopped'],
        ]);
    });

    test('announces when the server is already stopped on startup', async () => {
        const transitions: Array<[ServerStatus | undefined, ServerStatus]> = [];
        const monitor = new ServerStatusMonitor(
            { async checkHealth() { return false; } },
            (current, previous) => {
                transitions.push([previous, current.status]);
            },
            30_000,
            5_000,
            1,
        );

        expect((await monitor.checkNow()).status).toBe('stopped');
        expect((await monitor.checkNow()).status).toBe('stopped');
        expect(transitions).toEqual([[undefined, 'stopped']]);
    });

    test('retries an outage announcement when delivery fails', async () => {
        let attempts = 0;
        const monitor = new ServerStatusMonitor(
            { async checkHealth() { return false; } },
            async () => {
                attempts += 1;
                if (attempts === 1) throw new Error('Discord unavailable');
            },
            30_000,
            5_000,
            1,
        );

        await monitor.checkNow();
        await monitor.checkNow();
        await monitor.checkNow();
        expect(attempts).toBe(2);
    });

    test('waits for consecutive failures before announcing an outage', async () => {
        const healthResults = [true, false, true, false, false, false];
        let outageAnnouncements = 0;
        const monitor = new ServerStatusMonitor(
            {
                async checkHealth() {
                    return healthResults.shift() ?? false;
                },
            },
            (current) => {
                if (current.status === 'stopped') outageAnnouncements += 1;
            },
            30_000,
            5_000,
            3,
        );

        for (let index = 0; index < 5; index += 1) {
            await monitor.checkNow();
            expect(outageAnnouncements).toBe(0);
        }

        await monitor.checkNow();
        expect(outageAnnouncements).toBe(1);
    });
});
