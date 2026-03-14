import unittest

from src.text_merger import TextMerger


class TextMergerTests(unittest.TestCase):
    def test_japanese_overlap_is_deduplicated(self):
        merger = TextMerger(overlap_threshold=0.6, min_overlap_words=3)

        merged = merger.merge_segments([
            "今日は良い天気ですね。明日も晴れるでしょう。",
            "明日も晴れるでしょう。洗濯日和です。"
        ])

        self.assertEqual(merged.count("明日も晴れるでしょう。"), 1)
        self.assertIn("洗濯日和です。", merged)


if __name__ == '__main__':
    unittest.main()
