#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI 音声文字起こしAPIサービス

対応モデル:
- gpt-4o-transcribe: GPT-4oベースの高精度文字起こし（推奨）
- gpt-4o-mini-transcribe: 低コスト版（whisper-1より高精度・半額）
- whisper-1: Whisper large-v2ベース（レガシー）
"""

import os
from typing import Optional, Dict, Any, Tuple, List

from .exceptions import TranscriptionError, ApiConnectionError
from .constants import OPENAI_BILLING_OVERVIEW_URL
from .logger import logger
from .utils import format_duration, get_file_size_mb


class WhisperApiService:
    """OpenAI 音声文字起こしAPIサービス

    OpenAI の音声文字起こしAPIは以下のモデルを提供しています:
    - gpt-4o-transcribe: GPT-4oベース、最高精度（推奨）
    - gpt-4o-mini-transcribe: GPT-4o miniベース、低コスト・高精度
    - whisper-1: Whisper large-v2ベース（レガシー）

    すべて同じ client.audio.transcriptions.create エンドポイントを使用。
    """

    # OpenAI 文字起こしAPIでサポートされているモデル（推奨順）
    # 参考: https://platform.openai.com/docs/models
    SUPPORTED_MODELS = [
        'gpt-4o-transcribe',       # 最高精度（推奨）
        'gpt-4o-mini-transcribe',  # 低コスト・高精度
        'whisper-1',               # レガシー
    ]

    # モデル別料金 (USD per minute)
    MODEL_PRICING = {
        'gpt-4o-transcribe': 0.006,       # $0.006/分
        'gpt-4o-mini-transcribe': 0.003,  # $0.003/分
        'whisper-1': 0.006,               # $0.006/分
    }

    # モデル説明（UI表示用）
    MODEL_DESCRIPTIONS = {
        'gpt-4o-transcribe': 'GPT-4o (高精度・推奨)',
        'gpt-4o-mini-transcribe': 'GPT-4o Mini (低コスト)',
        'whisper-1': 'Whisper (レガシー)',
    }

    DEFAULT_MODEL = 'gpt-4o-mini-transcribe'
    DEFAULT_REQUEST_TIMEOUT_SEC = 1800  # 30分

    def __init__(self, api_key: Optional[str] = None,
                 request_timeout_sec: int = DEFAULT_REQUEST_TIMEOUT_SEC,
                 model: Optional[str] = None):
        """文字起こしAPIサービスの初期化

        Args:
            api_key: OpenAI APIキー
            request_timeout_sec: リクエストタイムアウト（秒）
            model: 使用するモデル名（Noneの場合はデフォルト）
        """
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key, timeout=request_timeout_sec) if api_key else None
            self.api_key = api_key
            self.request_timeout_sec = request_timeout_sec
        except ImportError:
            raise ApiConnectionError(
                "openaiパッケージがインストールされていません。"
                "pip install openai でインストールしてください。"
            )

        # モデル設定
        if model and model in self.SUPPORTED_MODELS:
            self.model = model
        else:
            self.model = self.DEFAULT_MODEL

    def _coerce_to_dict(self, value: Any) -> Optional[Dict[str, Any]]:
        """SDKレスポンスを辞書へ正規化する"""
        if isinstance(value, dict):
            return value

        for method_name in ('model_dump', 'to_dict', 'dict'):
            method = getattr(value, method_name, None)
            if callable(method):
                try:
                    result = method()
                    if isinstance(result, dict):
                        return result
                except Exception:
                    pass

        return None

    def _extract_text(self, transcript: Any) -> str:
        """レスポンスから文字起こし本文を抽出する"""
        if isinstance(transcript, str):
            return transcript

        text = getattr(transcript, 'text', None)
        if isinstance(text, str):
            return text

        transcript_dict = self._coerce_to_dict(transcript)
        if transcript_dict:
            text = transcript_dict.get('text')
            if isinstance(text, str):
                return text

        return str(transcript or '')

    def _normalize_segment(self, segment: Any, index: int) -> Dict[str, Any]:
        """セグメント情報を辞書へ正規化する"""
        segment_dict = self._coerce_to_dict(segment) or {}
        return {
            'id': segment_dict.get('id', getattr(segment, 'id', index)),
            'start': segment_dict.get('start', getattr(segment, 'start', 0.0)),
            'end': segment_dict.get('end', getattr(segment, 'end', 0.0)),
            'text': (segment_dict.get('text', getattr(segment, 'text', '')) or '').strip(),
        }

    def _extract_segments(self, transcript: Any) -> List[Dict[str, Any]]:
        """レスポンスからセグメント一覧を抽出する"""
        transcript_dict = self._coerce_to_dict(transcript) or {}
        raw_segments = transcript_dict.get('segments', getattr(transcript, 'segments', [])) or []
        return [self._normalize_segment(segment, index) for index, segment in enumerate(raw_segments)]

    def transcribe(self, audio_path: str, language: Optional[str] = 'ja',
                   response_format: str = 'text', **kwargs) -> Tuple[str, Dict[str, Any]]:
        """音声ファイルを文字起こし

        Args:
            audio_path: 音声ファイルのパス
            language: 言語コード（'ja'など、Noneの場合は自動検出）
            response_format: レスポンス形式（'text', 'json', 'verbose_json', 'srt', 'vtt'）
            **kwargs: その他のオプション

        Returns:
            tuple: (文字起こしテキスト, メタデータ)
        """
        if not self.client:
            raise ApiConnectionError("OpenAI APIキーが設定されていません")

        if not os.path.exists(audio_path):
            raise TranscriptionError(f"音声ファイルが見つかりません: {audio_path}")

        file_size_mb = get_file_size_mb(audio_path)
        logger.info(f"OpenAI文字起こし開始: {os.path.basename(audio_path)}, モデル={self.model}, サイズ={file_size_mb:.2f}MB")

        try:
            # ファイルを開いてAPIに送信
            with open(audio_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    language=language,
                    response_format=response_format,
                    **kwargs
                )

            text = self._extract_text(transcript)

            if not text or not text.strip():
                raise TranscriptionError("文字起こし結果が空でした")

            segments = self._extract_segments(transcript)
            transcript_dict = self._coerce_to_dict(transcript) or {}
            detected_language = (
                transcript_dict.get('language')
                or getattr(transcript, 'language', None)
                or language
                or 'auto'
            )

            # メタデータを構築
            metadata = {
                'model': self.model,
                'language': detected_language,
                'file_size_mb': file_size_mb,
                'service': 'openai-transcription-api'
            }

            if segments:
                metadata['segments'] = segments
                metadata['total_segments'] = len(segments)

            logger.info(f"OpenAI文字起こし完了: モデル={self.model}, テキスト長={len(text)}文字")

            return text.strip(), metadata

        except Exception as e:
            error_msg = str(e)
            error_text = error_msg.lower()
            error_code = str(getattr(e, 'code', '') or '').lower()
            error_type = str(getattr(e, 'type', '') or '').lower()
            error_markers = " ".join(marker for marker in (error_text, error_code, error_type) if marker)
            logger.error(f"OpenAI文字起こしエラー: {error_msg}")

            # エラーの種類に応じた詳細メッセージ
            if 'api_key' in error_text or 'authentication' in error_text:
                raise ApiConnectionError(
                    "OpenAI APIキーが無効です。正しいAPIキーを設定してください。"
                )
            elif (
                'insufficient_quota' in error_markers
                or 'current quota' in error_markers
                or 'billing' in error_markers
                or 'credit balance' in error_markers
            ):
                raise ApiConnectionError(
                    "OpenAI APIの利用残高が不足している可能性があります。Billing の残高と請求設定を確認してください。",
                    error_code="INSUFFICIENT_CREDIT",
                    solution=(
                        "OpenAI の Billing でクレジット残高と支払い方法を確認し、残高が 0 の場合はチャージ後に再実行してください。\n"
                        f"{OPENAI_BILLING_OVERVIEW_URL}"
                    )
                )
            elif 'timeout' in error_text or 'timed out' in error_text:
                raise ApiConnectionError(
                    "OpenAI APIの応答がタイムアウトしました。しばらく待ってから再実行してください。",
                    error_code="API_TIMEOUT",
                    solution="長い音声は分割して再実行するか、時間を置いてから再試行してください。"
                )
            elif 'rate_limit' in error_text or '429' in error_msg:
                raise ApiConnectionError(
                    "APIのレート制限に達しました。しばらく待ってから再度実行してください。"
                )
            elif 'file_size' in error_text or 'too large' in error_text:
                raise TranscriptionError(
                    "ファイルサイズが大きすぎます。"
                    "OpenAI APIは25MB以下のファイルをサポートしています。"
                )
            else:
                raise TranscriptionError(f"OpenAI文字起こしに失敗しました: {error_msg}")

    def transcribe_with_segments(self, audio_path: str, language: Optional[str] = 'ja',
                                 **kwargs) -> Tuple[str, Dict[str, Any]]:
        """セグメント情報付きで文字起こし

        Args:
            audio_path: 音声ファイルのパス
            language: 言語コード
            **kwargs: その他のオプション

        Returns:
            tuple: (文字起こしテキスト, メタデータ)
        """
        text, metadata = self.transcribe(
            audio_path,
            language=language,
            response_format='verbose_json',
            **kwargs
        )
        return text, metadata

    def estimate_cost(self, audio_duration_seconds: float, model: Optional[str] = None) -> Dict[str, float]:
        """料金を推定

        Args:
            audio_duration_seconds: 音声の長さ（秒）
            model: モデル名（Noneの場合は現在のモデル）

        Returns:
            dict: 料金情報

        参考: https://openai.com/api/pricing/
        - gpt-4o-transcribe: $0.006/分
        - gpt-4o-mini-transcribe: $0.003/分
        - whisper-1: $0.006/分
        """
        model = model or self.model
        cost_per_minute = self.MODEL_PRICING.get(model, 0.006)
        duration_minutes = audio_duration_seconds / 60.0
        cost_usd = duration_minutes * cost_per_minute
        cost_jpy = cost_usd * 150  # 概算レート

        return {
            'cost_usd': cost_usd,
            'cost_jpy': cost_jpy,
            'duration_minutes': duration_minutes,
            'cost_per_minute': cost_per_minute,
            'model': model
        }
