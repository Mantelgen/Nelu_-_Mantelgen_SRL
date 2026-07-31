import { Rcon } from 'rcon-client';

export class RCONManager {
    private client: Rcon | null = null;
    public isConnected = false;
    private connectPromise: Promise<void> | null = null;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    private readonly host: string;
    private readonly port: number;
    private readonly password: string;

    constructor() {
        this.host = process.env.RCON_HOST!;
        this.port = parseInt(process.env.RCON_PORT ?? '25575', 10);
        this.password = process.env.RCON_PASSWORD!;
    }

    async connect(): Promise<void> {
        if (this.isConnected) return;
        if (this.connectPromise) return this.connectPromise;

        this.connectPromise = this.openConnection();

        try {
            await this.connectPromise;
        } finally {
            this.connectPromise = null;
        }
    }

    private async openConnection(): Promise<void> {
        console.log('Trying to connect to RCON server...');

        const connection = new Rcon({
            host: this.host,
            port: this.port,
            password: this.password,
        });

        this.client = connection;
        connection.on('end', () => this.handleDisconnect(connection, 'RCON connection closed'));
        connection.on('error', (err: Error) => this.handleDisconnect(connection, `RCON error: ${err.message}`));

        try {
            await connection.connect();

            if (this.client !== connection) {
                await connection.disconnect().catch(() => undefined);
                return;
            }

            this.isConnected = true;
            this.clearReconnectTimer();
            console.log('RCON connection established!');
        } catch (err) {
            const error = err as Error;
            console.error('Failed to connect to RCON:', error.message);
            if (this.client === connection) {
                this.client = null;
                this.isConnected = false;
            }
            this.scheduleReconnect();
        }
    }

    async forceReconnect(): Promise<void> {
        const oldClient = this.client;
        this.client = null;
        this.isConnected = false;
        this.clearReconnectTimer();

        if (oldClient) {
            try { await oldClient.disconnect(); } catch { /* already closed */ }
        }

        await this.connect();
    }

    async sendCommand(command: string): Promise<string> {
        const connection = this.client;

        if (!this.isConnected || !connection) {
            throw new Error('RCON is currently disconnected. Please try again in a moment.');
        }

        try {
            return await connection.send(command);
        } catch (err) {
            this.handleDisconnect(connection, 'RCON command failed');
            throw err;
        }
    }

    async checkHealth(timeoutMs = 5000): Promise<boolean> {
        if (!this.isConnected || !this.client) return false;

        let timeout: ReturnType<typeof setTimeout> | undefined;

        try {
            await Promise.race([
                this.sendCommand('list'),
                new Promise<never>((_, reject) => {
                    timeout = setTimeout(() => reject(new Error('RCON health check timed out')), timeoutMs);
                }),
            ]);
            return true;
        } catch {
            const connection = this.client;
            if (connection) {
                this.handleDisconnect(connection, 'RCON health check failed');
            }
            return false;
        } finally {
            if (timeout) clearTimeout(timeout);
        }
    }

    private handleDisconnect(connection: Rcon, reason: string): void {
        if (this.client !== connection) return;

        console.warn(`${reason} - Attempting to reconnect...`);
        this.client = null;
        this.isConnected = false;
        connection.disconnect().catch(() => undefined);
        this.scheduleReconnect();
    }

    private scheduleReconnect(): void {
        if (this.reconnectTimer) return;

        this.reconnectTimer = setTimeout(async () => {
            this.reconnectTimer = null;
            await this.connect();
        }, 5000);
    }

    private clearReconnectTimer(): void {
        if (!this.reconnectTimer) return;
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
    }
}
