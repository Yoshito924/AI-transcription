import unittest
from unittest.mock import MagicMock

from src.controllers import TranscriptionController


class DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class ImmediateAfterWidget:
    def after(self, _delay, callback):
        callback()


class WaveformPreviewCacheTests(unittest.TestCase):
    def test_refresh_preserves_cached_auto_threshold_when_switching_back_to_auto(self):
        waveform_viewer = MagicMock()
        waveform_viewer.after = ImmediateAfterWidget().after
        waveform_viewer._format_duration.return_value = "0:05"

        audio_processor = MagicMock()
        audio_processor.extract_waveform_and_silence.return_value = {
            'samples': [0.1, 0.2],
            'duration': 12.0,
            'auto_threshold_db': -41.5,
            'silence_regions': [(1.0, 4.0)],
        }
        audio_processor.resolve_silence_parameters.side_effect = [
            {
                'mode': 'manual',
                'mode_label': '手動',
                'threshold_db': -28.0,
                'min_silence_sec': 1.5,
                'keep_silence_sec': 0.5,
                'resolved_threshold_db': -28.0,
            },
            {
                'mode': 'auto',
                'mode_label': '自動',
                'threshold_db': -28.0,
                'min_silence_sec': 1.5,
                'keep_silence_sec': 0.5,
                'resolved_threshold_db': -41.5,
            },
        ]
        audio_processor.detect_silence_regions.return_value = [(2.0, 5.0)]
        audio_processor.build_silence_cut_preview.return_value = ([(2.5, 5.0)], 2.5)

        processor = MagicMock()
        processor.audio_processor = audio_processor
        ui_elements = {
            'root': MagicMock(),
            'progress': MagicMock(),
            'progress_label': MagicMock(),
            'waveform_viewer': waveform_viewer,
            'trim_long_silence_var': DummyVar(True),
            'silence_trim_mode_var': DummyVar('手動しきい値'),
            'silence_trim_mode_display_to_value': {
                '自動判定（推奨）': 'auto',
                '手動しきい値': 'manual',
            },
            'silence_trim_threshold_db_var': DummyVar(-28.0),
            'silence_trim_min_silence_sec_var': DummyVar(1.5),
        }
        controller = TranscriptionController(processor, MagicMock(), MagicMock(), ui_elements)
        controller.current_file = 'dummy.mp3'

        controller._load_waveform('dummy.mp3', reload_samples=True)
        self.assertEqual(controller._waveform_cache['auto_threshold_db'], -41.5)
        self.assertEqual(controller._waveform_cache['resolved_threshold_db'], -28.0)

        ui_elements['silence_trim_mode_var'].value = '自動判定（推奨）'
        controller.refresh_waveform_preview()

        self.assertEqual(
            audio_processor.resolve_silence_parameters.call_args_list[1].kwargs['precomputed_auto_threshold_db'],
            -41.5
        )
        self.assertEqual(controller._waveform_cache['auto_threshold_db'], -41.5)
        self.assertEqual(controller._waveform_cache['resolved_threshold_db'], -41.5)
        audio_processor.detect_silence_regions.assert_called_once()
        waveform_viewer.set_data.assert_called()


if __name__ == '__main__':
    unittest.main()
