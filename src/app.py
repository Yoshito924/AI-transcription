#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import re
import datetime

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
        self.selected_transcription_file = None
        
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
        
        # 処理タイプコンボボックスの更新
        self.update_process_combo()
        
        # 履歴選択時のイベントハンドラを設定
        self.ui_elements['history_tree'].bind('<<TreeviewSelect>>', self.on_history_select)
        
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
        
        self._update_status("API接続を確認中...")
        self.root.update_idletasks()
        
        try:
            # Gemini APIの接続テスト
            result = self.processor.test_api_connection(api_key)
            
            # 設定を保存
            self.config.set("api_key", api_key)
            self.config.save()
            
            messagebox.showinfo("成功", "Gemini APIへの接続に成功しました！")
            self._update_status("API接続確認完了")
        except Exception as e:
            messagebox.showerror("エラー", f"API接続エラー: {str(e)}")
            self._update_status("API接続エラー")
    
    def _update_status(self, message):
        """ステータスラベルを更新（短く保つ）"""
        # ステータスメッセージは短くする（40文字まで）
        if len(message) > 40:
            status_message = message[:37] + "..."
        else:
            status_message = message
        self.ui_elements['status_label'].config(text=status_message)
        
        # ログにも追加
        self.add_log(message)
    
    def add_log(self, message):
        """ログエリアにメッセージを追加"""
        if 'log_text' not in self.ui_elements:
            return
            
        # 現在時刻を取得
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        # ログテキストエリアを編集可能に設定
        log_text = self.ui_elements['log_text']
        log_text.config(state=tk.NORMAL)
        
        # メッセージを追加
        log_text.insert(tk.END, log_message)
        
        # 最新の行にスクロール
        log_text.see(tk.END)
        
        # 再び読み取り専用に設定
        log_text.config(state=tk.DISABLED)
    
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
                # ファイル名が長い場合、短く表示
                display_name = filename
                if len(display_name) > 25:
                    display_name = display_name[:22] + "..."
                self.ui_elements['file_label'].config(text=f"ファイル: {display_name}")
                self._update_status(f"ファイル読み込み完了")
            else:
                messagebox.showerror("エラー", f"ファイルが見つかりません")
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
    
    def on_history_select(self, event=None):
        """履歴リストでファイルが選択されたときの処理"""
        tree = self.ui_elements['history_tree']
        selection = tree.selection()
        if not selection:
            # 選択解除された場合
            self.selected_transcription_file = None
            self.ui_elements['selected_file_label'].config(text="未選択")
            self.ui_elements['process_button'].config(state=tk.DISABLED)
            return
        
        # 選択されたファイル情報を取得
        item = tree.item(selection[0])
        filename = item['values'][0]
        file_path = os.path.join(self.output_dir, filename)
        
        # ファイルが文字起こし結果かどうかをファイル名パターンで判断
        # 例: filename_文字起こし_20250316_061541.txt の形式を想定
        if "_文字起こし_" in filename or "transcription" in filename.lower():
            self.selected_transcription_file = file_path
            
            # ファイル名を表示（長い場合は省略）
            display_name = filename
            if len(display_name) > 25:
                display_name = display_name[:22] + "..."
            
            self.ui_elements['selected_file_label'].config(text=display_name)
            self.ui_elements['process_button'].config(state=tk.NORMAL)
        else:
            # 文字起こし結果でない場合
            self.selected_transcription_file = None
            self.ui_elements['selected_file_label'].config(text="未選択（文字起こしファイルを選択してください）")
            self.ui_elements['process_button'].config(state=tk.DISABLED)
    
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
    
    def update_process_combo(self):
        """処理タイプコンボボックスを更新"""
        combo = self.ui_elements['process_combo']
        
        # プロンプトから処理タイプリストを作成（文字起こし以外）
        process_types = []
        prompts = self.prompt_manager.get_prompts()
        for key, info in prompts.items():
            if key != "transcription" and info["name"] != "文字起こし":
                process_types.append(info["name"])
        
        # デフォルト処理タイプを追加（なければ）
        if "議事録作成" not in process_types:
            process_types.append("議事録作成")
        if "要約" not in process_types:
            process_types.append("要約")
        
        # リストを設定
        combo['values'] = process_types
        if combo['values']:
            combo.current(0)
    
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
        self.update_process_combo()  # プロンプト変更に伴い処理タイプも更新
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
            self.update_process_combo()  # プロンプト変更に伴い処理タイプも更新
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
        
        # 処理タイプに基づいて適切なステータスメッセージを表示
        process_name = "文字起こし"
        self._update_status(f"{process_name}の処理を開始しています...")
        
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
                self.root.after(0, lambda: self._update_status(message))
            
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
            self.root.after(0, lambda: self._update_status(error_msg))
            self.root.after(0, lambda: messagebox.showerror("エラー", error_msg))
            self.root.after(0, self.ui_elements['progress'].stop)
            self.is_processing = False
    
    def _on_processing_complete(self, output_file):
        """処理完了時の処理"""
        self.ui_elements['progress'].stop()
        self.is_processing = False
        self._update_status(f"処理完了: {os.path.basename(output_file)}")
        self.update_history()
        messagebox.showinfo("成功", f"処理が完了しました。\n出力ファイル: {os.path.basename(output_file)}")
    
    def process_selected_transcription(self):
        """選択した文字起こしファイルに対して追加処理を実行"""
        if self.is_processing:
            messagebox.showinfo("情報", "すでに処理中です。完了までお待ちください。")
            return
        
        if not self.selected_transcription_file:
            messagebox.showerror("エラー", "文字起こしファイルを選択してください。")
            return
        
        api_key = self.api_key.get().strip()
        if not api_key:
            messagebox.showerror("エラー", "APIキーを入力してください。")
            return
        
        # 選択された処理タイプを取得
        process_type = self.ui_elements['process_var'].get()
        if not process_type:
            messagebox.showerror("エラー", "処理タイプを選択してください。")
            return
        
        # プロンプト情報を取得
        prompt_key = None
        for key, info in self.prompt_manager.get_prompts().items():
            if info["name"] == process_type:
                prompt_key = key
                break
        
        if not prompt_key:
            # プロンプトがない場合はデフォルトのプロンプトを作成
            if "議事録" in process_type:
                prompt_key = "meeting_minutes"
                self.prompt_manager.get_prompts()[prompt_key] = {
                    "name": process_type,
                    "prompt": "以下の文字起こしから議事録を作成してください。箇条書きで重要なポイントをまとめ、決定事項と次のアクションアイテムを明確にしてください。\n\n{transcription}"
                }
            elif "要約" in process_type:
                prompt_key = "summary"
                self.prompt_manager.get_prompts()[prompt_key] = {
                    "name": process_type,
                    "prompt": "以下の文字起こしを300字程度に要約してください。\n\n{transcription}"
                }
            else:
                messagebox.showerror("エラー", f"処理タイプ '{process_type}' に対応するプロンプトがありません。")
                return
        
        # 処理開始
        self.is_processing = True
        self.ui_elements['progress'].start()
        self._update_status(f"{process_type}の処理を開始しています...")
        
        # スレッドで処理を実行
        thread = threading.Thread(
            target=self._process_transcription_in_thread, 
            args=(self.selected_transcription_file, prompt_key, api_key)
        )
        thread.daemon = True
        thread.start()
    
    def _process_transcription_in_thread(self, transcription_file, prompt_key, api_key):
        """文字起こしファイルの追加処理をスレッドで実行"""
        try:
            # 開始時間を記録
            start_time = datetime.datetime.now()
            
            # ステータス更新用コールバック
            def update_status(message):
                self.root.after(0, lambda: self._update_status(message))
            
            # 文字起こしファイルのサイズを取得
            file_size_kb = os.path.getsize(transcription_file) / 1024
            
            # 文字起こしファイルを読み込む
            update_status(f"文字起こしファイル（{file_size_kb:.1f}KB）を読み込み中...")
            
            try:
                with open(transcription_file, 'r', encoding='utf-8') as f:
                    transcription = f.read()
            except Exception as e:
                raise Exception(f"ファイル読み込みエラー: {str(e)}")
            
            # プロンプト情報取得
            prompts = self.prompt_manager.get_prompts()
            if prompt_key not in prompts:
                raise Exception(f"プロンプトキー '{prompt_key}' が見つかりません")
            
            prompt_info = prompts[prompt_key]
            process_name = prompt_info["name"]
            
            # ファイル名のベース部分を抽出（元の文字起こし元のファイル名）
            base_name = os.path.basename(transcription_file)
            # ファイル名パターン: basename_文字起こし_timestamp.txt
            match = re.match(r'(.+?)_文字起こし_\d+_\d+\.txt', base_name)
            if match:
                base_name = match.group(1)
            else:
                # 別のパターンも試す
                match = re.match(r'(.+?)_\d+_\d+\.txt', base_name)
                if match:
                    base_name = match.group(1)
            
            update_status(f"{process_name}を生成中...")
            
            # APIを使用して処理
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            # 最適なモデルを選択
            model_name = self.processor.api_utils.get_best_available_model(api_key)
            model = genai.GenerativeModel(model_name)
            
            # プロンプトに文字起こし結果を埋め込む
            prompt = prompt_info["prompt"].replace("{transcription}", transcription)
            
            # API呼び出し
            try:
                response = model.generate_content(prompt)
                result_text = response.text
            except Exception as e:
                error_msg = f"API処理エラー: {str(e)}"
                update_status(error_msg)
                raise Exception(error_msg)
            
            # 出力ファイル名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{base_name}_{process_name}_{timestamp}.txt"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # ファイル出力
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result_text)
            
            # 処理完了時間を記録
            end_time = datetime.datetime.now()
            process_time = end_time - start_time
            process_seconds = process_time.total_seconds()
            
            # 処理時間を分:秒形式に
            process_time_str = f"{int(process_seconds // 60)}分{int(process_seconds % 60)}秒"
            
            # 詳細なログメッセージ
            log_message = (
                f"処理完了: {os.path.basename(output_path)}\n"
                f"- 元ファイルサイズ: {file_size_kb:.1f}KB\n"
                f"- 処理時間: {process_time_str}\n"
                f"- 使用モデル: {model_name}"
            )
            
            update_status(log_message)
            
            # 処理完了通知
            self.root.after(0, lambda: self._on_processing_complete(output_path))
            
        except Exception as e:
            error_msg = f"処理エラー: {str(e)}"
            self.root.after(0, lambda: self._update_status(error_msg))
            self.root.after(0, lambda: messagebox.showerror("エラー", error_msg))
            self.root.after(0, self.ui_elements['progress'].stop)
            self.is_processing = False
