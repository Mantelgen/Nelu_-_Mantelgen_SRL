import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.models.music import GuildMusicState, Song
from app.services.music_runtime import MusicRuntimeService
from app.ui.music_views import FuegoControlsView


class FakeVoiceClient:
    def __init__(self):
        self.connected = True
        self.playing = False
        self.paused = False
        self.source = None
        self.after = None

    def is_connected(self):
        return self.connected

    def is_playing(self):
        return self.playing

    def is_paused(self):
        return self.paused

    def play(self, source, *, after):
        self.source = source
        self.after = after
        self.playing = True

    def stop(self):
        self.playing = False


def make_song(title="Track"):
    requester = SimpleNamespace(display_name="Tester")
    return Song("https://example.test/watch", title, 60, requester)


class MusicRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state = GuildMusicState()
        self.service = MusicRuntimeService(get_state=lambda guild_id: self.state)

    async def test_advance_queue_starts_prepared_track_with_saved_volume(self):
        voice = FakeVoiceClient()
        self.state.voice_client = voice
        self.state.volume = 0.35
        song = make_song()
        song.is_fuego = True
        song.prepared_source = (
            "https://stream.example.test/audio",
            {"title": "Resolved title", "duration": 121.9},
            "stream",
            {},
        )
        self.state.queue.append(song)

        with (
            patch("app.services.music_runtime.discord.FFmpegPCMAudio", return_value=object()),
            patch(
                "app.services.music_runtime.discord.PCMVolumeTransformer",
                side_effect=lambda source, volume: SimpleNamespace(source=source, volume=volume),
            ),
        ):
            await self.service.advance_queue(1)

        self.assertIs(self.state.current, song)
        self.assertTrue(voice.playing)
        self.assertEqual(voice.source.volume, 0.35)
        self.assertEqual(song.title, "Resolved title")
        self.assertEqual(song.duration, 121)
        self.assertIsNone(song.prepared_source)
        self.assertTrue(self.state.skip_loop_once)

    async def test_close_fuego_prioritizes_interrupted_track(self):
        voice = FakeVoiceClient()
        voice.playing = True
        self.state.voice_client = voice
        fuego = make_song("Fuego")
        fuego.is_fuego = True
        interrupted = make_song("Interrupted")
        other = make_song("Other")
        self.state.current = fuego
        self.state.interrupted_song = interrupted
        self.state.queue.extend([other, interrupted])

        changed, message = self.service.close_fuego_and_resume(1)

        self.assertTrue(changed)
        self.assertIn("resumed", message)
        self.assertIs(self.state.queue[0], interrupted)
        self.assertEqual(list(self.state.queue).count(interrupted), 1)
        self.assertTrue(self.state.skip_loop_once)
        self.assertFalse(voice.playing)

    async def test_end_fuego_without_interrupted_track(self):
        voice = FakeVoiceClient()
        voice.playing = True
        self.state.voice_client = voice
        fuego = make_song("Fuego")
        fuego.is_fuego = True
        self.state.current = fuego

        changed, message = self.service.close_fuego_and_resume(1)

        self.assertTrue(changed)
        self.assertIn("Ended Fuego", message)
        self.assertFalse(voice.playing)

    async def test_cleanup_song_removes_prepared_download(self):
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            path = Path(temp_file.name)
        song = make_song()
        song.prepared_source = (str(path), {}, "file", {})

        self.service.cleanup_song(song)

        self.assertFalse(path.exists())
        self.assertIsNone(song.prepared_source)

    async def test_clear_queue_forgets_removed_interrupted_track(self):
        interrupted = make_song("Interrupted")
        self.state.interrupted_song = interrupted
        self.state.queue.append(interrupted)

        self.service.clear_queue(self.state)

        self.assertFalse(self.state.queue)
        self.assertIsNone(self.state.interrupted_song)

    async def test_header_blob_uses_real_crlf_and_strips_newlines(self):
        blob = self.service.build_header_blob(
            {"User-Agent": "agent\ninjected", "Referer": "https://example.test"}
        )

        self.assertEqual(
            blob,
            "User-Agent: agent injected\r\nReferer: https://example.test\r\n",
        )

    async def test_fuego_view_replaces_stop_with_end_fuego(self):
        music_cog = SimpleNamespace(get_state=lambda guild_id: self.state, runtime=self.service)
        view = FuegoControlsView(music_cog, 1)
        labels = [item.label for item in view.children]

        self.assertCountEqual(labels, ["Start", "End Fuego", "Skip"])
        view.stop()


if __name__ == "__main__":
    unittest.main()
