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
            
            print(f"読み込むファイル: {file_path}")
            
            if os.path.exists(file_path):
                self.current_file = file_path
                filename = os.path.basename(file_path)
                self.ui_elements['file_label'].config(text=f"ファイル: {filename}")
                self.ui_elements['status_label'].config(text=f"ファイル '{filename}' を読み込みました。処理を開始するボタンをクリックしてください。")
            else:
                messagebox.showerror("エラー", f"ファイルが見つかりません: {file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"ファイル読み込みエラー: {str(e)}")
            print(f"ファイル読み込みエラー: {str(e)}")
    
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
        
        try:
            os.startfile(file_path)
        except:
            messagebox.showerror("エラー", f"ファイル '{filename}' を開けません。")
    
    def open_output_folder(self):
        """出力フォルダを開く"""
        try:
            os.startfile(self.output_dir)
        except:
            messagebox.showerror("エラー", "出力フォルダを開けません。")
    
    def update_prompt_combo(self):
        """プロンプトコンボボックスを更新"""
        combo = self.ui_elements['prompt_combo']
        prompt_names = self.prompt_manager.get_sorted_names()
        
        combo['values'] = prompt_names
        if combo['values']:
            combo.current(0)
            self.load_selected_prompt()
    
    def load_selected_prompt(self, event=None):
        """選択されたプロンプトを読み込む"""
        selected_name = self.ui_elements['prompt_var'].get()
        if not selected_name:
            return
        
        # プロンプト情報取得
        prompt_info = self.prompt_manager.get_prompt_by_name(selected_name)
        if prompt_info:
            self.ui_elements['prompt_name_var'].set(prompt_info["name"])
            self.ui_elements['prompt_text'].delete(1.0, tk.END)
            self.ui_elements['prompt_text'].insert(tk.END, prompt_info["prompt"])
    
    def save_current_prompt(self):
        """現在のプロンプトを保存"""
        selected_name = self.ui_elements['prompt_var'].get()
        new_name = self.ui_elements['prompt_name_var'].get().strip()
        prompt_text = self.ui_elements['prompt_text'].get(1.0, tk.END).strip()
        
        if not new_name:
            messagebox.showerror("エラー", "プロンプト名を入力してください。")
            return
        
        if not prompt_text:
            messagebox.showerror("エラー", "プロンプトを入力してください。")
            return
        
        # マークダウン形式のプロンプトを保持するために改行をそのまま保存
        # プロンプト保存
        self.prompt_manager.save_prompt(selected_name, new_name, prompt_text)
        self.update_prompt_combo()
        messagebox.showinfo("成功", f"プロンプト '{new_name}' を保存しました。")
    
    def create_new_prompt(self):
        """新規プロンプトを作成"""
        self.ui_elements['prompt_name_var'].set("新規プロンプト")
        self.ui_elements['prompt_text'].delete(1.0, tk.END)
        self.ui_elements['prompt_text'].insert(tk.END, "")
    
    def delete_current_prompt(self):
        """現在のプロンプトを削除"""
        selected_name = self.ui_elements['prompt_var'].get()
        if not selected_name:
            return
        
        result = messagebox.askyesno("確認", f"プロンプト '{selected_name}' を削除しますか？")
        if result:
            self.prompt_manager.delete_prompt(selected_name)
            self.update_prompt_combo()
            messagebox.showinfo("成功", f"プロンプト '{selected_name}' を削除しました。")
    
    def start_process(self, process_type):
        """処理を開始"""
        if self.is_processing:
            messagebox.showinfo("情報", "すでに処理中です。完了までお待ちください。")
            return
        
        if not self.current_file:
            messagebox.showerror("エラー", "ファイルを選択してください。")
            return
        
        api_key = self.api_key.get().strip()
        if not api_key:
            messagebox.showerror("エラー", "APIキーを入力してください。")
            return
        
        # 処理開始
        self.is_processing = True
        self.ui_elements['progress'].start()
        self.ui_elements['status_label'].config(text="処理を開始しています...")
        
        # スレッドで処理を実行
        thread = threading.Thread(
            target=self._process_in_thread, 
            args=(process_type, api_key)
        )
        thread.daemon = True
        thread.start()
    
    def _process_in_thread(self, process_type, api_key):
        """スレッドで実行される処理"""
        try:
            # 処理の進捗を受け取るコールバック
            def update_status(message):
                self.root.after(0, lambda: self.ui_elements['status_label'].config(text=message))
            
            # ファイル処理実行
            output_file = self.processor.process_file(
                self.current_file,
                process_type,
                api_key,
                self.prompt_manager.get_prompts(),
                update_status
            )
            
            # 処理完了後の処理
            self.root.after(0, lambda: self._on_processing_complete(output_file))
            
        except Exception as e:
            error_msg = f"処理エラー: {str(e)}"
            self.root.after(0, lambda: self.ui_elements['status_label'].config(text=error_msg))
            self.root.after(0, lambda: messagebox.showerror("エラー", error_msg))
            self.root.after(0, self.ui_elements['progress'].stop)
            self.is_processing = False
    
    def _on_processing_complete(self, output_file):
        """処理完了時の処理"""
        self.ui_elements['progress'].stop()
        self.is_processing = False
        self.ui_elements['status_label'].config(text=f"処理が完了しました: {os.path.basename(output_file)}")
        self.update_history()
        messagebox.showinfo("成功", f"処理が完了しました。\n出力ファイル: {os.path.basename(output_file)}")
