#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
アプリケーション固有の例外クラスを定義
"""


class TranscriptionError(Exception):
    """文字起こし処理関連のエラー"""
    pass


class AudioProcessingError(Exception):
    """音声処理関連のエラー"""
    pass


class ApiConnectionError(Exception):
    """API接続関連のエラー"""
    pass


class FileProcessingError(Exception):
    """ファイル処理関連のエラー"""
    pass


class ConfigurationError(Exception):
    """設定関連のエラー"""
    pass
