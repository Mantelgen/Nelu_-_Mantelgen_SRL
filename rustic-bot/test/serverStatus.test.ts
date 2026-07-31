import { describe, expect, test } from 'bun:test';
import { ServerStatusMonitor, type ServerStatus } from '../src/serverStatus';

describe('ServerStatusMonitor', () => {
    test('announces only transitions and not the initial state', async () => {
        const healthResults = [true, false, false, true, false];
        const transitions: Array<[ServerStatus, ServerStatus]> = [];
        const healthChecker = {
            async checkHealth() {
                return healthResults.shift() ?? false;
            },
        };
        const monitor = new ServerStatusMonitor(
            healthChecker,
            (current, previous) => transitions.push([previous, current.status]),
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
});
