import os
import re
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent.parent


def _find_ffmpeg() -> str:
    configured = os.getenv("FFMPEG_EXECUTABLE", "").strip()
    if configured:
        return configured
    return shutil.which("ffmpeg") or "ffmpeg"


FFMPEG_EXECUTABLE = _find_ffmpeg()
FFMPEG_OPTIONS = {
    "before_options": "-nostdin",
    "options": "-vn -loglevel warning",
}


# yt-dlp

def build_ytdl_options() -> dict:
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "age_limit": 99,
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "ios", "android", "web"],
            }
        },
    }

    po_token = os.getenv("YTDLP_PO_TOKEN", "").strip()
    if po_token:
        options["extractor_args"]["youtube"]["po_token"] = [f"android.gvs+{po_token}"]

    cookies_file = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    if cookies_file:
        options["cookiefile"] = cookies_file
    else:
        for relative_cookie_path in [
            "secrets/youtube_cookies.txt",
            "youtube_cookies.txt",
            "secrets/cookies.txt",
            "cookies.txt",
        ]:
            default_cookie_path = PROJECT_DIR / relative_cookie_path
            if default_cookie_path.exists():
                options["cookiefile"] = str(default_cookie_path)
                break

    if "cookiefile" not in options:
        cookies_browser = os.getenv("YTDLP_COOKIES_BROWSER", "").strip().lower()
        if cookies_browser:
            cookies_profile = os.getenv("YTDLP_COOKIES_PROFILE", "").strip()
            if cookies_profile:
                options["cookiesfrombrowser"] = (cookies_browser, cookies_profile)
            else:
                options["cookiesfrombrowser"] = (cookies_browser,)

    return options


YTDL_OPTIONS = build_ytdl_options()
YTDL_DOWNLOAD_OPTIONS = {
    **YTDL_OPTIONS,
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "outtmpl": str(Path(tempfile.gettempdir()) / "fuego_bot_audio" / "%(id)s.%(ext)s"),
}


# Music domain constants
SPOTIFY_TRACK_RE = re.compile(r"open\.spotify\.com/track/([A-Za-z0-9]+)")
SPOTIFY_PLAYLIST_RE = re.compile(r"open\.spotify\.com/playlist/([A-Za-z0-9]+)")

FUEGO_OLDIES_QUERIES = [
    "https://youtu.be/pPQoaffONRc",
    "https://youtu.be/MvC9GIu7Fho",
    "https://youtu.be/h8Znx79U6bs",
    "https://youtu.be/KF-6PC_6xlo",
    "https://youtu.be/agObSG8g5eM",
    "https://youtu.be/SJ7sBrmiUAw",
    "https://youtu.be/ALoPRQFHaM4",
    "https://youtu.be/_jMudAsaZX4",
    "https://youtu.be/CSv7OIXsL_4",
    "https://youtu.be/t0WMLj0sqFo",
    "https://youtu.be/riDfckDM3ZA",
    "https://youtu.be/OA0zC5BvSyA",
    "https://youtu.be/mxnP-Szdfec",
    "https://youtu.be/M5V6xe15-sw",
    "https://youtu.be/bd-LSfzmywg",
]

RADIO_STATIONS = {
    "radio zu": "https://icecast.radiozu.ro/radiozu",
    "zu": "https://icecast.radiozu.ro/radiozu",
    "kiss fm": "https://live.kissfm.ro/kissfm.aacp",
    "kiss": "https://live.kissfm.ro/kissfm.aacp",
    "magic fm": "https://live.magicfm.ro/magicfm.aacp",
    "magic": "https://live.magicfm.ro/magicfm.aacp",
    "europa fm": "https://astreaming.europafm.ro/europafm/mp3_128k",
    "virgin radio": "https://astreaming.virginradio.ro/virginradio.mp3",
    "rock fm": "https://live.rockfm.ro/rockfm.aacp",
    "rockfm": "https://live.rockfm.ro/rockfm.aacp",
}

try:
    MUSIC_IDLE_TIMEOUT_MINUTES = max(0, int(os.getenv("MUSIC_IDLE_TIMEOUT_MINUTES", "10")))
except ValueError:
    MUSIC_IDLE_TIMEOUT_MINUTES = 10

MUSIC_IDLE_TIMEOUT_SECONDS = MUSIC_IDLE_TIMEOUT_MINUTES * 60

try:
    VOICE_CONNECT_TIMEOUT_SECONDS = max(10.0, float(os.getenv("VOICE_CONNECT_TIMEOUT_SECONDS", "30")))
except ValueError:
    VOICE_CONNECT_TIMEOUT_SECONDS = 30.0

try:
    VOICE_CONNECT_RETRIES = max(0, min(3, int(os.getenv("VOICE_CONNECT_RETRIES", "1"))))
except ValueError:
    VOICE_CONNECT_RETRIES = 1
