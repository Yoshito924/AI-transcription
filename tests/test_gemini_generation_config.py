"""モデル世代に応じた生成設定と 2.5 Flash 移行の検証（Issue #5）

SDKの送信部分だけを置き換え、実SDKが組み立てるリクエストを検査する。
"""
from types import SimpleNamespace
from unittest import mock

import pytest

pytest.importorskip("google.genai")

from google import genai
from google.genai._api_client import BaseApiClient

from src.api_utils import ApiUtils, build_generation_config
from src.constants import DEPRECATED_GEMINI_MODELS, PREFERRED_MODELS, TITLE_GENERATION_MODELS
from src.processor import FileProcessor
from src.usage_tracker import UsageTracker

SAMPLING_KEYS = {"temperature", "topP", "topK", "candidateCount"}


class _Sent(Exception):
    """送信直前で処理を止めるための例外"""


@pytest.fixture
def sent():
    """送信された (path, payload) を記録する"""
    captured = []

    def fake_request(self, method, path, request_dict, http_options=None):
        captured.append((path, request_dict))
        raise _Sent()

    client = genai.Client(api_key="synthetic")
    with mock.patch.object(BaseApiClient, "request", fake_request), \
            mock.patch("src.api_utils.create_genai_client", return_value=client), \
            mock.patch("src.processor.create_genai_client", return_value=client):
        yield captured


def _generation_config(captured):
    path, payload = captured[-1]
    return path, payload.get("generationConfig", {})


def _assert_no_sampling(captured, model):
    path, config = _generation_config(captured)
    assert model in path
    assert not SAMPLING_KEYS & set(config)
    assert config["maxOutputTokens"]


@pytest.fixture
def processor(tmp_path):
    return FileProcessor(str(tmp_path), enable_cache=False)


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "a.mp3"
    path.write_bytes(b"\0" * 16)
    return str(path)


def test_connection_test_payload(sent):
    utils = ApiUtils()
    with mock.patch.object(utils, "_get_available_models", return_value=["models/gemini-3.8-flash"]):
        with pytest.raises(Exception):
            utils.test_api_connection("synthetic")
    _assert_no_sampling(sent, "gemini-3.8-flash")


def test_single_audio_payload(sent, processor, audio):
    with mock.patch.object(processor.api_utils, "get_best_available_model",
                           return_value="models/gemini-3.8-flash"):
        with pytest.raises(_Sent):
            processor._perform_single_transcription(audio, "synthetic", lambda _: None)
    _assert_no_sampling(sent, "gemini-3.8-flash")


def test_segment_audio_payload(sent, processor, audio):
    with mock.patch.object(processor.audio_processor, "get_audio_duration", return_value=10):
        # 送信後の例外は分割処理側で分類されるため、ここでは送信内容だけを見る
        processor._transcribe_segment_enhanced(
            audio, "synthetic", 1, 2, "models/gemini-3.8-flash"
        )
    _assert_no_sampling(sent, "gemini-3.8-flash")


def test_additional_processing_payload(sent, processor):
    with mock.patch.object(processor.api_utils, "get_best_available_model",
                           return_value="models/gemini-3.8-flash"):
        with pytest.raises(_Sent):
            processor._perform_additional_processing(
                "text", "summary",
                {"summary": {"name": "要約", "prompt": "{transcription}"}},
                "synthetic", lambda _: None,
                additional_processing_engine="gemini",
            )
    _assert_no_sampling(sent, "gemini-3.8-flash")


def test_title_generation_payload_keeps_token_override(sent, processor):
    with mock.patch.object(processor.api_utils, "_get_available_models",
                           return_value=["models/gemini-3.5-flash-lite"]):
        assert processor.generate_summary_title("text", "synthetic") is None
    _assert_no_sampling(sent, "gemini-3.5-flash-lite")
    assert _generation_config(sent)[1]["maxOutputTokens"] == 100


def test_legacy_model_keeps_sampling_params(sent):
    client = genai.Client(api_key="synthetic")
    with pytest.raises(_Sent):
        client.models.generate_content(
            model="models/gemini-2.5-flash-lite",
            contents="x",
            config=build_generation_config("models/gemini-2.5-flash-lite", relax_safety=False),
        )
    config = _generation_config(sent)[1]
    assert config["temperature"] == 0.1
    assert config["topK"] == 20


@pytest.mark.parametrize("model", ["gemini-3.8-flash", "models/gemini-10-flash", "gemini-flash-latest"])
def test_overrides_cannot_reintroduce_unsupported_params(model):
    config = build_generation_config(model, relax_safety=False, temperature=0.5, candidate_count=1)
    assert config.temperature is None
    assert config.candidate_count is None


# --- 2.5 Flash 移行 ---

def _utils_listing(*names):
    utils = ApiUtils()
    client = mock.MagicMock()
    client.models.list.return_value = [
        SimpleNamespace(name=f"models/{n}", supported_actions=["generateContent"]) for n in names
    ]
    return utils, client


def _best(names, preferred=None):
    utils, client = _utils_listing(*names)
    with mock.patch("src.api_utils.create_genai_client", return_value=client):
        return utils.get_best_available_model("synthetic", preferred)


def test_candidates_drop_2_5_flash_but_keep_lite():
    for candidates in (PREFERRED_MODELS, TITLE_GENERATION_MODELS):
        assert "gemini-2.5-flash" not in candidates
        assert "gemini-2.5-flash-lite" in candidates


def test_both_names_listed_never_selects_old():
    assert _best(["gemini-2.5-flash", "gemini-3.5-flash-lite"]) == "models/gemini-3.5-flash-lite"


def test_only_old_name_listed_is_still_usable():
    assert _best(["gemini-2.5-flash"]) == "models/gemini-2.5-flash"


def test_flash_lite_is_not_treated_as_deprecated():
    assert _best(["gemini-2.5-flash", "gemini-2.5-flash-lite"]) == "models/gemini-2.5-flash-lite"


@pytest.mark.parametrize("saved", ["gemini-2.5-flash", "models/gemini-2.5-flash"])
def test_saved_old_name_maps_to_explicit_replacement(saved):
    names = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
    assert _best(names, saved) == "models/" + DEPRECATED_GEMINI_MODELS["gemini-2.5-flash"]


def test_history_for_old_model_keeps_its_own_pricing(tmp_path):
    tracker = UsageTracker(str(tmp_path))
    assert tracker._normalize_model_name("models/gemini-2.5-flash") == "gemini-2.5-flash"
    assert abs(tracker._calculate_cost("gemini-2.5-flash", 1000, 1000) - 0.0035) < 1e-9
