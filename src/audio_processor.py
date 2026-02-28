#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import tempfile

from .constants import (
    MAX_AUDIO_SIZE_MB, 
    DEFAULT_AUDIO_BITRATE, 
    DEFAULT_SAMPLE_RATE, 
    DEFAULT_CHANNELS,
    MIN_BITRATE,
    MAX_BITRATE,
    MAX_COMPRESSION_ATTEMPTS,
    OVERLAP_SECONDS,
    SEGMENT_DURATION_SEC
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
                     channels=DEFAULT_CHANNELS):
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

            logger.info(f"音声変換開始: {os.path.basename(input_file)} (タイムアウト: {timeout}秒)")

            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='replace')
                # エラーメッセージが長い場合は末尾のみ表示
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
