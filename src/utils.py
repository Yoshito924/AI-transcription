#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import platform
import tempfile
from datetime import datetime

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

def convert_audio(input_file, output_format='mp3', bitrate='128k', sample_rate='44100', channels=2):
    """音声/動画ファイルを指定したフォーマットに変換する"""
    with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as temp_file:
        output_path = temp_file.name
    
    try:
        # FFmpegで変換
        cmd = [
            'ffmpeg', '-y', '-i', input_file, 
            '-vn',                         # 映像を除去
            '-ar', str(sample_rate),       # サンプルレート
            '-ac', str(channels),          # チャンネル数
            '-b:a', bitrate,               # ビットレート
            output_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='replace')
            raise Exception(f"音声変換エラー: {error_msg}")
        
        return output_path
    
    except Exception as e:
        # エラー時は一時ファイルを削除
        try:
            os.unlink(output_path)
        except:
            pass
        raise e

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
