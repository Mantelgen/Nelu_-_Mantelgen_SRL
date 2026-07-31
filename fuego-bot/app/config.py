import os
import re
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# FFmpeg
_FFMPEG_CANDIDATES = [
    Path(r"D:\3. Aplicatii si torrenturi\ffmpeg-2026-04-06-git-7fd2be97b9-full_build\ffmpeg-2026-04-06-git-7fd2be97b9-full_build\bin\ffmpeg.exe"),
    Path(r"C:\Users\Cosmin\AppData\Local\Overwolf\Extensions\ncfplpkmiejjaklknfnkgcpapnhkggmlcppckhcb\270.0.25\obs\bin\64bit\ffmpeg.exe"),
]


def _find_ffmpeg() -> str:
    for path in _FFMPEG_CANDIDATES:
        if path.exists():
            return str(path)
    return "ffmpeg"


FFMPEG_EXECUTABLE = _find_ffmpeg()
FFPROBE_EXECUTABLE = FFMPEG_EXECUTABLE.replace("ffmpeg.exe", "ffprobe.exe")
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
        for default_cookie_path in [
            Path("secrets/youtube_cookies.txt"),
            Path("youtube_cookies.txt"),
            Path("secrets/cookies.txt"),
            Path("cookies.txt"),
        ]:
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

DJ_ROLE_NAME = os.getenv("DJ_ROLE_NAME", "DJ").strip() or "DJ"

try:
    MUSIC_IDLE_TIMEOUT_MINUTES = max(0, int(os.getenv("MUSIC_IDLE_TIMEOUT_MINUTES", "10")))
except ValueError:
    MUSIC_IDLE_TIMEOUT_MINUTES = 10

MUSIC_IDLE_TIMEOUT_SECONDS = MUSIC_IDLE_TIMEOUT_MINUTES * 60
