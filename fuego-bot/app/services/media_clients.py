import os
from copy import deepcopy
from pathlib import Path

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
    except Exception:
        return None


class _QuietLogger:
    """Suppress the 'Requested format is not available' noise that yt-dlp prints
    to stderr on every failed fallback attempt.  All other errors are forwarded."""

    def debug(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        if "requested format is not available" not in msg.lower():
            print(msg)


def _with_quiet_logger(options: dict) -> dict:
    patched = dict(options)
    patched["logger"] = _QuietLogger()
    return patched


ytdl = yt_dlp.YoutubeDL(_with_quiet_logger(YTDL_OPTIONS))
ytdl_download = yt_dlp.YoutubeDL(_with_quiet_logger(YTDL_DOWNLOAD_OPTIONS))
_browser_cookies_disabled = False


def _is_auth_required_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "sign in to confirm your age" in message
        or "use --cookies" in message
        or "age-restricted" in message
        or "age restricted" in message
        or "login required" in message
        or "authentication" in message
    )


def _is_dpapi_cookie_error(error: Exception) -> bool:
    message = str(error).lower()
    return "failed to decrypt with dpapi" in message


def _is_format_unavailable_error(error: Exception) -> bool:
    return "requested format is not available" in str(error).lower()


def _build_cookieless_options(options: dict) -> dict:
    fallback = dict(options)
    fallback.pop("cookiesfrombrowser", None)
    return fallback


def _iter_browser_cookie_names() -> list[str]:
    configured = os.getenv("YTDLP_COOKIES_BROWSER_FALLBACKS", "").strip()
    if configured:
        names = [name.strip().lower() for name in configured.split(",") if name.strip()]
        if names:
            return names
    return ["chrome", "edge", "brave", "firefox"]


def _build_browser_cookie_options(options: dict, browser_name: str) -> dict:
    with_browser = dict(options)
    with_browser.pop("cookiefile", None)
    with_browser["cookiesfrombrowser"] = (browser_name,)
    return with_browser


def _build_cookiefile_options(options: dict, cookie_file_path: str) -> dict:
    with_cookiefile = dict(options)
    with_cookiefile.pop("cookiesfrombrowser", None)
    with_cookiefile["cookiefile"] = cookie_file_path
    return with_cookiefile


def _build_flexible_format_options(options: dict) -> dict:
    # Relax format constraints when providers expose unusual/limited formats.
    fallback = dict(options)
    fallback["format"] = "best"
    return fallback


def _build_relaxed_extractor_options(options: dict) -> dict:
    fallback = deepcopy(options)
    fallback.pop("extractor_args", None)
    return fallback


def _iter_format_fallback_options(options: dict) -> list[dict]:
    attempts: list[dict] = []

    def _append(candidate: dict):
        if not any(existing == candidate for existing in attempts):
            attempts.append(candidate)

    # 1. Try broader format selectors with the same extractor_args.
    for selector in ["bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best", "bestaudio/best", "bestaudio*", "best"]:
        with_selector = dict(options)
        with_selector["format"] = selector
        _append(with_selector)

    # 2. Try without extractor_args entirely (yt-dlp picks the client itself).
    relaxed = _build_relaxed_extractor_options(options)
    for selector in ["bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best", "bestaudio/best", "best"]:
        relaxed_with_selector = dict(relaxed)
        relaxed_with_selector["format"] = selector
        _append(relaxed_with_selector)

    # 3. Last resort: no extractor_args, no format constraint.
    _append(_build_flexible_format_options(relaxed))

    return attempts


def _extract_info_with_format_fallback(client: yt_dlp.YoutubeDL, url: str, download: bool, options: dict) -> dict:
    try:
        return client.extract_info(url, download=download)
    except DownloadError as error:
        if not _is_format_unavailable_error(error):
            raise

        last_error: Exception = error
        for fallback_options in _iter_format_fallback_options(options):
            try:
                fallback_client = yt_dlp.YoutubeDL(_with_quiet_logger(fallback_options))
                return fallback_client.extract_info(url, download=download)
            except DownloadError as fallback_error:
                last_error = fallback_error
                continue

        raise last_error


