#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI Whisper APIを使用した文字起こしサービス
"""

import os
from typing import Optional, Dict, Any, Tuple, List

from .exceptions import TranscriptionError, ApiConnectionError
from .logger import logger
from .utils import format_duration, get_file_size_mb


class WhisperApiService:
    """OpenAI Whisper APIを使用した文字起こしサービス
    
    OpenAI Whisper APIは現在 whisper-1 モデルのみ提供されています。
    このモデルはWhisper large-v2をベースにしており、多言語対応・高精度です。
    
    注意: ローカルWhisperでlarge-v3を使用したい場合は WhisperService を使用してください。
    """
    
    # OpenAI Whisper APIでサポートされているモデル
    # 参考: https://platform.openai.com/docs/models/whisper
    SUPPORTED_MODELS = ['whisper-1']  # 現在はwhisper-1のみ
    
    def __init__(self, api_key: Optional[str] = None):
        """Whisper APIサービスの初期化
        
        Args:
            api_key: OpenAI APIキー
        """
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key) if api_key else None
            self.api_key = api_key
        except ImportError:
            raise ApiConnectionError(
                "openaiパッケージがインストールされていません。"
                "pip install openai でインストールしてください。"
            )

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
        logger.info(f"Whisper API文字起こし開始: {os.path.basename(audio_path)}, サイズ={file_size_mb:.2f}MB")
        
        try:
            # ファイルを開いてAPIに送信
            with open(audio_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
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
                'model': 'whisper-1',
                'language': detected_language,
                'file_size_mb': file_size_mb,
                'service': 'openai-whisper-api'
            }

            if segments:
                metadata['segments'] = segments
                metadata['total_segments'] = len(segments)
            
            logger.info(f"Whisper API文字起こし完了: テキスト長={len(text)}文字")
            
            return text.strip(), metadata
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Whisper API文字起こしエラー: {error_msg}")
            
            # エラーの種類に応じた詳細メッセージ
            if 'api_key' in error_msg.lower() or 'authentication' in error_msg.lower():
                raise ApiConnectionError(
                    "OpenAI APIキーが無効です。正しいAPIキーを設定してください。"
                )
            elif 'rate_limit' in error_msg.lower() or '429' in error_msg:
                raise ApiConnectionError(
                    "APIのレート制限に達しました。しばらく待ってから再度実行してください。"
                )
            elif 'file_size' in error_msg.lower() or 'too large' in error_msg.lower():
                raise TranscriptionError(
                    "ファイルサイズが大きすぎます。"
                    "Whisper APIは25MB以下のファイルをサポートしています。"
                )
            else:
                raise TranscriptionError(f"Whisper API文字起こしに失敗しました: {error_msg}")
    
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
    
    def estimate_cost(self, audio_duration_seconds: float) -> Dict[str, float]:
        """料金を推定
        
        Args:
            audio_duration_seconds: 音声の長さ（秒）
            
        Returns:
            dict: 料金情報
            
        参考: https://openai.com/api/pricing/ (2025年1月時点)
        - Whisper: $0.006 per minute
        """
        # Whisper APIの料金: $0.006 per minute (2025年1月時点)
        cost_per_minute = 0.006
        duration_minutes = audio_duration_seconds / 60.0
        cost_usd = duration_minutes * cost_per_minute
        cost_jpy = cost_usd * 155  # 1ドル=155円として概算（2025年1月為替レート）
        
        return {
            'cost_usd': cost_usd,
            'cost_jpy': cost_jpy,
            'duration_minutes': duration_minutes,
            'cost_per_minute': cost_per_minute,
            'model': 'whisper-1'  # 現在利用可能なモデル
        }
