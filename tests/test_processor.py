import datetime
import os
import time
import unittest
from unittest.mock import MagicMock, patch

from src.exceptions import ApiConnectionError, AudioProcessingError, TranscriptionError
from src.processor import FileProcessor


class StubWhisperService:
    def __init__(self, responses):
        self._responses = iter(responses)

    def transcribe_segment(self, *args, **kwargs):
        return next(self._responses)


class SlowWhisperApiService:
    def __init__(self, delay_sec=0.03):
        self.api_key = "test"
        self.delay_sec = delay_sec

    def transcribe(self, *args, **kwargs):
        time.sleep(self.delay_sec)
        return "ok", {}

    def estimate_cost(self, audio_duration_seconds):
        return {
            'cost_usd': 0.006,
            'cost_jpy': 1.0,
        }


class QuotaWhisperApiService:
    def __init__(self):
        self.api_key = "test"

    def transcribe(self, *args, **kwargs):
        raise ApiConnectionError(
            "quota exceeded",
            error_code="INSUFFICIENT_CREDIT",
            user_message="OpenAI APIの利用残高が不足している可能性があります。"
        )


class FileProcessorTests(unittest.TestCase):
    def make_output_dir(self):
        output_dir = os.path.join(os.getcwd(), 'output')
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def test_whisper_service_is_lazy_initialized(self):
        temp_dir = self.make_output_dir()
        with patch('src.processor.WhisperService', side_effect=AudioProcessingError("missing")) as whisper_cls:
            processor = FileProcessor(temp_dir, enable_cache=False)

            self.assertIsNone(processor.whisper_service)
            whisper_cls.assert_not_called()

            with self.assertRaises(AudioProcessingError):
                processor.get_whisper_service()

            whisper_cls.assert_called_once()

    def test_whisper_segment_errors_are_filtered_and_warned(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor.get_whisper_service = lambda: StubWhisperService([
            ("最初の成功セグメントです。", {'is_error': False}),
            ("[セグメント 2 処理エラー: GPUエラー]", {'is_error': True, 'error_category': 'GPUエラー'}),
        ])

        result = processor._perform_whisper_segmented_transcription(
            audio_path="dummy.mp3",
            update_status=lambda message: None,
            whisper_model='base',
            cached_segments=['seg1.mp3', 'seg2.mp3'],
            cleanup_segments=False
        )

        self.assertIn("最初の成功セグメントです。", result)
        self.assertNotIn("処理エラー", result)
        self.assertIsNotNone(processor.last_warning)

    def test_all_failed_segments_raise_error(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)

        with self.assertRaises(TranscriptionError):
            processor._handle_segment_errors(
                audio_path="dummy.mp3",
                total_segments=2,
                segment_errors=[{'segment_index': 1, 'error_text': 'e1'}, {'segment_index': 2, 'error_text': 'e2'}],
                successful_segments=0,
                update_status=lambda message: None
            )

    def test_all_failed_segments_preserve_root_exception_type(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        root_exception = ApiConnectionError("認証エラー", user_message="APIキーが無効です")

        with self.assertRaises(ApiConnectionError) as ctx:
            processor._handle_segment_errors(
                audio_path="dummy.mp3",
                total_segments=2,
                segment_errors=[{'segment_index': 1, 'error_text': 'e1'}],
                successful_segments=0,
                update_status=lambda message: None,
                fatal_exception=root_exception
            )

        self.assertIn("APIキーが無効です", ctx.exception.user_message)

    def test_prepare_audio_file_uses_trimmed_duration_for_followup_processing(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor.enable_cache = True
        processor.cache_manager = MagicMock()
        processor.cache_manager.get_cache_entry.return_value = None
        processor.audio_processor.get_audio_duration = MagicMock(side_effect=[7200.0, 7200.0])
        processor.audio_processor.convert_audio = MagicMock(return_value="processed.mp3")
        processor.audio_processor.reduce_long_silence = MagicMock(return_value=("trimmed.mp3", 7200.0, 120.0))
        statuses = []

        with patch('src.processor.get_file_size_mb', side_effect=[5124.0, 188.0]), \
             patch('src.processor.os.unlink'):
            audio_path, segments, from_cache = processor._prepare_audio_file(
                "dummy.mp4",
                statuses.append,
                engine='gemini',
                trim_long_silence=True
            )

        self.assertEqual(audio_path, "trimmed.mp3")
        self.assertIsNone(segments)
        self.assertFalse(from_cache)
        self.assertEqual(processor.last_audio_duration_sec, 120.0)
        compression_messages = [message for message in statuses if "長い無音を圧縮しました" in message]
        self.assertTrue(compression_messages)
        self.assertIn("1時間58分0秒短縮", compression_messages[0])
        self.assertIn("98.3%削減", compression_messages[0])
        processor.cache_manager.get_cache_entry.assert_called_once_with(
            "dummy.mp4",
            cache_profile={'preprocess_version': 2, 'trim_long_silence': True}
        )
        self.assertEqual(processor.cache_manager.save_cache_entry.call_args.args[3], 120.0)
        self.assertEqual(
            processor.cache_manager.save_cache_entry.call_args.kwargs['cache_profile'],
            {'preprocess_version': 2, 'trim_long_silence': True}
        )

    def test_prepare_audio_file_logs_trim_summary_when_loading_from_cache(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor.enable_cache = True
        processor.cache_manager = MagicMock()
        processor.cache_manager.get_cache_entry.return_value = {
            'cache_id': 'cache-1',
            'duration': 120.0,
        }
        processor.cache_manager.get_cached_files.return_value = ("cached.mp3", None)
        processor.audio_processor.get_audio_duration = MagicMock(return_value=7200.0)
        statuses = []

        with patch('src.processor.get_file_size_mb', return_value=5124.0):
            audio_path, segments, from_cache = processor._prepare_audio_file(
                "dummy.mp4",
                statuses.append,
                engine='gemini',
                trim_long_silence=True
            )

        self.assertEqual(audio_path, "cached.mp3")
        self.assertIsNone(segments)
        self.assertTrue(from_cache)
        self.assertEqual(processor.last_audio_duration_sec, 120.0)
        cache_messages = [message for message in statuses if "長い無音圧縮を再利用" in message]
        self.assertTrue(cache_messages)
        self.assertIn("1時間58分0秒短縮", cache_messages[0])
        self.assertIn("98.3%削減", cache_messages[0])

    def test_gemini_large_file_ignores_cached_segments_and_uses_single_path(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor._perform_single_transcription = MagicMock(return_value="ok")
        processor._perform_segmented_transcription = MagicMock(side_effect=AssertionError("segmented path should not be used"))
        processor.audio_processor.get_audio_duration = lambda path: 60

        with patch('src.processor.get_file_size_mb', return_value=21.0):
            result = processor._perform_transcription(
                audio_path="dummy.mp3",
                api_key="test",
                update_status=lambda message: None,
                cached_segments=['seg1.mp3']
            )

        self.assertEqual(result, "ok")
        processor._perform_single_transcription.assert_called_once()
        processor._perform_segmented_transcription.assert_not_called()

    def test_gemini_safety_filter_retries_with_segments_before_whisper(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor.audio_processor.get_audio_duration = lambda path: 300
        processor.audio_processor.split_audio = MagicMock(return_value=['seg1.mp3', 'seg2.mp3', 'seg3.mp3'])
        processor._perform_segmented_transcription = MagicMock(return_value="segmented ok")
        processor._perform_whisper_transcription = MagicMock(side_effect=AssertionError("whisper fallback should not be used"))
        statuses = []
        exception = TranscriptionError(
            "blocked",
            error_code="SAFETY_FILTER",
            user_message="安全性フィルターによりブロックされました"
        )

        result = processor._recover_from_gemini_safety_filter(
            exception,
            audio_path="dummy.mp3",
            api_key="test",
            update_status=statuses.append,
            recovery_mode='segment'
        )

        self.assertEqual(result, "segmented ok")
        processor.audio_processor.split_audio.assert_called_once()
        processor._perform_segmented_transcription.assert_called_once()
        processor._perform_whisper_transcription.assert_not_called()
        self.assertTrue(any("セグメント単位で再試行" in message for message in statuses))
        self.assertIn("セグメント単位で再試行", processor.last_warning)

    def test_gemini_safety_filter_falls_back_to_whisper_when_segments_do_not_split(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor.audio_processor.get_audio_duration = lambda path: 30
        processor.audio_processor.split_audio = MagicMock(return_value=['dummy.mp3'])
        processor.get_whisper_service = MagicMock(return_value=object())
        processor._perform_whisper_transcription = MagicMock(return_value="whisper ok")
        exception = TranscriptionError(
            "blocked",
            error_code="SAFETY_FILTER",
            user_message="安全性フィルターによりブロックされました"
        )

        result = processor._recover_from_gemini_safety_filter(
            exception,
            audio_path="dummy.mp3",
            api_key="test",
            update_status=lambda message: None,
            recovery_mode='segment'
        )

        self.assertEqual(result, "whisper ok")
        processor._perform_whisper_transcription.assert_called_once()

    def test_gemini_safety_filter_whisper_mode_skips_segment_retry(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor.audio_processor.split_audio = MagicMock(side_effect=AssertionError("segment retry should not run"))
        processor.get_whisper_service = MagicMock(return_value=object())
        processor._perform_whisper_transcription = MagicMock(return_value="whisper ok")
        exception = TranscriptionError(
            "blocked",
            error_code="SAFETY_FILTER",
            user_message="安全性フィルターによりブロックされました"
        )

        result = processor._recover_from_gemini_safety_filter(
            exception,
            audio_path="dummy.mp3",
            api_key="test",
            update_status=lambda message: None,
            recovery_mode='whisper'
        )

        self.assertEqual(result, "whisper ok")
        processor.audio_processor.split_audio.assert_not_called()
        processor._perform_whisper_transcription.assert_called_once()

    def test_whisper_api_single_file_emits_heartbeat_while_waiting(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor.whisper_api_service = SlowWhisperApiService()
        processor.whisper_api_status_heartbeat_sec = 0.01
        processor.audio_processor.get_audio_duration = lambda path: 60
        statuses = []

        with patch('src.processor.get_file_size_mb', return_value=5.0):
            result = processor._perform_whisper_api_transcription(
                audio_path="dummy.mp3",
                api_key="test",
                update_status=statuses.append
            )

        self.assertEqual(result, "ok")
        self.assertTrue(any("経過" in message for message in statuses))

    def test_whisper_api_single_file_preserves_insufficient_credit_error(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)
        processor.whisper_api_service = QuotaWhisperApiService()
        processor.audio_processor.get_audio_duration = lambda path: 60

        with patch('src.processor.get_file_size_mb', return_value=5.0):
            with self.assertRaises(ApiConnectionError) as ctx:
                processor._perform_whisper_api_transcription(
                    audio_path="dummy.mp3",
                    api_key="test",
                    update_status=lambda message: None
                )

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_CREDIT")
        self.assertIn("利用残高", ctx.exception.user_message)


    def test_generated_title_strips_labels_and_followup_sections(self):
        temp_dir = self.make_output_dir()
        processor = FileProcessor(temp_dir, enable_cache=False)

        title = processor._normalize_generated_title(
            "タイトル：暑さで機械が止まる 浴衣姿も 要約：これは不要"
        )

        self.assertEqual(title, "暑さで機械が止まる 浴衣姿も")

    def test_save_result_avoids_duplicate_summary_title_in_filename(self):
        temp_dir = self.make_output_dir()
        output_path = None
        try:
            processor = FileProcessor(temp_dir, enable_cache=False)
            start_time = datetime.datetime.now()

            output_path = processor._save_result(
                input_file=os.path.join(os.getcwd(), "暑さで機械が止まる.mp4"),
                final_text="dummy text",
                process_type="transcription",
                prompts={},
                start_time=start_time,
                update_status=lambda message: None,
                save_to_output_dir=True,
                save_to_source_dir=False,
                summary_title="タイトル：暑さで機械が止まる"
            )

            self.assertTrue(os.path.exists(output_path))
            self.assertEqual(
                os.path.basename(output_path),
                "暑さで機械が止まる_文字起こし.txt"
            )
        finally:
            if output_path and os.path.exists(output_path):
                os.remove(output_path)

if __name__ == '__main__':
    unittest.main()