def _iter_cookie_file_candidates() -> list[str]:
    env_path = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    candidates: list[str] = []
    if env_path:
        candidates.append(env_path)

    for filename in [
        "secrets/youtube_cookies.txt",
        "youtube_cookies.txt",
        "secrets/cookies.txt",
        "cookies.txt",
        "yt_cookies.txt",
    ]:
        file_path = Path(filename)
        if file_path.exists():
            candidates.append(str(file_path))

    # Preserve order while removing duplicates.
    unique: list[str] = []
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def _retry_with_cookie_file(url: str, download: bool, options: dict) -> dict | None:
    for candidate in _iter_cookie_file_candidates():
        try:
            print(f"[INFO] Retrying yt-dlp with cookie file: {candidate}")
            cookie_options = _build_cookiefile_options(options, candidate)
            client = yt_dlp.YoutubeDL(_with_quiet_logger(cookie_options))
            return _extract_info_with_format_fallback(client, url, download=download, options=cookie_options)
        except DownloadError:
            continue
    return None


def _retry_with_browser_cookies(url: str, download: bool, options: dict) -> dict:
    cookie_file_result = _retry_with_cookie_file(url, download=download, options=options)
    if cookie_file_result is not None:
        return cookie_file_result

    last_error: Exception | None = None
    missing_db_count = 0
    for browser_name in _iter_browser_cookie_names():
        try:
            print(f"[INFO] Retrying yt-dlp with browser cookies from: {browser_name}")
            browser_options = _build_browser_cookie_options(options, browser_name)
            client = yt_dlp.YoutubeDL(_with_quiet_logger(browser_options))
            return _extract_info_with_format_fallback(client, url, download=download, options=browser_options)
        except DownloadError as retry_error:
            last_error = retry_error
            if "could not find" in str(retry_error).lower() and "cookies database" in str(retry_error).lower():
                missing_db_count += 1
            continue

    if missing_db_count > 0 and missing_db_count == len(_iter_browser_cookie_names()):
        raise DownloadError(
            "No browser cookie database was found on this host. "
            "If you run the bot in WSL/Linux, export YouTube cookies to a Netscape file "
            "and set YTDLP_COOKIES_FILE (for example: /home/cosmin/Bot_discord/youtube_cookies.txt)."
        )

    if last_error is not None:
        raise last_error
    raise DownloadError("No browser cookie fallback candidates available.")


def extract_stream_info(url: str) -> dict:
    global _browser_cookies_disabled
    if _browser_cookies_disabled and "cookiesfrombrowser" in YTDL_OPTIONS:
        fallback_options = _build_cookieless_options(YTDL_OPTIONS)
        fallback_client = yt_dlp.YoutubeDL(_with_quiet_logger(fallback_options))
        return _extract_info_with_format_fallback(fallback_client, url, download=False, options=fallback_options)

    try:
        return _extract_info_with_format_fallback(ytdl, url, download=False, options=YTDL_OPTIONS)
    except DownloadError as error:
        if not _is_dpapi_cookie_error(error) or "cookiesfrombrowser" not in YTDL_OPTIONS:
            if _is_auth_required_error(error):
                return _retry_with_browser_cookies(url, download=False, options=YTDL_OPTIONS)
            raise
        _browser_cookies_disabled = True
        fallback_options = _build_cookieless_options(YTDL_OPTIONS)
        fallback_client = yt_dlp.YoutubeDL(_with_quiet_logger(fallback_options))
        return _extract_info_with_format_fallback(fallback_client, url, download=False, options=fallback_options)


def extract_download_info(url: str) -> dict:
    global _browser_cookies_disabled
    if _browser_cookies_disabled and "cookiesfrombrowser" in YTDL_DOWNLOAD_OPTIONS:
        fallback_options = _build_cookieless_options(YTDL_DOWNLOAD_OPTIONS)
        fallback_client = yt_dlp.YoutubeDL(_with_quiet_logger(fallback_options))
        return _extract_info_with_format_fallback(fallback_client, url, download=True, options=fallback_options)

    try:
        return _extract_info_with_format_fallback(ytdl_download, url, download=True, options=YTDL_DOWNLOAD_OPTIONS)
    except DownloadError as error:
        if not _is_dpapi_cookie_error(error) or "cookiesfrombrowser" not in YTDL_DOWNLOAD_OPTIONS:
            if _is_auth_required_error(error):
                return _retry_with_browser_cookies(url, download=True, options=YTDL_DOWNLOAD_OPTIONS)
            raise
        _browser_cookies_disabled = True
        fallback_options = _build_cookieless_options(YTDL_DOWNLOAD_OPTIONS)
        fallback_client = yt_dlp.YoutubeDL(_with_quiet_logger(fallback_options))
        return _extract_info_with_format_fallback(fallback_client, url, download=True, options=fallback_options)
