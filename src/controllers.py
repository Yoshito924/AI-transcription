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
    FILE_NAME_DISPLAY_MAX_LENGTH,
    TOKEN_ESTIMATION_FACTOR,
    OUTPUT_TOKEN_RATIO
)
from .exceptions import (
    TranscriptionError,
    AudioProcessingError,
    ApiConnectionError,
    FileProcessingError
)
from .utils import (
    get_file_size_mb,
    normalize_file_path,
    truncate_display_name,
    truncate_status_message,
    get_engine_value,
    get_whisper_model_value
)
from .logger import logger


class TranscriptionController:
    """文字起こし処理のコントローラー"""
    
    def __init__(self, processor, config, usage_tracker, ui_elements):
        self.processor = processor
        self.config = config
        self.usage_tracker = usage_tracker
        self.ui_elements = ui_elements
        self.is_processing = False
        self._processing_lock = threading.Lock()
        self.current_file = None
        self.preferred_model = None
    
    def update_status(self, message):
        """ステータスを更新"""
        # ステータスメッセージは短くする
        status_message = truncate_status_message(message, STATUS_MESSAGE_MAX_LENGTH)
        
        # ステータスラベルを更新
        if 'status_label' in self.ui_elements:
            self.ui_elements['status_label'].config(text=status_message)
        
        # API接続状態の更新
        self._update_api_status(message)
        
        # ログにも追加
        self.add_log(message)
    
    def _update_api_status(self, message):
        """API接続状態を更新"""
        if 'api_status' not in self.ui_elements:
            return

        if "API接続" in message and "成功" in message:
            self.ui_elements['api_status'].config(
                text="\u25cf 接続済み",
                fg="#5B9A6B"
            )
        elif "エラー" in message:
            self.ui_elements['api_status'].config(
                text="\u25cf エラー",
                fg="#C25450"
            )

        # ステータスドットの色を更新
        if 'status_dot' in self.ui_elements:
            if "完了" in message or "成功" in message:
                self.ui_elements['status_dot'].config(fg="#5B9A6B")
            elif "エラー" in message or "失敗" in message:
                self.ui_elements['status_dot'].config(fg="#C25450")
            elif "処理" in message or "開始" in message or "確認中" in message:
                self.ui_elements['status_dot'].config(fg="#5586B0")
            else:
                self.ui_elements['status_dot'].config(fg="#B0ACA7")
    
    def add_log(self, message):
        """ログエリアにメッセージを追加（色付きタグ対応）"""
        if 'log_text' not in self.ui_elements:
            return

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_text = self.ui_elements['log_text']
        log_text.config(state='normal')

        # タイムスタンプ部分を色付きで挿入
        log_text.insert('end', f"[{timestamp}] ", 'timestamp')

        # メッセージの内容に応じてタグを選択
        if "エラー" in message or "失敗" in message:
            tag = 'error'
        elif "完了" in message or "成功" in message:
            tag = 'success'
        elif "警告" in message:
            tag = 'warning'
        elif "━━━" in message:
            tag = 'separator'
        else:
            tag = 'normal'

        log_text.insert('end', f"{message}\n", tag)
        log_text.see('end')
        log_text.config(state='disabled')
    
    def load_file(self, file_path):
        """ファイルを読み込む"""
        try:
            # ファイルパスの正規化
            file_path = normalize_file_path(file_path)
            
            if os.path.exists(file_path):
                self.current_file = file_path
                filename = os.path.basename(file_path)
                
                # ファイル名が長い場合、短く表示
                display_name = truncate_display_name(filename, FILE_NAME_DISPLAY_MAX_LENGTH)
                    
                self.ui_elements['file_label'].config(text=f"選択ファイル: {display_name}")
                self.update_status("ファイル読み込み完了")
                
                # ファイルサイズをチェック
                size_mb = get_file_size_mb(file_path)
                self.add_log(f"ファイルサイズ: {size_mb:.1f} MB")
            else:
                raise FileProcessingError("ファイルが見つかりません")
                
        except FileProcessingError as e:
            # カスタム例外の場合は詳細メッセージを使用
            user_msg = e.get_detailed_message() if hasattr(e, 'get_detailed_message') else str(e)
            messagebox.showerror("エラー", user_msg)
            self.update_status(e.user_message if hasattr(e, 'user_message') else str(e))
        except Exception as e:
            # その他の例外
            error_msg = f"ファイル読み込みエラー: {str(e)}"
            messagebox.showerror("エラー", error_msg)
            self.update_status(error_msg)
            self.add_log(f"エラー詳細: {type(e).__name__}: {str(e)}")
    
    def start_transcription(self):
        """文字起こし処理を開始"""
        if self.is_processing:
            messagebox.showinfo("情報", "すでに処理中です。完了までお待ちください。")
            return
        
        if not self.current_file:
            messagebox.showerror("エラー", "ファイルを選択してください。")
            return
        
        # エンジンの取得
        engine_value = get_engine_value(self.ui_elements)
        
        # エンジンに応じたAPIキーを取得
        if engine_value == 'whisper-api':
            # Whisper APIの場合はOpenAI APIキーを使用
            api_key = self.ui_elements.get('openai_api_key_var')
            api_key = api_key.get().strip() if api_key else ""
            if not api_key:
                messagebox.showerror("エラー", "Whisper APIモードではOpenAI APIキーを入力してください。")
                return
        elif engine_value == 'gemini':
            # GeminiはGemini APIキーを使用
            api_key = self.ui_elements['api_key_var'].get().strip()
            if not api_key:
                messagebox.showerror("エラー", "GeminiモードではGemini APIキーを入力してください。")
                return
        else:
            # Whisper（ローカル）の場合はAPIキー不要
            api_key = ""
        
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
        with self._processing_lock:
            if self.is_processing:
                return
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

            # エンジンとモデルの取得
            engine_value = get_engine_value(self.ui_elements)
            whisper_model = get_whisper_model_value(self.ui_elements)

            # エンジンに応じた開始メッセージを表示
            if engine_value == 'whisper':
                self.ui_elements['root'].after(0, lambda: self.add_log(f"━━━ Whisper処理開始 (モデル: {whisper_model}) ━━━"))
            elif engine_value == 'whisper-api':
                self.ui_elements['root'].after(0, lambda: self.add_log(f"━━━ Whisper API処理開始 ━━━"))
            else:
                self.ui_elements['root'].after(0, lambda: self.add_log(f"━━━ Gemini処理開始 ━━━"))

            # 保存先設定の取得
            save_to_output = self.ui_elements.get('save_to_output_var')
            save_to_source = self.ui_elements.get('save_to_source_var')
            save_to_output_dir = save_to_output.get() if save_to_output else True
            save_to_source_dir = save_to_source.get() if save_to_source else False

            output_file = self.processor.process_file(
                self.current_file,
                process_type,
                api_key,
                prompts,
                progress_callback,
                self.preferred_model,
                engine_value,
                whisper_model,
                save_to_output_dir=save_to_output_dir,
                save_to_source_dir=save_to_source_dir
            )
            
            self.ui_elements['root'].after(0, lambda: self._on_processing_complete(output_file))
            
        except (TranscriptionError, AudioProcessingError, ApiConnectionError, FileProcessingError) as e:
            # カスタム例外の場合は詳細メッセージを使用
            user_msg = e.get_detailed_message() if hasattr(e, 'get_detailed_message') else str(e)
            status_msg = e.user_message if hasattr(e, 'user_message') else str(e)
            self.ui_elements['root'].after(0, lambda: self._handle_processing_error(e, user_msg, status_msg))
        except Exception as e:
            # その他の例外
            error_msg = f"処理エラー: {str(e)}"
            self.ui_elements['root'].after(0, lambda: self._handle_processing_error(e, error_msg, error_msg))
    
    def _handle_processing_error(self, exception, user_message, status_message):
        """処理エラーをハンドル"""
        self.update_status(status_message)
        messagebox.showerror("エラー", user_message)
        self.ui_elements['progress'].stop()
        self.is_processing = False
        # ログに詳細を記録
        if hasattr(exception, 'error_code'):
            self.add_log(f"エラーコード: {exception.error_code}")
        self.add_log(f"エラー詳細: {type(exception).__name__}: {str(exception)}")
    
    def _on_processing_complete(self, output_file):
        """処理完了時の処理"""
        self.ui_elements['progress'].stop()
        self.is_processing = False
        self.update_status(f"処理完了: {os.path.basename(output_file)}")

        # エンジンの確認
        engine_value = get_engine_value(self.ui_elements)

        # GeminiまたはWhisper APIの場合のみ使用量を記録
        if engine_value == 'gemini':
            try:
                file_size_mb = get_file_size_mb(self.current_file) if self.current_file else 0.0
                filename = os.path.basename(self.current_file) if self.current_file else "unknown"

                # 音声時間とファイルサイズから概算トークン数を推定
                estimated_input_tokens = int(file_size_mb * TOKEN_ESTIMATION_FACTOR)
                estimated_output_tokens = int(estimated_input_tokens * OUTPUT_TOKEN_RATIO)

                cost = self.usage_tracker.record_usage(
                    model="gemini-2.5-flash",  # デフォルトモデル（2025年11月推奨）
                    input_tokens=estimated_input_tokens,
                    output_tokens=estimated_output_tokens,
                    file_name=filename,
                    file_size_mb=file_size_mb
                )

                self.add_log(f"使用料金: ${cost:.4f} (概算)")
                self.add_log(f"━━━ Gemini処理完了 ━━━")

                # 使用量表示を更新
                if hasattr(self, 'update_usage_callback') and self.update_usage_callback:
                    self.update_usage_callback()
            except Exception as e:
                logger.error(f"使用量記録エラー: {e}")
        elif engine_value == 'whisper-api':
            # Whisper APIの場合
            self.add_log(f"━━━ Whisper API処理完了 ━━━")
        else:
            # Whisper（ローカル）の場合
            whisper_model = get_whisper_model_value(self.ui_elements)
            self.add_log(f"━━━ Whisper処理完了 (モデル: {whisper_model}, 無料) ━━━")

            # ファイルサイズ情報を記録
            try:
                file_size_mb = get_file_size_mb(self.current_file) if self.current_file else 0.0
                self.add_log(f"処理ファイルサイズ: {file_size_mb:.2f}MB")
            except Exception as e:
                logger.error(f"ファイルサイズ取得エラー: {e}")

        # 履歴更新のコールバックがある場合は呼び出し
        if hasattr(self, 'update_history_callback') and self.update_history_callback:
            self.update_history_callback()

        # エンジンに応じたメッセージを表示
        self._show_completion_message(engine_value, output_file)
    
    def _show_completion_message(self, engine_value, output_file):
        """処理完了メッセージを表示"""
        filename = os.path.basename(output_file)
        
        if engine_value == 'whisper':
            whisper_model = get_whisper_model_value(self.ui_elements)
            messagebox.showinfo(
                "成功",
                f"Whisperによる文字起こしが完了しました。\n"
                f"モデル: {whisper_model} (ローカル/無料)\n"
                f"出力ファイル: {filename}"
            )
        elif engine_value == 'whisper-api':
            messagebox.showinfo(
                "成功",
                f"Whisper APIによる文字起こしが完了しました。\n"
                f"出力ファイル: {filename}"
            )
        else:
            messagebox.showinfo(
                "成功",
                f"Geminiによる文字起こしが完了しました。\n"
                f"出力ファイル: {filename}"
            )
    
    def set_update_history_callback(self, callback):
        """履歴更新のコールバックを設定"""
        self.update_history_callback = callback