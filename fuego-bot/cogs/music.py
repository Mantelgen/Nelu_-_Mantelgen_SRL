import random
from collections import deque
from typing import Optional

import discord
from discord.ext import commands

from app.config import (
    FFMPEG_EXECUTABLE,
    FFPROBE_EXECUTABLE,
    RADIO_STATIONS,
)
from app.models.music import GuildMusicState, Song
from app.services.music_resolver import MusicResolverService
from app.services.music_runtime import MusicRuntimeService
from app.ui.music_views import FuegoControlsView, PlayerControlsView

print(f"[INFO] Using ffmpeg:  {FFMPEG_EXECUTABLE}")
print(f"[INFO] Using ffprobe: {FFPROBE_EXECUTABLE}")

# ─── Music Cog ──────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildMusicState] = {}
        self.resolver = MusicResolverService()
        self.runtime = MusicRuntimeService(bot=bot, get_state=self.get_state)

    def get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    def _make_embed(self, title: str, description: Optional[str] = None, color: Optional[discord.Color] = None) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or discord.Color.blurple(),
        )
        embed.set_footer(text="Fuego Music")
        return embed

    def _song_embed(self, title: str, song: Song, color: Optional[discord.Color] = None) -> discord.Embed:
        embed = self._make_embed(title, color=color)
        embed.add_field(name="Track", value=song.title, inline=False)
        embed.add_field(name="Duration", value=song.format_duration(), inline=True)
        embed.add_field(name="Requested by", value=song.requester.display_name, inline=True)
        return embed


    # ── Commands ─────────────────────────────────────────────────────────────────

    @commands.command(name="join", aliases=["j"], help="Join your voice channel.")
    async def join(self, ctx: commands.Context):
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel first.")
        channel = ctx.author.voice.channel
        state = self.get_state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_connected():
            await state.voice_client.move_to(channel)
        else:
            state.voice_client = await channel.connect()
        await self.runtime.refresh_idle_disconnect(ctx.guild.id)
        await ctx.send(embed=self._make_embed("✅ Joined Voice", f"Connected to **{channel.name}**."))

    @commands.command(name="leave", aliases=["disconnect", "dc"], help="Leave the voice channel.")
    async def leave(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if not state.voice_client or not state.voice_client.is_connected():
            return await ctx.send("I'm not in a voice channel.")
        self.runtime.cancel_idle_disconnect(state)
        state.queue.clear()
        state.current = None
        await state.voice_client.disconnect()
        state.voice_client = None
        await ctx.send(embed=self._make_embed("👋 Disconnected", "Left the voice channel."))

    @commands.command(name="play", aliases=["p"], help="Play a YouTube/Spotify/SoundCloud link or search query.")
    async def play(self, ctx: commands.Context, *, query: str):
        # Auto-join if not connected
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel first.")

        state = self.get_state(ctx.guild.id)
        if not state.voice_client or not state.voice_client.is_connected():
            state.voice_client = await ctx.author.voice.channel.connect()
        self.runtime.cancel_idle_disconnect(state)

        async with ctx.typing():
            try:
                songs = await self.resolver.resolve_query(query, ctx.author)
            except ValueError as e:
                return await ctx.send(f"Error: {e}")
            except Exception as e:
                return await ctx.send(f"Something went wrong: {e}")

        if not songs:
            return await ctx.send("No results found.")

        should_start_now = not state.is_playing() and not state.is_paused()
        for song in songs:
            state.queue.append(song)

        if len(songs) == 1:
            song = songs[0]
            if should_start_now:
                status_message = await ctx.send(
                    embed=self._make_embed("⏳ Loading", "Preparing your track...", color=discord.Color.gold())
                )
                await self.runtime.advance_queue(ctx.guild.id)
                state = self.get_state(ctx.guild.id)
                if state.current:
                    await status_message.edit(
                        embed=self._song_embed("🎵 Now Playing", state.current, color=discord.Color.green()),
                        view=PlayerControlsView(self, ctx.guild.id),
                    )
                else:
                    message = state.last_error or "Could not start playback."
                    await status_message.edit(
                        embed=self._make_embed("⚠️ Playback Failed", message, color=discord.Color.red())
                    )
            else:
                await ctx.send(embed=self._song_embed("➕ Added to Queue", song, color=discord.Color.orange()))
        else:
            embed = self._make_embed(
                "📚 Playlist Queued",
                f"Added **{len(songs)}** songs to the queue.",
                color=discord.Color.blurple(),
            )
            await ctx.send(embed=embed)
            if should_start_now:
                await self.runtime.advance_queue(ctx.guild.id)

    @commands.command(name="fuego", help="Interrupt current track, play a random Fuego song, then resume previous track.")
    async def fuego(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)

        if not state.voice_client or not state.voice_client.is_connected():
            if not ctx.author.voice:
                return await ctx.send("You need to be in a voice channel first.")
            state.voice_client = await ctx.author.voice.channel.connect()
        self.runtime.cancel_idle_disconnect(state)

        async with ctx.typing():
            try:
                songs = await self.resolver.resolve_query(self.runtime.pick_fuego_query(state), ctx.author)
            except ValueError as error:
                return await ctx.send(f"Error: {error}")
            except Exception as error:
                return await ctx.send(f"Something went wrong: {error}")

        if not songs:
            return await ctx.send("Could not find a Fuego track right now.")

        fuego_song = songs[0]
        fuego_song.is_fuego = True
        interrupted_song = state.current if (state.current and (state.is_playing() or state.is_paused())) else None

        async with ctx.typing():
            try:
                fuego_song.prepared_source = await self.runtime.prepare_playback_source(fuego_song.url)
            except ValueError as error:
                return await ctx.send(f"Error preparing Fuego track: {error}")
            except Exception as error:
                return await ctx.send(f"Failed to prepare Fuego track: {error}")

        if interrupted_song:
            if state.is_playing():
                self.runtime.pause_tracking(state)
                state.voice_client.pause()

            elapsed_seconds = self.runtime.current_elapsed_seconds(state)
            if interrupted_song.duration > 1:
                interrupted_song.resume_at_seconds = min(elapsed_seconds, max(0, interrupted_song.duration - 1))
            else:
                interrupted_song.resume_at_seconds = elapsed_seconds
            interrupted_song.file_path = None
            interrupted_song.is_fuego = False
            state.interrupted_song = interrupted_song
            state.queue.appendleft(interrupted_song)
            state.queue.appendleft(fuego_song)
            state.skip_loop_once = True
            state.voice_client.stop()
            await ctx.send(
                embed=self._make_embed(
                    "LINISTE SCLAVILOR!!! MAESTRUL FUEGO CANTA",
                    f"Maestrul liric recita  **{fuego_song.title}** acum, ASA CA LINISTE PLEBEILOR",
                    color=discord.Color.orange(),
                ),
                view=FuegoControlsView(self, ctx.guild.id),
            )
            return

        state.interrupted_song = None
        state.queue.appendleft(fuego_song)
        if not state.is_playing() and not state.is_paused():
            status_message = await ctx.send(
                embed=self._make_embed("⏳ Loading", "Preparing Fuego track...", color=discord.Color.gold())
            )
            await self.runtime.advance_queue(ctx.guild.id)
            state = self.get_state(ctx.guild.id)
            if state.current:
                await status_message.edit(
                    embed=self._song_embed("🔥 Fuego Now Playing", state.current, color=discord.Color.orange()),
                    view=FuegoControlsView(self, ctx.guild.id) if state.current.is_fuego else PlayerControlsView(self, ctx.guild.id),
                )
            else:
                message = state.last_error or "Could not start Fuego playback."
                await status_message.edit(
                    embed=self._make_embed("⚠️ Playback Failed", message, color=discord.Color.red())
                )
        else:
            await ctx.send(embed=self._song_embed("➕ Fuego Added Next", fuego_song, color=discord.Color.orange()))

    @commands.command(name="radio", aliases=["stations"], help="Play a radio station by name, or provide a direct stream URL.")
    async def radio(self, ctx: commands.Context, *, station: Optional[str] = None):
        if not station or station.strip().lower() == "list":
            lines = [f"`{name}`" for name in sorted(set(RADIO_STATIONS.keys()))]
            embed = self._make_embed(
                "📻 Radio Stations",
                "Use `!radio <name>` or `!radio <stream_url>`.\n\n" + " • ".join(lines),
                color=discord.Color.teal(),
            )
            return await ctx.send(embed=embed)

        key = station.strip().lower()
        query = RADIO_STATIONS.get(key, station.strip())
        return await self.play(ctx, query=query)

    @commands.command(name="pause", help="Pause the current song.")
    async def pause(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if state.is_playing():
            self.runtime.pause_tracking(state)
            state.voice_client.pause()
            await ctx.send("Paused.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name="resume", aliases=["r"], help="Resume the paused song.")
    async def resume(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if state.is_paused():
            self.runtime.resume_tracking(state)
            state.voice_client.resume()
            await ctx.send("Resumed.")
        else:
            await ctx.send("Nothing is paused.")

    @commands.command(name="skip", aliases=["s"], help="Skip the current song.")
    async def skip(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if not state.is_playing() and not state.is_paused():
            return await ctx.send("Nothing is playing.")
        state.voice_client.stop()  # triggers _after_play → _advance_queue
        await ctx.send("Skipped.")

    @commands.command(name="stop", help="Stop playback and clear the queue.")
    async def stop(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        state.queue.clear()
        state.loop = False
        if state.voice_client and (state.is_playing() or state.is_paused()):
            state.voice_client.stop()
            state.current = None
        await self.runtime.refresh_idle_disconnect(ctx.guild.id)
        await ctx.send("Stopped and queue cleared.")

    @commands.command(name="queue", aliases=["q"], help="Show the current queue.")
    async def queue(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        embed = self._make_embed("🧾 Music Queue", color=discord.Color.blurple())

        if state.current:
            embed.add_field(
                name="Now Playing",
                value=f"**{state.current.title}**\n`{state.current.format_duration()}` • {state.current.requester.display_name}",
                inline=False,
            )
        else:
            embed.add_field(name="Now Playing", value="Nothing is currently playing.", inline=False)

        if state.queue:
            queue_lines = []
            for i, song in enumerate(list(state.queue)[:10], start=1):
                queue_lines.append(f"`{i}.` {song.title} • `{song.format_duration()}`")
            if len(state.queue) > 10:
                queue_lines.append(f"…and {len(state.queue) - 10} more")
            embed.add_field(name="Up Next", value="\n".join(queue_lines), inline=False)
        else:
            empty_text = "Queue is empty."
            if state.last_error:
                empty_text = f"Queue is empty.\nLast issue: {state.last_error}"
            embed.add_field(name="Up Next", value=empty_text, inline=False)

        embed.add_field(name="Loop", value="ON ♾️" if state.loop else "OFF", inline=True)
        embed.add_field(name="Queue Size", value=str(len(state.queue)), inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"], help="Show what's currently playing.")
    async def nowplaying(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if not state.current:
            return await ctx.send("Nothing is playing right now.")
        view = FuegoControlsView(self, ctx.guild.id) if state.current.is_fuego else PlayerControlsView(self, ctx.guild.id)
        await ctx.send(
            embed=self._song_embed("🎵 Now Playing", state.current, color=discord.Color.green()),
            view=view,
        )

    @commands.command(name="loop", aliases=["l"], help="Toggle loop for the current song.")
    async def loop(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        state.loop = not state.loop
        status = "ON" if state.loop else "OFF"
        await ctx.send(f"Loop is now **{status}**.")

    @commands.command(name="clear", help="Clear the queue without stopping current song.")
    async def clear(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        state.queue.clear()
        await self.runtime.refresh_idle_disconnect(ctx.guild.id)
        await ctx.send("Queue cleared.")

    @commands.command(name="remove", help="Remove a song from the queue by position.")
    async def remove(self, ctx: commands.Context, position: int):
        state = self.get_state(ctx.guild.id)
        if position < 1 or position > len(state.queue):
            return await ctx.send(f"Invalid position. Queue has {len(state.queue)} song(s).")
        queue_list = list(state.queue)
        removed = queue_list.pop(position - 1)
        state.queue = deque(queue_list)
        await ctx.send(f"Removed: **{removed.title}**")

    @commands.command(name="volume", aliases=["vol"], help="Set volume (0-100). Not supported with stream audio.")
    async def volume(self, ctx: commands.Context, vol: int):
        if not 0 <= vol <= 100:
            return await ctx.send("Volume must be between 0 and 100.")
        state = self.get_state(ctx.guild.id)
        if state.voice_client and state.voice_client.source:
            if isinstance(state.voice_client.source, discord.PCMVolumeTransformer):
                state.voice_client.source.volume = vol / 100
            else:
                state.voice_client.source = discord.PCMVolumeTransformer(
                    state.voice_client.source, volume=vol / 100
                )
            await ctx.send(f"Volume set to **{vol}%**.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name="shuffle", help="Shuffle the queue.")
    async def shuffle(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if len(state.queue) < 2:
            return await ctx.send("Not enough songs in the queue to shuffle.")
        queue_list = list(state.queue)
        random.shuffle(queue_list)
        state.queue = deque(queue_list)
        await ctx.send("Queue shuffled.")

    @commands.command(name="musichelp", aliases=["mh"], help="Show all music commands.")
    async def musichelp(self, ctx: commands.Context):
        prefix = ctx.prefix
        embed = self._make_embed("🎼 Music Commands", color=discord.Color.blurple())
        embed.add_field(
            name="Playback",
            value=(
                f"`{prefix}play <link/search>`\n"
                f"`{prefix}radio <name|url>` (`{prefix}radio list`)\n"
                f"`{prefix}pause` • `{prefix}resume` • `{prefix}skip` • `{prefix}stop` • `{prefix}fuego`\n"
                f"`{prefix}nowplaying` • `{prefix}volume <0-100>`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Queue",
            value=(
                f"`{prefix}queue` • `{prefix}shuffle` • `{prefix}clear`\n"
                f"`{prefix}remove <#>` • `{prefix}loop`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Voice",
            value=f"`{prefix}join` • `{prefix}leave`",
            inline=False,
        )
        embed.add_field(
            name="Quick Tip",
            value=f"Use `{prefix}nowplaying` for controls (Start • Stop • Skip).",
            inline=False,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
