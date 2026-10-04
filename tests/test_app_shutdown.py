import unittest
from unittest.mock import MagicMock, patch

from src.app import TranscriptionApp


class AppShutdownTests(unittest.TestCase):
    def test_shutdown_releases_resources_without_spawning_processes(self):
        # Shutdown is independent of the shell, terminal host or IDE ancestors.
        app = MagicMock()
        app.controller.is_processing = False
        app.audio_recorder.is_recording = False
        app._startup_complete = False
        app._waveform_refresh_job = None
        with patch('subprocess.Popen') as popen, patch('subprocess.run') as run:
            TranscriptionApp.on_closing(app)
        popen.assert_not_called()
        run.assert_not_called()
        app.audio_recorder.close.assert_called_once()
        app.preview_player.shutdown.assert_called_once()
        app.config.save.assert_called_once()
        app.root.destroy.assert_called_once()
