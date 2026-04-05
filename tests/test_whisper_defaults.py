import inspect
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config
from src.constants import OLLAMA_DEFAULT_MODEL
from src.processor import FileProcessor
from src.utils import get_whisper_model_value, get_ollama_model_value
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

    def test_config_default_ollama_model_is_gemma4_e4b(self):
        tmpdir = tempfile.mkdtemp(dir=os.getcwd())
        try:
            config = Config(tmpdir)
            self.assertEqual(config.get("ollama_model"), OLLAMA_DEFAULT_MODEL)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_ollama_model_helper_defaults_to_gemma4_e4b(self):
        self.assertEqual(get_ollama_model_value({}), OLLAMA_DEFAULT_MODEL)

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
        self.assertEqual(
            inspect.signature(FileProcessor.generate_summary_title_ollama).parameters["model"].default,
            OLLAMA_DEFAULT_MODEL
        )
