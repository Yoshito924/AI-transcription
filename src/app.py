#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tkinter as tk
from tkinter import messagebox
import threading

from src.ui import setup_ui
from src.config import Config, PromptManager
from src.processor import FileProcessor

class TranscriptionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI文字起こしアプリ")
        
        # アプリケーションのデータディレクトリ
        self.app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = os.path.join(self.app_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 設定とプロンプトの管理
        self.config = Config(self.app_dir)
        self.prompt_manager = PromptManager(self.app_dir)
        
        # 変数初期化
        self.api_key = tk.StringVar(value=self.config.get("api_key", ""))
        self.current_file = None
        self.is_processing = False
        
        # ダミーのstatus_labelを初期化（UI構築時に上書きされる）
        self.ui_elements = {'status_label': tk.Label(root)}
        
        # プロセッサの初期化
        self.processor = FileProcessor(self.output_dir)
        
        # UIの構築
        self.ui_elements = setup_ui(self)
        
        # ウィンドウサイズと位置の設定を適用（UI構築後）
        self.config.apply_window_geometry(self.root)
        
        # 履歴の更新
        self.update_history()
        
        # プロンプトのアップデート
        self.update_prompt_combo()
        
        # 終了時にジオメトリを保存
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_closing(self):
        """ウィンドウが閉じられるときの処理"""
        if self.is_processing:
            result = messagebox.askyesno(
                "確認", 
                "処理が進行中です。本当に終了しますか？"
            )
            if not result:
                return
        
        # ウィンドウのジオメトリを保存
        self.config.save_window_geometry(self.root)
        
        # APIキーを保存
        self.config.set("api_key", self.api_key.get())
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
        api_key = self.api_key.get().strip()
        if not api_key:
            messagebox.showerror("エラー", "APIキーを入力してください。")
            return
        
        self.ui_elements['status_label'].config(text="API接続を確認中...")
        self.root.update_idletasks()
        
        try:
            # Gemini APIの接続テスト
            result = self.processor.test_api_connection(api_key)
            
            # 設定を保存
            self.config.set("api_key", api_key)
            self.config.save()
            
            messagebox.showinfo("成功", "Gemini APIへの接続に成功しました！")
            self.ui_elements['status_label'].config(text="API接続確認完了。処理の準備ができました。")
        except Exception as e:
            messagebox.showerror("エラー", f"API接続エラー: {str(e)}")
            self.ui_elements['status_label'].config(text="API接続エラー。APIキーを確認してください。")
    
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
        """ファイルを読み込む"""
        try:
            # ファイルパスの正規化（特にD&Dの場合に必要）
            file_path = file_path.strip()
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]  # 括弧を削除
            
            # Windowsパスの修正
            file_path = file_path.replace('\\', '/')
            
            # パスの修正: voice/ → data/voice/
            if '/voice/' in file_path:
                old_path = file_path
                parts = file_path.split('/voice/')
                file_path = parts[0] + '/data/voice/' + parts[1]
                print(f"パスを修正しました: {old_path} → {file_path}")
            
            print(f"読み込むファイル: {file_path}")
            
            if os.path.exists(file_path):
                self.current_file = file_path
                filename = os.path.basename(file_path)
                self.ui_elements['file_label'].config(text=f"ファイル: {filename}")
                self.ui_elements['status_label'].config(text=f"ファイル '{filename}' を読み込みました。処理を開始するボタンをクリックしてください。")
            else:
                # 元のパスが見