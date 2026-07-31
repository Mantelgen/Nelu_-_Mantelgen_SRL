import asyncio
import re

import discord
from yt_dlp.utils import DownloadError

from app.config import SPOTIFY_PLAYLIST_RE, SPOTIFY_TRACK_RE
from app.models.music import Song
from app.services.media_clients import extract_stream_info, get_spotify_client


class MusicResolverService:
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

    async def resolve_query(self, query: str, requester: discord.Member) -> list[Song]:
        loop = asyncio.get_event_loop()

        if "open.spotify.com/track/" in query:
            sp = get_spotify_client()
            if sp is None:
                raise ValueError(
                    "Spotify credentials not configured. Add SPOTIFY_CLIENT_ID and "
                    "SPOTIFY_CLIENT_SECRET to your .env file."
                )
            match = SPOTIFY_TRACK_RE.search(query)
            if not match:
                raise ValueError("Could not parse Spotify track URL.")
            track_id = match.group(1)
            track = await loop.run_in_executor(None, lambda: sp.track(track_id))
            artists = ", ".join(a["name"] for a in track["artists"])
            search_query = f"{artists} - {track['name']}"
            return await self.search_youtube(search_query, requester)

        if "open.spotify.com/playlist/" in query:
            sp = get_spotify_client()
            if sp is None:
                raise ValueError(
                    "Spotify credentials not configured. Add SPOTIFY_CLIENT_ID and "
                    "SPOTIFY_CLIENT_SECRET to your .env file."
                )
            match = SPOTIFY_PLAYLIST_RE.search(query)
            if not match:
                raise ValueError("Could not parse Spotify playlist URL.")
            playlist_id = match.group(1)
            results = await loop.run_in_executor(None, lambda: sp.playlist_tracks(playlist_id))
            songs = []
            for item in results["items"]:
                track = item.get("track")
                if not track:
                    continue
                artists = ", ".join(a["name"] for a in track["artists"])
                search_query = f"{artists} - {track['name']}"
                try:
                    found = await self.search_youtube(search_query, requester)
                    songs.extend(found)
                except Exception:
                    pass
            return songs

        return await self.fetch_ytdl(query, requester)

    async def search_youtube(self, query: str, requester: discord.Member) -> list[Song]:
        return await self.fetch_ytdl(f"ytsearch:{query}", requester)

    async def fetch_ytdl(self, query: str, requester: discord.Member) -> list[Song]:
        loop = asyncio.get_event_loop()

        def _extract():
            return extract_stream_info(query)

        try:
            data = await loop.run_in_executor(None, _extract)
        except DownloadError as error:
            message = re.sub(r"\x1b\[[0-9;]*m", "", str(error))
            if "403" in message or self._is_auth_required_error(message):
                raise ValueError(
                    "YouTube requires authentication for this video (403/age-restricted). "
                    "Set YTDLP_COOKIES_BROWSER or YTDLP_COOKIES_FILE in your .env and restart the bot."
                ) from error
            if "requested format is not available" in message.lower():
                raise ValueError(
                    "YouTube did not provide a playable audio/video format for this link right now. "
                    "Try another mirror/upload, refresh cookies, or try again later."
                ) from error
            raise ValueError(f"yt-dlp error: {message}") from error

        if data is None:
            raise ValueError("Could not retrieve any information from that link/query.")

        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            if not entries:
                raise ValueError("No results found.")
            data = entries[0]

        url = data.get("webpage_url") or data.get("original_url") or data.get("url")
        title = data.get("title", "Unknown Title")
        duration = int(data.get("duration") or 0)
        return [Song(url=url, title=title, duration=duration, requester=requester)]
