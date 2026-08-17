#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    KEYRING_AVAILABLE = False

from .constants import (
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_TRIM_LONG_SILENCE,
    DEFAULT_SILENCE_TRIM_MODE,
    DEFAULT_SILENCE_TRIM_THRESHOLD_DB,
    DEFAULT_SILENCE_TRIM_MIN_SILENCE_SEC,
    DEFAULT_RECORDING_GAIN_PERCENT,
    OLLAMA_DEFAULT_MODEL,
    DEFAULT_TRANSCRIPTION_ENGINE,
    DEFAULT_WHISPER_MODEL,
    DEFAULT_WHISPER_API_MODEL,
    DEFAULT_TITLE_GENERATION_ENGINE,
    DEFAULT_ADDITIONAL_PROCESSING_ENGINE,
    DEFAULT_PANE_FRACTIONS,
    CONFIG_DIR,
    CONFIG_FILE,
    RECORDINGS_DIR
)
from .exceptions import ConfigurationError
from .logger import logger

class Config:
    """アプリケーション設定の管理クラス

    APIキーなどの秘密情報は config.json に平文保存せず、OSのキーストア
    （Windows: 資格情報マネージャー）に keyring 経由で保存する。
    keyring が使えない環境では従来どおり config.json に保存する。
    """

    # keyring に保存する秘密キー（config.json には書き出さない）
    SECRET_KEYS = frozenset({"api_key", "openai_api_key"})
    KEYRING_SERVICE = "AI-transcription"

    def __init__(self, app_dir):
        config_dir = os.path.join(app_dir, CONFIG_DIR)
        self.config_file = os.path.join(config_dir, CONFIG_FILE)
        self.config = self.load()
        self._migrate_secrets_to_keyring()

        # デフォルト設定
        self.defaults = {
            "window_width": DEFAULT_WINDOW_WIDTH,
            "window_height": DEFAULT_WINDOW_HEIGHT,
            "window_x": None,
            "window_y": None,
            "window_maximized": False,
            "last_open_tab": "file",
            "api_key": "",  # Gemini API用
            "openai_api_key": "",  # OpenAI API用（Whisper API等）
            "transcription_engine": DEFAULT_TRANSCRIPTION_ENGINE,  # "gemini" または "whisper" または "whisper-api"
            "gemini_safety_filter_recovery": "segment-whisper",  # "segment-whisper", "segment", "whisper"
            "additional_processing_engine": DEFAULT_ADDITIONAL_PROCESSING_ENGINE,  # "gemini" または "ollama"
            "title_generation_engine": DEFAULT_TITLE_GENERATION_ENGINE,  # "ollama", "auto", "gemini", "disabled"
            "ollama_model": OLLAMA_DEFAULT_MODEL,
            "whisper_model": DEFAULT_WHISPER_MODEL,
            "whisper_api_model": DEFAULT_WHISPER_API_MODEL,
            "trim_long_silence": DEFAULT_TRIM_LONG_SILENCE,
            "silence_trim_mode": DEFAULT_SILENCE_TRIM_MODE,
            "silence_trim_threshold_db": DEFAULT_SILENCE_TRIM_THRESHOLD_DB,
            "silence_trim_min_silence_sec": DEFAULT_SILENCE_TRIM_MIN_SILENCE_SEC,
            "save_to_output_dir": True,
            "save_to_source_dir": False,
            "rename_source_file": False,
            "queued_files": [],
            "recording_dir": RECORDINGS_DIR,
            "auto_queue_recordings": True,
            "recording_gain_percent": DEFAULT_RECORDING_GAIN_PERCENT,
            "recording_input_device": None,
            "recording_input_channels": [1],
            "recording_settings_expanded": False,
        }
        self.defaults.update(DEFAULT_PANE_FRACTIONS)

        # デフォルト値で埋める（秘密キーは config.json に持ち込まない）
        for key, value in self.defaults.items():
            if key not in self.config and not self._use_keyring_for(key):
                self.config[key] = value

    def _use_keyring_for(self, key):
        """このキーを keyring で管理するかどうか"""
        return KEYRING_AVAILABLE and key in self.SECRET_KEYS

    def _migrate_secrets_to_keyring(self):
        """config.json に平文保存された秘密情報を keyring へ移行して除去する"""
        if not KEYRING_AVAILABLE:
            return

        migrated = False
        for key in self.SECRET_KEYS:
            if key in self.config:
                value = self.config.pop(key)
                if value:
                    try:
                        keyring.set_password(self.KEYRING_SERVICE, key, value)
                        logger.info(f"{key} を config.json からOSキーストアへ移行しました")
                    except Exception as e:
                        # 移行に失敗した場合は平文のまま残す（消失防止）
                        logger.warning(f"{key} のキーストア移行に失敗: {e}")
                        self.config[key] = value
                        continue
                migrated = True

        if migrated:
            try:
                self.save()
            except OSError:
                pass

    def load(self):
        """設定ファイルを読み込む"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def save(self):
        """設定ファイルを保存する（秘密キーは書き出さない）"""
        # configディレクトリがなければ作成
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

        data = self.config
        if KEYRING_AVAILABLE:
            data = {k: v for k, v in self.config.items() if k not in self.SECRET_KEYS}

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        """設定値を取得する（秘密キーは keyring から取得）"""
        if self._use_keyring_for(key):
            try:
                value = keyring.get_password(self.KEYRING_SERVICE, key)
                return value if value is not None else default
            except Exception as e:
                logger.warning(f"キーストアからの {key} 取得に失敗: {e}")
                return default
        return self.config.get(key, default)

    def set(self, key, value):
        """設定値を設定する

        秘密キーは keyring に保存する。それ以外は、値が実際に変化した場合
        だけファイルへ書き出す（write-through）。
        """
        if self._use_keyring_for(key):
            try:
                if value:
                    keyring.set_password(self.KEYRING_SERVICE, key, value)
                else:
                    # 空文字はキーストアから削除して「未設定」に戻す
                    try:
                        keyring.delete_password(self.KEYRING_SERVICE, key)
                    except keyring.errors.PasswordDeleteError:
                        pass
            except Exception as e:
                logger.warning(f"キーストアへの {key} 保存に失敗: {e}")
            return

        if self.config.get(key, object()) == value and key in self.config:
            # 値が変わっていなければ書き込みを省略する
            return
        self.config[key] = value
        try:
            self.save()
        except OSError:
            # 保存に失敗してもメモリ上の設定は更新済みなので致命的ではない
            pass

    def save_window_geometry(self, root):
        """ウィンドウのジオメトリ情報を保存

        Windows で最大化（zoomed）中の場合は最大化フラグだけ保存し、
        サイズ・位置は通常時の値を上書きしない（復元用の通常ジオメトリを保持）。
        """
        # 最大化状態を判定（state() は Windows で 'zoomed'/'normal' を返す）
        try:
            is_maximized = root.state() == 'zoomed'
        except Exception:
            is_maximized = False

        self.config["window_maximized"] = is_maximized

        if is_maximized:
            # 最大化中は通常ジオメトリを保持したいので上書きしない
            self.save()
            return

        # ウィンドウのサイズと位置を取得
        geometry = root.geometry()
        parts = geometry.split('+')
        size = parts[0].split('x')

        self.config["window_width"] = int(size[0])
        self.config["window_height"] = int(size[1])

        if len(parts) > 2:  # 位置情報がある場合
            self.config["window_x"] = int(parts[1])
            self.config["window_y"] = int(parts[2])

        self.save()

    def _is_position_on_screen(self, root, x, y):
        """指定位置が仮想スクリーン範囲内にあるかを判定する

        マルチモニター環境で前回位置が画面外（取り外したモニター等）の場合に
        ウィンドウが見えなくなるのを防ぐためのガード。
        """
        try:
            virtual_left = root.winfo_vrootx()
            virtual_top = root.winfo_vrooty()
            virtual_width = root.winfo_vrootwidth()
            virtual_height = root.winfo_vrootheight()
        except Exception:
            # 取得できない場合は安全側（範囲内とみなす）に倒す
            return True

        # 仮想スクリーンのサイズが取れない環境ではガードしない
        if virtual_width <= 0 or virtual_height <= 0:
            return True

        # タイトルバーが掴める程度の余白を持って範囲内かチェックする
        margin = 50
        within_x = virtual_left - margin <= x <= virtual_left + virtual_width - margin
        within_y = virtual_top - margin <= y <= virtual_top + virtual_height - margin
        return within_x and within_y

    def apply_window_geometry(self, root):
        """保存されたジオメトリ情報をウィンドウに適用"""
        width = self.get("window_width", DEFAULT_WINDOW_WIDTH)
        height = self.get("window_height", DEFAULT_WINDOW_HEIGHT)

        geometry = f"{width}x{height}"

        # 位置情報がある場合は追加（ただし画面外なら位置指定を省略する）
        x = self.get("window_x")
        y = self.get("window_y")

        if x is not None and y is not None and self._is_position_on_screen(root, x, y):
            geometry += f"+{x}+{y}"

        # 先に通常ジオメトリを適用してから最大化を反映する
        root.geometry(geometry)

        if self.get("window_maximized", False):
            try:
                root.state('zoomed')
            except Exception:
                # zoomed 非対応環境（一部 Linux 等）では無視する
                pass
