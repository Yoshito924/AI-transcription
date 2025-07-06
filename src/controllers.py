#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
シンプルなコントローラークラス
文字起こし機能に特化したビジネスロジック
"""

import os
import threading
import datetime
from tkinter import messagebox

from .constants import (
    STATUS_MESSAGE_MAX_LENGTH, 
    FILE_NAME_DISPLAY_MAX_LENGTH
)
from .exceptions import (
    TranscriptionError, 
    AudioProcessingError, 
    ApiConnectionError, 
    FileProcessingError
)


class TranscriptionController:
    """文字起こし処理のコントローラー"""
    
    def __init__(self, processor, config, usage_tracker, ui_elements):
        self.processor = processor
        self.config = config
        self.usage_tracker = usage_tracker
        self.ui_elements = ui_elements
        self.is_processing = False
        self.current_file = None
        self.preferred_model = None
    
    def update_status(self, message):
        """ステータスを更新"""
        # ステータスメッセージは短くする
        if len(message) > STATUS_MESSAGE_MAX_LENGTH:
            status_message = message[:STATUS_MESSAGE_MAX_LENGTH-3] + "..."
        else:
            status_message = message
        
        # ステータスラベルを更新
        if 'status_label' in self.ui_elements:
            self.ui_elements['status_label'].config(text=status_message)
        
        # API接続状態の更新
        if 'api_status' in self.ui_elements:
            if "API接続" in message and "成功" in message:
                self.ui_elements['api_status'].config(
                    text="● 接続済み",
                    fg="#4caf50"  # 緑色
                )
            elif "エラー" in message:
                self.ui_elements['api_status'].config(
                    text="● エラー",
                    fg="#f44336"  # 赤色
                )
        
        # ログにも追加
        self.add_log(message)
    
    def add_log(self, message):
        """ログエリアにメッセージを追加"""
        if 'log_text' not in self.ui_elements:
            return
            
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        log_text = self.ui_elements['log_text']
        log_text.config(state='normal')
        log_text.insert('end', log_message)
        log_text.see('end')
        log_text.config(state='disabled')
    
    def load_file(self, file_path):
        """ファイルを読み込む"""
        try:
            # ファイルパスの正規化
            file_path = file_path.strip()
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]
            
            file_path = file_path.replace('\\', '/')
            
            if os.path.exists(file_path):
                self.current_file = file_path
                filename = os.path.basename(file_path)
                
                # ファイル名が長い場合、短く表示
                display_name = filename
                if len(display_name) > FILE_NAME_DISPLAY_MAX_LENGTH:
                    display_name = display_name[:FILE_NAME_DISPLAY_MAX_LENGTH-3] + "..."
                    
                self.ui_elements['file_label'].config(text=f"選択ファイル: {display_name}")
                self.update_status("ファイル読み込み完了")
                
                # ファイルサイズをチェック
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)
                self.add_log(f"ファイルサイズ: {size_mb:.1f} MB")
            else:
                raise FileProcessingError("ファイルが見つかりません")
                
        except Exception as e:
            error_msg = f"ファイル読み込みエラー: {str(e)}"
            messagebox.showerror("エラー", error_msg)
            self.update_status(error_msg)
    
    def start_transcription(self):
        """文字起こし処理を開始"""
        if self.is_processing:
            messagebox.showinfo("情報", "すでに処理中です。完了までお待ちください。")
            return
        
        if not self.current_file:
            messagebox.showerror("エラー", "ファイルを選択してください。")
            return
        
        api_key = self.ui_elements['api_key_var'].get().strip()
        if not api_key:
            messagebox.showerror("エラー", "APIキーを入力してください。")
            return
        
        # 固定プロンプト（文字起こし専用）
        prompts = {
            "transcription": {
                "name": "文字起こし",
                "prompt": """以下の音声を正確に文字起こししてください。話者が複数いる場合は話者を区別してください。

重要な指示:
- 元の音声の内容を忠実に文字起こしすること
- 話者の区別が可能な場合は「話者A:」「話者B:」のように表記
- 聞き取れない部分は[聞き取り不能]と表記
- 時刻への言及がある場合はそのまま記載

{transcription}"""
            }
        }
        
        self._start_processing_thread("transcription", api_key, prompts)
    
    def _start_processing_thread(self, process_type, api_key, prompts):
        """処理スレッドを開始"""
        self.is_processing = True
        self.ui_elements['progress'].start()
        self.update_status("文字起こし処理を開始しています...")
        
        thread = threading.Thread(
            target=self._process_in_thread,
            args=(process_type, api_key, prompts)
        )
        thread.daemon = True
        thread.start()
    
    def _process_in_thread(self, process_type, api_key, prompts):
        """スレッドで実行される処理"""
        try:
            # プログレスコールバック
            def progress_callback(msg):
                self.ui_elements['root'].after(0, lambda: self.update_status(msg))
            
            output_file = self.processor.process_file(
                self.current_file,
                process_type,
                api_key,
                prompts,
                progress_callback,
                self.preferred_model
            )
            
            self.ui_elements['root'].after(0, lambda: self._on_processing_complete(output_file))
            
        except Exception as e:
            error_msg = f"処理エラー: {str(e)}"
            self.ui_elements['root'].after(0, lambda: self.update_status(error_msg))
            self.ui_elements['root'].after(0, lambda: messagebox.showerror("エラー", error_msg))
            self.ui_elements['root'].after(0, self.ui_elements['progress'].stop)
            self.is_processing = False
    
    def _on_processing_complete(self, output_file):
        """処理完了時の処理"""
        self.ui_elements['progress'].stop()
        self.is_processing = False
        self.update_status(f"処理完了: {os.path.basename(output_file)}")
        
        # 使用量を記録（仮のトークン数で記録）
        try:
            import os
            file_size_mb = os.path.getsize(self.current_file) / (1024 * 1024) if self.current_file else 0
            filename = os.path.basename(self.current_file) if self.current_file else "unknown"
            
            # 音声時間とファイルサイズから概算トークン数を推定
            estimated_input_tokens = int(file_size_mb * 1000)  # 概算値
            estimated_output_tokens = int(estimated_input_tokens * 0.1)  # 出力は入力の10%程度
            
            cost = self.usage_tracker.record_usage(
                model="gemini-1.5-flash",  # デフォルトモデル
                input_tokens=estimated_input_tokens,
                output_tokens=estimated_output_tokens,
                file_name=filename,
                file_size_mb=file_size_mb
            )
            
            self.add_log(f"使用料金: ${cost:.4f} (概算)")
            
            # 使用量表示を更新
            if hasattr(self, 'update_usage_callback') and self.update_usage_callback:
                self.update_usage_callback()
                
        except Exception as e:
            print(f"使用量記録エラー: {e}")
        
        # 履歴更新のコールバックがある場合は呼び出し
        if hasattr(self, 'update_history_callback') and self.update_history_callback:
            self.update_history_callback()
        
        messagebox.showinfo("成功", f"文字起こしが完了しました。\n出力ファイル: {os.path.basename(output_file)}")
    
    def set_update_history_callback(self, callback):
        """履歴更新のコールバックを設定"""
        self.update_history_callback = callback