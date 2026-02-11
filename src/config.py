#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json

from .constants import (
    DEFAULT_WINDOW_WIDTH, 
    DEFAULT_WINDOW_HEIGHT, 
    CONFIG_DIR, 
    DATA_DIR, 
    CONFIG_FILE, 
    PROMPT_FILE
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
            "api_key": "",  # Gemini API用
            "openai_api_key": "",  # OpenAI API用（Whisper API等）
            "transcription_engine": "gemini",  # "gemini" または "whisper" または "whisper-api"
            "whisper_model": "base"  # "tiny", "base", "small", "medium", "large", "turbo"
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


class PromptManager:
    """プロンプト設定の管理クラス"""
    
    def __init__(self, app_dir):
        data_dir = os.path.join(app_dir, DATA_DIR)
        self.prompt_file = os.path.join(data_dir, PROMPT_FILE)
        self.prompts = self.load()
    
    def load(self):
        """プロンプトファイルを読み込む"""
        if os.path.exists(self.prompt_file):
            try:
                with open(self.prompt_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return self.default_prompts()
        return self.default_prompts()
    
    def save(self):
        """プロンプトファイルを保存する"""
        # dataディレクトリがなければ作成
        os.makedirs(os.path.dirname(self.prompt_file), exist_ok=True)
        
        with open(self.prompt_file, 'w', encoding='utf-8') as f:
            json.dump(self.prompts, f, ensure_ascii=False, indent=2)
    
    def default_prompts(self):
        """デフォルトのプロンプト設定"""
        return {
            "transcription": {
                "name": "文字起こし",
                "prompt": "以下の音声ファイルを文字起こししてください。"
            },
            "meeting_minutes": {
                "name": "議事録作成",
                "prompt": """以下の文字起こしから議事録を作成してください。

以下の形式で整理してください：
## 会議の概要
- 日時、参加者、目的

## 主要な議題と内容
- 議題ごとに箇条書きで整理

## 決定事項
- 明確に決定された事項をリストアップ

## アクションアイテム
- 誰が何をいつまでに行うかを明記

## その他
- 次回会議の予定など

{transcription}"""
            },
            "summary": {
                "name": "要約",
                "prompt": """以下の文字起こしを簡潔に要約してください。

要約のポイント：
- 重要な内容を300字程度でまとめる
- 主要なトピックと結論を含める
- 客観的で分かりやすい表現を使用する

{transcription}"""
            },
            "detailed_summary": {
                "name": "詳細要約",
                "prompt": """以下の文字起こしを詳細に要約してください。

## 主要トピック
内容の中心となるテーマを整理

## 重要なポイント
- 話し合われた主要な内容
- 提示された意見や提案
- 結論や合意事項

## 詳細な内容
具体的な議論の流れと詳細を記載

{transcription}"""
            }
        }
    
    def get_prompts(self):
        """全プロンプトを取得"""
        return self.prompts
    
    def get_sorted_names(self):
        """プロンプト名のソートされたリストを取得"""
        prompt_names = [(key, self.prompts[key]["name"]) for key in self.prompts]
        prompt_names.sort(key=lambda x: x[1])  # 名前でソート
        return [name for _, name in prompt_names]
    
    def get_prompt_by_name(self, name):
        """名前からプロンプト情報を取得"""
        for key, info in self.prompts.items():
            if info["name"] == name:
                return info
        return None
    
    def get_key_by_name(self, name):
        """名前からプロンプトキーを取得"""
        for key, info in self.prompts.items():
            if info["name"] == name:
                return key
        return None
    
    def save_prompt(self, old_name, new_name, prompt_text):
        """プロンプトを保存（更新または新規作成）"""
        # 既存のプロンプトを更新するか新規作成
        existing_key = self.get_key_by_name(old_name)
        
        if existing_key:
            # 既存のプロンプトを更新
            self.prompts[existing_key]["name"] = new_name
            self.prompts[existing_key]["prompt"] = prompt_text
        else:
            # 新しいプロンプトを作成
            new_key = new_name.lower().replace(' ', '_')
            counter = 1
            while new_key in self.prompts:
                new_key = f"{new_name.lower().replace(' ', '_')}_{counter}"
                counter += 1
            
            self.prompts[new_key] = {
                "name": new_name,
                "prompt": prompt_text
            }
        
        # 保存
        self.save()
    
    def delete_prompt(self, name):
        """プロンプトを削除"""
        key = self.get_key_by_name(name)
        if key:
            del self.prompts[key]
            self.save()
