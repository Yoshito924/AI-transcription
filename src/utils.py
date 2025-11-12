#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
汎用ユーティリティ関数
"""

import os
import subprocess
import platform
from datetime import datetime

from .constants import (
    DEFAULT_AUDIO_BITRATE, DEFAULT_SAMPLE_RATE, DEFAULT_CHANNELS, GEMINI_PRICING,
    AUDIO_TOKENS_PER_SECOND, MAX_AUDIO_DURATION_SEC
)


def get_timestamp():
    """現在の日時のタイムスタンプを取得する"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_formatted_date():
    """現在の日時を日本語形式で取得する"""
    return datetime.now().strftime("%Y年%m月%d日 %H:%M")


def format_file_size(size_bytes):
    """ファイルサイズを人間が読める形式に変換する"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration(seconds):
    """秒数を時:分:秒形式に変換"""
    if seconds is None:
        return "不明"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}時間{minutes}分{secs}秒"
    else:
        return f"{minutes}分{secs}秒"


def ensure_dir(directory):
    """ディレクトリが存在することを確認し、なければ作成する"""
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory


def check_ffmpeg():
    """FFmpegがインストールされているか確認する"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
        return result.returncode == 0
    except:
        return False


def open_file(file_path):
    """ファイルをデフォルトのアプリケーションで開く"""
    try:
        if platform.system() == 'Windows':
            os.startfile(file_path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', file_path])
        else:  # Linux
            subprocess.run(['xdg-open', file_path])
        return True
    except:
        return False


def open_directory(dir_path):
    """ディレクトリをファイルエクスプローラーで開く"""
    try:
        if platform.system() == 'Windows':
            os.startfile(dir_path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', dir_path])
        else:  # Linux
            subprocess.run(['xdg-open', dir_path])
        return True
    except:
        return False


def normalize_file_path(file_path):
    """ファイルパスを正規化（D&D対応）"""
    file_path = file_path.strip()
    if file_path.startswith('{') and file_path.endswith('}'):
        file_path = file_path[1:-1]
    return file_path.replace('\\', '/')


def truncate_display_name(name, max_length):
    """表示名を指定の長さに切り詰める"""
    if len(name) > max_length:
        return name[:max_length-3] + "..."
    return name


def calculate_gemini_cost(model_name, input_tokens, output_tokens, is_audio_input=False, audio_duration_seconds=None):
    """Gemini APIの使用料金を計算する

    Args:
        model_name: モデル名
        input_tokens: 入力トークン数
        output_tokens: 出力トークン数
        is_audio_input: 音声入力かどうか
        audio_duration_seconds: 音声の長さ（秒）- Gemini 1.5系の音声入力時に必要

    Returns:
        dict: コスト情報
    """
    # モデル名を正規化してマッチング
    pricing_key = None
    for key in GEMINI_PRICING.keys():
        if key in model_name:
            pricing_key = key
            break

    # 未知のモデルの場合はgemini-2.0-flashの料金を適用
    if not pricing_key:
        pricing_key = "gemini-2.0-flash"

    pricing = GEMINI_PRICING[pricing_key]
    input_cost = 0
    output_cost = 0

    # Gemini 1.5系の音声入力は秒数ベースで計算
    if "gemini-1.5" in model_name and is_audio_input:
        if audio_duration_seconds and "input_audio_per_second" in pricing:
            # 音声入力は秒数ベース
            input_cost = audio_duration_seconds * pricing["input_audio_per_second"]
        else:
            # 秒数が不明な場合は概算（入力トークンから推測）
            # 参考: https://ai.google.dev/gemini-api/docs/audio?hl=ja
            # 音声の1秒は32トークンとして表される（1分間の音声は1,920トークン）
            estimated_seconds = input_tokens / AUDIO_TOKENS_PER_SECOND  # 公式ドキュメントに基づく正確な換算
            input_cost = estimated_seconds * pricing.get("input_audio_per_second", 0.002)

        # 出力は通常通りトークンベース
        if output_tokens <= 128000:
            output_cost = (output_tokens / 1000000) * pricing["output_128k"]
        else:
            output_cost = (output_tokens / 1000000) * pricing["output_over_128k"]

    # Gemini 1.5系のテキスト入力
    elif "gemini-1.5" in model_name and not is_audio_input:
        # 128Kトークンを基準に料金を分ける
        if input_tokens <= 128000:
            input_cost = (input_tokens / 1000000) * pricing["input_text_128k"]
            output_cost = (output_tokens / 1000000) * pricing["output_128k"]
        else:
            input_cost = (input_tokens / 1000000) * pricing["input_text_over_128k"]
            output_cost = (output_tokens / 1000000) * pricing["output_over_128k"]

    # Gemini 2.x系（トークンベース）
    else:
        # プロンプトサイズによる料金の違いを考慮（200Kトークンが境界）
        # gemini-2.5-flashはプロンプトサイズで料金が変わる
        if "gemini-2.5-flash" in model_name:
            if input_tokens <= 200000:
                input_price = pricing.get("input_text", 0.15)
                output_price = pricing.get("output", 2.50)
            else:
                input_price = pricing.get("input_text_over_200k", pricing.get("input_text", 0.30))
                output_price = pricing.get("output_over_200k", pricing.get("output", 5.00))
        else:
            # その他の2.x系モデルは標準料金
            input_price = pricing.get("input_text", 0.10)
            output_price = pricing.get("output", 0.40)
        
        if is_audio_input:
            # 音声入力の場合、input_audioがあればそれを使用、なければinput_textを使用
            input_price = pricing.get("input_audio", input_price)
        
        input_cost = (input_tokens / 1000000) * input_price
        output_cost = (output_tokens / 1000000) * output_price

    total_cost = input_cost + output_cost
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "audio_duration_seconds": audio_duration_seconds,
        "pricing_note": "秒数ベース" if ("gemini-1.5" in model_name and is_audio_input) else "トークンベース"
    }


def format_token_usage(cost_info):
    """トークン使用量と料金を見やすく整形する"""
    input_tokens = cost_info["input_tokens"]
    output_tokens = cost_info["output_tokens"]
    total_tokens = input_tokens + output_tokens
    total_cost = cost_info["total_cost"]
    
    # トークン数の表示
    if total_tokens >= 1000:
        token_display = f"{total_tokens:,}トークン"
    else:
        token_display = f"{total_tokens}トークン"
    
    # 料金の表示（ドル）
    if total_cost >= 0.01:
        cost_display = f"${total_cost:.3f}"
    elif total_cost >= 0.001:
        cost_display = f"${total_cost:.4f}"
    else:
        cost_display = f"${total_cost:.5f}"
    
    # 円換算（1ドル=150円として概算）
    yen_cost = total_cost * 150
    if yen_cost >= 0.01:
        yen_display = f"（約{yen_cost:.2f}円）"
    else:
        yen_display = f"（約{yen_cost:.3f}円）"
    
    return f"{token_display} / {cost_display} {yen_display}"
