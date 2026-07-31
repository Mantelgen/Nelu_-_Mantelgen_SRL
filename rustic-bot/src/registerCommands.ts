import type { Collection, Guild } from 'discord.js';
import type { Command } from '..';

export async function registerGuildCommands(
    guild: Guild,
    commands: Collection<string, Command>,
): Promise<void> {
    const registered = await guild.commands.set(
        commands.map((command) => command.data.toJSON()),
    );

    console.log(`Registered ${registered.size} slash commands in ${guild.name}.`);
}
