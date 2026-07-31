import { Collection } from 'discord.js';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'crypto';
import type { Command } from '..';

const commandsPath = path.join(__dirname, '../commands');

export function loadCommands(): Collection<string, Command> {
    const commands: Collection<string, Command> = new Collection();

    const commandFiles = fs.readdirSync(commandsPath).filter((file) => file.endsWith('.ts'));

    for (const file of commandFiles) {
        const filePath = path.join(commandsPath, file);
        
        const module = require(filePath);
        const command = module.default || module;

        if (command && 'data' in command && 'execute' in command) {
            commands.set(command.data.name, command);
        } else {
            console.log(`[WARNING] The command at ${filePath} is missing a required "data" or "execute" property.`);
        }
    }

    return commands;
}

export function offlineUUID(name: string): string {
    const hash = createHash('md5').update(`OfflinePlayer:${name}`, 'utf8').digest();
    hash[6] = (hash[6] & 0x0f) | 0x30;
    hash[8] = (hash[8] & 0x3f) | 0x80;
    const h = hash.toString('hex');
    return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20,32)}`;
}