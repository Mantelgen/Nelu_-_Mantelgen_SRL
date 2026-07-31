# rustic_bot

To install dependencies:

```bash
bun install
```

To run:

```bash
bun run dev
```

## Server status monitoring

Copy `.env.example` to `.env` and configure the RCON connection plus:

```dotenv
STATUS_CHANNEL_IDS=first_channel_id,second_channel_id
STATUS_CHECK_INTERVAL_SECONDS=30
STATUS_CHECK_TIMEOUT_MS=5000
```

Minecraft must have RCON enabled and the values of `RCON_HOST`, `RCON_PORT`,
and `RCON_PASSWORD` must match the server's `server.properties` settings.

The `/status` command is available to everyone. It performs a fresh RCON health
check and displays **Active** or **Stopped**, the player count, and online player
names in one private response. Because the response is ephemeral, using the
command does not add messages to the channel.
While the bot is running, it checks the server periodically and
sends one alert to every channel in `STATUS_CHANNEL_IDS` when the state changes
from active to stopped. Configure one channel ID for each Discord server. The
old `STATUS_CHANNEL_ID` setting is also supported. It also alerts if the
Minecraft server is already stopped when the bot starts.
It will not repeatedly alert while the server remains offline, and a failed
Discord delivery is retried during the next check.
The bot needs **View Channel**, **Send Messages**, and **Embed Links**
permissions in every configured alert channel.

Slash commands are registered automatically in every Discord server the bot
joins. To register them manually, only `APP_TOKEN` is required:

```bash
bun run deploy
```

