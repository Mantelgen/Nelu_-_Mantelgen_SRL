import {
    ChatInputCommandInteraction,
    EmbedBuilder,
    MessageFlags,
    PermissionFlagsBits,
    SlashCommandBuilder,
} from 'discord.js';
import type { MyClient } from '..';

export default {
    data: new SlashCommandBuilder()
        .setName('status')
        .setDescription('Shows whether the Minecraft server is active or stopped'),
    async execute(interaction: ChatInputCommandInteraction) {
        // The server status is public so everyone in the channel can see it.
        await interaction.deferReply();

        const { statusMonitor, rconManager } = interaction.client as MyClient;
        const snapshot = await statusMonitor.checkNow();
        const playerList = rconManager.getLastPlayerList();
        const isActive = snapshot.status === 'active';

        const statusEmbed = new EmbedBuilder()
            .setColor(isActive ? 0x57F287 : 0xED4245)
            .setTitle('Minecraft Server Status')
            .addFields({
                name: 'Status',
                value: isActive ? '🟢 Active' : '🔴 Stopped',
                inline: true,
            })
            .setFooter({ text: 'Last checked' })
            .setTimestamp(snapshot.checkedAt);

        if (isActive && playerList) {
            statusEmbed.addFields({
                name: 'Players Online',
                value: `${playerList.onlinePlayers}/${playerList.maxPlayers}`,
                inline: true,
            });
        }

        await interaction.editReply({ embeds: [statusEmbed] });

        if (!canViewPlayerNames(interaction)) return;

        const playerEmbed = new EmbedBuilder()
            .setColor(0x5865F2)
            .setTitle('Online Minecraft Players')
            .setDescription(
                playerList
                    ? formatPlayerNames(playerList.players)
                    : 'The player list is currently unavailable.',
            );

        if (playerList) {
            playerEmbed.setFooter({
                text: `${playerList.onlinePlayers}/${playerList.maxPlayers} players online`,
            });
        }

        await interaction.followUp({
            embeds: [playerEmbed],
            flags: MessageFlags.Ephemeral,
        });
    },
};

function canViewPlayerNames(interaction: ChatInputCommandInteraction): boolean {
    if (interaction.memberPermissions?.has(PermissionFlagsBits.Administrator)) {
        return true;
    }

    if (!interaction.inCachedGuild()) return false;

    const configuredModeratorRoleId = process.env.MOD_ROLE_ID?.trim();

    return interaction.member.roles.cache.some((role) =>
        (configuredModeratorRoleId && role.id === configuredModeratorRoleId)
        || role.name.toLocaleLowerCase() === 'moderatori',
    );
}

function formatPlayerNames(players: string[]): string {
    if (players.length === 0) return 'No players are currently online.';

    const maxLength = 3_900;
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
