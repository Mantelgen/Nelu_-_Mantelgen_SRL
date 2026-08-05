import unittest
from unittest.mock import AsyncMock, patch

from cogs.music import Music, VoiceConnectionError


class FakeVoiceClient:
    def __init__(self, channel):
        self.channel = channel
        self.cleaned = False

    def is_connected(self):
        return True

    async def disconnect(self, *, force=False):
        pass

    def cleanup(self):
        self.cleaned = True


class FakeChannel:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.connect_calls = []

    async def connect(self, **kwargs):
        self.connect_calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeGuild:
    def __init__(self):
        self.id = 123
        self.voice_client = None


class FakeBot:
    def __init__(self, guild):
        self.guild = guild
        self.user = None

    def get_guild(self, guild_id):
        return self.guild if guild_id == self.guild.id else None


class VoiceConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_is_cleaned_up_and_retried_once(self):
        guild = FakeGuild()
        channel = FakeChannel([])
        voice_client = FakeVoiceClient(channel)
        channel.outcomes = [TimeoutError(), voice_client]
        music = Music(FakeBot(guild))

        with (
            patch("cogs.music.VOICE_CONNECT_RETRIES", 1),
            patch("cogs.music.asyncio.sleep", new=AsyncMock()),
        ):
            connected = await music._connect_voice(guild, channel)

        self.assertIs(connected, voice_client)
        self.assertIs(music.get_state(guild.id).voice_client, voice_client)
        self.assertEqual(len(channel.connect_calls), 2)
        self.assertTrue(channel.connect_calls[0]["reconnect"])
        self.assertTrue(channel.connect_calls[0]["self_deaf"])

    async def test_repeated_timeout_becomes_user_safe_error(self):
        guild = FakeGuild()
        channel = FakeChannel([TimeoutError(), TimeoutError()])
        music = Music(FakeBot(guild))

        with (
            patch("cogs.music.VOICE_CONNECT_RETRIES", 1),
            patch("cogs.music.asyncio.sleep", new=AsyncMock()),
            self.assertRaisesRegex(VoiceConnectionError, "voice handshake"),
        ):
            await music._connect_voice(guild, channel)

        self.assertIsNone(music.get_state(guild.id).voice_client)
        self.assertEqual(len(channel.connect_calls), 2)


if __name__ == "__main__":
    unittest.main()
