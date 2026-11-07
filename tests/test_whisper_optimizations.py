import shutil
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from src.audio_cache import AudioCacheManager
from src.exceptions import AudioProcessingError
from src.processing_time_tracker import ProcessingTimeTracker
from src.whisper_service import WhisperService


def service(device='cuda'):
    instance = WhisperService.__new__(WhisperService)
    instance.device = device
    instance.batch_size = 4
    instance.model = None
    instance.current_model_name = None
    return instance


def response(text=' hello'):
    return iter([SimpleNamespace(text=text, start=0, end=1)]), SimpleNamespace(language='en', duration=1)


def test_lazy_gpu_oom_retries_without_duplicate_partial_text():
    instance = service()
    model = Mock()

    def failed_segments():
        yield SimpleNamespace(text='partial', start=0, end=1)
        raise RuntimeError('CUDA out of memory')

    with patch('faster_whisper.BatchedInferencePipeline') as pipeline:
        pipeline.return_value.transcribe.side_effect = [(failed_segments(), SimpleNamespace()), response()]
        result = instance._run_transcription(model, 'audio.wav', {'language': 'en'})
        assert result['text'] == 'hello'
        assert instance.batch_size == 2
        assert [c.kwargs['batch_size'] for c in pipeline.return_value.transcribe.call_args_list] == [4, 2]
        model.transcribe.assert_not_called()


def test_gpu_oom_eventually_uses_sequential_mode():
    instance = service()
    model = Mock()
    model.transcribe.return_value = response()
    with patch('faster_whisper.BatchedInferencePipeline') as pipeline:
        pipeline.return_value.transcribe.side_effect = RuntimeError('CUDA out of memory')
        assert instance._run_transcription(model, 'audio.wav', {})['text'] == 'hello'
        assert instance.batch_size == 1
        model.transcribe.assert_called_once()


def test_non_memory_errors_are_not_retried():
    with patch('faster_whisper.BatchedInferencePipeline') as pipeline:
        pipeline.return_value.transcribe.side_effect = RuntimeError('missing cudnn')
        with pytest.raises(RuntimeError, match='missing cudnn'):
            service()._run_transcription(Mock(), 'audio.wav', {})
        assert pipeline.return_value.transcribe.call_count == 1


def test_cpu_keeps_sequential_inference():
    instance = service('cpu')
    model = Mock()
    model.transcribe.return_value = response()
    assert instance._run_transcription(model, 'audio.wav', {})['text'] == 'hello'
    model.transcribe.assert_called_once_with('audio.wav')


def test_failed_reload_clears_stale_model_and_preserves_requested_model():
    instance = service()
    instance.model = Mock()
    instance.current_model_name = 'large-v3-turbo'
    with patch('src.whisper_service.WhisperModel', side_effect=RuntimeError('bad model')) as factory:
        with pytest.raises(AudioProcessingError, match='bad model'):
            instance.load_model('large-v3')
        factory.assert_called_once()
    assert instance.model is None
    assert instance.current_model_name is None


def test_alias_reuses_loaded_model():
    instance = service()
    with patch('src.whisper_service.WhisperModel') as factory:
        first = instance.load_model('turbo')
        assert instance.load_model('large-v3-turbo') is first
        factory.assert_called_once()


def test_eta_does_not_mix_devices_or_legacy_history(tmp_path):
    tracker = ProcessingTimeTracker(str(tmp_path))
    tracker.record('whisper', 'large-v3', 60, 100)
    tracker.record('whisper', 'large-v3@cpu-batch1', 60, 50)
    assert tracker.estimate('whisper', 'large-v3@cuda-batch4', 60) is None
    tracker.record('whisper', 'large-v3@cuda-batch4', 60, 5)
    assert tracker.estimate('whisper', 'large-v3@cuda-batch4', 120)['estimated_sec'] == 10


def test_cache_preserves_pcm_extension_for_audio_and_segments(tmp_path):
    audio = tmp_path / 'input.wav'
    audio.write_bytes(b'RIFF test audio')
    cache = AudioCacheManager(str(tmp_path / 'cache'))
    try:
        key = cache.save_cache_entry(str(audio), str(audio), [str(audio)])
        cached, segments = cache.get_cached_files(key)
        assert Path(cached).suffix == '.wav'
        assert Path(segments[0]).suffix == '.wav'
        assert Path(cached).read_bytes() == audio.read_bytes()
    finally:
        cache.flush_metadata()


@pytest.mark.skipif(shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None, reason='FFmpeg required')
def test_pcm_survives_conversion_silence_reduction_and_splitting(tmp_path):
    from src.audio_processor import AudioProcessor
    import numpy as np
    source = tmp_path / 'source.wav'
    tone = (np.sin(np.arange(64000) * 2 * np.pi * 440 / 16000) * 5000).astype(np.int16)
    samples = np.concatenate([tone, np.zeros(64000, dtype=np.int16), tone])
    with wave.open(str(source), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(samples.tobytes())
    processor = AudioProcessor()
    generated = set()
    try:
        converted = processor.convert_audio(str(source), output_format='wav', sample_rate=16000, channels=1)
        generated.add(converted)
        reduced, before, after = processor.reduce_long_silence(converted)
        generated.add(reduced)
        assert after < before
        segments = processor.split_audio(reduced, segment_duration_sec=2, overlap_sec=0)
        generated.update(segments)
        assert len(segments) >= 2
        for name in generated:
            assert Path(name).suffix == '.wav'
            with wave.open(name, 'rb') as audio:
                assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (16000, 1, 2)
    finally:
        for name in generated:
            Path(name).unlink(missing_ok=True)


def test_batch_uses_short_chunks_without_mutating_options():
    options = {'language': 'ja', 'vad_filter': True}
    with patch('faster_whisper.BatchedInferencePipeline') as pipeline:
        pipeline.return_value.transcribe.return_value = response()
        service()._run_transcription(Mock(), 'audio.wav', options)
        assert pipeline.return_value.transcribe.call_args.kwargs['chunk_length'] == 15
    assert options == {'language': 'ja', 'vad_filter': True}
