"""Gemini 3.7 Flash → 3.8 Flash 移行の受入テスト（Issue #3）"""
from unittest import mock

from src.api_utils import ApiUtils
from src.constants import DEFAULT_GEMINI_MODEL, GEMINI_PRICING, PREFERRED_MODELS
from src.usage_tracker import UsageTracker
from src.utils import calculate_gemini_cost


def test_defaults_point_to_3_8():
    assert DEFAULT_GEMINI_MODEL == "gemini-3.8-flash"
    assert PREFERRED_MODELS[0] == "gemini-3.8-flash"
    assert "gemini-3.7-flash" not in PREFERRED_MODELS


def _run_connection_test(available):
    utils = ApiUtils()
    client = mock.MagicMock()
    client.models.generate_content.return_value.text = "ok"
    with mock.patch.object(utils, "_get_available_models", return_value=available), \
            mock.patch("src.api_utils.create_genai_client", return_value=client),             mock.patch("src.api_utils.build_generation_config", return_value=None):
        return utils.test_api_connection("key")


def test_connection_test_prefers_3_8_when_both_listed():
    models = ["models/gemini-3.7-flash", "models/gemini-3.8-flash"]
    assert _run_connection_test(models) == "models/gemini-3.8-flash"


def test_connection_test_uses_3_8_when_only_3_8():
    assert _run_connection_test(["models/gemini-3.8-flash"]) == "models/gemini-3.8-flash"


def test_ranking_prefers_3_8():
    ranked = ApiUtils()._rank_models_by_priority(
        ["models/gemini-3.7-flash", "models/gemini-3.8-flash", "models/gemini-3.6-flash"]
    )
    assert ranked[0] == "models/gemini-3.8-flash"


def test_usage_tracker_pricing(tmp_path):
    tracker = UsageTracker(str(tmp_path))
    assert tracker._normalize_model_name("models/gemini-3.8-flash") == "gemini-3.8-flash"
    assert tracker._normalize_model_name("gemini-3.7-flash") == "gemini-3.7-flash"
    cost_38 = tracker._calculate_cost("gemini-3.8-flash", 1_000_000, 1_000_000)
    assert abs(cost_38 - (0.75 + 3.75)) < 1e-9
    # 履歴の 3.7 も引き続き計算できる
    assert tracker._calculate_cost("gemini-3.7-flash", 1000, 1000) > 0
    # 不明モデルは既定（3.8）料金にフォールバック
    assert tracker._calculate_cost("unknown-model", 1000, 1000) > 0


def test_constants_pricing_has_3_8():
    assert "gemini-3.8-flash" in GEMINI_PRICING
    assert "gemini-3.7-flash" in GEMINI_PRICING
    for model in ("models/gemini-3.8-flash", "gemini-3.7-flash", "unknown-model"):
        cost = calculate_gemini_cost(model, 1000, 1000, is_audio_input=True)
        assert isinstance(cost, dict)
