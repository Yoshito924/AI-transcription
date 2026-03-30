import inspect
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config
from src.processor import FileProcessor
from src.utils import get_whisper_model_value
from src.whisper_service import WhisperService


class WhisperDefaultTests(unittest.TestCase):
    def test_config_default_whisper_model_is_large_v3(self):
        tmpdir = tempfile.mkdtemp(dir=os.getcwd())
        try:
            config = Config(tmpdir)
            self.assertEqual(config.get("whisper_model"), "large-v3")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_whisper_model_helper_defaults_to_large_v3(self):
        self.assertEqual(get_whisper_model_value({}), "large-v3")

    def test_processing_entrypoints_default_to_large_v3(self):
        self.assertEqual(
            inspect.signature(FileProcessor.process_file).parameters["whisper_model"].default,
            "large-v3"
        )
        self.assertEqual(
            inspect.signature(WhisperService.load_model).parameters["model_name"].default,
            "large-v3"
        )
        self.assertEqual(
            inspect.signature(WhisperService.transcribe).parameters["model_name"].default,
            "large-v3"
        )