import { BaseInteraction, ChatInputCommandInteraction, Client, Collection, Events, GatewayIntentBits, MessageFlags, SlashCommandBuilder, type SlashCommandOptionsOnlyBuilder } from "discord.js";
import SftpClient from "ssh2-sftp-client";
import { SFTPManager } from "./src/sftp";
import { RCONManager } from "./src/rcon";
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
client.once(Events.ClientReady, (readyClient) => {
    console.log(`Logged in as ${readyClient.user.tag}`)

    for (const guild of readyClient.guilds.cache.values()) {
        registerGuildCommands(guild, client.commands).catch((err) => {
            console.error(`Failed to register commands in ${guild.name}:`, err);
        });
    }

    void client.sftpManager.connect();
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
