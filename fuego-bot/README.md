# FuegoBot

Simple Discord music bot built with Python.

## Features

- Play music in voice channels
- Queue and basic playback controls
- Spotify and YouTube resolving support
- Idle auto-disconnect support

## Requirements

- Python 3.10+
- FFmpeg installed and available in PATH
- A Discord bot token

## Setup

1. Clone the repository:

```bash
git clone https://github.com/Mantelgen/FuegoBot.git
cd FuegoBot
```

2. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root:

```dotenv
DISCORD_TOKEN=your_discord_token_here
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
PREFIX=!
DJ_ROLE_NAME=Prieteni
MUSIC_IDLE_TIMEOUT_MINUTES=3
YTDLP_COOKIES_FILE=/absolute/path/to/secrets/youtube_cookies.txt
```

## Run

Using Python directly:

```bash
python3 bot.py
```

Or with the helper script:

```bash
bash run.sh
```

## Project Structure

- `bot.py` - Bot entrypoint
- `cogs/` - Discord cogs/commands
- `app/services/` - Media clients, resolver, runtime
- `app/ui/` - Discord views and UI helpers
- `app/models/` - Domain models
- `secrets/` - Local secret files (ignored by git)

## Notes

- Keep `.env` private and never commit it.
- Keep `secrets/` private and out of version control.
