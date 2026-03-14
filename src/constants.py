#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
アプリケーション全体で使用する定数を定義
"""

# 音声処理関連の定数
MAX_AUDIO_SIZE_MB = 20  # Geminiの推奨上限サイズ（リクエストの合計サイズが20MBを超える場合はFiles APIを使用）
WHISPER_API_MAX_AUDIO_SIZE_MB = 25  # OpenAI Speech-to-Text API のファイル上限
MAX_AUDIO_DURATION_SEC = 34200  # 9.5時間（34,200秒）- Gemini APIの最大音声長
# 参考: https://ai.google.dev/gemini-api/docs/audio?hl=ja
# - 1つのプロンプトでサポートされる音声データの最大長は9.5時間
# - 音声の1秒は32トークンとして表される（1分間の音声は1,920トークン）
AUDIO_TOKENS_PER_SECOND = 32  # 音声1秒あたりのトークン数
AUDIO_TOKENS_PER_MINUTE = 1920  # 音声1分あたりのトークン数（32 * 60）
DEFAULT_AUDIO_BITRATE = '128k'
DEFAULT_SAMPLE_RATE = '44100'
DEFAULT_CHANNELS = 2
DEFAULT_RECORDING_SAMPLE_RATE = 16000
DEFAULT_RECORDING_CHANNELS = 1
DEFAULT_RECORDING_GAIN_PERCENT = 100
OVERLAP_SECONDS = 10  # セグメント間のオーバーラップ時間
SEGMENT_DURATION_SEC = 600  # 10分

# ファイル処理関連
# FFmpegで音声抽出しやすい代表的な音声・動画形式を受け付ける
SUPPORTED_AUDIO_FORMATS = [
    'mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg', 'oga', 'opus', 'weba',
    'wma', 'aiff', 'aif', 'caf', 'amr', 'ac3', 'mp2',
    'mp4', 'm4v', 'mov', 'avi', 'mkv', 'webm', 'wmv',
    'mpeg', 'mpg', '3gp', '3g2', 'ts', 'mts', 'm2ts', 'flv'
]
SUPPORTED_MEDIA_FILE_GLOB = ' '.join(f'*.{ext}' for ext in SUPPORTED_AUDIO_FORMATS)
SUPPORTED_MEDIA_FILE_TYPES = [
    ('音声・動画ファイル', SUPPORTED_MEDIA_FILE_GLOB),
    ('すべてのファイル', '*.*')
]
AUDIO_MIME_TYPE = 'audio/mpeg'
# Gemini APIでサポートされる音声MIMEタイプ
GEMINI_SUPPORTED_AUDIO_MIME_TYPES = {
    'wav': 'audio/wav',
    'mp3': 'audio/mp3',
    'aiff': 'audio/aiff',
    'aac': 'audio/aac',
    'ogg': 'audio/ogg',
    'flac': 'audio/flac'
}

# UI関連の定数
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 780
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
STATUS_MESSAGE_MAX_LENGTH = 40
FILE_NAME_DISPLAY_MAX_LENGTH = 30
SUMMARY_TITLE_MAX_LENGTH = 30  # ファイル名に含める要約タイトルの最大文字数

# レイアウト設定
SIDEBAR_WIDTH = 380
MAIN_CONTENT_MIN_WIDTH = 500
DRAG_DROP_AREA_HEIGHT = 110
CARD_PADDING = 16
CARD_INNER_PADDING = 12
SECTION_SPACING = 8
MAIN_PADDING_X = 18
MAIN_PADDING_Y = 14
ACCENT_STRIPE_WIDTH = 4
HISTORY_ROW_HEIGHT = 26
QUEUE_LISTBOX_HEIGHT = 3

# API関連（優先順位: 安定版 → 最新プレビュー → 高速 → コスト重視 → 従来型）
# 2025年11月時点の推奨: gemini-2.5-flashが安定版として推奨
PREFERRED_MODELS = [
    "gemini-2.5-flash",                  # 2.5 Flash安定版（推奨）
    "gemini-2.5-flash-preview-09-2025",  # 2025年9月最新プレビュー版
    "gemini-2.5-flash-preview-08-2025",  # 2025年8月プレビュー版
    "gemini-2.5-flash-lite",             # Flash Lite 2.5
    "gemini-2.0-flash-lite",             # 最軽量・最速
    "gemini-2.0-flash",                  # Flash 2.0
    "gemini-1.5-flash",                  # Flash 1.5（後方互換性）
    "gemini-1.5-pro",                    # Pro 1.5
    "gemini-pro"                         # 従来版
]
# タイトル生成用の軽量モデル（優先順位順）
TITLE_GENERATION_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
]

MIN_BITRATE = 32  # 最低品質確保のための最小ビットレート
MAX_BITRATE = 256  # 最大ビットレート
MAX_COMPRESSION_ATTEMPTS = 5

# トークン数の概算パラメータ（使用量記録用）
TOKEN_ESTIMATION_FACTOR = 1000  # 概算: 1MB ≈ 1000トークン
OUTPUT_TOKEN_RATIO = 0.1  # 出力トークン数 ≈ 入力トークン数の10%

# AI生成パラメータ（安定した出力のため）
AI_GENERATION_CONFIG = {
    'temperature': 0.1,        # 低い温度で安定した出力
    'top_p': 0.8,             # 高品質な候補のみを考慮
    'top_k': 20,              # 上位20個の候補のみ
    'max_output_tokens': 8192, # 最大出力トークン数
    'candidate_count': 1       # 候補数は1つに限定
}

# Gemini API 安全性フィルター設定（文字起こし用に緩和）
# 参考: https://ai.google.dev/gemini-api/docs/safety-settings
# 文字起こしでは音声の内容をそのまま書き起こす必要があるため、
# 安全性フィルターを緩和して誤ブロックを防ぐ
# しきい値:
#   BLOCK_NONE: すべて許可（文字起こし推奨）
#   BLOCK_ONLY_HIGH: 高リスクのみブロック
#   BLOCK_MEDIUM_AND_ABOVE: 中リスク以上をブロック（デフォルト）
#   BLOCK_LOW_AND_ABOVE: 低リスク以上をブロック
SAFETY_SETTINGS_TRANSCRIPTION = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
]

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
RECORDINGS_DIR = "recordings"

# ファイル名
CONFIG_FILE = "config.json"
PROMPT_FILE = "prompts.json"

# Gemini API料金設定（100万トークンあたりの米ドル）
# 注意: 音声入力の場合、モデルによって計算方法が異なる
# - Gemini 2.x系: トークン数ベース（100万トークンあたり）
# - Gemini 1.5系: 秒数ベース（音声1秒あたり0.002ドル）
# 参考: https://ai.google.dev/gemini-api/docs/pricing?hl=ja
GEMINI_PRICING = {
    "gemini-2.5-flash": {
        "input_text": 0.30,  # プロンプト200Kトークン以下（標準）
        "input_text_over_200k": 0.60,  # プロンプト200Kトークン超
        "input_audio": 1.00,  # 100万トークンあたり（音声入力）
        "input_audio_batch": 0.50,  # バッチAPI使用時（50%割引）
        "output": 2.50,  # プロンプト200Kトークン以下（標準）
        "output_over_200k": 5.00,  # プロンプト200Kトークン超
        "output_batch": 1.25,  # バッチAPI使用時（50%割引）
        "pricing_type": "token_based",
        "recommended_use": "大量文字起こし（バッチ処理推奨）"
    },
    "gemini-2.0-flash-lite": {
        "input_text": 0.075,
        "input_audio": 0.075,  # 100万トークンあたり（最安値・音声/テキスト同額）
        "input_audio_batch": 0.0375,  # バッチAPI使用時（50%割引）
        "output": 0.30,
        "output_batch": 0.15,  # バッチAPI使用時（50%割引）
        "pricing_type": "token_based",
        "recommended_use": "コスト重視・大量処理"
    },
    "gemini-2.5-flash-lite": {
        "input_text": 0.10,
        "input_audio": 0.30,  # 100万トークンあたり（音声入力）
        "input_audio_batch": 0.15,  # バッチAPI使用時（50%割引）
        "output": 0.40,
        "output_batch": 0.20,  # バッチAPI使用時（50%割引）
        "pricing_type": "token_based",
        "recommended_use": "Flash Liteシリーズ最新版"
    },
    "gemini-2.0-flash": {
        "input_text": 0.10,
        "input_audio": 0.70,  # 100万トークンあたり（音声入力）
        "input_audio_batch": 0.35,  # バッチAPI使用時（50%割引）
        "output": 0.40,
        "output_batch": 0.20,  # バッチAPI使用時（50%割引）
        "pricing_type": "token_based",
        "recommended_use": "バランス型"
    },
    "gemini-1.5-flash": {
        "input_text_128k": 0.075,
        "input_text_over_128k": 0.15,
        "input_audio_per_second": 0.002,  # 音声1秒あたり（秒数ベース）
        "output_128k": 0.30,
        "output_over_128k": 0.60,
        "pricing_type": "mixed",  # テキストはトークンベース、音声は秒数ベース
        "recommended_use": "従来型"
    },
    "gemini-1.5-pro": {
        "input_text_128k": 1.25,
        "input_text_over_128k": 2.50,
        "input_audio_per_second": 0.002,  # 音声1秒あたり（秒数ベース）
        "output_128k": 5.00,
        "output_over_128k": 10.00,
        "pricing_type": "mixed",
        "recommended_use": "高品質処理"
    },
    "gemini-2.5-flash-live": {
        "input_audio": 3.00,  # 100万トークンあたり（リアルタイム処理）
        "output": 2.00,
        "pricing_type": "token_based",
        "recommended_use": "リアルタイム処理専用"
    }
}
