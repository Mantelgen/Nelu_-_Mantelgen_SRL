import SftpClient from "ssh2-sftp-client";
import { offlineUUID } from "./utils";

export type WhitelistEntry = { uuid: string; name: string };

const WHITELIST_PATH = process.env.SFTP_WHITELIST_PATH ?? '/whitelist.json';

export class SFTPManager {
    sftp: SftpClient;
    isConnected: boolean = false;
    sftpConfig: SftpClient.ConnectOptions;
    
    constructor(config: SftpClient.ConnectOptions) {
        this.sftp = new SftpClient();
        this.sftpConfig = config;
    }

    async connect() {
        try {
            console.log('Trying to connect to SFTP server...');
            await this.sftp.connect(this.sftpConfig);
            this.isConnected = true;

            console.log('SFTP connection established!');

            this.sftp.on('close', () => this.handleDisconnect('SFTP connection closed!'));
            this.sftp.on('error', (err: Error) => this.handleDisconnect(`SFTP connection had error: ${err.message}`));


        } catch (err) {
            const error = err as Error;
            console.error('Failed to connect to SFTP:', error.message);
            this.scheduleReconnect();
        }
    }

    private async handleDisconnect(reason: string): Promise<void> {
    console.warn(`${reason} - Attempting to reconnect...`);
    this.isConnected = false;
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    setTimeout(async () => {
      await this.connect();
    }, 5000);
  }

  public async getClient(): Promise<SftpClient> {
    if (!this.isConnected) {
      throw new Error('SFTP client is currently disconnected. Please try again in a moment.');
    }
    return this.sftp;
  }

  public async readWhitelist(): Promise<WhitelistEntry[]> {
    const client = await this.getClient();
    const data = await client.get(WHITELIST_PATH) as Buffer;
    return JSON.parse(data.toString('utf-8'));
  }

  public async addToWhitelist(user: string): Promise<void> {
    const whitelist = await this.readWhitelist();
    if (!whitelist.some(entry => entry.name === user)) {
      whitelist.push({ name: user, uuid: offlineUUID(user) });
      await this.writeWhitelist(whitelist);
    }
  }

  public async writeWhitelist(whitelist: WhitelistEntry[]): Promise<void> {
    const client = await this.getClient();
    const buffer = Buffer.from(JSON.stringify(whitelist, null, 2), 'utf-8');
    await client.put(buffer, WHITELIST_PATH);
  }
}