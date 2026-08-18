import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config
from src.constants import DEFAULT_PANE_FRACTIONS, PANE_FRACTION_MAX, PANE_FRACTION_MIN
from src.ui import _clamp_pane_fraction, _setup_responsive_h_split


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

    def test_responsive_split_keeps_combobox_visible(self):
        try:
            import tkinter as tk
            from tkinter import ttk
        except Exception:
            self.skipTest('tkinter が使えない')

        root = tk.Tk()
        try:
            root.geometry('800x400')
            strip = tk.Frame(root, width=700)
            strip.pack(fill=tk.X)
            left = tk.Frame(strip)
            right = tk.Frame(strip)
            ttk.Label(left, text='ローカルモデル').pack(anchor='w')
            combo = ttk.Combobox(left, values=['高速', '高精度'], state='readonly')
            combo.pack(fill=tk.X, pady=(6, 0))
            tk.Label(right, text='保存先').pack(anchor='w')
            _setup_responsive_h_split(strip, left, right, threshold=540)
            root.update_idletasks()
            root.update()
            self.assertGreater(combo.winfo_height(), 10)
            self.assertTrue(combo.winfo_viewable())
            combo_bottom = combo.winfo_y() + combo.winfo_height()
            self.assertLessEqual(combo_bottom, left.winfo_height() + 4)
        finally:
            root.destroy()

    def test_processing_settings_keeps_model_combo_visible(self):
        try:
            import tkinter as tk
        except Exception:
            self.skipTest('tkinter が使えない')

        from src.ui_styles import ModernTheme, ModernWidgets
        from src.ui_settings import create_processing_settings_section

        class DummyConfig:
            def get(self, key, default=None):
                return default

            def set(self, key, value):
                return None

            def save(self):
                return None

        class DummyApp:
            def __init__(self):
                self.config = DummyConfig()

            def on_silence_trim_settings_changed(self, immediate=False):
                return None

        root = tk.Tk()
        try:
            theme = ModernTheme()
            widgets = ModernWidgets(theme)
            theme.apply_theme(root)
            section = create_processing_settings_section(root, DummyApp(), theme, widgets)
            section.pack(fill=tk.BOTH, expand=True)
            root.update_idletasks()
            root.update()
            combo = section.whisper_model_combo
            self.assertGreater(combo.winfo_height(), 10)
            self.assertTrue(combo.winfo_viewable())
            self.assertTrue(section.summary_model_text())
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
