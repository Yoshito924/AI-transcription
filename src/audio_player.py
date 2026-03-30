#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
波形プレビュー用の軽量オーディオプレイヤー

ffmpeg で任意位置から PCM をデコードし、sounddevice で既定の出力デバイスへ流す。
"""

import math
import os
import struct
import subprocess
import threading

from .exceptions import AudioProcessingError
from .logger import logger

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - インストール有無で分岐
    sd = None


class AudioPreviewPlayer:
    """クリックシーク対応の簡易オーディオプレイヤー"""

    CHUNK_FRAMES = 4096
    DEFAULT_SAMPLE_RATE = 48000
    DEFAULT_CHANNELS = 2

    def __init__(self):
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._play_thread = None
        self._ffmpeg_process = None
        self._output_stream = None
        self._state = {
            'file_path': None,
            'duration': 0.0,
            'position': 0.0,
            'is_playing': False,
            'is_paused': False,
            'error': None,
            'sample_rate': 0,
            'channels': 0,
            'current_db': -float('inf'),
        }

    def get_state(self):
        """現在の再生状態を返す"""
        with self._lock:
            return dict(self._state)

    def get_availability(self):
        """既定の出力デバイスで再生可能か確認する"""
        if sd is None:
            return False, "sounddevice が未インストールのためプレビュー再生できません。"

        try:
            device_info = sd.query_devices(kind='output')
        except Exception as exc:
            return False, f"既定の出力デバイスを取得できません: {exc}"

        max_output_channels = int(device_info.get('max_output_channels') or 0)
        if max_output_channels < 1:
            return False, "再生に使える出力デバイスが見つかりません。"

        sample_rate = int(device_info.get('default_samplerate') or self.DEFAULT_SAMPLE_RATE)
        channels = 2 if max_output_channels >= 2 else 1

        try:
            sd.check_output_settings(
                samplerate=sample_rate,
                channels=channels,
                dtype='int16'
            )
        except Exception as exc:
            return False, f"出力デバイス設定を初期化できません: {exc}"

        return True, f"{device_info.get('name', '既定デバイス')} | {sample_rate}Hz | {channels}ch"

    def play(self, file_path, start_sec=0.0, duration=None):
        """指定位置から再生を開始する"""
        if not file_path or not os.path.exists(file_path):
            raise AudioProcessingError("再生するファイルが見つかりません。")

        available, message = self.get_availability()
        if not available:
            raise AudioProcessingError(message)

        sample_rate, channels = self._resolve_output_settings()
        current_state = self.stop(reset_position=False, keep_file=True)

        with self._lock:
            target_duration = float(duration) if duration is not None else float(current_state.get('duration') or 0.0)
            if target_duration > 0:
                start_sec = max(0.0, min(float(start_sec), target_duration))
            else:
                start_sec = max(0.0, float(start_sec))

            self._stop_event.clear()
            self._state.update({
                'file_path': file_path,
                'duration': target_duration,
                'position': start_sec,
                'is_playing': True,
                'is_paused': False,
                'error': None,
                'sample_rate': sample_rate,
                'channels': channels,
            })

            self._play_thread = threading.Thread(
                target=self._playback_worker,
                args=(file_path, start_sec, target_duration, sample_rate, channels),
                name="audio-preview-player",
                daemon=True
            )
            self._play_thread.start()

        return self.get_state()

    def pause(self):
        """再生を一時停止する"""
        state = self.get_state()
        if not state.get('is_playing'):
            return state

        position = float(state.get('position') or 0.0)
        self.stop(reset_position=False, keep_file=True)
        with self._lock:
            self._state['position'] = position
            self._state['is_paused'] = True
        return self.get_state()

    def stop(self, reset_position=True, keep_file=True):
        """再生を停止する"""
        with self._lock:
            thread = self._play_thread
            self._stop_event.set()
            self._terminate_backend_locked()

        if thread is not None:
            thread.join(timeout=2.0)

        with self._lock:
            if self._play_thread is thread:
                self._play_thread = None
            self._ffmpeg_process = None
            self._output_stream = None
            self._state['is_playing'] = False
            self._state['is_paused'] = False
            if reset_position:
                self._state['position'] = 0.0
            if not keep_file:
                self._state['file_path'] = None
                self._state['duration'] = 0.0
                self._state['error'] = None
            self._stop_event.clear()
            return dict(self._state)

    def seek(self, position_sec, file_path=None, duration=None, resume=False):
        """再生位置を移動する"""
        state = self.get_state()
        target_file = file_path or state.get('file_path')
        target_duration = float(duration) if duration is not None else float(state.get('duration') or 0.0)
        position_sec = max(0.0, float(position_sec))
        if target_duration > 0:
            position_sec = min(position_sec, target_duration)

        if resume and target_file:
            return self.play(target_file, start_sec=position_sec, duration=target_duration)

        with self._lock:
            if target_file:
                self._state['file_path'] = target_file
            if duration is not None:
                self._state['duration'] = target_duration
            self._state['position'] = position_sec
            self._state['is_paused'] = False
            self._state['error'] = None
            return dict(self._state)

    def shutdown(self):
        """終了時に再生を完全停止する"""
        self.stop(reset_position=False, keep_file=False)

    def _resolve_output_settings(self):
        """既定の出力設定を返す"""
        device_info = sd.query_devices(kind='output')
        max_output_channels = int(device_info.get('max_output_channels') or 0)
        if max_output_channels < 1:
            raise AudioProcessingError("再生に使える出力デバイスが見つかりません。")

        sample_rate = int(device_info.get('default_samplerate') or self.DEFAULT_SAMPLE_RATE)
        channels = 2 if max_output_channels >= 2 else 1
        return sample_rate, channels

    def _terminate_backend_locked(self):
        """再生バックエンドを停止する"""
        if self._ffmpeg_process is not None:
            try:
                if self._ffmpeg_process.poll() is None:
                    self._ffmpeg_process.terminate()
            except Exception:
                pass

        if self._output_stream is not None:
            try:
                self._output_stream.abort(ignore_errors=True)
            except Exception:
                try:
                    self._output_stream.stop()
                except Exception:
                    pass
            try:
                self._output_stream.close(ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def _calc_rms_db(chunk_bytes, channels):
        """PCM int16 チャンクから RMS dB (dBFS) を計算する"""
        num_samples = len(chunk_bytes) // 2
        if num_samples == 0:
            return -float('inf')
        samples = struct.unpack(f'<{num_samples}h', chunk_bytes[:num_samples * 2])
        sum_sq = sum(s * s for s in samples)
        rms = math.sqrt(sum_sq / num_samples)
        if rms < 1:
            return -float('inf')
        return 20.0 * math.log10(rms / 32768.0)

    def _build_ffmpeg_command(self, file_path, start_sec, sample_rate, channels):
        """ffmpeg の再生用デコードコマンドを構築する"""
        return [
            'ffmpeg',
            '-nostdin',
            '-loglevel', 'error',
            '-ss', f"{start_sec:.3f}",
            '-i', file_path,
            '-vn',
            '-ac', str(channels),
            '-ar', str(sample_rate),
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            'pipe:1'
        ]

    def _playback_worker(self, file_path, start_sec, duration, sample_rate, channels):
        """ffmpeg を使って PCM をストリーミング再生する"""
        bytes_per_frame = max(1, channels) * 2
        chunk_bytes = self.CHUNK_FRAMES * bytes_per_frame
        process = None
        stream = None
        played_frames = 0
        final_error = None

        try:
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            process = subprocess.Popen(
                self._build_ffmpeg_command(file_path, start_sec, sample_rate, channels),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags
            )
            stream = sd.RawOutputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype='int16',
                blocksize=self.CHUNK_FRAMES
            )
            stream.start()

            with self._lock:
                self._ffmpeg_process = process
                self._output_stream = stream

            while not self._stop_event.is_set():
                chunk = process.stdout.read(chunk_bytes) if process.stdout else b''
                if not chunk:
                    break

                usable = len(chunk) - (len(chunk) % bytes_per_frame)
                if usable <= 0:
                    continue

                chunk = chunk[:usable]
                stream.write(chunk)
                played_frames += usable // bytes_per_frame

                db = self._calc_rms_db(chunk, channels)
                with self._lock:
                    position = start_sec + (played_frames / float(sample_rate))
                    if duration > 0:
                        position = min(position, duration)
                    self._state['position'] = position
                    self._state['current_db'] = db

            if process.poll() is None:
                process.wait(timeout=1.0)
            return_code = process.returncode
            stderr_text = ""
            if process.stderr is not None:
                stderr_text = process.stderr.read().decode('utf-8', errors='replace').strip()

            if not self._stop_event.is_set() and return_code not in (0, None):
                final_error = stderr_text or f"ffmpeg 再生プロセスが異常終了しました (code={return_code})"
        except Exception as exc:
            if not self._stop_event.is_set():
                final_error = str(exc)
                logger.warning(f"波形プレビュー再生エラー: {exc}", exc_info=True)
        finally:
            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    pass
                try:
                    stream.close(ignore_errors=True)
                except Exception:
                    pass

            if process is not None:
                try:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=1.0)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

            with self._lock:
                if self._ffmpeg_process is process:
                    self._ffmpeg_process = None
                if self._output_stream is stream:
                    self._output_stream = None
                if self._play_thread is threading.current_thread():
                    self._play_thread = None
                self._state['is_playing'] = False
                self._state['is_paused'] = False
                self._state['current_db'] = -float('inf')
                if final_error:
                    self._state['error'] = final_error
                elif duration > 0:
                    self._state['position'] = min(
                        duration,
                        start_sec + (played_frames / float(sample_rate))
                    )
                else:
                    self._state['position'] = max(
                        self._state.get('position', 0.0),
                        start_sec + (played_frames / float(sample_rate))
                    )
