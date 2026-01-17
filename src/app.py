#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tkinter as tk
from tkinter import messagebox
import re

from .ui import setup_ui
from .config import Config
from .processor import FileProcessor
from .controllers import TranscriptionController
from .usage_tracker import UsageTracker
from .constants import OUTPUT_DIR, FILE_NAME_DISPLAY_MAX_LENGTH
from .utils import (
    open_file,
    open_directory,
    normalize_file_path,
    truncate_display_name,
    get_engine_value,
    get_whisper_model_value
)
from .exceptions import FileProcessingError

class TranscriptionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI文字起こしアプリ")
        
        # アプリケーションのデータディレクトリ
        self.app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = os.path.join(self.app_dir, OUTPUT_DIR)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 設定の管理
        self.config = Config(self.app_dir)
        
        # 使用量追跡
        self.usage_tracker = UsageTracker(self.app_dir)
        
        # 変数初期化
        self.api_key = tk.StringVar(value=self.config.get("api_key", ""))
        self.preferred_model = None  # 手動選択されたモデル
        
        # プロセッサの初期化
        self.processor = FileProcessor(self.output_dir)
        
        # UIの構築
        self.ui_elements = setup_ui(self)
        
        # コントローラーの初期化
        self.ui_elements['api_key_var'] = self.api_key
        self.ui_elements['root'] = self.root
        self.controller = TranscriptionController(
            self.processor, self.config, self.usage_tracker, self.ui_elements
        )
        self.controller.set_update_history_callback(self.update_history)
        self.controller.update_usage_callback = self.update_usage_display
        
        
        # ウィンドウサイズと位置の設定を適用（UI構築後）
        self.config.apply_window_geometry(self.root)
        
        # 初期設定
        self.update_history()
        self.update_usage_display()
        
        # 終了時にジオメトリを保存
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_closing(self):
        """ウィンドウが閉じられるときの処理"""
        if self.controller.is_processing:
            result = messagebox.askyesno(
                "確認", 
                "処理が進行中です。本当に終了しますか？"
            )
            if not result:
                return
        
        # ウィンドウのジオメトリを保存
        self.config.save_window_geometry(self.root)
        
        # 設定を保存
        self.config.set("api_key", self.api_key.get())
        
        # エンジン選択とWhisperモデル選択を保存
        self._save_engine_settings()
        self.config.save()
        
        # アプリケーションを終了
        self.root.destroy()
    
    def toggle_api_key_visibility(self):
        """APIキーの表示/非表示を切り替える"""
        entry = self.ui_elements['api_entry']
        if entry['show'] == '*':
            entry.config(show='')
        else:
            entry.config(show='*')
    
    def check_api_connection(self):
        """API接続を確認"""
        # エンジンの確認
        engine_value = get_engine_value(self.ui_elements)
        
        if engine_value == 'whisper':
            # Whisperモードの場合は利用可能性を確認
            self.controller.update_status("Whisper利用可能性を確認中...")
            self.root.update_idletasks()
            
            try:
                is_available, message = self.processor.whisper_service.test_whisper_availability()
                
                if is_available:
                    device_info = self.processor.whisper_service.get_device_info()
                    if 'model_label' in self.ui_elements:
                        self.ui_elements['model_label'].config(text=f"Whisper ({device_info})")
                    
                    messagebox.showinfo("成功", f"Whisperが利用可能です！\n{message}")
                    self.controller.update_status(f"Whisper利用可能: {device_info}")
                else:
                    raise Exception(message)
                    
            except Exception as e:
                messagebox.showerror("エラー", f"Whisperエラー: {str(e)}")
                self.controller.update_status("Whisperエラー")
                if 'model_label' in self.ui_elements:
                    self.ui_elements['model_label'].config(text="Whisperエラー")
        elif engine_value == 'whisper-api':
            # Whisper APIモードの場合はAPI接続を確認
            api_key = self.api_key.get().strip()
            if not api_key:
                messagebox.showerror("エラー", "Whisper APIモードではAPIキーを入力してください。")
                return
            
            self.controller.update_status("Whisper API接続を確認中...")
            self.root.update_idletasks()
            
            try:
                from .whisper_api_service import WhisperApiService
                service = WhisperApiService(api_key=api_key)
                
                # 簡単なテスト（実際にはファイルが必要なので、サービスが初期化できればOK）
                if 'model_label' in self.ui_elements:
                    self.ui_elements['model_label'].config(text="Whisper API")
                
                messagebox.showinfo("成功", "Whisper APIへの接続準備が完了しました！")
                self.controller.update_status("Whisper API接続準備完了")
            except Exception as e:
                messagebox.showerror("エラー", f"Whisper APIエラー: {str(e)}")
                self.controller.update_status("Whisper APIエラー")
                if 'model_label' in self.ui_elements:
                    self.ui_elements['model_label'].config(text="Whisper APIエラー")
        else:
            # Geminiモードの場合は従来通り
            api_key = self.api_key.get().strip()
            if not api_key:
                messagebox.showerror("エラー", "APIキーを入力してください。")
                return
            
            self.controller.update_status("API接続を確認中...")
            self.root.update_idletasks()
            
            try:
                result = self.processor.test_api_connection(api_key)
                
                # 使用モデルを表示
                if 'model_label' in self.ui_elements:
                    self.ui_elements['model_label'].config(text=result)
                
                # 設定を保存
                self.config.set("api_key", api_key)
                # エンジン設定も同時に保存
                self._save_engine_settings()
                self.config.save()
                
                messagebox.showinfo("成功", f"Gemini APIへの接続に成功しました！\n使用モデル: {result}")
                self.controller.update_status(f"API接続確認完了 - モデル: {result}")
            except Exception as e:
                messagebox.showerror("エラー", f"API接続エラー: {str(e)}")
                self.controller.update_status("API接続エラー")
                if 'model_label' in self.ui_elements:
                    self.ui_elements['model_label'].config(text="接続エラー")
    
    def browse_file(self, event=None):
        """ファイル選択ダイアログを表示"""
        from tkinter import filedialog
        file_types = [
            ('音声・動画ファイル', '*.mp3 *.wav *.mp4 *.avi *.mov *.m4a *.flac *.ogg'),
            ('すべてのファイル', '*.*')
        ]
        file_path = filedialog.askopenfilename(filetypes=file_types)
        if file_path:
            self.load_file(file_path)
    
    def load_file(self, file_path):
        """ファイルを読み込む（コントローラーに委譲）"""
        self.controller.load_file(file_path)
    
    def start_process(self, process_type):
        """処理を開始（コントローラーに委譲）"""
        if process_type == "transcription":
            self.controller.start_transcription()
    
    
    def update_history(self):
        """履歴リストを更新"""
        tree = self.ui_elements['history_tree']
        
        # リストをクリア
        for item in tree.get_children():
            tree.delete(item)
        
        # ファイルリスト取得と表示
        files = self.processor.get_output_files()
        for file, date, size, _ in files:
            tree.insert('', 'end', values=(file, date, size))
    
    
    def open_output_file(self, event=None):
        """選択された出力ファイルを開く"""
        tree = self.ui_elements['history_tree']
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("情報", "ファイルを選択してください。")
            return
        
        item = tree.item(selection[0])
        filename = item['values'][0]
        file_path = os.path.join(self.output_dir, filename)
        
        if not open_file(file_path):
            messagebox.showerror("エラー", f"ファイル '{filename}' を開けません。")
    
    def open_output_folder(self):
        """出力フォルダを開く"""
        if not open_directory(self.output_dir):
            messagebox.showerror("エラー", "出力フォルダを開けません。")
    
    def update_usage_display(self):
        """使用量表示を更新"""
        try:
            usage_data = self.usage_tracker.get_current_month_usage()
            
            # UI要素の更新（コンパクト版）
            self.ui_elements['usage_sessions'].config(text=f"回数: {usage_data['total_sessions']}回")
            
            total_tokens = usage_data['total_input_tokens'] + usage_data['total_output_tokens']
            if total_tokens > 1000:
                tokens_text = f"トークン: {total_tokens//1000}K"
            else:
                tokens_text = f"トークン: {total_tokens}"
            self.ui_elements['usage_tokens'].config(text=tokens_text)
            
            self.ui_elements['usage_cost_usd'].config(text=f"${usage_data['total_cost_usd']:.3f}")
            self.ui_elements['usage_cost_jpy'].config(text=f"¥{usage_data['total_cost_jpy']:.0f}")
            
        except Exception as e:
            print(f"使用量表示の更新エラー: {e}")
    
    def _save_engine_settings(self):
        """エンジン設定を保存"""
        if hasattr(self, 'ui_elements'):
            engine_value = get_engine_value(self.ui_elements)
            whisper_model = get_whisper_model_value(self.ui_elements)
            self.config.set("transcription_engine", engine_value)
            self.config.set("whisper_model", whisper_model)
    