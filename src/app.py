#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import re

from .ui import setup_ui
from .config import Config
from .processor import FileProcessor
from .audio_recorder import MicrophoneRecorder
from .audio_player import AudioPreviewPlayer
from .controllers import TranscriptionController
from .terminal_cleanup import schedule_launch_terminal_close
from .usage_tracker import UsageTracker
from .processing_time_tracker import ProcessingTimeTracker
from .constants import (
    OUTPUT_DIR,
    DATA_DIR,
    DEFAULT_RECORDING_GAIN_PERCENT,
    FILE_NAME_DISPLAY_MAX_LENGTH,
    RECORDINGS_DIR,
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_MEDIA_FILE_TYPES
)
from .utils import (
    open_file,
    open_directory,
    normalize_file_path,
    truncate_display_name,
    get_engine_value,
    get_whisper_model_value,
    get_gemini_safety_filter_recovery_value,
    get_trim_long_silence_value,
    get_silence_trim_settings,
    format_duration,
    format_file_size
)
from .exceptions import AudioProcessingError, FileProcessingError

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

        # 処理時間追跡
        self.time_tracker = ProcessingTimeTracker(self.app_dir)
        
        # 変数初期化
        self.api_key = tk.StringVar(value=self.config.get("api_key", ""))  # Gemini API用
        self.openai_api_key = tk.StringVar(value=self.config.get("openai_api_key", ""))  # OpenAI API用
        self.preferred_model = None  # 手動選択されたモデル
        self.recording_dir = self._resolve_recording_dir(
            self.config.get("recording_dir", RECORDINGS_DIR)
        )
        os.makedirs(self.recording_dir, exist_ok=True)
        self.recording_dir_var = tk.StringVar(value=self.recording_dir)
        self.auto_queue_recordings_var = tk.BooleanVar(
            value=self.config.get("auto_queue_recordings", True)
        )
        saved_recording_device = self.config.get("recording_input_device", None)
        try:
            self.recording_input_device_id = (
                None if saved_recording_device in (None, '', 'default') else int(saved_recording_device)
            )
        except (TypeError, ValueError):
            self.recording_input_device_id = None
        self.recording_input_device_var = tk.StringVar(value="")
        self._recording_device_options = {}
        self._recording_input_devices = []
        self.recording_input_channels_var = tk.StringVar(value="")
        self._recording_channel_options = {}
        self.recording_gain_percent_var = tk.DoubleVar(
            value=float(self.config.get("recording_gain_percent", DEFAULT_RECORDING_GAIN_PERCENT))
        )
        self.recording_gain_display_var = tk.StringVar(value="")
        self.recording_status_var = tk.StringVar(value="待機中")
        self.recording_elapsed_var = tk.StringVar(value="00:00:00")
        self.recording_device_var = tk.StringVar(value="マイク確認中...")
        self.recording_hint_var = tk.StringVar(value="停止後にそのままキューへ追加できます")
        self.recording_format_var = tk.StringVar(value="WAV / 16bit PCM")
        self.recording_level_var = tk.StringVar(value="0%")
        self.recording_peak_var = tk.StringVar(value="0%")
        self.audio_recorder = MicrophoneRecorder()
        self.preview_player = AudioPreviewPlayer()
        self._playback_poll_job = None
        self._waveform_refresh_job = None
        self._last_preview_error = None
        self.audio_recorder.set_input_preferences(
            device_id=self.recording_input_device_id,
            input_channels=self._normalize_recording_input_channels(
                self.config.get("recording_input_channels", [1])
            )
        )
        self.set_recording_gain(self.recording_gain_percent_var.get(), persist=False)
        self._recording_timer_job = None
        self._recording_visual_job = None
        self._recording_visual_phase = 0.0
        
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
            self.processor, self.config, self.usage_tracker, self.ui_elements,
            time_tracker=self.time_tracker
        )
        self.controller.set_update_history_callback(self._on_history_update)
        self.controller.update_usage_callback = self.update_usage_display
        self.controller.history_metadata = self.history_metadata
        self.controller.update_queue_callback = self._update_queue_display
        self._restore_queue_state()

        
        # ウィンドウサイズと位置の設定を適用（UI構築後）
        self.config.apply_window_geometry(self.root)
        
        # 初期設定
        self._restore_column_widths()
        self.update_history()
        self.update_usage_display()
        self.refresh_recording_input_options(persist=False)
        self.audio_recorder.start_monitoring()
        self._refresh_recording_ui()
        self._start_recording_visual_loop()
        self._start_playback_poll_loop()

        # ウィンドウにフォーカスが戻ったとき履歴を自動更新
        self.root.bind('<FocusIn>', self._on_focus_in)

        # 終了時にジオメトリを保存
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _resolve_recording_dir(self, configured_path):
        """録音保存先を絶対パスへ解決する"""
        configured_path = (configured_path or RECORDINGS_DIR).strip()
        if os.path.isabs(configured_path):
            return configured_path
        return os.path.abspath(os.path.join(self.app_dir, configured_path))

    def _format_recording_clock(self, total_seconds):
        """録音経過時間を HH:MM:SS で返す"""
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _normalize_recording_input_channels(self, value):
        """設定値から入力チャンネル配列を正規化する"""
        if value in (None, '', []):
            return [1]
        if isinstance(value, int):
            candidates = [value]
        elif isinstance(value, str):
            candidates = []
            for part in value.replace('-', ',').split(','):
                part = part.strip()
                if not part:
                    continue
                try:
                    candidates.append(int(part))
                except ValueError:
                    continue
        else:
            candidates = []
            for item in value:
                try:
                    candidates.append(int(item))
                except (TypeError, ValueError):
                    continue

        normalized = []
        for channel in candidates:
            if channel >= 1 and channel not in normalized:
                normalized.append(channel)
        return normalized or [1]

    def _format_recording_channel_option(self, channels):
        """入力チャンネル設定の表示名を返す"""
        normalized = self._normalize_recording_input_channels(channels)
        if len(normalized) == 1:
            return f"CH {normalized[0]} (mono)"
        if len(normalized) == 2 and normalized[1] == normalized[0] + 1:
            return f"CH {normalized[0]}-{normalized[1]} (stereo)"
        return "CH " + ",".join(str(channel) for channel in normalized)

    def _build_recording_device_label(self, device):
        """入力デバイス表示名を作る"""
        prefix = "既定" if device.get('is_default') else f"#{device['index']}"
        return (
            f"{prefix} | {device['name']} | "
            f"{device['max_input_channels']}ch | {device['hostapi_name']}"
        )

    def _build_recording_channel_options(self, max_input_channels):
        """選択可能な入力チャンネル一覧を返す"""
        options = [([1], "CH 1 (mono)")]
        if max_input_channels >= 1:
            options = []
            for channel in range(1, max_input_channels + 1):
                options.append(([channel], f"CH {channel} (mono)"))
            for channel in range(1, max_input_channels):
                options.append(([channel, channel + 1], f"CH {channel}-{channel + 1} (stereo)"))
        return options

    def _restart_recording_monitor(self):
        """入力設定変更後に待機モニターを張り直す"""
        if self.audio_recorder.is_recording:
            return
        self.audio_recorder.stop_monitoring()
        self.audio_recorder.start_monitoring()
        self._refresh_recording_ui(preserve_status=True)
        self._start_recording_visual_loop()

    def refresh_recording_input_options(self, persist=False):
        """録音用入力デバイス一覧とチャンネル候補を更新する"""
        devices = self.audio_recorder.list_input_devices()
        self._recording_input_devices = devices
        self._recording_device_options = {"既定マイクを使う": None}
        device_values = ["既定マイクを使う"]
        selected_device_label = "既定マイクを使う"
        selected_device = None

        for device in devices:
            label = self._build_recording_device_label(device)
            self._recording_device_options[label] = device
            device_values.append(label)
            if self.recording_input_device_id is not None and device['index'] == self.recording_input_device_id:
                selected_device_label = label
                selected_device = device

        if self.recording_input_device_id is None:
            selected_device = next((device for device in devices if device.get('is_default')), None)
        elif selected_device is None:
            self.recording_input_device_id = None

        self.recording_input_device_var.set(selected_device_label)

        device_combo = self.ui_elements.get('recording_device_combo') if hasattr(self, 'ui_elements') else None
        if device_combo:
            device_combo.configure(values=device_values, state='readonly' if device_values else 'disabled')

        max_input_channels = selected_device['max_input_channels'] if selected_device else 2
        channel_options = self._build_recording_channel_options(max_input_channels)
        self._recording_channel_options = {label: channels for channels, label in channel_options}
        channel_values = [label for _, label in channel_options]
        configured_channels = self._normalize_recording_input_channels(
            self.config.get("recording_input_channels", self.audio_recorder.selected_input_channels)
        )
        selected_channel_label = self._format_recording_channel_option(configured_channels)
        if selected_channel_label not in self._recording_channel_options:
            selected_channel_label = channel_values[0]
        self.recording_input_channels_var.set(selected_channel_label)

        channel_combo = self.ui_elements.get('recording_channel_combo') if hasattr(self, 'ui_elements') else None
        if channel_combo:
            channel_combo.configure(values=channel_values, state='readonly' if channel_values else 'disabled')

        selected_channels = self._recording_channel_options.get(selected_channel_label, [1])
        self.audio_recorder.set_input_preferences(
            device_id=self.recording_input_device_id,
            input_channels=selected_channels
        )
        if persist:
            self.config.set("recording_input_device", self.recording_input_device_id)
            self.config.set("recording_input_channels", list(selected_channels))
            self.config.save()

    def on_recording_device_selected(self, event=None):
        """録音用入力デバイス選択時の処理"""
        if self.audio_recorder.is_recording:
            return

        selected_label = self.recording_input_device_var.get()
        selected_device = self._recording_device_options.get(selected_label)
        self.recording_input_device_id = None if selected_device is None else selected_device['index']
        self.refresh_recording_input_options(persist=True)
        self._restart_recording_monitor()
        self.controller.add_log(
            "録音入力デバイスを変更: "
            + ("既定マイク" if selected_device is None else selected_device['name'])
        )

    def on_recording_channel_selected(self, event=None):
        """録音入力チャンネル選択時の処理"""
        if self.audio_recorder.is_recording:
            return

        selected_label = self.recording_input_channels_var.get()
        selected_channels = self._recording_channel_options.get(selected_label, [1])
        self.audio_recorder.set_input_preferences(
            device_id=self.recording_input_device_id,
            input_channels=selected_channels
        )
        self.config.set("recording_input_device", self.recording_input_device_id)
        self.config.set("recording_input_channels", list(selected_channels))
        self.config.save()
        self._restart_recording_monitor()
        self.controller.add_log(f"録音入力チャンネルを変更: {selected_label}")

    def refresh_recording_inputs(self):
        """録音入力一覧を再取得して待機モニターへ反映する"""
        self.refresh_recording_input_options(persist=False)
        self._restart_recording_monitor()

    def set_recording_gain(self, gain_percent, persist=False):
        """録音用ソフトウェアゲインを更新する"""
        applied_percent = self.audio_recorder.set_input_gain(gain_percent)
        self.recording_gain_percent_var.set(applied_percent)
        self.recording_gain_display_var.set(
            f"{applied_percent}% ({applied_percent / 100.0:.2f}x)"
        )
        self.config.set("recording_gain_percent", applied_percent)
        if persist:
            self.config.save()
        return applied_percent

    def on_recording_gain_change(self, value):
        """録音レベルスライダー変更時の処理"""
        self.set_recording_gain(value, persist=False)

    def persist_recording_gain(self, event=None):
        """録音レベル設定を保存する"""
        self.set_recording_gain(self.recording_gain_percent_var.get(), persist=True)

    def reset_recording_gain(self):
        """録音レベルを既定値へ戻す"""
        self.set_recording_gain(DEFAULT_RECORDING_GAIN_PERCENT, persist=True)

    def _set_recording_status(self, text, color=None):
        """録音ステータス表示を更新する"""
        self.recording_status_var.set(text)
        label = self.ui_elements.get('recording_status_label') if hasattr(self, 'ui_elements') else None
        badge = self.ui_elements.get('recording_badge_label') if hasattr(self, 'ui_elements') else None
        if label and color:
            label.config(fg=color)
        if badge:
            badge_map = {
                "録音中": ("REC", "#F8E5E3", "#BD5B55"),
                "保存完了": ("SAVED", "#E4F0E7", "#4F8B63"),
                "録音不可": ("ERROR", "#F8E5E3", "#BD5B55"),
                "待機中": ("STANDBY", "#E5EDF5", "#4E7DA5"),
            }
            badge_text, badge_bg, badge_fg = badge_map.get(
                text, ("READY", "#E5EDF5", "#4E7DA5")
            )
            badge.config(text=badge_text, bg=badge_bg, fg=badge_fg)

    def _update_recording_visual_state(self, level=0.0, peak=0.0, is_active=False,
                                       spectrum=None, waveform=None, is_live=False):
        """録音メーターと波形表示を更新する"""
        level_pct = max(0, min(100, int(level * 100)))
        peak_pct = max(0, min(100, int(peak * 100)))
        self.recording_level_var.set(f"{level_pct}%")
        self.recording_peak_var.set(f"{peak_pct}%")

        canvas = self.ui_elements.get('recording_visual_canvas') if hasattr(self, 'ui_elements') else None
        if canvas and hasattr(canvas, 'draw_visual'):
            canvas.draw_visual(
                level,
                peak,
                is_active,
                self._recording_visual_phase,
                spectrum or [],
                waveform or [],
                is_live
            )

    def _refresh_recording_ui(self, preserve_status=False):
        """録音UIの状態を現在の録音状態に合わせて更新する"""
        if not hasattr(self, 'ui_elements'):
            return

        record_button = self.ui_elements.get('record_button')
        stop_button = self.ui_elements.get('stop_record_button')
        choose_folder_button = self.ui_elements.get('choose_recording_folder_button')
        device_combo = self.ui_elements.get('recording_device_combo')
        channel_combo = self.ui_elements.get('recording_channel_combo')
        refresh_input_button = self.ui_elements.get('refresh_recording_inputs_button')
        status_label = self.ui_elements.get('recording_status_label')
        device_message = "既定マイク"
        available, availability_message = self.audio_recorder.get_availability()
        snapshot = self.audio_recorder.get_monitor_snapshot()

        if self.audio_recorder.is_recording:
            self._set_recording_status("録音中", "#BD5B55")
            device_message = (
                f"{self.audio_recorder.current_device_name} | "
                f"{self.audio_recorder.current_sample_rate}Hz | "
                f"{self.audio_recorder.get_monitor_snapshot().get('input_channel_label', '入力 CH 1')} | "
                f"保存 {self.audio_recorder.current_channels}ch"
            )
            current_file = os.path.basename(self.audio_recorder.current_file_path or "")
            self.recording_hint_var.set(f"保存先: {current_file}")
            self.recording_format_var.set(
                f"WAV / {self.audio_recorder.current_sample_rate}Hz / {self.audio_recorder.current_channels}ch"
            )
            if record_button:
                if hasattr(record_button, 'active_text'):
                    record_button.config(text=record_button.active_text)
                record_button.state(['disabled'])
            if stop_button:
                if hasattr(stop_button, 'active_text'):
                    stop_button.config(text=stop_button.active_text)
                stop_button.state(['!disabled'])
            if choose_folder_button:
                choose_folder_button.state(['disabled'])
            if device_combo:
                device_combo.configure(state='disabled')
            if channel_combo:
                channel_combo.configure(state='disabled')
            if refresh_input_button:
                refresh_input_button.state(['disabled'])
        else:
            device_message = availability_message
            if not preserve_status:
                if available:
                    self._set_recording_status("待機中", "#64605A")
                    self.recording_hint_var.set("停止後にそのままキューへ追加できます")
                else:
                    self._set_recording_status("録音不可", "#C25450")
                    self.recording_hint_var.set(availability_message)
            else:
                current_text = self.recording_status_var.get()
                if status_label:
                    if current_text == "保存完了":
                        status_label.config(fg="#4F8B63")
                    elif current_text == "録音不可":
                        status_label.config(fg="#C25450")
                    else:
                        status_label.config(fg="#64605A")

            if record_button:
                if hasattr(record_button, 'idle_text'):
                    record_button.config(text=record_button.idle_text)
                record_button.state(['!disabled'] if available else ['disabled'])
            if stop_button:
                if hasattr(stop_button, 'idle_text'):
                    stop_button.config(text=stop_button.idle_text)
                stop_button.state(['disabled'])
            if choose_folder_button:
                choose_folder_button.state(['!disabled'])
            if device_combo:
                device_combo.configure(state='readonly' if self._recording_device_options else 'disabled')
            if channel_combo:
                channel_combo.configure(state='readonly' if self._recording_channel_options else 'disabled')
            if refresh_input_button:
                refresh_input_button.state(['!disabled'])

            if not preserve_status and not self.audio_recorder.is_recording:
                self.recording_elapsed_var.set("00:00:00")
                self.recording_format_var.set("WAV / 16bit PCM")

        self.recording_device_var.set(device_message)
        self._update_recording_visual_state(
            level=snapshot['level'],
            peak=snapshot['peak'],
            is_active=self.audio_recorder.is_recording,
            spectrum=snapshot.get('spectrum', []),
            waveform=snapshot.get('waveform', []),
            is_live=self.audio_recorder.is_recording or self.audio_recorder.is_monitoring
        )

    def _start_recording_timer(self):
        """録音経過時間の表示更新を開始する"""
        self._stop_recording_timer()
        self._update_recording_elapsed()

    def _stop_recording_timer(self):
        """録音経過時間の表示更新を停止する"""
        if self._recording_timer_job is not None:
            self.root.after_cancel(self._recording_timer_job)
            self._recording_timer_job = None

    def _start_recording_visual_loop(self):
        """待機中の録音モニター描画を開始する"""
        if self._recording_visual_job is None:
            self._tick_recording_visual_loop()

    def _stop_recording_visual_loop(self):
        """待機中の録音モニター描画を停止する"""
        if self._recording_visual_job is not None:
            self.root.after_cancel(self._recording_visual_job)
            self._recording_visual_job = None

    def _tick_recording_visual_loop(self):
        """待機中でも録音モニターを周期更新する"""
        if self.audio_recorder.is_recording:
            self._recording_visual_job = None
            return

        snapshot = self.audio_recorder.get_monitor_snapshot()
        self._recording_visual_phase += 0.18
        self._update_recording_visual_state(
            level=snapshot['level'],
            peak=snapshot['peak'],
            is_active=False,
            spectrum=snapshot.get('spectrum', []),
            waveform=snapshot.get('waveform', []),
            is_live=self.audio_recorder.is_monitoring
        )
        self._recording_visual_job = self.root.after(140, self._tick_recording_visual_loop)

    def _update_recording_elapsed(self):
        """録音経過時間を1秒ごとに更新する"""
        elapsed = self.audio_recorder.get_elapsed_seconds()
        snapshot = self.audio_recorder.get_monitor_snapshot()
        self.recording_elapsed_var.set(self._format_recording_clock(elapsed))
        self._recording_visual_phase += 0.45
        self._update_recording_visual_state(
            level=snapshot['level'],
            peak=snapshot['peak'],
            is_active=self.audio_recorder.is_recording,
            spectrum=snapshot.get('spectrum', []),
            waveform=snapshot.get('waveform', []),
            is_live=self.audio_recorder.is_recording or self.audio_recorder.is_monitoring
        )
        if self.audio_recorder.is_recording:
            self._recording_timer_job = self.root.after(120, self._update_recording_elapsed)
        else:
            self._recording_timer_job = None

    def _start_playback_poll_loop(self):
        """波形プレビュー再生状態のポーリングを開始する"""
        if self._playback_poll_job is None:
            self._playback_poll_job = self.root.after(120, self._poll_playback_state)

    def _stop_playback_poll_loop(self):
        """波形プレビュー再生状態のポーリングを停止する"""
        if self._playback_poll_job is not None:
            self.root.after_cancel(self._playback_poll_job)
            self._playback_poll_job = None

    def _poll_playback_state(self):
        """再生状態をビューアへ反映する"""
        self._playback_poll_job = None
        viewer = self.ui_elements.get('waveform_viewer') if hasattr(self, 'ui_elements') else None
        if viewer:
            state = self.preview_player.get_state()
            viewer.set_playback_state(
                state.get('position', 0.0),
                is_playing=state.get('is_playing', False),
                current_db=state.get('current_db')
            )
            error_text = state.get('error')
            if error_text and error_text != self._last_preview_error:
                self._last_preview_error = error_text
                self.controller.add_log(f"注意: 波形プレビュー再生に失敗: {error_text}")
            elif not error_text:
                self._last_preview_error = None

        if self.root.winfo_exists():
            self._playback_poll_job = self.root.after(120, self._poll_playback_state)

    def toggle_waveform_playback(self):
        """波形プレビューの再生/一時停止を切り替える"""
        if not self.controller.current_file:
            messagebox.showinfo("情報", "まず音声ファイルを選択してください。")
            return

        viewer = self.ui_elements.get('waveform_viewer')
        if not viewer:
            return

        state = self.preview_player.get_state()
        current_file = os.path.abspath(self.controller.current_file)
        playing_file = state.get('file_path')
        is_same_file = bool(playing_file and os.path.abspath(playing_file) == current_file)
        preview_duration = self.controller._waveform_cache.get('duration')

        try:
            if state.get('is_playing') and is_same_file:
                paused_state = self.preview_player.pause()
                viewer.set_playback_state(paused_state.get('position', viewer.get_current_time()), is_playing=False)
            else:
                start_sec = viewer.get_current_time()
                next_state = self.preview_player.play(
                    self.controller.current_file,
                    start_sec=start_sec,
                    duration=preview_duration
                )
                viewer.set_playback_state(next_state.get('position', start_sec), is_playing=True)
        except AudioProcessingError as exc:
            messagebox.showerror("再生エラー", str(exc))
            self.controller.add_log(f"注意: 波形プレビュー再生を開始できませんでした: {exc}")

    def stop_waveform_playback(self, reset_position=True, silent=False):
        """波形プレビュー再生を停止する"""
        state = self.preview_player.stop(reset_position=reset_position, keep_file=True)
        viewer = self.ui_elements.get('waveform_viewer') if hasattr(self, 'ui_elements') else None
        if viewer:
            viewer.set_playback_state(
                0.0 if reset_position else state.get('position', viewer.get_current_time()),
                is_playing=False
            )
        if not silent:
            self._last_preview_error = None

    def seek_waveform_playback(self, position_sec):
        """波形クリック時に再生位置を移動する"""
        if not self.controller.current_file:
            return

        current_state = self.preview_player.get_state()
        preview_duration = self.controller._waveform_cache.get('duration')
        resume = bool(
            current_state.get('is_playing') and
            current_state.get('file_path') and
            os.path.abspath(current_state['file_path']) == os.path.abspath(self.controller.current_file)
        )

        try:
            next_state = self.preview_player.seek(
                position_sec,
                file_path=self.controller.current_file,
                duration=preview_duration,
                resume=resume
            )
            viewer = self.ui_elements.get('waveform_viewer')
            if viewer:
                viewer.set_playback_state(position_sec, is_playing=next_state.get('is_playing', False))
        except AudioProcessingError as exc:
            messagebox.showerror("再生エラー", str(exc))
            self.controller.add_log(f"注意: シークに失敗しました: {exc}")

    def on_silence_trim_settings_changed(self, immediate=False):
        """無音カット設定変更時に波形プレビューを再解析する"""
        if self._waveform_refresh_job is not None:
            self.root.after_cancel(self._waveform_refresh_job)
            self._waveform_refresh_job = None

        if not self.controller.current_file:
            return

        delay_ms = 0 if immediate else 250
        self._waveform_refresh_job = self.root.after(delay_ms, self._refresh_waveform_preview)

    def _refresh_waveform_preview(self):
        """現在選択中ファイルの波形プレビューを更新する"""
        self._waveform_refresh_job = None
        self.controller.refresh_waveform_preview()

    def on_closing(self):
        """ウィンドウが閉じられるときの処理"""
        if self.controller.is_processing:
            result = messagebox.askyesno(
                "確認", 
                "処理が進行中です。本当に終了しますか？"
            )
            if not result:
                return

        if self.audio_recorder.is_recording:
            result = messagebox.askyesno(
                "確認",
                "録音中です。停止して保存してから終了しますか？"
            )
            if not result:
                return

            try:
                self.stop_recording(add_to_queue=False, show_message=False)
            except AudioProcessingError as e:
                messagebox.showerror("録音エラー", str(e))
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
        self._save_recording_settings()
        self._persist_queue_state(save=False)

        # カラム幅を保存
        self._save_column_widths()
        self.config.save()
        if self._waveform_refresh_job is not None:
            self.root.after_cancel(self._waveform_refresh_job)
            self._waveform_refresh_job = None
        self.stop_waveform_playback(reset_position=False, silent=True)
        self.preview_player.shutdown()
        self._stop_playback_poll_loop()
        self._stop_recording_timer()
        self._stop_recording_visual_loop()
        self.audio_recorder.stop_monitoring()
        
        # アプリケーションを終了
        self.root.destroy()
        try:
            schedule_launch_terminal_close()
        except Exception:
            pass
    
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
                is_available, message = self.processor.test_whisper_availability()
                
                if is_available:
                    device_info = self.processor.get_whisper_device_info()
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
        """ファイル選択ダイアログを表示（複数選択・複数回追加対応）"""
        file_paths = filedialog.askopenfilenames(filetypes=SUPPORTED_MEDIA_FILE_TYPES)
        if file_paths:
            paths = list(file_paths)
            # キューに既にファイルがある or 複数選択 → キューに追加
            if len(paths) > 1 or self.controller.file_queue:
                self._add_files_to_queue(paths)
                preview_path = self._find_previewable_path(paths)
                if preview_path:
                    self.load_file(preview_path)
            else:
                self.load_file(paths[0])

    def toggle_auto_queue_recordings(self):
        """録音停止後の自動キュー投入設定を保存"""
        self.config.set("auto_queue_recordings", self.auto_queue_recordings_var.get())
        self.config.save()

    def choose_recording_folder(self):
        """録音保存先フォルダを選択する"""
        if self.audio_recorder.is_recording:
            messagebox.showinfo("情報", "録音中は保存先を変更できません。停止後に変更してください。")
            return

        selected_dir = filedialog.askdirectory(
            title="録音保存先を選択",
            initialdir=self.recording_dir
        )
        if not selected_dir:
            return

        self.recording_dir = os.path.abspath(selected_dir)
        os.makedirs(self.recording_dir, exist_ok=True)
        self.recording_dir_var.set(self.recording_dir)
        self.config.set("recording_dir", self.recording_dir)
        self.config.save()
        self.recording_hint_var.set("停止後にそのままキューへ追加できます")
        self.controller.add_log(f"録音保存先を変更: {self.recording_dir}")

    def open_recording_folder(self):
        """録音保存先フォルダを開く"""
        os.makedirs(self.recording_dir, exist_ok=True)
        if not open_directory(self.recording_dir):
            messagebox.showerror("エラー", "録音フォルダを開けません。")

    def _list_recording_files(self):
        """録音フォルダ内の対応ファイル一覧を返す"""
        if not os.path.isdir(self.recording_dir):
            return []

        files = []
        active_recording = os.path.abspath(self.audio_recorder.current_file_path) if self.audio_recorder.is_recording else None
        for name in os.listdir(self.recording_dir):
            file_path = os.path.join(self.recording_dir, name)
            if not os.path.isfile(file_path):
                continue
            ext = os.path.splitext(file_path)[1].lower().lstrip('.')
            if ext not in SUPPORTED_AUDIO_FORMATS:
                continue
            abs_path = os.path.abspath(file_path)
            if active_recording and abs_path == active_recording:
                continue
            files.append(abs_path)

        files.sort(key=lambda path: os.path.getmtime(path))
        return files

    def add_recordings_to_queue(self):
        """録音フォルダ内のファイルをキューへ追加する"""
        recording_files = self._list_recording_files()
        if not recording_files:
            messagebox.showinfo("情報", "録音フォルダにキュー追加できる音声ファイルがありません。")
            return

        self._add_files_to_queue(recording_files, prompt_on_duplicates=False)

    def start_recording(self):
        """既定マイクから録音を開始する"""
        if self.audio_recorder.is_recording:
            messagebox.showinfo("情報", "すでに録音中です。")
            return

        os.makedirs(self.recording_dir, exist_ok=True)

        try:
            info = self.audio_recorder.start_recording(self.recording_dir)
        except AudioProcessingError as e:
            self._set_recording_status("録音不可", "#C25450")
            self.recording_device_var.set(str(e))
            self.recording_hint_var.set("録音を開始できませんでした")
            self._refresh_recording_ui(preserve_status=True)
            messagebox.showerror("録音エラー", str(e))
            return

        self.recording_elapsed_var.set("00:00:00")
        self.recording_hint_var.set(f"保存先: {os.path.basename(info['file_path'])}")
        self.recording_format_var.set(
            f"WAV / {info['sample_rate']}Hz / {info['channels']}ch"
        )
        self._recording_visual_phase = 0.0
        self._stop_recording_visual_loop()
        self._refresh_recording_ui()
        self._start_recording_timer()
        self.controller.add_log(
            f"録音開始: {os.path.basename(info['file_path'])} | "
            f"{info['device_name']} | "
            f"{self._format_recording_channel_option(info.get('input_channels', [1]))} | "
            f"{info['sample_rate']}Hz / {info['channels']}ch"
        )

    def stop_recording(self, add_to_queue=None, show_message=True):
        """録音を停止して保存する"""
        if not self.audio_recorder.is_recording:
            if show_message:
                messagebox.showinfo("情報", "録音中ではありません。")
            return None

        try:
            result = self.audio_recorder.stop_recording()
        except AudioProcessingError as e:
            self._set_recording_status("録音不可", "#C25450")
            self.recording_device_var.set(str(e))
            self.recording_hint_var.set("録音データの保存に失敗しました")
            self._refresh_recording_ui(preserve_status=True)
            if show_message:
                messagebox.showerror("録音エラー", str(e))
            raise
        finally:
            self._stop_recording_timer()

        duration_text = format_duration(result['duration_sec'])
        size_text = format_file_size(result['size_bytes'])
        self.recording_elapsed_var.set(self._format_recording_clock(result['duration_sec']))
        self._set_recording_status("保存完了", "#4F8B63")
        self.recording_device_var.set(
            f"{result['device_name']} | "
            f"{self._format_recording_channel_option(result.get('input_channels', [1]))} | "
            f"{result['sample_rate']}Hz / {result['channels']}ch"
        )
        self.recording_hint_var.set(f"最後に保存: {os.path.basename(result['file_path'])}")
        self.recording_format_var.set(
            f"WAV / {result['sample_rate']}Hz / {result['channels']}ch"
        )
        self.audio_recorder.start_monitoring()
        self._refresh_recording_ui(preserve_status=True)
        self._start_recording_visual_loop()
        self.controller.add_log(
            f"録音保存: {os.path.basename(result['file_path'])} | "
            f"{duration_text} | {size_text}"
        )

        if add_to_queue is None:
            add_to_queue = self.auto_queue_recordings_var.get()

        if add_to_queue:
            self._add_files_to_queue([result['file_path']], prompt_on_duplicates=False)

        return result
    
    def load_file(self, file_path):
        """ファイルを読み込む（コントローラーに委譲）"""
        self.stop_waveform_playback(reset_position=True, silent=True)
        self.controller.load_file(file_path)

    def load_files(self, raw_data):
        """D&Dデータから複数ファイルを解析してキューに追加"""
        paths = self._parse_dnd_paths(raw_data)
        if not paths:
            return
        # キューに既にファイルがある or 複数ドロップ → キューに追加
        if len(paths) > 1 or self.controller.file_queue:
            self._add_files_to_queue(paths)
            preview_path = self._find_previewable_path(paths)
            if preview_path:
                self.load_file(preview_path)
        else:
            self.load_file(paths[0])

    def _find_previewable_path(self, file_paths):
        """波形プレビュー対象に使える最初のファイルを返す"""
        for path in file_paths:
            normalized_path = normalize_file_path(path)
            if not normalized_path:
                continue
            abs_path = os.path.abspath(normalized_path)
            ext = os.path.splitext(abs_path)[1].lower().lstrip('.')
            if ext in SUPPORTED_AUDIO_FORMATS and os.path.exists(abs_path):
                return abs_path
        return None

    def _parse_dnd_paths(self, raw_data):
        """tkinterdnd2のD&Dデータからファイルパスリストを解析

        形式例:
          {C:/path with spaces/file.mp3} C:/simple.wav
          {C:/path with spaces/file.mp3}
          C:/simple.wav
        """
        raw_data = (raw_data or "").strip()
        if not raw_data:
            return []

        single_path = normalize_file_path(raw_data)
        if single_path and os.path.exists(single_path):
            return [single_path]

        parsed_paths = []

        def score_paths(paths):
            existing = sum(1 for path in paths if os.path.exists(path))
            supported = sum(
                1 for path in paths
                if os.path.splitext(path)[1].lower().lstrip('.') in SUPPORTED_AUDIO_FORMATS
            )
            return (existing, supported, -len(paths))

        try:
            i = 0
            while i < len(raw_data):
                if raw_data[i] == '{':
                    end = raw_data.index('}', i)
                    parsed_paths.append(raw_data[i + 1:end])
                    i = end + 1
                elif raw_data[i] in (' ', '\t', '\n', '\r'):
                    i += 1
                elif raw_data[i] in ('"', "'"):
                    quote = raw_data[i]
                    end = raw_data.index(quote, i + 1)
                    parsed_paths.append(raw_data[i + 1:end])
                    i = end + 1
                else:
                    end = i
                    while end < len(raw_data) and raw_data[end] not in (' ', '\t', '\n', '\r', '{'):
                        end += 1
                    parsed_paths.append(raw_data[i:end])
                    i = end
        except Exception:
            try:
                parsed_paths = list(self.root.tk.splitlist(raw_data))
            except Exception:
                parsed_paths = []

        normalized_paths = []
        for path in parsed_paths:
            normalized_path = normalize_file_path(path)
            if normalized_path:
                normalized_paths.append(normalized_path)

        try:
            splitlist_paths = [
                normalize_file_path(path)
                for path in self.root.tk.splitlist(raw_data)
                if normalize_file_path(path)
            ]
        except Exception:
            splitlist_paths = []

        if score_paths(splitlist_paths) > score_paths(normalized_paths):
            return splitlist_paths
        return normalized_paths

    def _normalize_queue_path(self, file_path):
        """キュー保存用のファイルパスを正規化する"""
        normalized_path = normalize_file_path(file_path)
        if not normalized_path:
            return None

        abs_path = os.path.abspath(normalized_path)
        ext = os.path.splitext(abs_path)[1].lower().lstrip('.')
        if ext not in SUPPORTED_AUDIO_FORMATS:
            return None
        return abs_path

    def _get_persisted_queue_paths(self):
        """永続化対象のキュー一覧を返す"""
        queue_paths = list(self.controller.file_queue)

        if self.controller.queue_processing and self.controller.current_file:
            current_path = self._normalize_queue_path(self.controller.current_file)
            first_path = os.path.abspath(queue_paths[0]) if queue_paths else None
            if current_path and current_path != first_path:
                queue_paths = [current_path] + queue_paths

        persisted_paths = []
        for path in queue_paths:
            normalized_path = self._normalize_queue_path(path)
            if normalized_path:
                persisted_paths.append(normalized_path)
        return persisted_paths

    def _persist_queue_state(self, save=True):
        """現在のキューを設定ファイルへ保存する"""
        queued_files = self._get_persisted_queue_paths()
        if self.config.get("queued_files", []) == queued_files:
            return False

        self.config.set("queued_files", queued_files)
        if save:
            self.config.save()
        return True

    def _restore_queue_state(self):
        """前回終了時のキューを復元する"""
        saved_queue = self.config.get("queued_files", [])
        if not isinstance(saved_queue, list):
            saved_queue = []

        restored_queue = []
        skipped_entries = 0
        for path in saved_queue:
            normalized_path = self._normalize_queue_path(path)
            if normalized_path:
                restored_queue.append(normalized_path)
            else:
                skipped_entries += 1

        self.controller.file_queue = restored_queue
        if restored_queue:
            self.controller.add_log(f"前回のキューを{len(restored_queue)}件復元")
        if skipped_entries:
            self.controller.add_log(f"前回キューの不正な項目を{skipped_entries}件スキップ")
        self._update_queue_display()

    def _format_queue_location(self, file_path, max_length=54):
        """キュー一覧向けにディレクトリ表示を短縮する"""
        directory = os.path.dirname(file_path) or file_path
        if len(directory) <= max_length:
            return directory
        return "..." + directory[-(max_length - 3):]

    def _describe_queue_item(self, file_path, index):
        """キュー一覧の行表示情報を返す"""
        abs_path = os.path.abspath(file_path)
        exists = os.path.exists(abs_path)

        if exists:
            try:
                size_label = format_file_size(os.path.getsize(abs_path))
                status_label = f"準備OK / {size_label}"
            except OSError:
                status_label = "準備OK / サイズ不明"
        else:
            status_label = "見つかりません"

        return {
            'iid': f"queue:{index}",
            'values': (
                index + 1,
                os.path.basename(abs_path),
                self._format_queue_location(abs_path),
                status_label
            ),
            'exists': exists,
            'tag': 'queue_ready' if exists else 'queue_missing'
        }

    def _get_selected_queue_indices(self):
        """キュー一覧で選択中のインデックスを返す"""
        queue_tree = self.ui_elements.get('queue_tree')
        if not queue_tree:
            return []

        indices = []
        for item_id in queue_tree.selection():
            try:
                indices.append(int(str(item_id).split(':', 1)[1]))
            except (IndexError, ValueError):
                continue
        return sorted(set(indices))

    def _add_files_to_queue(self, file_paths, prompt_on_duplicates=True):
        """ファイルリストをキューに追加（重複検出付き）"""
        added, duplicated_paths, invalid = self.controller.add_files_to_queue(file_paths)

        if duplicated_paths:
            if prompt_on_duplicates:
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
            else:
                self.controller.add_log(f"重複ファイルを{len(duplicated_paths)}件スキップ")

        if invalid > 0:
            self.controller.add_log(f"対応していないファイル形式: {invalid}件スキップ")

        if added > 0:
            self.controller.add_log(f"キューに{added}件追加（合計: {len(self.controller.file_queue)}件）")

    def _update_queue_display(self):
        """キュー一覧を更新"""
        queue_frame = self.ui_elements.get('queue_frame')
        queue_tree = self.ui_elements.get('queue_tree')
        queue_count_label = self.ui_elements.get('queue_count_label')
        if not queue_frame or not queue_tree or not queue_count_label:
            return

        for item_id in queue_tree.get_children():
            queue_tree.delete(item_id)

        queue = self.controller.file_queue

        if queue:
            ready_count = 0
            missing_count = 0

            for index, path in enumerate(queue):
                item = self._describe_queue_item(path, index)
                queue_tree.insert('', 'end', iid=item['iid'], values=item['values'], tags=(item['tag'],))
                if item['exists']:
                    ready_count += 1
                else:
                    missing_count += 1

            summary_parts = [f"現在のキュー: {len(queue)}件"]
            if ready_count:
                summary_parts.append(f"準備OK {ready_count}件")
            if missing_count:
                summary_parts.append(f"見つからない {missing_count}件")
            queue_count_label.config(text=" | ".join(summary_parts))
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
            queue_count_label.config(text="現在のキュー: 0件")
            if queue_frame.winfo_ismapped():
                queue_frame.pack_forget()

        self._persist_queue_state()

    def remove_from_queue(self):
        """キュー一覧の選択項目を削除"""
        indices = self._get_selected_queue_indices()
        if indices:
            self.controller.remove_from_queue(indices)

    def clear_queue(self):
        """キュー全クリア"""
        self.controller.clear_queue()

    def start_process(self, process_type):
        """処理を開始（コントローラーに委譲）"""
        if process_type == "transcription":
            self.stop_waveform_playback(reset_position=False, silent=True)
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
        """ウィンドウにフォーカスが戻ったとき履歴・キューを自動更新"""
        # ルートウィンドウのイベントのみ処理（子ウィジェットの連鎖を無視）
        if event and event.widget is not self.root:
            return
        self.update_history()
        self._cleanup_queue()
        self.audio_recorder.start_monitoring()
        self._refresh_recording_ui(preserve_status=True)

    def _cleanup_queue(self):
        """キュー内ファイルの状態表示を更新"""
        self._update_queue_display()

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

    def open_selected_output_directory(self, event=None):
        """選択された出力ファイルの保存先ディレクトリを開く"""
        tree = self.ui_elements['history_tree']
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("情報", "履歴からファイルを選択してください。")
            return

        item = tree.item(selection[0])
        filename = item['values'][0]
        directory = os.path.dirname(os.path.join(self.output_dir, filename))

        if not open_directory(directory):
            messagebox.showerror("エラー", f"保存先ディレクトリを開けません。\n{directory}")

    def open_history_directory(self):
        """処理履歴メタデータを保存しているディレクトリを開く"""
        history_dir = os.path.dirname(self.history_meta_path)
        if not open_directory(history_dir):
            messagebox.showerror("エラー", "処理履歴のディレクトリを開けません。")

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

    def _on_history_update(self, output_file=None):
        """処理完了時のコールバック - メタデータ保存 + 履歴更新"""
        if self.controller.current_file and output_file:
            output_dir = os.path.abspath(os.path.dirname(output_file))
            if output_dir == os.path.abspath(self.output_dir):
                output_name = os.path.basename(output_file)
                source_file = self.controller.current_file
                self.history_metadata[output_name] = {
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
            
            self.ui_elements['usage_sessions'].config(text=f"{usage_data['total_sessions']}回")
            
            total_tokens = usage_data['total_input_tokens'] + usage_data['total_output_tokens']
            if total_tokens > 1000:
                tokens_text = f"{total_tokens//1000}K"
            else:
                tokens_text = f"{total_tokens}"
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
            gemini_safety_filter_recovery = get_gemini_safety_filter_recovery_value(self.ui_elements)
            self.config.set("transcription_engine", engine_value)
            self.config.set("whisper_model", whisper_model)
            self.config.set("gemini_safety_filter_recovery", gemini_safety_filter_recovery)

    def _save_destination_settings(self):
        """保存先設定を保存"""
        if hasattr(self, 'ui_elements'):
            save_to_output = self.ui_elements.get('save_to_output_var')
            save_to_source = self.ui_elements.get('save_to_source_var')
            trim_long_silence = get_trim_long_silence_value(self.ui_elements)
            silence_trim_settings = get_silence_trim_settings(self.ui_elements)
            if save_to_output is not None:
                self.config.set("save_to_output_dir", save_to_output.get())
            if save_to_source is not None:
                self.config.set("save_to_source_dir", save_to_source.get())
            self.config.set("trim_long_silence", trim_long_silence)
            self.config.set("silence_trim_mode", silence_trim_settings['mode'])
            self.config.set("silence_trim_threshold_db", silence_trim_settings['threshold_db'])
            self.config.set("silence_trim_min_silence_sec", silence_trim_settings['min_silence_sec'])

    def _save_recording_settings(self):
        """録音設定を保存"""
        self.config.set("recording_dir", self.recording_dir)
        self.config.set("auto_queue_recordings", self.auto_queue_recordings_var.get())
        self.config.set("recording_gain_percent", int(round(self.recording_gain_percent_var.get())))
        self.config.set("recording_input_device", self.recording_input_device_id)
        self.config.set(
            "recording_input_channels",
            list(self._recording_channel_options.get(self.recording_input_channels_var.get(), [1]))
        )

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
