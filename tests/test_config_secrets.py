"""APIキーのキーストア移行で元データを失わないことの検証（Issue #5）"""
import json
from types import SimpleNamespace
from unittest import mock

import pytest

from src import config as config_module
from src.config import Config

KEY_A = "synthetic-gemini-value"
KEY_B = "synthetic-openai-value"


class PasswordDeleteError(Exception):
    pass


class FakeKeyring:
    """failing に含むキーの保存が失敗するキーストア"""
    errors = SimpleNamespace(PasswordDeleteError=PasswordDeleteError)

    def __init__(self, failing=()):
        self.failing = set(failing)
        self.store = {}

    def set_password(self, service, key, value):
        if key in self.failing:
            raise RuntimeError("no backend")
        self.store[key] = value

    def get_password(self, service, key):
        return self.store.get(key)

    def delete_password(self, service, key):
        if key not in self.store:
            raise PasswordDeleteError()
        del self.store[key]


@pytest.fixture
def make_config(tmp_path):
    path = tmp_path / "config" / "config.json"
    path.parent.mkdir()

    def _make(initial, backend):
        if initial is not None:
            path.write_text(json.dumps(initial), encoding="utf-8")
        with mock.patch.object(config_module, "keyring", backend), \
                mock.patch.object(config_module, "KEYRING_AVAILABLE", True):
            return Config(str(tmp_path))

    # keyring のモックをテスト本体の操作でも有効にする
    patchers = []

    def start(backend):
        for patcher in (
            mock.patch.object(config_module, "keyring", backend),
            mock.patch.object(config_module, "KEYRING_AVAILABLE", True),
        ):
            patcher.start()
            patchers.append(patcher)

    _make.start = start
    _make.disk = lambda: json.loads(path.read_text(encoding="utf-8"))
    yield _make
    for patcher in patchers:
        patcher.stop()


def test_all_fail_keeps_original_file(make_config):
    backend = FakeKeyring(failing={"api_key", "openai_api_key"})
    make_config.start(backend)
    original = {"api_key": KEY_A, "openai_api_key": KEY_B, "window_width": 800}
    cfg = make_config(original, backend)

    assert make_config.disk() == original
    assert cfg.get("api_key") == KEY_A
    assert cfg.pending_secret_keys == ["api_key", "openai_api_key"]


def test_one_succeeds_one_fails(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    cfg = make_config({"api_key": KEY_A, "openai_api_key": KEY_B}, backend)

    disk = make_config.disk()
    assert disk["api_key"] == KEY_A
    assert "openai_api_key" not in disk
    assert backend.store == {"openai_api_key": KEY_B}
    assert cfg.get("api_key") == KEY_A
    assert cfg.get("openai_api_key") == KEY_B


def test_failure_with_other_key_empty_keeps_failed_key(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    make_config({"api_key": KEY_A, "openai_api_key": ""}, backend)

    disk = make_config.disk()
    assert disk["api_key"] == KEY_A
    assert "openai_api_key" not in disk


def test_later_regular_save_keeps_failed_key(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    cfg = make_config({"api_key": KEY_A}, backend)

    cfg.set("window_width", 1234)

    disk = make_config.disk()
    assert disk["api_key"] == KEY_A
    assert disk["window_width"] == 1234


def test_restart_retries_and_removes_only_after_success(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    make_config({"api_key": KEY_A}, backend)
    assert make_config.disk()["api_key"] == KEY_A

    backend.failing.clear()
    cfg = make_config(None, backend)

    assert "api_key" not in make_config.disk()
    assert backend.store["api_key"] == KEY_A
    assert cfg.get("api_key") == KEY_A
    assert cfg.pending_secret_keys == []


def test_unverifiable_store_is_treated_as_failure(make_config):
    backend = FakeKeyring()
    backend.get_password = lambda service, key: None
    make_config.start(backend)
    make_config({"api_key": KEY_A}, backend)

    assert make_config.disk()["api_key"] == KEY_A


def test_set_failure_reports_false_and_writes_no_new_plaintext(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    cfg = make_config({"window_width": 800}, backend)

    assert cfg.set("api_key", KEY_A) is False
    assert "api_key" not in make_config.disk()


def test_set_same_pending_value_is_not_reported_as_loss(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    cfg = make_config({"api_key": KEY_A}, backend)

    assert cfg.set("api_key", KEY_A) is True
    assert make_config.disk()["api_key"] == KEY_A


def test_set_new_value_replaces_pending_plaintext_once_stored(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    cfg = make_config({"api_key": KEY_A}, backend)

    backend.failing.clear()
    assert cfg.set("api_key", "synthetic-new-value") is True

    assert "api_key" not in make_config.disk()
    assert cfg.get("api_key") == "synthetic-new-value"


def test_clearing_pending_key_removes_it_from_file(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    cfg = make_config({"api_key": KEY_A}, backend)

    assert cfg.set("api_key", "") is True
    assert "api_key" not in make_config.disk()
    assert not cfg.get("api_key")


def test_secret_values_are_not_logged(make_config):
    backend = FakeKeyring(failing={"api_key"})
    make_config.start(backend)
    with mock.patch.object(config_module, "logger") as logger:
        make_config({"api_key": KEY_A}, backend)
    assert KEY_A not in str(logger.mock_calls)


def test_failed_write_keeps_previous_file(make_config):
    backend = FakeKeyring()
    make_config.start(backend)
    cfg = make_config({"window_width": 800}, backend)
    before = make_config.disk()

    with mock.patch.object(config_module.json, "dump", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            cfg.save()

    assert make_config.disk() == before
