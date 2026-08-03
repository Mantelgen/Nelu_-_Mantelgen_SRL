# rustic_bot

To install dependencies:

```bash
bun install
```

To run:

```bash
bun run dev
```

## Server status

Copy `.env.example` to `.env` and configure the RCON connection.

Minecraft must have RCON enabled and the values of `RCON_HOST`, `RCON_PORT`,
and `RCON_PASSWORD` must match the server's `server.properties` settings.

The `/status` command is available to everyone. It performs a fresh RCON health
check and displays **Active** or **Stopped**, the player count, and online player
names in one private response. Because the response is ephemeral, using the
command does not add messages to the channel.

Slash commands are registered automatically in every Discord server the bot
joins. To register them manually, only `APP_TOKEN` is required:

```bash
bun run deploy
```

