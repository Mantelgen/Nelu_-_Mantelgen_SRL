import { ChatInputCommandInteraction, EmbedBuilder, MessageFlags, SlashCommandBuilder } from 'discord.js';
import type { MyClient } from '..';

export default {
    data: new SlashCommandBuilder()
        .setName('status')
        .setDescription('Shows whether the Minecraft server is active or stopped'),
    async execute(interaction: ChatInputCommandInteraction) {
        await interaction.deferReply({ flags: MessageFlags.Ephemeral });

        const { statusMonitor } = interaction.client as MyClient;
        const snapshot = statusMonitor
            ? await statusMonitor.checkNow()
            : { status: 'stopped' as const, checkedAt: new Date() };
        const isActive = snapshot.status === 'active';

        const embed = new EmbedBuilder()
            .setColor(isActive ? 0x57F287 : 0xED4245)
            .setTitle('Minecraft Server Status')
            .addFields({
                name: 'Status',
                value: isActive ? '🟢 Active' : '🔴 Stopped',
                inline: true,
            })
            .setFooter({ text: 'Last checked' })
            .setTimestamp(snapshot.checkedAt);

        await interaction.editReply({ embeds: [embed] });
    },
};
