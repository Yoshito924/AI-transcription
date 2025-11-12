#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI Whisper APIを使用した文字起こしサービス
"""

import os
from typing import Optional, Dict, Any, Tuple

from .exceptions import TranscriptionError, ApiConnectionError
from .logger import logger
from .utils import format_duration, get_file_size_mb


class WhisperApiService:
    """OpenAI Whisper APIを使用した文字起こしサービス"""
    
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
            
            # レスポンス形式に応じてテキストを抽出
            if response_format == 'text':
                text = transcript if isinstance(transcript, str) else str(transcript)
            elif response_format == 'json':
                text = transcript.get('text', '') if isinstance(transcript, dict) else str(transcript)
            elif response_format in ['verbose_json', 'srt', 'vtt']:
                if isinstance(transcript, dict):
                    text = transcript.get('text', '')
                else:
                    text = str(transcript)
            else:
                text = str(transcript)
            
            if not text or not text.strip():
                raise TranscriptionError("文字起こし結果が空でした")
            
            # メタデータを構築
            metadata = {
                'model': 'whisper-1',
                'language': language or 'auto',
                'file_size_mb': file_size_mb,
                'service': 'openai-whisper-api'
            }
            
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
        # verbose_json形式で取得してセグメント情報を含める
        text, metadata = self.transcribe(
            audio_path,
            language=language,
            response_format='verbose_json',
            **kwargs
        )
        
        # セグメント情報があれば追加
        try:
            import openai
            with open(audio_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format='verbose_json',
                    **kwargs
                )
            
            if isinstance(transcript, dict):
                segments = transcript.get('segments', [])
                metadata['segments'] = segments
                metadata['total_segments'] = len(segments)
        except Exception as e:
            logger.warning(f"セグメント情報の取得に失敗: {str(e)}")
        
        return text, metadata
    
    def estimate_cost(self, audio_duration_seconds: float) -> Dict[str, float]:
        """料金を推定
        
        Args:
            audio_duration_seconds: 音声の長さ（秒）
            
        Returns:
            dict: 料金情報
        """
        # Whisper APIの料金: $0.006 per minute
        cost_per_minute = 0.006
        duration_minutes = audio_duration_seconds / 60.0
        cost_usd = duration_minutes * cost_per_minute
        cost_jpy = cost_usd * 150  # 1ドル=150円として概算
        
        return {
            'cost_usd': cost_usd,
            'cost_jpy': cost_jpy,
            'duration_minutes': duration_minutes,
            'cost_per_minute': cost_per_minute
        }

