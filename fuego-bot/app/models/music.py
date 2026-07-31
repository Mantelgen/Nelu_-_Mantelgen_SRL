import asyncio
from collections import deque

import discord


class Song:
    def __init__(self, url: str, title: str, duration: int, requester: discord.Member):
        self.url = url
        self.title = title
        self.duration = duration
        self.requester = requester
        self.file_path: str | None = None
        self.prepared_source: tuple[str, dict, str, dict] | None = None
        self.resume_at_seconds = 0
        self.is_fuego = False

    def format_duration(self) -> str:
        mins, secs = divmod(self.duration, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"


class GuildMusicState:
    def __init__(self):
        self.queue: deque[Song] = deque()
        self.current: Song | None = None
        self.voice_client: discord.VoiceClient | None = None
        self.loop = False
        self.skip_loop_once = False
        self.last_error: str | None = None
        self.last_fuego_query: str | None = None
        self.interrupted_song: Song | None = None
        self.current_started_at: float | None = None
        self.current_pause_started_at: float | None = None
        self.current_paused_total = 0.0
        self.idle_disconnect_task: asyncio.Task | None = None
        self._play_next_event = asyncio.Event()

    def is_playing(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_playing()

    def is_paused(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_paused()
