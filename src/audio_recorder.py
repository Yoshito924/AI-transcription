#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
マイク録音サービス

sounddevice を利用して既定の入力デバイスから WAV ファイルへ録音する。
録音後は既存の文字起こしキューへそのまま渡せるよう、安定したファイル保存を優先する。
"""

import os
import queue
import threading
import wave
from datetime import datetime

import numpy as np

from .constants import (
    DEFAULT_RECORDING_CHANNELS,
    DEFAULT_RECORDING_GAIN_PERCENT,
    DEFAULT_RECORDING_SAMPLE_RATE
)
from .exceptions import AudioProcessingError
from .logger import logger

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - インストール有無で分岐
    sd = None


class MicrophoneRecorder:
    """既定マイクから音声を録音して WAV に保存する"""

    def __init__(self, default_sample_rate=DEFAULT_RECORDING_SAMPLE_RATE,
                 preferred_channels=DEFAULT_RECORDING_CHANNELS):
        self.default_sample_rate = default_sample_rate
        self.preferred_channels = preferred_channels
        self.sample_width_bytes = 2  # int16

        self.is_recording = False
        self.input_gain = DEFAULT_RECORDING_GAIN_PERCENT / 100.0
        self.input_gain_percent = DEFAULT_RECORDING_GAIN_PERCENT
        self.selected_device_id = None
        self.selected_input_channels = [1]
        self.current_file_path = None
        self.current_device_name = None
        self.current_sample_rate = default_sample_rate
        self.current_channels = preferred_channels
        self.current_stream_channels = preferred_channels
        self.current_input_channels = [1]
        self.started_at = None

        self._stream = None
        self._monitor_stream = None
        self._wave_handle = None
        self._frame_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._writer_done_event = threading.Event()
        self._writer_thread = None
        self._writer_error = None
        self.is_monitoring = False
        self._meter_lock = threading.Lock()
        self._current_level = 0.0
        self._peak_level = 0.0
        self._spectrum_bins = [0.0] * 28
        self._waveform_preview = [0.0] * 72

    def get_availability(self):
        """録音に必要な依存関係と既定マイクの利用可否を返す"""
        if sd is None:
            return False, "sounddevice が未インストールです。`pip install sounddevice` を実行してください。"

        try:
            device_info, sample_rate, stream_channels, output_channels, selected_input_channels, device_ref = self._resolve_input_settings()
        except AudioProcessingError as exc:
            logger.warning(f"録音デバイス確認エラー: {exc}")
            return False, str(exc)

        device_name = device_info.get('name', '既定のマイク')
        channel_label = self._format_input_channel_label(selected_input_channels)
        return True, f"{device_name} | {channel_label} | {sample_rate}Hz"

    def get_elapsed_seconds(self):
        """録音経過秒数を返す"""
        if not self.is_recording or not self.started_at:
            return 0
        return max(0, int((datetime.now() - self.started_at).total_seconds()))

    def get_monitor_snapshot(self):
        """録音モニター用の現在値を返す"""
        with self._meter_lock:
            return {
                'level': self._current_level,
                'peak': self._peak_level,
                'sample_rate': self.current_sample_rate,
                'channels': self.current_channels,
                'gain_percent': self.input_gain_percent,
                'input_channels': list(self.current_input_channels),
                'input_channel_label': self._format_input_channel_label(self.current_input_channels),
                'spectrum': list(self._spectrum_bins),
                'waveform': list(self._waveform_preview),
            }

    def list_input_devices(self):
        """利用可能な入力デバイス一覧を返す"""
        if sd is None:
            return []

        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            default_input_id = self._get_default_input_device_id()
        except Exception as exc:
            logger.warning(f"入力デバイス一覧取得エラー: {exc}")
            return []

        input_devices = []
        for index, device in enumerate(devices):
            max_input_channels = int(device.get('max_input_channels') or 0)
            if max_input_channels < 1:
                continue

            hostapi_index = int(device.get('hostapi') or 0)
            if 0 <= hostapi_index < len(hostapis):
                hostapi_name = hostapis[hostapi_index].get('name', 'Unknown')
            else:
                hostapi_name = 'Unknown'

            input_devices.append({
                'index': index,
                'name': device.get('name', f'Input {index}'),
                'hostapi_name': hostapi_name,
                'max_input_channels': max_input_channels,
                'default_samplerate': int(device.get('default_samplerate') or self.default_sample_rate),
                'is_default': default_input_id == index,
            })

        return input_devices

    def set_input_preferences(self, device_id=None, input_channels=None):
        """入力デバイスと使用チャンネルを設定する"""
        if device_id in (None, '', 'default'):
            self.selected_device_id = None
        else:
            self.selected_device_id = int(device_id)
        self.selected_input_channels = self._normalize_input_channels(input_channels)
        return {
            'device_id': self.selected_device_id,
            'input_channels': list(self.selected_input_channels),
        }

    def set_input_gain(self, gain_percent):
        """録音用ソフトウェアゲインを設定する"""
        try:
            gain_value = float(gain_percent)
        except (TypeError, ValueError):
            gain_value = DEFAULT_RECORDING_GAIN_PERCENT

        gain_value = max(25.0, min(250.0, gain_value))
        self.input_gain = gain_value / 100.0
        self.input_gain_percent = int(round(gain_value))
        return self.input_gain_percent

    def start_recording(self, output_dir):
        """録音を開始し、保存先ファイル情報を返す"""
        if self.is_recording:
            raise AudioProcessingError("すでに録音中です。")

        available, message = self.get_availability()
        if not available:
            raise AudioProcessingError(message)

        device_info, sample_rate, stream_channels, output_channels, selected_input_channels, device_ref = self._resolve_input_settings()
        os.makedirs(output_dir, exist_ok=True)
        self.stop_monitoring()

        file_path = self._build_output_path(output_dir)
        logger.info(
            "録音開始: file=%s, device=%s, sample_rate=%s, channels=%s",
            file_path,
            device_info.get('name', 'unknown'),
            sample_rate,
            output_channels
        )

        self._reset_runtime_state()
        self.current_file_path = file_path
        self.current_device_name = device_info.get('name', '既定のマイク')
        self.current_sample_rate = sample_rate
        self.current_channels = output_channels
        self.current_stream_channels = stream_channels
        self.current_input_channels = list(selected_input_channels)

        try:
            self._wave_handle = wave.open(file_path, 'wb')
            self._wave_handle.setnchannels(output_channels)
            self._wave_handle.setsampwidth(self.sample_width_bytes)
            self._wave_handle.setframerate(sample_rate)

            self._writer_thread = threading.Thread(
                target=self._writer_loop,
                name="microphone-recorder-writer",
                daemon=True
            )
            self._writer_thread.start()

            self._stream = sd.RawInputStream(
                samplerate=sample_rate,
                device=device_ref,
                channels=stream_channels,
                dtype='int16',
                callback=self._audio_callback
            )
            self._stream.start()
        except Exception as exc:
            logger.error(f"録音開始に失敗: {exc}", exc_info=True)
            self._abort_recording_setup()
            raise AudioProcessingError(f"マイク録音を開始できませんでした: {exc}")

        self.is_recording = True
        self.started_at = datetime.now()

        return {
            'file_path': file_path,
            'device_name': self.current_device_name,
            'sample_rate': sample_rate,
            'channels': output_channels,
            'input_channels': list(selected_input_channels),
        }

    def start_monitoring(self):
        """録音していない間だけモニターストリームを開始する"""
        if sd is None or self.is_recording or self.is_monitoring:
            return False

        available, _ = self.get_availability()
        if not available:
            return False

        try:
            device_info, sample_rate, stream_channels, output_channels, selected_input_channels, device_ref = self._resolve_input_settings()
            self._reset_meter_state()
            self.current_file_path = None
            self.current_device_name = device_info.get('name', '既定のマイク')
            self.current_sample_rate = sample_rate
            self.current_channels = output_channels
            self.current_stream_channels = stream_channels
            self.current_input_channels = list(selected_input_channels)
            self._monitor_stream = sd.RawInputStream(
                samplerate=sample_rate,
                device=device_ref,
                channels=stream_channels,
                dtype='int16',
                callback=self._monitor_callback
            )
            self._monitor_stream.start()
            self.is_monitoring = True
            return True
        except Exception as exc:
            logger.warning(f"録音モニター開始エラー: {exc}")
            if self._monitor_stream is not None:
                try:
                    self._monitor_stream.close()
                except Exception:
                    pass
                self._monitor_stream = None
            self.is_monitoring = False
            return False

    def stop_monitoring(self):
        """モニターストリームを停止する"""
        if self._monitor_stream is None:
            self.is_monitoring = False
            return

        try:
            self._monitor_stream.stop()
            self._monitor_stream.close()
        except Exception as exc:
            logger.warning(f"録音モニター停止中の警告: {exc}")
        finally:
            self._monitor_stream = None
            self.is_monitoring = False
            if not self.is_recording:
                self._clear_handles(keep_file_path=False)

    def stop_recording(self):
        """録音を停止し、保存されたファイル情報を返す"""
        if not self.is_recording:
            raise AudioProcessingError("録音中ではありません。")

        elapsed_seconds = self.get_elapsed_seconds()
        self._stop_event.set()

        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        except Exception as exc:
            logger.warning(f"録音ストリーム停止中の警告: {exc}")
        finally:
            self._stream = None

        if self._writer_thread is not None:
            self._writer_done_event.wait(timeout=5)
            self._writer_thread = None

        self.is_recording = False
        self.started_at = None

        if self._writer_error:
            error = self._writer_error
            self._clear_handles()
            raise AudioProcessingError(f"録音データの保存に失敗しました: {error}")

        file_path = self.current_file_path
        if not file_path or not os.path.exists(file_path):
            self._clear_handles()
            raise AudioProcessingError("録音ファイルの保存に失敗しました。")

        file_size = os.path.getsize(file_path)
        if file_size <= 44:
            try:
                os.remove(file_path)
            except OSError:
                pass
            self._clear_handles()
            raise AudioProcessingError("録音データが取得できませんでした。マイク設定を確認してください。")

        result = {
            'file_path': file_path,
            'device_name': self.current_device_name,
            'sample_rate': self.current_sample_rate,
            'channels': self.current_channels,
            'input_channels': list(self.current_input_channels),
            'duration_sec': elapsed_seconds,
            'size_bytes': file_size,
        }

        logger.info(
            "録音停止: file=%s, duration=%ss, size=%s bytes",
            file_path,
            elapsed_seconds,
            file_size
        )
        self._clear_handles(keep_file_path=False)
        return result

    def _resolve_input_settings(self):
        """既定入力デバイスの安全な録音設定を解決する"""
        try:
            if self.selected_device_id is None:
                device_info = sd.query_devices(kind='input')
                device_ref = self._get_default_input_device_id()
            else:
                device_ref = self.selected_device_id
                device_info = sd.query_devices(device_ref)
        except Exception as exc:
            if self.selected_device_id is None:
                raise AudioProcessingError(f"既定の入力マイクを取得できません: {exc}") from exc
            raise AudioProcessingError(f"選択した入力デバイスを取得できません: {exc}") from exc

        max_input_channels = int(device_info.get('max_input_channels') or 0)
        if max_input_channels < 1:
            raise AudioProcessingError("利用可能なマイク入力が見つかりません。")

        sample_rate = int(device_info.get('default_samplerate') or self.default_sample_rate)
        selected_input_channels = [
            channel for channel in self._normalize_input_channels(self.selected_input_channels)
            if 1 <= channel <= max_input_channels
        ]
        if not selected_input_channels:
            selected_input_channels = [1]

        stream_channels = max(selected_input_channels)
        output_channels = len(selected_input_channels)

        try:
            sd.check_input_settings(
                device=device_ref,
                samplerate=sample_rate,
                channels=stream_channels,
                dtype='int16'
            )
            return (
                device_info,
                sample_rate,
                stream_channels,
                output_channels,
                selected_input_channels,
                device_ref
            )
        except Exception as exc:
            raise AudioProcessingError(f"入力デバイス設定を初期化できませんでした: {exc}") from exc

    def _audio_callback(self, indata, frames, time_info, status):
        """sounddevice のコールバック。音声バッファを書き込みキューへ渡す"""
        if status:
            logger.warning(f"録音中ステータス通知: {status}")
        if not self._stop_event.is_set():
            processed_bytes, mono_samples = self._prepare_audio_frame(indata)
            self._update_monitor_state(mono_samples)
            self._frame_queue.put(processed_bytes)

    def _monitor_callback(self, indata, frames, time_info, status):
        """待機中モニター用のコールバック"""
        if status:
            logger.warning(f"録音モニター中ステータス通知: {status}")
        _, mono_samples = self._prepare_audio_frame(indata)
        self._update_monitor_state(mono_samples)

    def _update_monitor_state(self, mono_samples):
        """入力サンプルからレベルと表示用データを更新する"""
        if not mono_samples.size:
            return

        rms = float(np.sqrt(np.mean(mono_samples ** 2)))
        peak = float(np.max(np.abs(mono_samples)))
        spectrum = self._compute_spectrum_bins(mono_samples)
        waveform = self._compute_waveform_preview(mono_samples)

        with self._meter_lock:
            self._current_level = (self._current_level * 0.40) + (rms * 0.60)
            self._peak_level = max(peak, self._peak_level * 0.94)
            self._spectrum_bins = [
                min(1.0, (prev * 0.30) + (current * 0.70))
                for prev, current in zip(self._spectrum_bins, spectrum)
            ]
            self._waveform_preview = waveform

    def _prepare_audio_frame(self, indata):
        """生入力へゲインを適用し、保存用 bytes とモノラル波形を返す"""
        samples = np.frombuffer(indata, dtype=np.int16)
        if not samples.size:
            return b'', np.array([], dtype=np.float32)

        stream_channels = max(1, int(self.current_stream_channels or len(self.current_input_channels) or 1))
        usable = (samples.size // stream_channels) * stream_channels
        if usable <= 0:
            return b'', np.array([], dtype=np.float32)

        scaled = samples[:usable].astype(np.float32).reshape(-1, stream_channels)
        if self.input_gain != 1.0:
            scaled *= self.input_gain
        scaled = np.clip(scaled, -32768.0, 32767.0).astype(np.int16)
        selected_indices = [
            min(stream_channels - 1, max(0, channel - 1))
            for channel in (self.current_input_channels or [1])
        ]
        selected = scaled[:, selected_indices]
        if selected.ndim == 1:
            selected = selected[:, np.newaxis]

        mono = selected.astype(np.float32).mean(axis=1)
        mono = np.clip(mono / 32768.0, -1.0, 1.0)
        return selected.astype(np.int16).tobytes(), mono

    def _normalize_input_channels(self, input_channels):
        """入力チャンネル設定を正規化する"""
        if input_channels in (None, '', []):
            return [1]

        if isinstance(input_channels, int):
            candidates = [input_channels]
        elif isinstance(input_channels, str):
            candidates = []
            for part in input_channels.replace('-', ',').split(','):
                part = part.strip()
                if not part:
                    continue
                try:
                    candidates.append(int(part))
                except ValueError:
                    continue
        else:
            candidates = []
            for value in input_channels:
                try:
                    candidates.append(int(value))
                except (TypeError, ValueError):
                    continue

        normalized = []
        for candidate in candidates:
            if candidate >= 1 and candidate not in normalized:
                normalized.append(candidate)

        return normalized or [1]

    def _format_input_channel_label(self, input_channels):
        """入力チャンネル表示用ラベルを返す"""
        normalized = self._normalize_input_channels(input_channels)
        if len(normalized) == 1:
            return f"入力 CH {normalized[0]}"
        if len(normalized) == 2 and normalized[1] == normalized[0] + 1:
            return f"入力 CH {normalized[0]}-{normalized[1]}"
        return "入力 CH " + ",".join(str(channel) for channel in normalized)

    def _get_default_input_device_id(self):
        """既定入力デバイスの ID を返す"""
        try:
            default_device = sd.default.device
        except Exception:
            return None

        if isinstance(default_device, (list, tuple)) and len(default_device) >= 1:
            try:
                input_device_id = int(default_device[0])
            except (TypeError, ValueError):
                return None
            return input_device_id if input_device_id >= 0 else None

        return None

    def _compute_spectrum_bins(self, mono_samples):
        """FFT を使って表示用の周波数帯レベルを計算する"""
        if mono_samples.size < 64:
            return [0.0] * len(self._spectrum_bins)

        window = np.hanning(mono_samples.size).astype(np.float32)
        spectrum = np.fft.rfft(mono_samples * window)
        magnitudes = np.abs(spectrum) / max(1, mono_samples.size)
        if magnitudes.size < 2:
            return [0.0] * len(self._spectrum_bins)

        sample_rate = max(1, int(self.current_sample_rate or self.default_sample_rate))
        freqs = np.fft.rfftfreq(mono_samples.size, d=1.0 / sample_rate)
        low_cut = 60.0
        high_cut = min(float(sample_rate) / 2.0, 6000.0)
        valid = (freqs >= low_cut) & (freqs <= high_cut)
        if not np.any(valid):
            return [0.0] * len(self._spectrum_bins)

        freqs = freqs[valid]
        magnitudes = magnitudes[valid]
        if freqs.size < 2:
            return [0.0] * len(self._spectrum_bins)

        edges = np.geomspace(low_cut, max(low_cut + 1.0, high_cut), len(self._spectrum_bins) + 1)
        raw_bins = []
        for index in range(len(self._spectrum_bins)):
            if index == len(self._spectrum_bins) - 1:
                mask = (freqs >= edges[index]) & (freqs <= edges[index + 1])
            else:
                mask = (freqs >= edges[index]) & (freqs < edges[index + 1])

            if not np.any(mask):
                raw_bins.append(0.0)
                continue

            band = magnitudes[mask]
            band_power = float(np.sqrt(np.mean(band ** 2)))
            raw_bins.append(band_power)

        raw = np.array(raw_bins, dtype=np.float32)
        if not raw.size or float(raw.max()) <= 0.0:
            return [0.0] * len(self._spectrum_bins)

        # 静かな入力は持ち上げすぎず、ピークとRMSで見た目を安定化する。
        overall_gain = min(1.0, (float(np.max(np.abs(mono_samples))) * 1.8) + (float(np.sqrt(np.mean(mono_samples ** 2))) * 6.5))
        normalized = np.log1p(raw * 140.0) / np.log1p(140.0)
        normalized = np.clip(normalized * overall_gain * 1.25, 0.0, 1.0)
        return normalized.tolist()

    def _compute_waveform_preview(self, mono_samples):
        """表示用の波形プレビューを固定長で返す"""
        point_count = len(self._waveform_preview)
        if mono_samples.size == 0:
            return [0.0] * point_count

        if mono_samples.size >= point_count:
            indices = np.linspace(0, mono_samples.size - 1, num=point_count, dtype=np.int32)
            preview = mono_samples[indices]
        else:
            preview = np.pad(mono_samples, (0, point_count - mono_samples.size), mode='constant')

        preview = np.clip(preview * 2.2, -1.0, 1.0)
        return preview.astype(np.float32).tolist()

    def _writer_loop(self):
        """録音データをファイルへ順次書き出す"""
        try:
            while not self._stop_event.is_set() or not self._frame_queue.empty():
                try:
                    chunk = self._frame_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                self._wave_handle.writeframes(chunk)
        except Exception as exc:
            logger.error(f"録音書き込み中にエラー: {exc}", exc_info=True)
            self._writer_error = exc
        finally:
            if self._wave_handle is not None:
                try:
                    self._wave_handle.close()
                except Exception:
                    pass
                self._wave_handle = None
            self._writer_done_event.set()

    def _abort_recording_setup(self):
        """録音開始途中の失敗時に後始末する"""
        self._stop_event.set()
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._writer_thread is not None:
            self._writer_done_event.wait(timeout=2)
            self._writer_thread = None
        file_path = self.current_file_path
        self._clear_handles(keep_file_path=False)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    def _reset_runtime_state(self):
        """録音開始前に内部状態を初期化する"""
        self._frame_queue = queue.Queue()
        self._stop_event.clear()
        self._writer_done_event.clear()
        self._writer_error = None
        self.started_at = None
        self._reset_meter_state()

    def _reset_meter_state(self):
        """モニター表示用の内部状態を初期化する"""
        with self._meter_lock:
            self._current_level = 0.0
            self._peak_level = 0.0
            self._spectrum_bins = [0.0] * len(self._spectrum_bins)
            self._waveform_preview = [0.0] * len(self._waveform_preview)

    def _clear_handles(self, keep_file_path=True):
        """停止後に参照をクリアする"""
        self._stream = None
        self._wave_handle = None
        self._writer_thread = None
        self._writer_error = None
        self._reset_meter_state()
        if not keep_file_path:
            self.current_file_path = None
        self.current_device_name = None
        self.current_sample_rate = self.default_sample_rate
        self.current_channels = self.preferred_channels
        self.current_stream_channels = self.preferred_channels
        self.current_input_channels = [1]

    def _build_output_path(self, output_dir):
        """録音ファイルの保存パスを作成する"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = os.path.join(output_dir, f"mic_recording_{timestamp}.wav")
        if not os.path.exists(candidate):
            return candidate

        counter = 2
        while True:
            candidate = os.path.join(output_dir, f"mic_recording_{timestamp}_{counter}.wav")
            if not os.path.exists(candidate):
                return candidate
            counter += 1
