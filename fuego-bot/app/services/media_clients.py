import os
from copy import deepcopy

import yt_dlp
from yt_dlp.utils import DownloadError

from app.config import YTDL_DOWNLOAD_OPTIONS, YTDL_OPTIONS


def get_spotify_client():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        return spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
            )
        )
    except Exception as error:  # noqa: BLE001 - Spotify support is optional.
        print(f"[WARN] Spotify client could not be initialized: {error}")
        return None


class _QuietLogger:
    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        if "requested format is not available" not in message.lower():
            print(message)


def _with_quiet_logger(options: dict) -> dict:
    patched = deepcopy(options)
    patched["logger"] = _QuietLogger()
    return patched


def _is_format_unavailable(error: Exception) -> bool:
    return "requested format is not available" in str(error).lower()


def _is_dpapi_cookie_error(error: Exception) -> bool:
    return "failed to decrypt with dpapi" in str(error).lower()


def _fallback_options(options: dict) -> list[dict]:
    relaxed = deepcopy(options)
    relaxed.pop("extractor_args", None)

    candidates = []
    for selector in ("bestaudio/best", "best"):
        candidate = deepcopy(relaxed)
        candidate["format"] = selector
        if candidate != options and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _extract(url: str, *, download: bool, options: dict) -> dict:
    attempts = [deepcopy(options)]

    try:
        client = yt_dlp.YoutubeDL(_with_quiet_logger(attempts[0]))
        return client.extract_info(url, download=download)
    except DownloadError as error:
        if _is_dpapi_cookie_error(error) and "cookiesfrombrowser" in options:
            without_browser_cookies = deepcopy(options)
            without_browser_cookies.pop("cookiesfrombrowser", None)
            attempts.append(without_browser_cookies)
        elif not _is_format_unavailable(error):
            raise
        last_error = error

    attempts.extend(_fallback_options(attempts[-1]))
    for fallback in attempts[1:]:
        try:
            client = yt_dlp.YoutubeDL(_with_quiet_logger(fallback))
            return client.extract_info(url, download=download)
        except DownloadError as error:
            last_error = error
            if not _is_format_unavailable(error) and not _is_dpapi_cookie_error(error):
                raise

    raise last_error


def extract_stream_info(url: str) -> dict:
    # A fresh client per call is intentional: multiple guilds resolve tracks in
    # worker threads, and a shared YoutubeDL instance is not safe to mutate.
    return _extract(url, download=False, options=YTDL_OPTIONS)


def extract_download_info(url: str) -> dict:
    return _extract(url, download=True, options=YTDL_DOWNLOAD_OPTIONS)
