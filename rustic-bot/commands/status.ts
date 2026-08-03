import {
    ChatInputCommandInteraction,
    EmbedBuilder,
    MessageFlags,
    SlashCommandBuilder,
} from 'discord.js';
import type { MyClient } from '..';

export default {
    data: new SlashCommandBuilder()
        .setName('status')
        .setDescription('Shows whether the Minecraft server is active or stopped'),
    async execute(interaction: ChatInputCommandInteraction) {
        // One private response prevents command use from filling the channel.
        await interaction.deferReply({ flags: MessageFlags.Ephemeral });

        const { rconManager } = interaction.client as MyClient;
        const isActive = await rconManager.checkHealth();
        const checkedAt = new Date();
        const playerList = rconManager.getLastPlayerList();

        const statusEmbed = new EmbedBuilder()
            .setColor(isActive ? 0x57F287 : 0xED4245)
            .setTitle('Minecraft Server Status')
            .addFields({
                name: 'Status',
                value: isActive ? '🟢 Active' : '🔴 Stopped',
                inline: true,
            })
            .setFooter({ text: 'Last checked' })
            .setTimestamp(checkedAt);

        if (isActive && playerList) {
            statusEmbed.addFields(
                {
                    name: 'Players Online',
                    value: `${playerList.onlinePlayers}/${playerList.maxPlayers}`,
                    inline: true,
                },
                {
                    name: 'Online Players',
                    value: formatPlayerNames(playerList.players),
                },
            );
        } else if (isActive) {
            statusEmbed.addFields({
                name: 'Online Players',
                value: 'The player list is currently unavailable.',
            });
        }

        await interaction.editReply({ embeds: [statusEmbed] });
    },
};

function formatPlayerNames(players: string[]): string {
    if (players.length === 0) return 'No players are currently online.';

    // Discord embed fields are limited to 1,024 characters.
    const maxLength = 1_000;
    const visible: string[] = [];

    for (const player of players) {
        const candidate = [...visible, player].join(', ');
        if (candidate.length > maxLength) break;
        visible.push(player);
    }

    const hiddenCount = players.length - visible.length;
    return hiddenCount > 0
        ? `${visible.join(', ')}\n…and ${hiddenCount} more.`
        : visible.join(', ');
}
