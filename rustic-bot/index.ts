import { BaseInteraction, ChatInputCommandInteraction, Client, Collection, EmbedBuilder, Events, GatewayIntentBits, MessageFlags, SlashCommandBuilder, type SlashCommandOptionsOnlyBuilder } from "discord.js";
import SftpClient from "ssh2-sftp-client";
import { SFTPManager } from "./src/sftp";
import { RCONManager } from "./src/rcon";
import { ServerStatusMonitor, type ServerStatusSnapshot } from "./src/serverStatus";
import { loadCommands } from "./src/utils";

export interface Command {
    data: SlashCommandBuilder | SlashCommandOptionsOnlyBuilder;
    execute: (interaction: ChatInputCommandInteraction) => Promise<void> | void;
}

export class MyClient extends Client {
    commands: Collection<string, Command> = new Collection();
    sftpManager!: SFTPManager;
    rconManager!: RCONManager;
    statusMonitor!: ServerStatusMonitor;
}
const client = new MyClient({intents: [GatewayIntentBits.Guilds]})

client.commands = loadCommands();

const sftpConfig: SftpClient.ConnectOptions = {
    host: process.env.SFTP_HOST,
    port: process.env.SFTP_PORT ? parseInt(process.env.SFTP_PORT, 10) : 2022,
    username: process.env.SFTP_USER,
    password: process.env.SFTP_PASSWORD,
};

client.sftpManager = new SFTPManager(sftpConfig);
client.rconManager = new RCONManager();
client.statusMonitor = new ServerStatusMonitor(
    client.rconManager,
    announceStoppedServer,
    readPositiveNumber('STATUS_CHECK_INTERVAL_SECONDS', 30) * 1000,
    readPositiveNumber('STATUS_CHECK_TIMEOUT_MS', 5000),
);

client.once(Events.ClientReady, async (readyClient) => {
    console.log(`Logged in as ${readyClient.user.tag}`)

    // Whitelist/SFTP availability must not prevent status monitoring from
    // starting. RCON health checks reconnect as needed by themselves.
    void client.sftpManager.connect();
    await client.statusMonitor.start();
})

client.on(Events.InteractionCreate, async (interaction: BaseInteraction) => {
    if (!interaction.isChatInputCommand()) return;
    const command = (interaction.client as MyClient).commands.get(interaction.commandName)

    if (!command) return;

    try {
        await command.execute(interaction);
    } catch (err) {
        const error = err as Error;
        console.error(error);
		if (interaction.deferred) {
			await interaction.editReply({
				content: 'There was an error while executing this command!',
				embeds: [],
			});
		} else if (interaction.replied) {
			await interaction.followUp({
				content: 'There was an error while executing this command!',
				flags: MessageFlags.Ephemeral,
			});
		} else {
			await interaction.reply({
				content: 'There was an error while executing this command!',
				flags: MessageFlags.Ephemeral,
			});
		}
    }
})

client.login(process.env.APP_TOKEN)

function readPositiveNumber(name: string, fallback: number): number {
    const value = Number(process.env[name]);
    return Number.isFinite(value) && value > 0 ? value : fallback;
}

async function announceStoppedServer(current: ServerStatusSnapshot): Promise<void> {
    if (current.status !== 'stopped') return;

    const channelId = process.env.STATUS_CHANNEL_ID;
    if (!channelId) {
        console.warn('The server stopped, but STATUS_CHANNEL_ID is not configured.');
        return;
    }

    const channel = await client.channels.fetch(channelId);
    if (!channel?.isSendable()) {
        console.error(`STATUS_CHANNEL_ID (${channelId}) is not a text channel the bot can access.`);
        return;
    }

    const embed = new EmbedBuilder()
        .setColor(0xED4245)
        .setTitle('🔴 Minecraft server is offline')
        .setDescription('The server stopped responding to health checks. It may have stopped or crashed.')
        .setTimestamp(current.checkedAt);

    await channel.send({ embeds: [embed] });
}
