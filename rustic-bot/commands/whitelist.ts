import { ChatInputCommandInteraction, MessageFlags, PermissionFlagsBits, SlashCommandBuilder, SlashCommandStringOption } from "discord.js";
import { MyClient } from "..";

export default {
    data: new SlashCommandBuilder()
            .setName('whitelist')
            .setDescription('Adaugă un membru în whitelist')
            .addStringOption(new SlashCommandStringOption()
                .setName('player')
                .setDescription('jucătorul să fie băgat în Sturmstadt')
                .setRequired(true)
            )
            .setDefaultMemberPermissions(PermissionFlagsBits.ManageRoles),
    async execute(interaction: ChatInputCommandInteraction) {
        const player = interaction.options.getString('player', true);
        await interaction.deferReply();

        const { sftpManager, rconManager } = interaction.client as MyClient;
        await sftpManager.addToWhitelist(player);
        await rconManager.forceReconnect();
        await rconManager.sendCommand('whitelist reload');

        await interaction.editReply({ content: `Am dat whitelist lui ${player}.` });
    }
}