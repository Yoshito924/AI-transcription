import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config
from src.constants import DEFAULT_PANE_FRACTIONS, PANE_FRACTION_MAX, PANE_FRACTION_MIN
from src.ui import _clamp_pane_fraction


class PaneLayoutTests(unittest.TestCase):
    def test_clamp_pane_fraction_keeps_valid_ratio(self):
        self.assertEqual(_clamp_pane_fraction(0.7, 0.5), 0.7)

    def test_clamp_pane_fraction_rejects_invalid_and_extreme_values(self):
        self.assertEqual(_clamp_pane_fraction("bad", 0.5), 0.5)
        self.assertEqual(_clamp_pane_fraction(None, 0.42), 0.42)
        self.assertEqual(_clamp_pane_fraction(0.01, 0.5), PANE_FRACTION_MIN)
        self.assertEqual(_clamp_pane_fraction(1.5, 0.5), PANE_FRACTION_MAX)

    def test_config_defaults_include_pane_fractions(self):
        tmpdir = tempfile.mkdtemp(dir=os.getcwd())
        try:
            config = Config(tmpdir)
            for key, expected in DEFAULT_PANE_FRACTIONS.items():
                self.assertAlmostEqual(config.get(key), expected)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
