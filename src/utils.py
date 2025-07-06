#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
汎用ユーティリティ関数
"""

import os
import subprocess
import platform
from datetime import datetime

from .constants import DEFAULT_AUDIO_BITRATE, DEFAULT_SAMPLE_RATE, DEFAULT_CHANNELS, GEMINI_PRICING


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


def calculate_gemini_cost(model_name, input_tokens, output_tokens, is_audio_input=False):
    """Gemini APIの使用料金を計算する"""
    if model_name not in GEMINI_PRICING:
        # 未知のモデルの場合はgemini-2.0-flashの料金を適用
        model_name = "gemini-2.0-flash"
    
    pricing = GEMINI_PRICING[model_name]
    input_cost = 0
    output_cost = 0
    
    # 入力料金の計算
    if "gemini-2.0-flash" in model_name or "gemini-2.5-flash" in model_name:
        if is_audio_input:
            input_cost = (input_tokens / 1000000) * pricing["input_audio"]
        else:
            input_cost = (input_tokens / 1000000) * pricing["input_text"]
        output_cost = (output_tokens / 1000000) * pricing["output"]
    
    elif "gemini-1.5" in model_name:
        # 128Kトークンを基準に料金を分ける
        if input_tokens <= 128000:
            input_cost = (input_tokens / 1000000) * pricing["input_text_128k"]
            output_cost = (output_tokens / 1000000) * pricing["output_128k"]
        else:
            input_cost = (input_tokens / 1000000) * pricing["input_text_over_128k"]
            output_cost = (output_tokens / 1000000) * pricing["output_over_128k"]
    
    total_cost = input_cost + output_cost
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
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
