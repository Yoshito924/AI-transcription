#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
アプリケーション全体で使用する定数を定義
"""

# 音声処理関連の定数
MAX_AUDIO_SIZE_MB = 20  # Geminiの推奨上限サイズ
MAX_AUDIO_DURATION_SEC = 1200  # 20分（1200秒）
DEFAULT_AUDIO_BITRATE = '128k'
DEFAULT_SAMPLE_RATE = '44100'
DEFAULT_CHANNELS = 2
OVERLAP_SECONDS = 10  # セグメント間のオーバーラップ時間
SEGMENT_DURATION_SEC = 600  # 10分

# ファイル処理関連
SUPPORTED_AUDIO_FORMATS = ['mp3', 'wav', 'mp4', 'avi', 'mov', 'm4a', 'flac', 'ogg']
AUDIO_MIME_TYPE = 'audio/mpeg'

# UI関連の定数
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 850
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
STATUS_MESSAGE_MAX_LENGTH = 40
FILE_NAME_DISPLAY_MAX_LENGTH = 30

# レイアウト設定
SIDEBAR_WIDTH = 380
MAIN_CONTENT_MIN_WIDTH = 500
DRAG_DROP_AREA_HEIGHT = 120
CARD_PADDING = 20
SECTION_SPACING = 16

# API関連
PREFERRED_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
MIN_BITRATE = 32  # 最低品質確保のための最小ビットレート
MAX_BITRATE = 256  # 最大ビットレート
MAX_COMPRESSION_ATTEMPTS = 5

# AI生成パラメータ（安定した出力のため）
AI_GENERATION_CONFIG = {
    'temperature': 0.1,        # 低い温度で安定した出力
    'top_p': 0.8,             # 高品質な候補のみを考慮
    'top_k': 20,              # 上位20個の候補のみ
    'max_output_tokens': 8192, # 最大出力トークン数
    'candidate_count': 1       # 候補数は1つに限定
}

# セグメント統合設定
SEGMENT_MERGE_CONFIG = {
    'overlap_threshold': 0.6,     # 重複判定の閾値
    'min_overlap_words': 3,       # 重複判定に必要な最小単語数
    'enable_smart_merge': True,   # スマート統合を有効化
    'enable_context_analysis': True  # コンテキスト分析を有効化
}

# ディレクトリ名
CONFIG_DIR = "config"
DATA_DIR = "data"
OUTPUT_DIR = "output"

# ファイル名
CONFIG_FILE = "config.json"
PROMPT_FILE = "prompts.json"

# Gemini API料金設定（100万トークンあたりの米ドル）
GEMINI_PRICING = {
    "gemini-2.5-flash": {
        "input_text": 0.15,
        "input_audio": 1.00,
        "input_audio_batch": 0.50,  # バッチAPI使用時
        "output": 2.50,
        "output_batch": 1.25,  # バッチAPI使用時
        "recommended_use": "大量文字起こし（バッチ処理推奨）"
    },
    "gemini-2.0-flash-lite": {
        "input_text": 0.075,
        "input_audio": 0.075,  # 最安値
        "output": 0.30,
        "recommended_use": "コスト重視・大量処理"
    },
    "gemini-2.5-flash-lite": {
        "input_text": 0.15,
        "input_audio": 0.50,
        "output": 0.40,
        "recommended_use": "Flash Liteシリーズ最新版"
    },
    "gemini-2.0-flash": {
        "input_text": 0.10,
        "input_audio": 0.70,
        "output": 0.40,
        "recommended_use": "バランス型"
    },
    "gemini-1.5-flash": {
        "input_text_128k": 0.075,
        "input_text_over_128k": 0.15,
        "input_audio_per_second": 0.002,
        "output_128k": 0.30,
        "output_over_128k": 0.60,
        "recommended_use": "従来型"
    },
    "gemini-1.5-pro": {
        "input_text_128k": 1.25,
        "input_text_over_128k": 2.50,
        "output_128k": 5.00,
        "output_over_128k": 10.00,
        "recommended_use": "高品質処理"
    },
    "gemini-2.5-flash-live": {
        "input_audio": 3.00,  # リアルタイム処理
        "output": 2.00,
        "recommended_use": "リアルタイム処理専用"
    }
}
