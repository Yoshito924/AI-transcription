#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import tkinter as tk
from tkinter import messagebox
import re

from .ui import setup_ui
from .config import Config
from .processor import FileProcessor
from .controllers import TranscriptionController
from .usage_tracker import UsageTracker
from .constants import OUTPUT_DIR, DATA_DIR, FILE_NAME_DISPLAY_MAX_LENGTH
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
        self.api_key = tk.StringVar(value=self.config.get("api_key", ""))  # Gemini API用
        self.openai_api_key = tk.StringVar(value=self.config.get("openai_api_key", ""))  # OpenAI API用
        self.preferred_model = None  # 手動選択されたモデル
        
        # プロセッサの初期化
        self.processor = FileProcessor(self.output_dir)

        # 処理履歴メタデータ（元ファイルパスの記録）
        self.data_dir = os.path.join(self.app_dir, DATA_DIR)
        os.makedirs(self.data_dir, exist_ok=True)
        self.history_meta_path = os.path.join(self.data_dir, 'processing_history.json')
        self.history_metadata = self._load_history_metadata()

        # UIの構築
        self.ui_elements = setup_ui(self)
        
        # コントローラーの初期化
        self.ui_elements['api_key_var'] = self.api_key
        self.ui_elements['openai_api_key_var'] = self.openai_api_key
        self.ui_elements['root'] = self.root
        self.controller = TranscriptionController(
            self.processor, self.config, self.usage_tracker, self.ui_elements
        )
        self.controller.set_update_history_callback(self._on_history_update)
        self.controller.update_usage_callback = self.update_usage_display
        self.controller.history_metadata = self.history_metadata
        self.controller.update_queue_callback = self._update_queue_display
        
        
        # ウィンドウサイズと位置の設定を適用（UI構築後）
        self.config.apply_window_geometry(self.root)
        
        # 初期設定
        self._restore_column_widths()
        self.update_history()
        self.update_usage_display()
        
        # ウィンドウにフォーカスが戻ったとき履歴を自動更新
        self.root.bind('<FocusIn>', self._on_focus_in)

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
        self.config.set("openai_api_key", self.openai_api_key.get())
        
        # エンジン選択とWhisperモデル選択を保存
        self._save_engine_settings()

        # 保存先設定を保存
        self._save_destination_settings()

        # カラム幅を保存
        self._save_column_widths()
        self.config.save()
        
        # アプリケーションを終了
        self.root.destroy()
    
    def toggle_api_key_visibility(self):
        """APIキーの表示/非表示を切り替える"""
        # Gemini API
        entry = self.ui_elements['api_entry']
        # OpenAI API
        openai_entry = self.ui_elements.get('openai_api_entry')

        if entry['show'] == '*':
            entry.config(show='')
            if openai_entry:
                openai_entry.config(show='')
        else:
            entry.config(show='*')
            if openai_entry:
                openai_entry.config(show='*')
    
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
            # Whisper APIモードの場合はOpenAI API接続を確認
            api_key = self.openai_api_key.get().strip()
            if not api_key:
                messagebox.showerror("エラー", "Whisper APIモードではOpenAI APIキーを入力してください。")
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
        """ファイル選択ダイアログを表示（複数選択対応）"""
        from tkinter import filedialog
        file_types = [
            ('音声・動画ファイル', '*.mp3 *.wav *.mp4 *.avi *.mov *.m4a *.flac *.ogg'),
            ('すべてのファイル', '*.*')
        ]
        file_paths = filedialog.askopenfilenames(filetypes=file_types)
        if file_paths:
            if len(file_paths) == 1:
                self.load_file(file_paths[0])
            else:
                self._add_files_to_queue(list(file_paths))
    
    def load_file(self, file_path):
        """ファイルを読み込む（コントローラーに委譲）"""
        self.controller.load_file(file_path)

    def load_files(self, raw_data):
        """D&Dデータから複数ファイルを解析してキューに追加"""
        paths = self._parse_dnd_paths(raw_data)
        if len(paths) == 1:
            self.load_file(paths[0])
        elif len(paths) > 1:
            self._add_files_to_queue(paths)

    def _parse_dnd_paths(self, raw_data):
        """tkinterdnd2のD&Dデータからファイルパスリストを解析

        形式例:
          {C:/path with spaces/file.mp3} C:/simple.wav
          {C:/path with spaces/file.mp3}
          C:/simple.wav
        """
        raw_data = raw_data.strip()
        paths = []
        i = 0
        while i < len(raw_data):
            if raw_data[i] == '{':
                # 中括弧で囲まれたパス
                end = raw_data.index('}', i)
                path = raw_data[i+1:end]
                paths.append(path.replace('\\', '/'))
                i = end + 1
            elif raw_data[i] in (' ', '\t', '\n', '\r'):
                i += 1
            else:
                # スペースなしのパス（次のスペースまたは末尾まで）
                end = i
                while end < len(raw_data) and raw_data[end] not in (' ', '\t', '\n', '\r', '{'):
                    end += 1
                path = raw_data[i:end]
                paths.append(path.replace('\\', '/'))
                i = end
        return paths

    def _add_files_to_queue(self, file_paths):
        """ファイルリストをキューに追加（重複検出付き）"""
        added, duplicated_paths, invalid = self.controller.add_files_to_queue(file_paths)

        if duplicated_paths:
            dup_names = [os.path.basename(p) for p in duplicated_paths]
            result = messagebox.askyesno(
                "重複検出",
                f"以下のファイルは既にキューまたは処理済みです:\n"
                + "\n".join(f"  - {n}" for n in dup_names)
                + "\n\nそれでも追加しますか？"
            )
            if result:
                for path in duplicated_paths:
                    self.controller.file_queue.append(os.path.abspath(path))
                    added += 1
                self._update_queue_display()

        if invalid > 0:
            self.controller.add_log(f"対応していないファイル形式: {invalid}件スキップ")

        if added > 0:
            self.controller.add_log(f"キューに{added}件追加（合計: {len(self.controller.file_queue)}件）")

    def _update_queue_display(self):
        """キューListboxを更新"""
        queue_frame = self.ui_elements.get('queue_frame')
        queue_listbox = self.ui_elements.get('queue_listbox')
        queue_count_label = self.ui_elements.get('queue_count_label')
        if not queue_frame or not queue_listbox:
            return

        queue_listbox.delete(0, tk.END)
        queue = self.controller.file_queue

        if queue:
            for path in queue:
                queue_listbox.insert(tk.END, os.path.basename(path))
            queue_count_label.config(text=f"待機ファイル: {len(queue)}件")
            # pack の前に親フレーム内の正しい位置に挿入
            if not queue_frame.winfo_ismapped():
                # D&Dエリアの後に挿入
                drop_area = self.ui_elements.get('drop_area')
                if drop_area:
                    queue_frame.pack(fill=tk.X, padx=16, pady=(0, 6),
                                     after=drop_area.master)
                else:
                    queue_frame.pack(fill=tk.X, padx=16, pady=(0, 6))
        else:
            if queue_frame.winfo_ismapped():
                queue_frame.pack_forget()

    def remove_from_queue(self):
        """Listboxの選択項目をキューから削除"""
        queue_listbox = self.ui_elements.get('queue_listbox')
        if not queue_listbox:
            return
        indices = list(queue_listbox.curselection())
        if indices:
            self.controller.remove_from_queue(indices)

    def clear_queue(self):
        """キュー全クリア"""
        self.controller.clear_queue()

    def start_process(self, process_type):
        """処理を開始（コントローラーに委譲）"""
        if process_type == "transcription":
            self.controller.start_queue_processing()
    
    
    def update_history(self):
        """履歴リストを更新（交互行色付き）"""
        tree = self.ui_elements['history_tree']

        # リストをクリア
        for item in tree.get_children():
            tree.delete(item)

        # ファイルリスト取得と表示（交互行色）
        files = self.processor.get_output_files()
        existing_filenames = {f[0] for f in files}
        for i, (file, date, size, _) in enumerate(files):
            tag = 'row_even' if i % 2 == 0 else 'row_odd'
            tree.insert('', 'end', values=(file, date, size), tags=(tag,))

        # 存在しないファイルのメタデータを削除
        stale_keys = [k for k in self.history_metadata if k not in existing_filenames]
        if stale_keys:
            for k in stale_keys:
                del self.history_metadata[k]
            self._save_history_metadata()
            self.controller.history_metadata = self.history_metadata

    def _on_focus_in(self, event=None):
        """ウィンドウにフォーカスが戻ったとき履歴を自動更新"""
        # ルートウィンドウのイベントのみ処理（子ウィジェットの連鎖を無視）
        if event and event.widget is not self.root:
            return
        self.update_history()
    
    
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
            import subprocess
            subprocess.Popen(['notepad.exe', file_path])
        except (FileNotFoundError, OSError):
            if not open_file(file_path):
                messagebox.showerror("エラー", f"ファイル '{filename}' を開けません。")
    
    def delete_output_file(self, event=None):
        """選択された出力ファイルを削除する"""
        tree = self.ui_elements['history_tree']
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("情報", "削除するファイルを選択してください。")
            return

        # 選択されたファイル名を収集
        filenames = []
        for sel in selection:
            item = tree.item(sel)
            filenames.append(item['values'][0])

        # 確認ダイアログ
        if len(filenames) == 1:
            msg = f"以下のファイルを削除しますか？\n\n{filenames[0]}"
        else:
            msg = f"{len(filenames)}件のファイルを削除しますか？\n\n" + "\n".join(f"  - {f}" for f in filenames)

        if not messagebox.askyesno("削除確認", msg):
            return

        # 削除実行
        deleted = 0
        for filename in filenames:
            file_path = os.path.join(self.output_dir, filename)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted += 1
                    # メタデータからも削除
                    if filename in self.history_metadata:
                        del self.history_metadata[filename]
            except OSError as e:
                messagebox.showerror("エラー", f"削除できませんでした:\n{filename}\n{e}")

        if deleted > 0:
            self._save_history_metadata()
            self.update_history()
            self.controller.add_log(f"{deleted}件のファイルを削除しました")

    def open_output_folder(self):
        """出力フォルダを開く"""
        if not open_directory(self.output_dir):
            messagebox.showerror("エラー", "出力フォルダを開けません。")

    def open_source_file_folder(self, event=None):
        """選択されたファイルの元ファイルのフォルダをエクスプローラーで開く"""
        tree = self.ui_elements['history_tree']
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("情報", "履歴からファイルを選択してください。")
            return

        item = tree.item(selection[0])
        filename = item['values'][0]

        meta = self.history_metadata.get(filename)
        if meta and 'source_dir' in meta:
            source_dir = meta['source_dir']
            if os.path.exists(source_dir):
                if not open_directory(source_dir):
                    messagebox.showerror("エラー", f"フォルダを開けません:\n{source_dir}")
            else:
                messagebox.showinfo("情報", f"元ファイルのフォルダが見つかりません:\n{source_dir}")
        else:
            messagebox.showinfo(
                "情報",
                "このファイルの元ファイル情報が記録されていません。\n"
                "（この機能は今後処理されたファイルに対して利用可能です）"
            )

    def _on_history_update(self):
        """処理完了時のコールバック - メタデータ保存 + 履歴更新"""
        if self.controller.current_file:
            files = self.processor.get_output_files()
            if files:
                latest_output = files[0][0]  # 最新の出力ファイル名
                source_file = self.controller.current_file
                self.history_metadata[latest_output] = {
                    'source_file': os.path.abspath(source_file),
                    'source_dir': os.path.dirname(os.path.abspath(source_file))
                }
                self._save_history_metadata()
                # コントローラーの参照も更新
                self.controller.history_metadata = self.history_metadata
        self.update_history()

    def _load_history_metadata(self):
        """処理履歴メタデータを読み込む"""
        try:
            if os.path.exists(self.history_meta_path):
                with open(self.history_meta_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 存在しない出力ファイルのエントリを削除
                cleaned = {}
                for filename, meta in data.items():
                    output_path = os.path.join(self.output_dir, filename)
                    if os.path.exists(output_path):
                        cleaned[filename] = meta
                return cleaned
        except Exception:
            pass
        return {}

    def _save_history_metadata(self):
        """処理履歴メタデータを保存する"""
        try:
            with open(self.history_meta_path, 'w', encoding='utf-8') as f:
                json.dump(self.history_metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"処理履歴メタデータの保存エラー: {e}")

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

    def _save_destination_settings(self):
        """保存先設定を保存"""
        if hasattr(self, 'ui_elements'):
            save_to_output = self.ui_elements.get('save_to_output_var')
            save_to_source = self.ui_elements.get('save_to_source_var')
            if save_to_output is not None:
                self.config.set("save_to_output_dir", save_to_output.get())
            if save_to_source is not None:
                self.config.set("save_to_source_dir", save_to_source.get())

    def _save_column_widths(self):
        """処理履歴のカラム幅を保存"""
        tree = self.ui_elements.get('history_tree')
        if not tree:
            return
        widths = {}
        for col in ('filename', 'date', 'size'):
            widths[col] = tree.column(col, 'width')
        self.config.set("history_column_widths", widths)

    def _restore_column_widths(self):
        """処理履歴のカラム幅を復元"""
        tree = self.ui_elements.get('history_tree')
        if not tree:
            return
        widths = self.config.get("history_column_widths", None)
        if not widths:
            return
        for col in ('filename', 'date', 'size'):
            if col in widths:
                tree.column(col, width=widths[col])
