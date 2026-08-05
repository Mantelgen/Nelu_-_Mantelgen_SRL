import asyncio
import random
import re
from collections import deque
from collections.abc import Callable
from pathlib import Path

import discord
from yt_dlp.utils import DownloadError

from app.config import (
    FFMPEG_EXECUTABLE,
    FFMPEG_OPTIONS,
    FUEGO_OLDIES_QUERIES,
    MUSIC_IDLE_TIMEOUT_MINUTES,
    MUSIC_IDLE_TIMEOUT_SECONDS,
)
from app.models.music import GuildMusicState, Song
from app.services.media_clients import extract_download_info, extract_stream_info


class MusicRuntimeService:
    def __init__(
        self,
        get_state: Callable[[int], GuildMusicState],
    ):
        self.get_state = get_state

    def mark_song_started(self, state: GuildMusicState):
        state.current_started_at = asyncio.get_running_loop().time()
        state.current_pause_started_at = None
        state.current_paused_total = 0.0

    def pause_tracking(self, state: GuildMusicState):
        if state.current_pause_started_at is None:
            state.current_pause_started_at = asyncio.get_running_loop().time()

    def resume_tracking(self, state: GuildMusicState):
        if state.current_pause_started_at is not None:
            now = asyncio.get_running_loop().time()
            state.current_paused_total += max(0.0, now - state.current_pause_started_at)
            state.current_pause_started_at = None

    def current_elapsed_seconds(self, state: GuildMusicState) -> int:
        if state.current_started_at is None:
            return 0
        now = asyncio.get_running_loop().time()
        paused_window = state.current_paused_total
        if state.current_pause_started_at is not None:
            paused_window += max(0.0, now - state.current_pause_started_at)
        elapsed = max(0.0, now - state.current_started_at - paused_window)
        return int(elapsed)

    @staticmethod
    def _is_auth_required_error(message: str) -> bool:
        lower = message.lower()
        return (
            "sign in to confirm your age" in lower
            or "use --cookies" in lower
            or "age-restricted" in lower
            or "age restricted" in lower
            or "login required" in lower
            or "authentication" in lower
        )

    def pick_fuego_query(self, state: GuildMusicState) -> str:
        candidates = [query for query in FUEGO_OLDIES_QUERIES if query != state.last_fuego_query]
        if not candidates:
            candidates = list(FUEGO_OLDIES_QUERIES)
        picked = random.choice(candidates)
        state.last_fuego_query = picked
        return picked

    def close_fuego_and_resume(self, guild_id: int) -> tuple[bool, str]:
        state = self.get_state(guild_id)
        if not state.current or not state.current.is_fuego:
            return False, "Current track is not a Fuego interrupt."

        if state.interrupted_song:
            queue_list = [song for song in state.queue if song is not state.interrupted_song]
            state.queue = deque(queue_list)
            state.queue.appendleft(state.interrupted_song)
            message = "Ended Fuego and resumed the previous track."
        else:
            message = "Ended Fuego playback."
        state.skip_loop_once = True

        if state.voice_client and (state.is_playing() or state.is_paused()):
            state.voice_client.stop()

        return True, message

    def cancel_idle_disconnect(self, state: GuildMusicState):
        if state.idle_disconnect_task and not state.idle_disconnect_task.done():
            state.idle_disconnect_task.cancel()
        state.idle_disconnect_task = None

    def is_idle_for_disconnect(self, state: GuildMusicState) -> bool:
        return (
            state.voice_client is not None
            and state.voice_client.is_connected()
            and not state.is_playing()
            and not state.is_paused()
            and state.current is None
            and len(state.queue) == 0
        )

    async def idle_disconnect_after(self, guild_id: int):
        state = self.get_state(guild_id)
        task = asyncio.current_task()
        try:
            await asyncio.sleep(MUSIC_IDLE_TIMEOUT_SECONDS)
            if not self.is_idle_for_disconnect(state):
                return
            await state.voice_client.disconnect()
            state.voice_client = None
            state.current = None
            state.interrupted_song = None
            print(f"[INFO] Auto-disconnected from voice in guild {guild_id} after {MUSIC_IDLE_TIMEOUT_MINUTES} min idle")
        except asyncio.CancelledError:
            return
        except Exception as error:  # noqa: BLE001 - background task must not escape.
            print(f"[WARN] Idle auto-disconnect failed in guild {guild_id}: {error}")
        finally:
            if state.idle_disconnect_task is task:
                state.idle_disconnect_task = None

    async def refresh_idle_disconnect(self, guild_id: int):
        state = self.get_state(guild_id)
        self.cancel_idle_disconnect(state)
        if MUSIC_IDLE_TIMEOUT_SECONDS <= 0:
            return
        if self.is_idle_for_disconnect(state):
            state.idle_disconnect_task = asyncio.create_task(self.idle_disconnect_after(guild_id))

    async def download_track(self, track_url: str) -> tuple[str, dict]:
        loop = asyncio.get_event_loop()

        def _extract():
            return extract_download_info(track_url)

        try:
            data = await loop.run_in_executor(None, _extract)
        except DownloadError as error:
            message = re.sub(r"\x1b\[[0-9;]*m", "", str(error))
            if "403" in message or self._is_auth_required_error(message):
                raise ValueError(
                    "YouTube requires authentication for this video (403/age-restricted). "
                    "Configure YTDLP_COOKIES_BROWSER or YTDLP_COOKIES_FILE in your .env."
                ) from error
            raise

        if data is None:
            raise ValueError("Could not download track.")

        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            if not entries:
                raise ValueError("No playable entries found.")
            data = entries[0]

        file_path = data.get("requested_downloads", [{}])[0].get("filepath") or data.get("filepath")
        if not file_path:
            raise ValueError("Downloaded file path is missing.")

        return file_path, data

    async def resolve_stream_track(self, track_url: str) -> tuple[str, dict, dict]:
        loop = asyncio.get_event_loop()

        def _extract():
            return extract_stream_info(track_url)

        try:
            data = await loop.run_in_executor(None, _extract)
        except DownloadError as error:
            message = re.sub(r"\x1b\[[0-9;]*m", "", str(error))
            if "403" in message or self._is_auth_required_error(message):
                raise ValueError(
                    "YouTube requires authentication for this video (403/age-restricted). "
                    "Configure YTDLP_COOKIES_BROWSER or YTDLP_COOKIES_FILE in your .env."
                ) from error
            raise ValueError(f"Could not resolve stream URL: {message}") from error

        if data is None:
            raise ValueError("Could not resolve stream URL.")

        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            if not entries:
                raise ValueError("No playable stream entries found.")
            data = entries[0]

        stream_url = data.get("url")
        if not stream_url:
            raise ValueError("Stream URL missing from extractor output.")

        headers = data.get("http_headers") or {}
        return stream_url, data, headers

    def build_header_blob(self, headers: dict) -> str:
        allowed = ["User-Agent", "Referer", "Origin", "Cookie"]
        lines = []
        for key in allowed:
            value = headers.get(key) or headers.get(key.lower())
            if value:
                safe = str(value).replace("\r", " ").replace("\n", " ")
                lines.append(f"{key}: {safe}\r\n")
        return "".join(lines)

    def build_before_options(self, mode: str, resume_at_seconds: int, headers: dict | None = None) -> str:
        if mode == "stream":
            before_options = "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            if headers:
                header_blob = self.build_header_blob(headers)
                if header_blob:
                    escaped = header_blob.replace('"', '\\"')
                    before_options = f"{before_options} -headers \"{escaped}\""
        else:
            before_options = FFMPEG_OPTIONS["before_options"]

        if resume_at_seconds > 0:
            before_options = f"{before_options} -ss {resume_at_seconds}"

        return before_options

    async def prepare_playback_source(self, track_url: str) -> tuple[str, dict, str, dict]:
        try:
            stream_url, stream_info, headers = await self.resolve_stream_track(track_url)
            return stream_url, stream_info, "stream", headers
        except Exception as stream_error:  # noqa: BLE001 - download is the universal fallback.
            print(f"[WARN] Stream-first prep failed, falling back to download: {stream_error}")

        file_path, file_info = await self.download_track(track_url)
        return file_path, file_info, "file", {}

    @staticmethod
    def cleanup_download(song: Song) -> None:
        if song.file_path:
            try:
                Path(song.file_path).unlink(missing_ok=True)
            except OSError as cleanup_error:
                print(f"[WARN] Failed to clean up audio file: {cleanup_error}")
            finally:
                song.file_path = None

    def cleanup_song(self, song: Song) -> None:
        self.cleanup_download(song)
        if song.prepared_source is not None:
            source_input, _, source_mode, _ = song.prepared_source
            if source_mode == "file":
                try:
                    Path(source_input).unlink(missing_ok=True)
                except OSError as cleanup_error:
                    print(f"[WARN] Failed to clean up prepared audio file: {cleanup_error}")
            song.prepared_source = None

    def clear_queue(self, state: GuildMusicState) -> None:
        while state.queue:
            song = state.queue.popleft()
            if state.interrupted_song is song:
                state.interrupted_song = None
            self.cleanup_song(song)

    async def handle_track_finished(self, guild_id: int, song: Song, error) -> None:
        state = self.get_state(guild_id)
        self.cleanup_download(song)
        if error:
            state.last_error = str(error)
            print(f"[Music] Playback error in guild {guild_id}: {error}")

        # Ignore a stale callback if another source has already become current.
        if state.current is not song and state.current is not None:
            return

        state.current_started_at = None
        state.current_pause_started_at = None
        state.current_paused_total = 0.0
        await self.advance_queue(guild_id)

    async def advance_queue(self, guild_id: int):
        state = self.get_state(guild_id)
        async with state.advance_lock:
            await self._advance_queue_locked(guild_id, state)

    async def _advance_queue_locked(self, guild_id: int, state: GuildMusicState):

        if not state.voice_client or not state.voice_client.is_connected():
            state.current = None
            self.cancel_idle_disconnect(state)
            return

        if state.skip_loop_once:
            state.skip_loop_once = False
        elif state.loop and state.current:
            state.queue.appendleft(state.current)

        while state.queue:
            next_song = state.queue.popleft()
            state.current = next_song

            if state.interrupted_song is next_song:
                state.interrupted_song = None

            try:
                if next_song.prepared_source is not None:
                    source_input, stream_info, source_mode, source_headers = next_song.prepared_source
                    next_song.prepared_source = None
                else:
                    source_input, stream_info, source_mode, source_headers = await self.prepare_playback_source(next_song.url)
            except Exception as error:  # noqa: BLE001 - skip an unplayable queue item.
                print(f"[WARN] Failed to prepare '{next_song.title}': {error}")
                state.last_error = f"Failed to prepare '{next_song.title}': {error}"
                state.current = None
                continue

            next_song.title = stream_info.get("title", next_song.title)
            resolved_duration = stream_info.get("duration")
            if resolved_duration is not None:
                next_song.duration = int(resolved_duration)
            next_song.file_path = source_input if source_mode == "file" else None
            state.last_error = None

            print(f"[INFO] Playing: {next_song.title}")
            print(f"[INFO] ffmpeg: {FFMPEG_EXECUTABLE}")
            print(f"[INFO] source mode: {source_mode}")

            try:
                before_options = self.build_before_options(
                    source_mode,
                    next_song.resume_at_seconds,
                    headers=source_headers,
                )

                ffmpeg_source = discord.FFmpegPCMAudio(
                    source_input,
                    executable=FFMPEG_EXECUTABLE,
                    before_options=before_options,
                    options=FFMPEG_OPTIONS["options"],
                )
                source = discord.PCMVolumeTransformer(ffmpeg_source, volume=state.volume)
                event_loop = asyncio.get_running_loop()

                def after_playback(error, loop=event_loop, played_song=next_song):
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(
                            self.handle_track_finished(guild_id, played_song, error)
                        )
                    )

                state.voice_client.play(source, after=after_playback)
                self.mark_song_started(state)
                self.cancel_idle_disconnect(state)
                if next_song.is_fuego:
                    # Fuego is an interrupt and must yield to the previous track,
                    # even when normal playback looping is enabled.
                    state.skip_loop_once = True
                next_song.resume_at_seconds = 0
                return
            except Exception as error:  # noqa: BLE001 - move on if FFmpeg cannot start.
                print(f"[WARN] Failed to start ffmpeg for '{next_song.title}': {error}")
                state.last_error = f"Failed to start '{next_song.title}': {error}"
                self.cleanup_download(next_song)
                state.current = None
                continue

        state.current = None
        state.current_started_at = None
        state.current_pause_started_at = None
        state.current_paused_total = 0.0
        await self.refresh_idle_disconnect(guild_id)
