#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from datetime import datetime

def setup_logger(name, log_dir='logs'):
    """アプリケーション用のロガーを設定"""
    
    # ログディレクトリの作成
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # ログファイル名（日付付き）
    log_filename = os.path.join(log_dir, f'transcription_{datetime.now().strftime("%Y%m%d")}.log')
    
    # ロガーの設定
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 既存のハンドラーをクリア
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # ファイルハンドラー（詳細ログ）
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # コンソールハンドラー（重要な情報のみ）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # ハンドラーをロガーに追加
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# メインロガーのインスタンス
logger = setup_logger('ai_transcription')