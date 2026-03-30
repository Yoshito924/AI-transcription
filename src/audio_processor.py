#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import shutil
import subprocess
import tempfile

import numpy as np

from .constants import (
    MAX_AUDIO_SIZE_MB, 
    DEFAULT_AUDIO_BITRATE, 
    DEFAULT_SAMPLE_RATE, 
    DEFAULT_CHANNELS,
    DEFAULT_SILENCE_TRIM_MODE,
    DEFAULT_SILENCE_TRIM_MIN_SILENCE_SEC,
    DEFAULT_SILENCE_TRIM_THRESHOLD_DB,
    MIN_BITRATE,
    MAX_BITRATE,
    MAX_COMPRESSION_ATTEMPTS,
    OVERLAP_SECONDS,
    SEGMENT_DURATION_SEC,
    SILENCE_TRIM_MIN_SILENCE_SEC,
    SILENCE_TRIM_KEEP_SILENCE_SEC,
    SILENCE_TRIM_THRESHOLD_DB
)
from .exceptions import AudioProcessingError
from .utils import format_duration, get_file_size_mb
from .logger import logger

class AudioProcessor:
    """音声ファイルの処理を行うクラス"""
    
    def __init__(self, max_audio_size_mb=MAX_AUDIO_SIZE_MB):
        self.max_audio_size_mb = max_audio_size_mb
    
    def get_audio_duration(self, file_path):
        """FFmpegを使用して音声ファイルの長さを秒単位で取得"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ]
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30
            )

            if result.returncode != 0:
                logger.error("音声長さの取得に失敗しました")
                return None

            duration = float(result.stdout.decode('utf-8').strip())
            return duration
        except subprocess.TimeoutExpired:
            logger.error(f"音声長さの取得がタイムアウトしました: {file_path}")
            return None
        except Exception as e:
            logger.error(f"音声長さの取得中に例外が発生: {file_path}", exc_info=True)
            return None

    def extract_waveform_data(self, file_path, target_samples=4000):
        """音声ファイルから波形表示用のサンプルデータを抽出する

        FFmpegでモノラル・低サンプルレートのPCMに変換し、
        numpyで目標サンプル数にダウンサンプリングする。
        動画ファイルの場合はNVDEC（GPU）デコードを試行する。

        Args:
            file_path: 入力音声ファイルのパス
            target_samples: 表示用に間引くサンプル数（デフォルト4000）

        Returns:
            tuple: (samples_array, duration_sec) or (None, None)
        """
        if not os.path.exists(file_path):
            return None, None

        duration = self.get_audio_duration(file_path)
        if not duration or duration <= 0:
            return None, None

        # 必要最小限のサンプルレートを計算（ダウンサンプリングの余裕を2倍に）
        target_sr = max(1000, min(8000, int(target_samples * 2 / duration)))

        # 動画ファイルかどうかを拡張子で判定
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        video_exts = {'mp4', 'm4v', 'mov', 'avi', 'mkv', 'webm', 'wmv',
                      'mpeg', 'mpg', '3gp', '3g2', 'ts', 'mts', 'm2ts', 'flv'}
        is_video = ext in video_exts

        # 長い音声（5分以上）はチャンク分割で高速化
        if duration > 300:
            fast_result = self._extract_waveform_chunked(
                file_path, duration, target_samples, is_video
            )
            if fast_result[0] is not None:
                return fast_result

        try:
            result = None

            # 動画ファイルの場合、NVDECでGPUデコードを試行
            if is_video:
                cmd_gpu = [
                    'ffmpeg', '-nostdin',
                    '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda',
                    '-i', file_path,
                    '-vn',
                    '-ac', '1',
                    '-ar', str(target_sr),
                    '-f', 's16le',
                    '-acodec', 'pcm_s16le',
                    'pipe:1'
                ]
                timeout = max(30, int(duration * 0.5))
                result = subprocess.run(
                    cmd_gpu, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=timeout
                )
                if result.returncode != 0:
                    result = None

            # CPU デコード（音声ファイル or GPUフォールバック）
            if result is None:
                cmd = [
                    'ffmpeg', '-nostdin',
                    '-i', file_path,
                    '-vn',
                    '-ac', '1',
                    '-ar', str(target_sr),
                    '-f', 's16le',
                    '-acodec', 'pcm_s16le',
                    'pipe:1'
                ]
                timeout = max(30, int(duration * 0.5))
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=timeout
                )

            if result.returncode != 0:
                logger.error("波形データの抽出に失敗しました")
                return None, None

            # PCMデータをnumpy配列に変換
            raw = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32)
            if len(raw) == 0:
                return None, None

            # -1.0〜1.0に正規化
            max_val = np.max(np.abs(raw))
            if max_val > 0:
                raw = raw / max_val

            # target_samples にダウンサンプリング（ピーク保持）
            if len(raw) > target_samples:
                chunk_size = len(raw) // target_samples
                trimmed = raw[:chunk_size * target_samples]
                chunks = trimmed.reshape(target_samples, chunk_size)
                max_idx = np.argmax(np.abs(chunks), axis=1)
                samples = chunks[np.arange(target_samples), max_idx]
            else:
                samples = raw

            return samples, duration

        except subprocess.TimeoutExpired:
            logger.error(f"波形データ抽出がタイムアウトしました: {file_path}")
            return None, None
        except Exception as e:
            logger.error(f"波形データ抽出中にエラー: {e}", exc_info=True)
            return None, None

    def _extract_waveform_chunked(self, file_path, duration, target_samples, is_video):
        """長い音声を等間隔にサンプリングして高速に波形データを生成する

        全体をデコードする代わりに、等間隔のポイントから短い断片だけを
        デコードすることで、長い音声でも高速に波形を取得する。
        """
        num_chunks = target_samples
        chunk_duration = 0.05  # 各チャンクは50ms
        interval = duration / num_chunks
        all_peaks = []

        # 並列度を上げるためバッチ処理（1回のFFmpeg呼び出しで複数チャンクを取得は困難なので、
        # 代わりにサンプリング数を減らして1回のFFmpegで済ませる）
        # 戦略: 超低サンプルレート（target_samples / duration Hz相当）で全体を1回デコード
        minimal_sr = max(100, int(target_samples / duration))

        try:
            hwaccel_args = []
            if is_video:
                hwaccel_args = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']

            cmd = [
                'ffmpeg', '-nostdin',
                *hwaccel_args,
                '-i', file_path,
                '-vn',
                '-ac', '1',
                '-ar', str(minimal_sr),
                '-f', 's16le',
                '-acodec', 'pcm_s16le',
                'pipe:1'
            ]
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30
            )

            # GPUデコード失敗時はCPUでリトライ
            if result.returncode != 0 and hwaccel_args:
                cmd = [
                    'ffmpeg', '-nostdin',
                    '-i', file_path,
                    '-vn',
                    '-ac', '1',
                    '-ar', str(minimal_sr),
                    '-f', 's16le',
                    '-acodec', 'pcm_s16le',
                    'pipe:1'
                ]
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=30
                )

            if result.returncode != 0:
                return None, None

            raw = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32)
            if len(raw) == 0:
                return None, None

            max_val = np.max(np.abs(raw))
            if max_val > 0:
                raw = raw / max_val

            if len(raw) > target_samples:
                chunk_size = len(raw) // target_samples
                trimmed = raw[:chunk_size * target_samples]
                chunks = trimmed.reshape(target_samples, chunk_size)
                max_idx = np.argmax(np.abs(chunks), axis=1)
                samples = chunks[np.arange(target_samples), max_idx]
            else:
                samples = raw

            return samples, duration

        except Exception as e:
            logger.debug(f"チャンク波形抽出に失敗、通常方式にフォールバック: {e}")
            return None, None

    def normalize_silence_trim_settings(self, silence_settings=None):
        """無音カット設定を正規化する"""
        settings = {
            'mode': DEFAULT_SILENCE_TRIM_MODE,
            'threshold_db': float(DEFAULT_SILENCE_TRIM_THRESHOLD_DB),
            'min_silence_sec': float(DEFAULT_SILENCE_TRIM_MIN_SILENCE_SEC),
            'keep_silence_sec': float(SILENCE_TRIM_KEEP_SILENCE_SEC),
        }

        if isinstance(silence_settings, dict):
            mode = silence_settings.get('mode', settings['mode'])
            if mode in ('auto', 'manual'):
                settings['mode'] = mode

            for key in ('threshold_db', 'min_silence_sec', 'keep_silence_sec'):
                value = silence_settings.get(key, settings[key])
                try:
                    settings[key] = float(value)
                except (TypeError, ValueError):
                    pass

        settings['threshold_db'] = max(-80.0, min(-5.0, settings['threshold_db']))
        settings['min_silence_sec'] = max(0.2, min(10.0, settings['min_silence_sec']))
        settings['keep_silence_sec'] = max(0.0, min(5.0, settings['keep_silence_sec']))
        return settings

    @staticmethod
    def _amplitude_to_db(amplitude):
        """線形振幅を dBFS に変換する"""
        return 20.0 * np.log10(max(float(amplitude), 1e-6))

    def estimate_auto_silence_threshold_db(self, file_path, sample_rate=16000, window_sec=0.05):
        """音量分布から無音判定しきい値を自動推定する"""
        if not os.path.exists(file_path):
            return float(DEFAULT_SILENCE_TRIM_THRESHOLD_DB)

        duration = self.get_audio_duration(file_path)
        if duration is None or duration <= 0:
            return float(DEFAULT_SILENCE_TRIM_THRESHOLD_DB)

        window_samples = max(256, int(sample_rate * window_sec))
        read_bytes = window_samples * 2 * 24
        levels = []
        process = None
        leftover = np.array([], dtype=np.int16)

        try:
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            process = subprocess.Popen(
                [
                    'ffmpeg',
                    '-nostdin',
                    '-loglevel', 'error',
                    '-i', file_path,
                    '-vn',
                    '-ac', '1',
                    '-ar', str(sample_rate),
                    '-f', 's16le',
                    '-acodec', 'pcm_s16le',
                    'pipe:1'
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags
            )

            while True:
                chunk = process.stdout.read(read_bytes) if process.stdout else b''
                if not chunk:
                    break

                data = np.frombuffer(chunk, dtype=np.int16)
                if leftover.size:
                    data = np.concatenate((leftover, data))

                usable = (data.size // window_samples) * window_samples
                if usable > 0:
                    windows = data[:usable].astype(np.float32).reshape(-1, window_samples) / 32768.0
                    rms = np.sqrt(np.mean(windows * windows, axis=1))
                    levels.extend(rms.tolist())

                leftover = data[usable:]

            if process.poll() is None:
                process.wait(timeout=max(60, int(duration * 1.5)))

            if process.returncode not in (0, None):
                raise AudioProcessingError("音量分布の解析に失敗しました")
        except Exception as exc:
            logger.warning(f"自動無音しきい値の推定に失敗: {exc}")
            return float(DEFAULT_SILENCE_TRIM_THRESHOLD_DB)
        finally:
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

        positive_levels = np.array([level for level in levels if level > 1e-6], dtype=np.float32)
        if positive_levels.size < 12:
            return float(DEFAULT_SILENCE_TRIM_THRESHOLD_DB)

        noise_db = self._amplitude_to_db(np.percentile(positive_levels, 20))
        speech_db = self._amplitude_to_db(np.percentile(positive_levels, 85))

        if speech_db <= noise_db + 3.0:
            threshold_db = max(-42.0, min(-28.0, speech_db - 6.0))
        else:
            threshold_db = noise_db + ((speech_db - noise_db) * 0.38)
            threshold_db = min(threshold_db, speech_db - 7.0)
            threshold_db = max(-48.0, min(-26.0, threshold_db))

        return round(float(threshold_db), 1)

    def resolve_silence_parameters(self, file_path, silence_settings=None, precomputed_auto_threshold_db=None):
        """自動/手動設定から実際に使う無音判定パラメータを解決する"""
        settings = self.normalize_silence_trim_settings(silence_settings)
        resolved_threshold_db = settings['threshold_db']

        if settings['mode'] == 'auto':
            try:
                resolved_threshold_db = float(precomputed_auto_threshold_db)
            except (TypeError, ValueError):
                resolved_threshold_db = self.estimate_auto_silence_threshold_db(file_path)

        resolved_threshold_db = round(float(resolved_threshold_db), 1)
        resolved = dict(settings)
        resolved['resolved_threshold_db'] = resolved_threshold_db
        resolved['mode_label'] = '自動' if settings['mode'] == 'auto' else '手動'
        return resolved

    def build_silence_cut_preview(self, silence_regions, silence_settings=None):
        """無音区間から短縮候補のプレビュー領域を作る"""
        resolved_settings = self.normalize_silence_trim_settings(silence_settings)
        keep_silence_sec = resolved_settings['keep_silence_sec']
        cut_regions = []
        total_reduction_sec = 0.0

        for start_sec, end_sec in silence_regions or []:
            duration_sec = max(0.0, float(end_sec) - float(start_sec))
            reducible_sec = max(0.0, duration_sec - keep_silence_sec)
            if reducible_sec <= 0.0:
                continue

            cut_start = min(float(end_sec), float(start_sec) + keep_silence_sec)
            cut_end = float(end_sec)
            if cut_end <= cut_start:
                continue

            cut_regions.append((cut_start, cut_end))
            total_reduction_sec += reducible_sec

        return cut_regions, total_reduction_sec

    def detect_silence_regions(self, file_path,
                               min_silence_sec=SILENCE_TRIM_MIN_SILENCE_SEC,
                               threshold_db=SILENCE_TRIM_THRESHOLD_DB,
                               silence_settings=None):
        """FFmpeg silencedetect で無音区間の開始・終了タイムスタンプを取得する

        Returns:
            list of (start_sec, end_sec) — 無音区間のリスト
        """
        if not os.path.exists(file_path):
            return []

        duration = self.get_audio_duration(file_path)
        if not duration or duration <= 0:
            return []

        normalized_settings = self.normalize_silence_trim_settings(silence_settings)
        if silence_settings is not None:
            min_silence_sec = normalized_settings['min_silence_sec']
            if normalized_settings['mode'] == 'auto' and 'resolved_threshold_db' not in normalized_settings:
                normalized_settings = self.resolve_silence_parameters(
                    file_path,
                    silence_settings=normalized_settings
                )
            threshold_db = normalized_settings.get('resolved_threshold_db', normalized_settings['threshold_db'])

        threshold_text = f"{threshold_db}dB" if isinstance(threshold_db, (int, float)) else str(threshold_db)
        af = f"silencedetect=noise={threshold_text}:d={min_silence_sec}"

        try:
            cmd = [
                'ffmpeg', '-nostdin',
                '-i', file_path,
                '-af', af,
                '-f', 'null', '-'
            ]
            timeout = max(60, int(duration * 1.5))
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout
            )
            stderr_text = result.stderr.decode('utf-8', errors='replace')

            # silence_start / silence_end をパース
            starts = [float(m.group(1)) for m in re.finditer(r'silence_start:\s*([\d.]+)', stderr_text)]
            ends = [float(m.group(1)) for m in re.finditer(r'silence_end:\s*([\d.]+)', stderr_text)]

            regions = []
            for i, s in enumerate(starts):
                e = ends[i] if i < len(ends) else duration
                regions.append((s, e))

            return regions

        except Exception as e:
            logger.error(f"無音検出中にエラー: {e}", exc_info=True)
            return []

    def _build_silence_reduction_filter(self,
                                        min_silence_sec=SILENCE_TRIM_MIN_SILENCE_SEC,
                                        keep_silence_sec=SILENCE_TRIM_KEEP_SILENCE_SEC,
                                        threshold_db=SILENCE_TRIM_THRESHOLD_DB):
        """ハムノイズ・環境音のみの長い区間を圧縮するFFmpegフィルタを構築"""
        threshold_text = f"{threshold_db}dB" if isinstance(threshold_db, (int, float)) else str(threshold_db)
        return (
            "silenceremove="
            f"start_periods=1:"
            f"start_duration={min_silence_sec}:"
            f"start_threshold={threshold_text}:"
            f"start_silence={keep_silence_sec}:"
            f"stop_periods=-1:"
            f"stop_duration={min_silence_sec}:"
            f"stop_threshold={threshold_text}:"
            f"stop_silence={keep_silence_sec}:"
            "detection=rms"
        )

    def reduce_long_silence(self, input_file_path, callback=None,
                            min_silence_sec=SILENCE_TRIM_MIN_SILENCE_SEC,
                            keep_silence_sec=SILENCE_TRIM_KEEP_SILENCE_SEC,
                            threshold_db=SILENCE_TRIM_THRESHOLD_DB,
                            silence_settings=None):
        """長い近似無音区間を圧縮した音声ファイルを生成する"""
        def update_status(message):
            logger.info(message)
            if callback:
                callback(message)

        if not os.path.exists(input_file_path):
            raise AudioProcessingError(f"ファイル {input_file_path} が見つかりません")

        duration = self.get_audio_duration(input_file_path)
        if duration is None or duration <= 0:
            raise AudioProcessingError("音声ファイルの長さを取得できませんでした")

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            output_path = temp_file.name

        try:
            if silence_settings is None:
                normalized_settings = self.normalize_silence_trim_settings({
                    'mode': 'manual',
                    'min_silence_sec': min_silence_sec,
                    'keep_silence_sec': keep_silence_sec,
                    'threshold_db': threshold_db,
                })
            else:
                normalized_settings = self.normalize_silence_trim_settings(silence_settings)
            resolved_settings = self.resolve_silence_parameters(
                input_file_path,
                silence_settings=normalized_settings
            )
            timeout = max(120, int(duration * 2))
            filter_text = self._build_silence_reduction_filter(
                min_silence_sec=resolved_settings['min_silence_sec'],
                keep_silence_sec=resolved_settings['keep_silence_sec'],
                threshold_db=resolved_settings['resolved_threshold_db']
            )
            update_status(
                "長い無音を圧縮中... "
                f"({resolved_settings['mode_label']} {resolved_settings['resolved_threshold_db']:.1f}dB / "
                f"{resolved_settings['min_silence_sec']:.1f}秒以上)"
            )

            command = [
                'ffmpeg',
                '-nostdin',
                '-i', input_file_path,
                '-y',
                '-af', filter_text,
                '-c:a', 'libmp3lame',
                '-b:a', DEFAULT_AUDIO_BITRATE,
                output_path
            ]

            process = subprocess.run(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=timeout
            )

            if process.returncode != 0:
                error_msg = process.stderr.decode('utf-8', errors='replace')
                if len(error_msg) > 500:
                    error_msg = "...\n" + error_msg[-500:]
                raise AudioProcessingError(f"無音圧縮エラー (returncode={process.returncode}): {error_msg}")

            reduced_duration = self.get_audio_duration(output_path)
            if reduced_duration is None or reduced_duration <= 0:
                raise AudioProcessingError("無音圧縮後の音声長を取得できませんでした")

            return output_path, duration, reduced_duration

        except Exception:
            try:
                os.unlink(output_path)
            except OSError:
                pass
            raise
    
    def split_audio(self, input_file_path, segment_duration_sec=SEGMENT_DURATION_SEC, callback=None, overlap_sec=OVERLAP_SECONDS):
        """音声ファイルを指定された時間（デフォルト10分）ごとに分割する
        
        Args:
            input_file_path: 入力音声ファイルのパス
            segment_duration_sec: 各セグメントの基本長さ（秒）
            callback: 状態更新用コールバック関数
            overlap_sec: セグメント間のオーバーラップ時間（秒）
        """
        def update_status(message):
            logger.info(message)
            if callback:
                callback(message)

        # 入力ファイルが存在するか確認
        if not os.path.exists(input_file_path):
            update_status(f"エラー: ファイル {input_file_path} が見つかりません")
            return None

        # 音声の長さを取得
        audio_duration_sec = self.get_audio_duration(input_file_path)
        if audio_duration_sec is None or audio_duration_sec <= 0:
            raise AudioProcessingError("音声ファイルの長さを取得できませんでした")
        
        # 分割数を計算（切り上げ）
        num_segments = int((audio_duration_sec + segment_duration_sec - 1) // segment_duration_sec)
        
        if num_segments <= 1:
            update_status("ファイルが短いため分割は不要です")
            return [input_file_path]
        
        update_status(f"音声ファイルを {num_segments} 個のセグメントに分割します（各 {segment_duration_sec // 60} 分、オーバーラップ {overlap_sec} 秒）")
        
        # 分割ファイルのリスト
        segment_files = []
        
        try:
            # 一時ディレクトリを作成
            with tempfile.TemporaryDirectory() as temp_dir:
                # 各セグメントを作成
                for i in range(num_segments):
                    # セグメントの開始時間と長さを計算（オーバーラップを考慮）
                    if i == 0:
                        # 最初のセグメント
                        start_time = 0
                        segment_length = segment_duration_sec + overlap_sec
                        # 音声の長さを超えないように調整
                        if segment_length > audio_duration_sec:
                            segment_length = audio_duration_sec
                    else:
                        # 2番目以降のセグメント
                        start_time = i * segment_duration_sec - overlap_sec
                        
                        # 最後のセグメントの場合、残りの時間すべてを使用
                        if i == num_segments - 1:
                            segment_length = audio_duration_sec - start_time
                        else:
                            segment_length = segment_duration_sec + (overlap_sec * 2)
                            # 音声の長さを超えないように調整
                            if start_time + segment_length > audio_duration_sec:
                                segment_length = audio_duration_sec - start_time
                    
                    # 出力ファイル名
                    output_path = os.path.join(temp_dir, f"segment_{i:03d}.mp3")
                    segment_files.append(output_path)
                    
                    # セグメント長に基づくタイムアウト（最低60秒、セグメント長の3倍）
                    segment_timeout = max(60, int(segment_length * 3))

                    # FFmpegコマンドを構築
                    command = [
                        'ffmpeg',
                        '-y',  # 既存ファイルを上書き
                        '-nostdin',
                        '-i', input_file_path,
                        '-ss', str(start_time),  # 開始時間
                        '-t', str(segment_length),  # セグメント長さ
                        '-c:a', 'libmp3lame',  # MP3エンコーダを使用
                        '-b:a', '128k',  # ビットレート
                        output_path
                    ]

                    update_status(f"セグメント {i+1}/{num_segments} を作成中... (開始: {format_duration(start_time)}, 長さ: {format_duration(segment_length)})")

                    # コマンドを実行
                    try:
                        process = subprocess.run(
                            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            timeout=segment_timeout
                        )
                    except subprocess.TimeoutExpired:
                        update_status(f"エラー: セグメント {i+1} の作成がタイムアウトしました（{segment_timeout}秒）")
                        return None

                    if process.returncode != 0:
                        error_msg = process.stderr.decode('utf-8', errors='replace')
                        if len(error_msg) > 500:
                            error_msg = "...\n" + error_msg[-500:]
                        update_status(f"エラー: セグメント {i+1} の作成に失敗しました: {error_msg}")
                        return None
                
                # 分割ファイルを一時ディレクトリから永続的な場所にコピー
                permanent_segments = []
                for i, segment_file in enumerate(segment_files):
                    if os.path.exists(segment_file):
                        try:
                            # 新しい一時ファイルを作成
                            with tempfile.NamedTemporaryFile(suffix=f'_segment_{i:03d}.mp3', delete=False) as temp_file:
                                perm_path = temp_file.name

                            # perm_pathが正しく作成されたことを確認
                            if not perm_path:
                                update_status(f"エラー: セグメント {i+1} の一時ファイル作成に失敗しました")
                                continue

                            # ファイルをコピー（shutil.copyfileでメモリ効率化）
                            shutil.copyfile(segment_file, perm_path)
                            if os.path.getsize(perm_path) > 0:
                                permanent_segments.append(perm_path)
                            else:
                                update_status(f"警告: セグメント {i+1} のデータが空です")
                        except Exception as e:
                            update_status(f"エラー: セグメント {i+1} のコピー中に例外が発生: {str(e)}")
                
                update_status(f"音声ファイルを {len(permanent_segments)} 個のセグメントに分割しました")
                return permanent_segments
                
        except Exception as e:
            update_status(f"エラー: 音声分割中に例外が発生しました: {str(e)}")
            return None
    
    def compress_audio(self, input_file_path, target_size_mb=MAX_AUDIO_SIZE_MB, callback=None, max_attempts=MAX_COMPRESSION_ATTEMPTS):
        """FFmpegを使用して音声ファイルを圧縮する。目標サイズに達するまで繰り返し圧縮を試みる"""
        def update_status(message):
            logger.info(message)
            if callback:
                callback(message)

        # 入力ファイルが存在するか確認
        if not os.path.exists(input_file_path):
            update_status(f"エラー: ファイル {input_file_path} が見つかりません")
            return None

        # 入力ファイルサイズを取得
        input_size_mb = get_file_size_mb(input_file_path)
        
        # 音声の長さを取得
        audio_duration_sec = self.get_audio_duration(input_file_path)
        if audio_duration_sec is None or audio_duration_sec <= 0:
            update_status("エラー: 音声ファイルの長さを取得できませんでした")
            return None
        
        # 最低品質を確保
        min_bitrate = MIN_BITRATE  # 最低32kbpsまで許容（圧縮を繰り返す場合）
        max_bitrate = MAX_BITRATE  # 最大256kbpsに制限
        
        # 現在の入力ファイル（初回は元のファイル、以降は前回の圧縮結果）
        current_input = input_file_path
        current_size_mb = input_size_mb
        
        # 一時ファイルのリスト（後で削除するため）
        temp_files = []
        
        # 圧縮を試行
        for attempt in range(1, max_attempts + 1):
            # 目標サイズに達していれば終了
            if current_size_mb <= target_size_mb:
                update_status(f"目標サイズ（{target_size_mb:.2f}MB）に達しました。圧縮完了。")
                
                # 最後に使用した一時ファイル以外を削除
                for temp_file in temp_files[:-1]:
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass

                return current_input

            # 一時ファイルを作成
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                output_path = temp_file.name
                temp_files.append(output_path)
            
            # 残りの試行回数に基づいてビットレートを調整
            # 最終試行に近づくほどビットレートを積極的に下げる
            remaining_attempts = max_attempts - attempt + 1
            
            # ビットレート計算: (ターゲットサイズMB * 8192) / 音声長さ秒
            # 残り試行回数が少ないほど、より小さなビットレートを使用
            target_bitrate_kbps = int((target_size_mb * 0.9 * 8192) / audio_duration_sec)
            
            # 残り試行回数に応じてビットレートを調整（徐々に下げる）
            adjusted_bitrate = target_bitrate_kbps * (0.9 ** (attempt - 1))
            
            # ビットレートの範囲を制限
            bitrate = max(min(int(adjusted_bitrate), max_bitrate), min_bitrate)
            
            update_status(f"音声圧縮 試行 {attempt}/{max_attempts}: 現在サイズ={current_size_mb:.2f}MB → 目標={target_size_mb:.2f}MB (ビットレート={bitrate}kbps)")
            
            # 圧縮タイムアウト（最低120秒、音声長の2倍）
            compress_timeout = max(120, int(audio_duration_sec * 2))

            # FFmpegコマンドを構築
            try:
                command = [
                    'ffmpeg',
                    '-nostdin',
                    '-i', current_input,
                    '-y',  # 既存ファイルを上書き
                    '-c:a', 'libmp3lame',  # MP3エンコーダを使用
                    '-b:a', f'{bitrate}k',  # 計算したビットレート
                    output_path
                ]

                # コマンドを実行
                process = subprocess.run(
                    command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    timeout=compress_timeout
                )
                
                if process.returncode != 0:
                    update_status(f"エラー: 音声圧縮に失敗しました")
                    # 一時ファイルを削除
                    for temp_file in temp_files:
                        try:
                            os.remove(temp_file)
                        except OSError:
                            pass
                    return None

                # 圧縮結果を確認
                output_size_mb = get_file_size_mb(output_path)
                compression_ratio = ((current_size_mb - output_size_mb) / current_size_mb * 100)
                update_status(f"圧縮結果: 新サイズ={output_size_mb:.2f}MB (圧縮率={compression_ratio:.2f}%)")
                
                # 圧縮が効果的でない場合（サイズがほとんど変わらない）
                if current_size_mb - output_size_mb < 0.1:  # 100KB未満の削減
                    update_status("圧縮効果が小さいため、これ以上の圧縮は行いません。")
                    
                    # 一時ファイルを削除（最後のファイル以外）
                    for temp_file in temp_files[:-1]:
                        try:
                            os.remove(temp_file)
                        except OSError:
                            pass

                    return output_path

                # 次の試行のための準備
                current_input = output_path
                current_size_mb = output_size_mb
                
            except subprocess.TimeoutExpired:
                update_status(f"エラー: 音声圧縮がタイムアウトしました（{compress_timeout}秒）")
                for temp_file in temp_files:
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                return None

            except Exception as e:
                update_status(f"エラー: 音声圧縮中に例外が発生しました: {str(e)}")
                # 一時ファイルを削除
                for temp_file in temp_files:
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                return None

        # 最大試行回数に達した場合
        update_status(f"最大試行回数（{max_attempts}回）に達しました。最終サイズ: {current_size_mb:.2f}MB")
        
        # 一時ファイルを削除（最後のファイル以外）
        for temp_file in temp_files[:-1]:
            try:
                os.remove(temp_file)
            except OSError:
                pass

        return current_input
    
    def convert_audio(self, input_file, output_format='mp3',
                     bitrate=DEFAULT_AUDIO_BITRATE,
                     sample_rate=DEFAULT_SAMPLE_RATE,
                     channels=DEFAULT_CHANNELS,
                     trim_long_silence=False):
        """音声/動画ファイルを指定したフォーマットに変換する"""
        with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as temp_file:
            output_path = temp_file.name

        try:
            # 音声の長さを取得してタイムアウトを計算（最低5分、音声長の2倍）
            duration = self.get_audio_duration(input_file)
            if duration and duration > 0:
                timeout = max(300, int(duration * 2))
            else:
                timeout = 3600  # 長さ不明の場合は1時間

            # FFmpegで変換
            cmd = [
                'ffmpeg', '-y',
                '-nostdin',                    # 標準入力を無効化
                '-i', input_file,
                '-vn',                         # 映像を除去
                '-ar', str(sample_rate),       # サンプルレート
                '-ac', str(channels),          # チャンネル数
                '-b:a', bitrate,               # ビットレート
                output_path
            ]

            if trim_long_silence:
                cmd[cmd.index(output_path):cmd.index(output_path)] = [
                    '-af',
                    self._build_silence_reduction_filter()
                ]

            logger.info(f"音声変換開始: {os.path.basename(input_file)} (タイムアウト: {timeout}秒)")

            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='replace')
                if trim_long_silence:
                    logger.warning(f"無音圧縮付き変換に失敗したため通常変換へフォールバック: {error_msg}")
                    fallback_cmd = [
                        'ffmpeg', '-y',
                        '-nostdin',
                        '-i', input_file,
                        '-vn',
                        '-ar', str(sample_rate),
                        '-ac', str(channels),
                        '-b:a', bitrate,
                        output_path
                    ]
                    result = subprocess.run(
                        fallback_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        timeout=timeout
                    )
                    error_msg = result.stderr.decode('utf-8', errors='replace')

                # エラーメッセージが長い場合は末尾のみ表示
                if result.returncode != 0:
                    if len(error_msg) > 500:
                        error_msg = "...\n" + error_msg[-500:]
                    raise AudioProcessingError(f"音声変換エラー (returncode={result.returncode}): {error_msg}")

            return output_path

        except subprocess.TimeoutExpired:
            try:
                os.unlink(output_path)
            except OSError:
                pass
            raise AudioProcessingError(f"音声変換がタイムアウトしました（{timeout}秒）。ファイルが大きすぎる可能性があります。")

        except AudioProcessingError:
            try:
                os.unlink(output_path)
            except OSError:
                pass
            raise

        except Exception as e:
            # エラー時は一時ファイルを削除
            try:
                os.unlink(output_path)
            except OSError:
                pass
            raise AudioProcessingError(f"音声変換に失敗しました: {str(e)}")
