import { loadCommands } from "./src/utils";
import { Collection, REST, Routes } from 'discord.js';
import { clientId, guildIds } from './config.json';
import type { Command } from ".";

const commands: Collection<string, Command> = loadCommands();

const rest = new REST().setToken(process.env.APP_TOKEN as string);

(async () => {
	try {
		console.log(`Started refreshing ${commands.size} application (/) commands.`);
		
		for (const guildId of guildIds) {
			const data = await rest.put(Routes.applicationGuildCommands(clientId, guildId), { body: commands.map((command) => command.data.toJSON()) });
			console.log(`Successfully reloaded ${data.length} application (/) commands for guild ${guildId}.`);
		}
	} catch (error) {
		console.error(error);
	}
})();