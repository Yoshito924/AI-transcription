import os
import unittest
from unittest.mock import MagicMock

from src.constants import SUPPORTED_AUDIO_FORMATS, SUPPORTED_MEDIA_FILE_GLOB
from src.controllers import TranscriptionController


class SupportedFormatsTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), 'output', 'format_support_tests')
        os.makedirs(self.test_dir, exist_ok=True)
        self.created_files = []

    def tearDown(self):
        for path in self.created_files:
            if os.path.exists(path):
                os.remove(path)

        if os.path.isdir(self.test_dir) and not os.listdir(self.test_dir):
            os.rmdir(self.test_dir)

    def _make_file(self, name):
        path = os.path.join(self.test_dir, name)
        with open(path, 'wb') as handle:
            handle.write(b'test')
        self.created_files.append(path)
        return path

    def test_extended_formats_are_exposed_in_dialog_glob(self):
        for extension in ('mov', 'mkv', 'wma', 'webm', 'mts'):
            self.assertIn(extension, SUPPORTED_AUDIO_FORMATS)
            self.assertIn(f'*.{extension}', SUPPORTED_MEDIA_FILE_GLOB)

    def test_controller_accepts_common_audio_and_video_formats(self):
        controller = TranscriptionController(MagicMock(), MagicMock(), MagicMock(), {})

        file_paths = [
            self._make_file('clip.MOV'),
            self._make_file('archive.mkv'),
            self._make_file('voice.WMA'),
            self._make_file('note.txt'),
        ]

        added, duplicated_paths, invalid = controller.add_files_to_queue(file_paths)

        self.assertEqual(added, 3)
        self.assertEqual(duplicated_paths, [])
        self.assertEqual(invalid, 1)


if __name__ == '__main__':
    unittest.main()
