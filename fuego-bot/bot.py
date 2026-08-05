import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!").strip() or "!"

intents = discord.Intents.default()
intents.message_content = True


class FuegoBot(commands.Bot):
    async def setup_hook(self) -> None:
        # setup_hook runs once per process; on_ready may run again after reconnects.
        await self.load_extension("cogs.music")


bot = FuegoBot(command_prefix=PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id if bot.user else 'unknown'})")
    print(f"Command prefix: {PREFIX}")
    print("------")


@bot.event
async def on_command_error(ctx, error):
    if ctx.command and ctx.command.has_error_handler():
        return
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("Music commands can only be used in a server.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        usage = f"{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}".strip()
        await ctx.send(f"Missing argument. Usage: `{usage}`")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"Invalid argument: {error}")
        return
    if isinstance(error, commands.MaxConcurrencyReached):
        await ctx.send("That command is already running in this server. Please wait for it to finish.")
        return
    original = error.original if isinstance(error, commands.CommandInvokeError) else error
    if isinstance(original, TimeoutError):
        await ctx.send("Discord timed out while connecting to voice. Please try again in a few seconds.")
        return
    raise error


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and add your bot token.")
    bot.run(TOKEN)
