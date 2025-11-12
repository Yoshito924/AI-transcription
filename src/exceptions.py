#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
アプリケーション固有の例外クラスを定義
"""


class TranscriptionError(Exception):
    """文字起こし処理関連のエラー"""
    def __init__(self, message, error_code=None, user_message=None, solution=None):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message
        self.solution = solution

    def get_detailed_message(self):
        """ユーザー向けの詳細メッセージを取得"""
        parts = [f"❌ {self.user_message}"]
        if self.solution:
            parts.append(f"\n💡 対処法: {self.solution}")
        return "\n".join(parts)


class AudioProcessingError(Exception):
    """音声処理関連のエラー"""
    def __init__(self, message, error_code=None, user_message=None, solution=None):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message
        self.solution = solution

    def get_detailed_message(self):
        """ユーザー向けの詳細メッセージを取得"""
        parts = [f"❌ {self.user_message}"]
        if self.solution:
            parts.append(f"\n💡 対処法: {self.solution}")
        return "\n".join(parts)


class ApiConnectionError(Exception):
    """API接続関連のエラー"""
    def __init__(self, message, error_code=None, user_message=None, solution=None):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message
        self.solution = solution

    def get_detailed_message(self):
        """ユーザー向けの詳細メッセージを取得"""
        parts = [f"❌ {self.user_message}"]
        if self.solution:
            parts.append(f"\n💡 対処法: {self.solution}")
        return "\n".join(parts)


class FileProcessingError(Exception):
    """ファイル処理関連のエラー"""
    def __init__(self, message, error_code=None, user_message=None, solution=None):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message
        self.solution = solution

    def get_detailed_message(self):
        """ユーザー向けの詳細メッセージを取得"""
        parts = [f"❌ {self.user_message}"]
        if self.solution:
            parts.append(f"\n💡 対処法: {self.solution}")
        return "\n".join(parts)


class ConfigurationError(Exception):
    """設定関連のエラー"""
    def __init__(self, message, error_code=None, user_message=None, solution=None):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message
        self.solution = solution

    def get_detailed_message(self):
        """ユーザー向けの詳細メッセージを取得"""
        parts = [f"❌ {self.user_message}"]
        if self.solution:
            parts.append(f"\n💡 対処法: {self.solution}")
        return "\n".join(parts)
