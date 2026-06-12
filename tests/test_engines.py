import unittest

from src.engines import ENGINES, get_engine_spec, resolve_api_key


class DummyVar:
    """tk.StringVar の最小モック"""
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class EngineSpecTests(unittest.TestCase):
    def test_all_engines_registered(self):
        self.assertEqual(set(ENGINES.keys()), {'gemini', 'whisper', 'whisper-api'})

    def test_get_engine_spec_unknown_falls_back_to_gemini(self):
        self.assertIs(get_engine_spec('unknown'), ENGINES['gemini'])

    def test_local_flags(self):
        self.assertTrue(ENGINES['whisper'].is_local)
        self.assertFalse(ENGINES['gemini'].is_local)
        self.assertFalse(ENGINES['whisper-api'].is_local)


class ResolveApiKeyTests(unittest.TestCase):
    def test_whisper_local_needs_no_key(self):
        api_key, error = resolve_api_key('whisper', {})
        self.assertEqual(api_key, "")
        self.assertIsNone(error)

    def test_gemini_with_key(self):
        ui_elements = {'api_key_var': DummyVar("  gemini-key  ")}
        api_key, error = resolve_api_key('gemini', ui_elements)
        self.assertEqual(api_key, "gemini-key")
        self.assertIsNone(error)

    def test_gemini_without_key(self):
        ui_elements = {'api_key_var': DummyVar("   ")}
        api_key, error = resolve_api_key('gemini', ui_elements)
        self.assertEqual(api_key, "")
        self.assertEqual(error, ENGINES['gemini'].api_key_error)

    def test_gemini_missing_var(self):
        api_key, error = resolve_api_key('gemini', {})
        self.assertEqual(api_key, "")
        self.assertEqual(error, ENGINES['gemini'].api_key_error)

    def test_whisper_api_with_key(self):
        ui_elements = {'openai_api_key_var': DummyVar("openai-key")}
        api_key, error = resolve_api_key('whisper-api', ui_elements)
        self.assertEqual(api_key, "openai-key")
        self.assertIsNone(error)

    def test_whisper_api_without_key(self):
        ui_elements = {'openai_api_key_var': DummyVar("")}
        api_key, error = resolve_api_key('whisper-api', ui_elements)
        self.assertEqual(api_key, "")
        self.assertEqual(error, ENGINES['whisper-api'].api_key_error)


if __name__ == '__main__':
    unittest.main()
