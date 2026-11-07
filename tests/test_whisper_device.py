import unittest
from unittest.mock import Mock, patch

from src.whisper_service import WhisperService


class WhisperDeviceTests(unittest.TestCase):
    def make_service(self, backend):
        with patch('src.whisper_service._ensure_faster_whisper', return_value=True), \
                patch.object(WhisperService, '_setup_cache_directory'), \
                patch.dict('sys.modules', {'ctranslate2': backend, 'torch': None}):
            return WhisperService()

    def test_gpu_is_used_without_torch(self):
        service = self.make_service(Mock(get_cuda_device_count=Mock(return_value=1)))
        self.assertEqual(service.device, 'cuda')
        with patch.dict('sys.modules', {'torch': None}):
            self.assertEqual(service.get_device_info(), 'GPU (CUDA / CTranslate2)')
        with patch('src.whisper_service.WhisperModel') as model:
            service.load_model('large-v3')
            model.assert_called_once_with('large-v3', device='cuda', compute_type='int8_float16')

    def test_no_gpu_uses_cpu(self):
        service = self.make_service(Mock(get_cuda_device_count=Mock(return_value=0)))
        self.assertEqual(service.device, 'cpu')

    def test_detection_failure_uses_cpu(self):
        service = self.make_service(Mock(get_cuda_device_count=Mock(side_effect=RuntimeError('driver unavailable'))))
        self.assertEqual(service.device, 'cpu')


if __name__ == '__main__':
    unittest.main()
