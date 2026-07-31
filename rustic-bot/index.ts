import { BaseInteraction, ChatInputCommandInteraction, Client, Collection, EmbedBuilder, Events, GatewayIntentBits, MessageFlags, SlashCommandBuilder, type SlashCommandOptionsOnlyBuilder } from "discord.js";
import SftpClient from "ssh2-sftp-client";
import { SFTPManager } from "./src/sftp";
import { RCONManager } from "./src/rcon";
import { ServerStatusMonitor, type ServerStatusSnapshot } from "./src/serverStatus";
import { registerGuildCommands } from "./src/registerCommands";
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

    for (const guild of readyClient.guilds.cache.values()) {
        registerGuildCommands(guild, client.commands).catch((err) => {
            console.error(`Failed to register commands in ${guild.name}:`, err);
        });
    }

    // Whitelist/SFTP availability must not prevent status monitoring from
    // starting. RCON health checks reconnect as needed by themselves.
    void client.sftpManager.connect();
    await client.statusMonitor.start();
})

client.on(Events.GuildCreate, (guild) => {
    registerGuildCommands(guild, client.commands).catch((err) => {
        console.error(`Failed to register commands in ${guild.name}:`, err);
    });
});

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

const notifiedStatusChannels = new Set<string>();

async function announceStoppedServer(current: ServerStatusSnapshot): Promise<void> {
    if (current.status !== 'stopped') {
        notifiedStatusChannels.clear();
        return;
    }

    const channelIds = getStatusChannelIds();
    if (channelIds.length === 0) {
        console.warn('The server stopped, but no status alert channels are configured.');
        return;
    }

    const embed = new EmbedBuilder()
        .setColor(0xED4245)
        .setTitle('🔴 Minecraft server is offline')
        .setDescription('The server stopped responding to health checks. It may have stopped or crashed.')
        .setTimestamp(current.checkedAt);

    const failedChannelIds: string[] = [];

    for (const channelId of channelIds) {
        if (notifiedStatusChannels.has(channelId)) continue;

        try {
            const channel = await client.channels.fetch(channelId);
            if (!channel?.isSendable()) {
                throw new Error('channel is not accessible or sendable');
            }

            await channel.send({ embeds: [embed] });
            notifiedStatusChannels.add(channelId);
        } catch (err) {
            console.error(`Failed to alert status channel ${channelId}:`, err);
            failedChannelIds.push(channelId);
        }
    }

    if (failedChannelIds.length > 0) {
        throw new Error(`Failed to alert ${failedChannelIds.length} configured status channel(s).`);
    }
}

function getStatusChannelIds(): string[] {
    const configuredIds = (process.env.STATUS_CHANNEL_ID ?? '').split(',');

    return [...new Set(configuredIds.map((id) => id.trim()).filter(Boolean))];
}
