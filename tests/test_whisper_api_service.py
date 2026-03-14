import unittest
from types import SimpleNamespace

from src.whisper_api_service import WhisperApiService


class FakeTranscript:
    def __init__(self):
        self.text = "こんにちは世界"
        self.language = "ja"
        self.segments = [
            SimpleNamespace(id=0, start=0.0, end=1.2, text="こんにちは"),
            SimpleNamespace(id=1, start=1.2, end=2.4, text="世界"),
        ]


class WhisperApiServiceTests(unittest.TestCase):
    def test_transcribe_handles_typed_verbose_response(self):
        service = WhisperApiService.__new__(WhisperApiService)
        service.api_key = "test"
        service.client = SimpleNamespace(
            audio=SimpleNamespace(
                transcriptions=SimpleNamespace(
                    create=lambda **kwargs: FakeTranscript()
                )
            )
        )

        text, metadata = service.transcribe("tests\\fixtures\\dummy.mp3", response_format='verbose_json')

        self.assertEqual(text, "こんにちは世界")
        self.assertEqual(metadata['language'], 'ja')
        self.assertEqual(metadata['total_segments'], 2)
        self.assertEqual(metadata['segments'][0]['text'], 'こんにちは')


if __name__ == '__main__':
    unittest.main()
