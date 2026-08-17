import unittest
from types import SimpleNamespace

from src.constants import OPENAI_BILLING_OVERVIEW_URL
from src.exceptions import ApiConnectionError
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

    def test_transcribe_converts_timeout_to_api_error(self):
        service = WhisperApiService.__new__(WhisperApiService)
        service.api_key = "test"
        service.client = SimpleNamespace(
            audio=SimpleNamespace(
                transcriptions=SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(Exception("request timed out"))
                )
            )
        )

        with self.assertRaises(ApiConnectionError) as ctx:
            service.transcribe("tests\\fixtures\\dummy.mp3")

        self.assertEqual(ctx.exception.error_code, "API_TIMEOUT")
        self.assertIn("タイムアウト", ctx.exception.user_message)

    def test_transcribe_converts_insufficient_quota_to_credit_error(self):
        service = WhisperApiService.__new__(WhisperApiService)
        service.api_key = "test"
        service.client = SimpleNamespace(
            audio=SimpleNamespace(
                transcriptions=SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(Exception("Error code: 429 - {'error': {'message': 'You exceeded your current quota', 'type': 'insufficient_quota', 'code': 'insufficient_quota'}}"))
                )
            )
        )

        with self.assertRaises(ApiConnectionError) as ctx:
            service.transcribe("tests\\fixtures\\dummy.mp3")

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_CREDIT")
        self.assertIn("Billing", ctx.exception.user_message)
        self.assertIn(OPENAI_BILLING_OVERVIEW_URL, ctx.exception.solution)

    def _make_service(self, capture, model):
        service = WhisperApiService.__new__(WhisperApiService)
        service.api_key = "test"
        service.model = model
        service.client = SimpleNamespace(
            audio=SimpleNamespace(
                transcriptions=SimpleNamespace(
                    create=lambda **kwargs: capture.append(kwargs) or FakeTranscript()
                )
            )
        )
        return service

    def test_gpt_transcribe_sends_languages_instead_of_language(self):
        captured = []
        service = self._make_service(captured, 'gpt-transcribe')

        service.transcribe("tests\\fixtures\\dummy.mp3", language='ja')

        self.assertEqual(captured[0]['model'], 'gpt-transcribe')
        self.assertEqual(captured[0]['languages'], ['ja'])
        self.assertNotIn('language', captured[0])

    def test_legacy_models_still_send_language(self):
        captured = []
        service = self._make_service(captured, 'gpt-4o-mini-transcribe')

        service.transcribe("tests\\fixtures\\dummy.mp3", language='ja')

        self.assertEqual(captured[0]['language'], 'ja')
        self.assertNotIn('languages', captured[0])


if __name__ == '__main__':
    unittest.main()
