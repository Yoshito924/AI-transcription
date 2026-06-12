#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json

from .constants import (
    DEFAULT_WINDOW_WIDTH, 
    DEFAULT_WINDOW_HEIGHT, 
    DEFAULT_TRIM_LONG_SILENCE,
    DEFAULT_SILENCE_TRIM_MODE,
    DEFAULT_SILENCE_TRIM_THRESHOLD_DB,
    DEFAULT_SILENCE_TRIM_MIN_SILENCE_SEC,
    DEFAULT_RECORDING_GAIN_PERCENT,
    OLLAMA_DEFAULT_MODEL,
    CONFIG_DIR, 
    CONFIG_FILE, 
    RECORDINGS_DIR
)
from .exceptions import ConfigurationError

class Config:
    """アプリケーション設定の管理クラス"""
    
    def __init__(self, app_dir):
        config_dir = os.path.join(app_dir, CONFIG_DIR)
        self.config_file = os.path.join(config_dir, CONFIG_FILE)
        self.config = self.load()
        
        # デフォルト設定
        self.defaults = {
            "window_width": DEFAULT_WINDOW_WIDTH,
            "window_height": DEFAULT_WINDOW_HEIGHT,
            "window_x": None,
            "window_y": None,
            "last_open_tab": "file",
            "api_key": "",  # Gemini API用
            "openai_api_key": "",  # OpenAI API用（Whisper API等）
            "transcription_engine": "whisper",  # "gemini" または "whisper" または "whisper-api"
            "gemini_safety_filter_recovery": "segment-whisper",  # "segment-whisper", "segment", "whisper"
            "additional_processing_engine": "ollama",  # "gemini" または "ollama"
            "title_generation_engine": "ollama",  # "ollama", "auto", "gemini", "disabled"
            "ollama_model": OLLAMA_DEFAULT_MODEL,
            "whisper_model": "large-v3",
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
            "recording_input_channels": [1]
        }
        
        # デフォルト値で埋める
        for key, value in self.defaults.items():
            if key not in self.config:
                self.config[key] = value
    
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
        """設定ファイルを保存する"""
        # configディレクトリがなければ作成
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def get(self, key, default=None):
        """設定値を取得する"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """設定値を設定する"""
        self.config[key] = value
    
    def save_window_geometry(self, root):
        """ウィンドウのジオメトリ情報を保存"""
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
    
    def apply_window_geometry(self, root):
        """保存されたジオメトリ情報をウィンドウに適用"""
        width = self.get("window_width", DEFAULT_WINDOW_WIDTH)
        height = self.get("window_height", DEFAULT_WINDOW_HEIGHT)
        
        geometry = f"{width}x{height}"
        
        # 位置情報がある場合は追加
        x = self.get("window_x")
        y = self.get("window_y")
        
        if x is not None and y is not None:
            geometry += f"+{x}+{y}"
        
        root.geometry(geometry)

