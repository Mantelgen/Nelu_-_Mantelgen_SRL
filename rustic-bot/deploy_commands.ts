import { Client, Events, GatewayIntentBits } from 'discord.js';
import { registerGuildCommands } from './src/registerCommands';
import { loadCommands } from './src/utils';

const token = process.env.APP_TOKEN;
if (!token) throw new Error('APP_TOKEN must be configured.');

const client = new Client({ intents: [GatewayIntentBits.Guilds] });
const commands = loadCommands();

client.once(Events.ClientReady, async (readyClient) => {
    try {
        for (const guild of readyClient.guilds.cache.values()) {
            await registerGuildCommands(guild, commands);
        }
    } finally {
        readyClient.destroy();
    }
});

await client.login(token);
