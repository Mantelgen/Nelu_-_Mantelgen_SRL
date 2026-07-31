from typing import Any

import discord


class PlayerControlsView(discord.ui.View):
    def __init__(self, music_cog: Any, guild_id: int):
        super().__init__(timeout=300)
        self.music_cog = music_cog
        self.guild_id = guild_id

    async def _get_state(self, interaction: discord.Interaction):
        state = self.music_cog.get_state(self.guild_id)
        if not state.voice_client or not state.voice_client.is_connected():
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
            return None
        return state

    @discord.ui.button(label="Start", emoji="▶️", style=discord.ButtonStyle.success)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._get_state(interaction)
        if state is None:
            return
        if state.is_paused():
            self.music_cog._resume_tracking(state)
            state.voice_client.resume()
            await interaction.response.send_message("Started.", ephemeral=True)
        elif state.is_playing():
            await interaction.response.send_message("Already playing.", ephemeral=True)
        elif state.queue:
            await self.music_cog._advance_queue(self.guild_id)
            await interaction.response.send_message("Started.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing to start.", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._get_state(interaction)
        if state is None:
            return
        if state.is_playing() or state.is_paused():
            state.queue.clear()
            state.loop = False
            state.interrupted_song = None
            state.voice_client.stop()
            state.current = None
            await interaction.response.send_message("Stopped and queue cleared.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._get_state(interaction)
        if state is None:
            return
        if state.is_playing() or state.is_paused():
            state.voice_client.stop()
            await interaction.response.send_message("Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)


class FuegoControlsView(PlayerControlsView):
    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._get_state(interaction)
        if state is None:
            return
        if state.is_playing():
            self.music_cog._pause_tracking(state)
            state.voice_client.pause()
            await interaction.response.send_message("Paused.", ephemeral=True)
        elif state.is_paused():
            await interaction.response.send_message("Already paused.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

