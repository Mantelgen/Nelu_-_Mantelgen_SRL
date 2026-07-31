import os
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Command prefix: {PREFIX}")
    print("------")
    await bot.load_extension("cogs.music")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument. Use `{PREFIX}help` for usage.")
        return
    raise error


if __name__ == "__main__":
    bot.run(TOKEN)
