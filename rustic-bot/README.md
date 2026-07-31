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
STATUS_CHANNEL_ID=your_discord_channel_id
STATUS_CHECK_INTERVAL_SECONDS=30
STATUS_CHECK_TIMEOUT_MS=5000
```

Minecraft must have RCON enabled and the values of `RCON_HOST`, `RCON_PORT`,
and `RCON_PASSWORD` must match the server's `server.properties` settings.

The `/status` command performs a fresh RCON health check and publicly displays
**Active** or **Stopped**, plus the number of online players. Users with the
Discord **Administrator** permission, the configured `MOD_ROLE_ID`, or a role
named **Moderatori** also receive a private list of the online player names.
While the bot is running, it checks the server periodically and
sends one alert to `STATUS_CHANNEL_ID` when the state changes from active to
stopped. It also alerts if the server is already stopped when the bot starts.
It will not repeatedly alert while the server remains offline, and a failed
Discord delivery is retried during the next check.
The bot needs **View Channel**, **Send Messages**, and **Embed Links**
permissions in that channel.

Set `DISCORD_CLIENT_ID` and `DISCORD_GUILD_IDS` (a comma-separated list) in
`.env`, then register the commands with Discord:

```bash
bun run deploy
```

