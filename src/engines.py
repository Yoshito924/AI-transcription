#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文字起こしエンジン仕様の集約モジュール

エンジンごとの差異（UI表示名・APIキーの取得元・ローカル実行か等）を
EngineSpec として一箇所にまとめ、各レイヤーに散在していた if/elif 分岐を
このモジュールへ集約する。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EngineSpec:
    """文字起こしエンジン1種類の仕様"""
    key: str                      # 'gemini' / 'whisper' / 'whisper-api'
    label: str                    # UI表示名
    api_key_var: Optional[str]    # ui_elements 内のAPIキー StringVar 名（'api_key_var' / 'openai_api_key_var' / None）
    api_key_error: Optional[str]  # キー未設定時のエラーメッセージ
    is_local: bool                # ローカル実行か


# 全エンジンの仕様。キーは get_engine_value() が返すエンジン値と一致させる。
ENGINES: dict = {
    'gemini': EngineSpec(
        key='gemini',
        label='Gemini',
        api_key_var='api_key_var',
        api_key_error='GeminiモードではGemini APIキーを入力してください。',
        is_local=False,
    ),
    'whisper': EngineSpec(
        key='whisper',
        label='Whisper',
        api_key_var=None,
        api_key_error=None,
        is_local=True,
    ),
    'whisper-api': EngineSpec(
        key='whisper-api',
        label='Whisper API',
        api_key_var='openai_api_key_var',
        api_key_error='Whisper APIモードではOpenAI APIキーを入力してください。',
        is_local=False,
    ),
}


def get_engine_spec(engine_key):
    """エンジンキーから EngineSpec を取得する（未知のキーは Gemini 扱い）"""
    return ENGINES.get(engine_key, ENGINES['gemini'])


def resolve_api_key(engine_key, ui_elements):
    """エンジンに応じたAPIキーを ui_elements から解決する。

    Args:
        engine_key: エンジン値（'gemini' / 'whisper' / 'whisper-api'）
        ui_elements: UI要素の辞書（APIキー StringVar を含む）

    Returns:
        tuple: (api_key, error_message)。エラーがなければ error_message は None。
        ローカルエンジン（Whisper）は ("", None)。
    """
    spec = get_engine_spec(engine_key)

    # ローカルエンジンはAPIキー不要
    if spec.api_key_var is None:
        return "", None

    api_key_var = ui_elements.get(spec.api_key_var)
    api_key = api_key_var.get().strip() if api_key_var else ""
    if not api_key:
        return "", spec.api_key_error
    return api_key, None
