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

The `/status` command performs a fresh RCON health check and displays **Active**
or **Stopped**. While the bot is running, it checks the server periodically and
sends one alert to `STATUS_CHANNEL_ID` when the state changes from active to
stopped. It will not repeatedly alert while the server remains offline.
The bot needs **View Channel**, **Send Messages**, and **Embed Links**
permissions in that channel.

After adding the command, register it with Discord:

```bash
bun run deploy
```

