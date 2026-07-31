import { loadCommands } from "./src/utils";
import { Collection, REST, Routes } from 'discord.js';
import type { Command } from ".";

const commands: Collection<string, Command> = loadCommands();
const clientId = process.env.DISCORD_CLIENT_ID;
const guildIds = (process.env.DISCORD_GUILD_IDS ?? '')
	.split(',')
	.map((guildId) => guildId.trim())
	.filter(Boolean);

if (!process.env.APP_TOKEN || !clientId || guildIds.length === 0) {
	throw new Error('APP_TOKEN, DISCORD_CLIENT_ID, and DISCORD_GUILD_IDS must be configured.');
}

const rest = new REST().setToken(process.env.APP_TOKEN);

(async () => {
	try {
		console.log(`Started refreshing ${commands.size} application (/) commands.`);

		for (const guildId of guildIds) {
			const data = await rest.put(
				Routes.applicationGuildCommands(clientId, guildId),
				{ body: commands.map((command) => command.data.toJSON()) },
			) as unknown[];
			console.log(`Successfully reloaded ${data.length} application (/) commands for guild ${guildId}.`);
		}
	} catch (error) {
		console.error(error);
	}
})();
