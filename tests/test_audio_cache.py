import os
from pathlib import Path
import tempfile
import unittest

from src.audio_cache import AudioCacheManager


class AudioCacheIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = AudioCacheManager(str(self.root / 'cache'))
        self.addCleanup(self.cache.flush_metadata)
        self.source = self.root / 'a' / 'clip.wav'
        self.source.parent.mkdir()
        self.source.write_bytes(b'AAAA')
        self.processed = self.root / 'processed.mp3'
        self.processed.write_bytes(b'AUDIO_A')
        self.profile = {'sample_rate': 16000, 'trim': False}
        self.cache.save_cache_entry(str(self.source), str(self.processed),
                                    cache_profile=self.profile)

    def test_different_directory_with_identical_metadata_misses(self):
        other = self.root / 'b' / 'clip.wav'
        other.parent.mkdir()
        other.write_bytes(b'BBBB')
        stat = self.source.stat()
        os.utime(other, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertIsNone(self.cache.get_cache_entry(str(other), self.profile))

    def test_same_file_and_equivalent_profile_reuse_processed_audio(self):
        entry = self.cache.get_cache_entry(
            str(self.source.parent / '..' / 'a' / 'clip.wav'),
            {'trim': False, 'sample_rate': 16000})
        self.assertIsNotNone(entry)
        audio, _ = self.cache.get_cached_files(entry['cache_id'])
        self.assertEqual(Path(audio).read_bytes(), b'AUDIO_A')

    def test_content_replacement_with_preserved_metadata_misses(self):
        stat = self.source.stat()
        self.source.write_bytes(b'BBBB')
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertIsNone(self.cache.get_cache_entry(str(self.source), self.profile))

    def test_changed_profile_misses(self):
        self.assertIsNone(self.cache.get_cache_entry(
            str(self.source), {'sample_rate': 16000, 'trim': True}))

    def test_changed_modification_time_misses(self):
        stat = self.source.stat()
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000))
        self.assertIsNone(self.cache.get_cache_entry(str(self.source), self.profile))
