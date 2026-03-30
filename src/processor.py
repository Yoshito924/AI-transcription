#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import json
import shutil
import datetime
import tempfile
import time
import threading
import google.generativeai as genai

from .constants import (
    DEFAULT_TRIM_LONG_SILENCE,
    MAX_AUDIO_SIZE_MB,
    WHISPER_API_MAX_AUDIO_SIZE_MB,
    MAX_AUDIO_DURATION_SEC,
    SEGMENT_DURATION_SEC,
    SILENCE_TRIM_MIN_REDUCTION_SEC,
    AUDIO_MIME_TYPE,
    OUTPUT_DIR,
    AI_GENERATION_CONFIG,
    SEGMENT_MERGE_CONFIG,
    SAFETY_SETTINGS_TRANSCRIPTION,
    SUMMARY_TITLE_MAX_LENGTH,
    TITLE_GENERATION_MODELS
)
from .exceptions import (
    TranscriptionError, 
    AudioProcessingError, 
    ApiConnectionError, 
    FileProcessingError
)
from .audio_processor import AudioProcessor
from .api_utils import ApiUtils, GENAI_SDK_LOCK
from .whisper_service import WhisperService
from .whisper_api_service import WhisperApiService
from .text_merger import EnhancedTextMerger
from .audio_cache import AudioCacheManager
from .utils import (
    get_timestamp, format_duration, calculate_gemini_cost, format_token_usage,
    get_file_size_mb, get_file_size_kb, format_process_time,
    extract_usage_metadata, process_usage_metadata,
    sanitize_filename
)
from .logger import logger

class FileProcessor:
    """音声/動画ファイルの処理を行うクラス"""
    
    def __init__(self, output_dir, enable_cache=True, max_cache_items=5):
        self.output_dir = output_dir
        self.audio_processor = AudioProcessor()
        self.api_utils = ApiUtils()
        self.whisper_service = None
        self.whisper_init_error = None
        self.whisper_api_service = None  # APIキーが設定されたときに初期化
        self.whisper_api_status_heartbeat_sec = 30
        self.last_transcription_model_name = None
        self.last_engine_used = None
        self.last_warning = None
        self.text_merger = EnhancedTextMerger(
            overlap_threshold=SEGMENT_MERGE_CONFIG['overlap_threshold'],
            min_overlap_words=SEGMENT_MERGE_CONFIG['min_overlap_words'],
            enable_context_analysis=SEGMENT_MERGE_CONFIG['enable_context_analysis']
        )

        # 音声キャッシュマネージャー
        self.enable_cache = enable_cache
        if enable_cache:
            self.cache_manager = AudioCacheManager(max_cache_items=max_cache_items)
            logger.info(f"音声キャッシュ機能: 有効 (最大{max_cache_items}件)")
        else:
            self.cache_manager = None
            logger.info("音声キャッシュ機能: 無効")
    
    def test_api_connection(self, api_key):
        """GeminiAPIの接続テスト"""
        return self.api_utils.test_api_connection(api_key)

    def get_whisper_service(self):
        """Whisperサービスを必要時に初期化して返す"""
        if self.whisper_service is not None:
            return self.whisper_service

        try:
            self.whisper_service = WhisperService()
            self.whisper_init_error = None
            return self.whisper_service
        except AudioProcessingError as e:
            self.whisper_init_error = str(e)
            logger.warning(f"Whisperサービスを初期化できません: {self.whisper_init_error}")
            raise

    def test_whisper_availability(self):
        """Whisper利用可能性を確認する"""
        service = self.get_whisper_service()
        return service.test_whisper_availability()

    def get_whisper_device_info(self):
        """Whisperデバイス情報を返す"""
        service = self.get_whisper_service()
        return service.get_device_info()

    def _run_with_status_heartbeat(self, operation, update_status, base_message):
        """長時間処理中に定期的な生存確認メッセージを出す"""
        interval_sec = getattr(self, 'whisper_api_status_heartbeat_sec', 30)
        if not interval_sec or interval_sec <= 0:
            return operation()

        stop_event = threading.Event()
        started_at = time.monotonic()

        def heartbeat():
            while not stop_event.wait(interval_sec):
                elapsed_sec = int(time.monotonic() - started_at)
                update_status(f"{base_message} {format_duration(elapsed_sec)}経過")

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

        try:
            return operation()
        finally:
            stop_event.set()
            heartbeat_thread.join(timeout=0.1)

    def _build_silence_trim_summary(self, before_sec, after_sec, prefix="長い無音を圧縮しました"):
        """長い無音圧縮の削減量をログ向けに整形する"""
        if before_sec is None or after_sec is None:
            return None

        reduction_sec = max(0.0, before_sec - after_sec)
        reduction_ratio = (reduction_sec / before_sec * 100.0) if before_sec else 0.0
        return (
            f"{prefix}: {format_duration(before_sec)} → {format_duration(after_sec)} "
            f"({format_duration(reduction_sec)}短縮 / {reduction_ratio:.1f}%削減)"
        )

    def _log_cached_silence_trim_summary(self, original_duration_sec, cache_entry, update_status):
        """キャッシュ再利用時にも無音圧縮の削減量を表示する"""
        cached_duration = cache_entry.get('duration')
        if original_duration_sec is None or cached_duration is None:
            return

        reduction_sec = original_duration_sec - cached_duration
        if reduction_sec < SILENCE_TRIM_MIN_REDUCTION_SEC:
            return

        summary = self._build_silence_trim_summary(
            original_duration_sec,
            cached_duration,
            prefix="長い無音圧縮を再利用"
        )
        if summary:
            update_status(summary)

    def _check_response_safety(self, response, segment_num=None):
        """Gemini APIレスポンスの安全性チェック

        Args:
            response: Gemini APIからのレスポンス
            segment_num: セグメント番号（セグメント処理時のみ）

        Raises:
            TranscriptionError: レスポンスに問題がある場合
        """
        try:
            if not hasattr(response, 'candidates') or not response.candidates:
                return

            candidate = response.candidates[0]
            if not hasattr(candidate, 'finish_reason'):
                return

            finish_reason = candidate.finish_reason
            segment_info = f"セグメント {segment_num}: " if segment_num else ""

            # finish_reasonの種類:
            # 0 or FINISH_REASON_STOP: 正常終了
            # 1 or FINISH_REASON_MAX_TOKENS: トークン数上限
            # 2 or FINISH_REASON_SAFETY: 安全性フィルターによるブロック
            # 3 or FINISH_REASON_RECITATION: 引用/転載の検出
            # 4: 著作権保護コンテンツの検出
            # 5 or FINISH_REASON_OTHER: その他の理由

            if finish_reason == 2:
                error_msg = f"{segment_info}安全性フィルター - 音声の内容が安全性基準に抵触する可能性があります"
                solution = (
                    "安全性フィルターは緩和設定済みですが、それでもブロックされました。\n"
                    "以下をお試しください：\n"
                    "1. Whisperエンジンに切り替える（ローカル処理で安全性フィルターなし）\n"
                    "2. 音声ファイルを分割して問題の箇所を特定する\n"
                    "3. 問題のセグメントのみスキップして処理を続行する"
                )
                logger.error(f"{error_msg} - 対処法: {solution}")
                raise TranscriptionError(
                    error_msg,
                    error_code="SAFETY_FILTER",
                    user_message=f"{error_msg}\n💡 対処法: {solution}",
                    solution=solution
                )
            elif finish_reason == 3:
                error_msg = f"{segment_info}応答が既存コンテンツの引用として検出されました。"
                logger.warning(error_msg)
                # 引用検出は警告のみで続行
            elif finish_reason == 4:
                error_msg = f"{segment_info}応答が著作権保護コンテンツとして検出されました"
                solution = "音声に含まれる音楽やBGMを削除するか、別の音声ファイルを使用してください。"
                logger.error(f"{error_msg} - 対処法: {solution}")
                raise TranscriptionError(
                    error_msg,
                    error_code="COPYRIGHT_CONTENT",
                    user_message=f"{error_msg}\n💡 対処法: {solution}",
                    solution=solution
                )
            elif finish_reason not in [0, 1]:
                error_msg = f"{segment_info}異常な終了理由が検出されました (finish_reason={finish_reason})"
                logger.warning(error_msg)

        except TranscriptionError:
            # TranscriptionErrorはそのまま再送出
            raise
        except Exception as e:
            # その他のエラーはログのみ
            logger.debug(f"レスポンス安全性チェック中にエラー: {str(e)}")
    
    def get_output_files(self):
        """出力ディレクトリのファイルリストを取得"""
        files = []
        for file in os.listdir(self.output_dir):
            if file.endswith('.txt'):
                file_path = os.path.join(self.output_dir, file)
                mod_time = os.path.getmtime(file_path)
                mod_date = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
                size = os.path.getsize(file_path)
                size_str = f"{size / 1024:.1f} KB"
                files.append((file, mod_date, size_str, mod_time))
        
        # 日時でソート（新しい順）
        files.sort(key=lambda x: x[3], reverse=True)
        return files
    
    def process_file(self, input_file, process_type, api_key, prompts, status_callback=None,
                    preferred_model=None, engine='gemini', whisper_model='base',
                    save_to_output_dir=True, save_to_source_dir=False,
                    progress_value_callback=None, gemini_api_key=None,
                    time_tracker=None, whisper_api_model=None,
                    gemini_safety_filter_recovery='segment',
                    trim_long_silence=DEFAULT_TRIM_LONG_SILENCE,
                    silence_trim_settings=None,
                    title_generation_engine='auto'):
        """ファイルを処理し、結果を返す"""
        start_time = datetime.datetime.now()
        self.last_transcription_model_name = None
        self.last_engine_used = engine
        self.last_warning = None
        self.last_audio_duration_sec = None
        self.last_processing_sec = None

        def update_status(message):
            logger.info(message)
            if status_callback:
                status_callback(message)

        def update_progress(value):
            if progress_value_callback:
                progress_value_callback(value)

        try:
            # 音声ファイルの準備（キャッシュ対応）
            update_progress(2)
            audio_path, cached_segments, from_cache = self._prepare_audio_file(
                input_file,
                update_status,
                engine=engine,
                trim_long_silence=trim_long_silence,
                silence_trim_settings=silence_trim_settings
            )
            update_progress(10)

            # ETA予測を表示
            if time_tracker and self.last_audio_duration_sec:
                if engine == 'whisper':
                    model_for_eta = whisper_model
                elif engine == 'whisper-api':
                    model_for_eta = whisper_api_model or 'gpt-4o-mini-transcribe'
                else:
                    model_for_eta = preferred_model or 'gemini-2.5-flash'
                estimate = time_tracker.estimate(engine, model_for_eta, self.last_audio_duration_sec)
                eta_msg = time_tracker.format_estimate(estimate)
                if eta_msg:
                    update_status(eta_msg)

            # 文字起こし実行（エンジンに応じて分岐）
            # キャッシュからセグメントを取得した場合は、それを使用
            try:
                if engine == 'whisper':
                    transcription = self._perform_whisper_transcription(
                        audio_path, update_status, whisper_model, cached_segments,
                        progress_callback=update_progress,
                        cleanup_segments=not from_cache
                    )
                elif engine == 'whisper-api':
                    transcription = self._perform_whisper_api_transcription(
                        audio_path, api_key, update_status, cached_segments,
                        progress_callback=update_progress,
                        cleanup_segments=not from_cache,
                        whisper_api_model=whisper_api_model
                    )
                else:  # gemini
                    transcription = self._perform_transcription(
                        audio_path, api_key, update_status, preferred_model, cached_segments,
                        progress_callback=update_progress,
                        cleanup_segments=not from_cache
                    )
            except TranscriptionError as e:
                if engine == 'gemini' and getattr(e, 'error_code', None) == "SAFETY_FILTER":
                    transcription = self._recover_from_gemini_safety_filter(
                        e,
                        audio_path,
                        api_key,
                        update_status,
                        preferred_model=preferred_model,
                        whisper_model=whisper_model,
                        cached_segments=cached_segments,
                        progress_callback=update_progress,
                        cleanup_segments=not from_cache,
                        recovery_mode=gemini_safety_filter_recovery
                    )
                else:
                    raise
            update_progress(85)

            # 追加処理（必要な場合）
            final_text = self._perform_additional_processing(
                transcription, process_type, prompts, api_key, update_status, preferred_model
            )
            update_progress(95)

            # 要約タイトルを生成
            summary_title = None
            if title_generation_engine != 'disabled':
                if title_generation_engine == 'gemini':
                    if gemini_api_key:
                        update_status("要約タイトルを生成中（Gemini）...")
                        summary_title = self.generate_summary_title(final_text, gemini_api_key)
                elif title_generation_engine == 'ollama':
                    update_status("要約タイトルを生成中（Ollama）...")
                    summary_title = self.generate_summary_title_ollama(final_text)
                else:  # auto
                    if gemini_api_key:
                        update_status("要約タイトルを生成中...")
                        summary_title = self.generate_summary_title(final_text, gemini_api_key)
                    if not summary_title:
                        update_status("要約タイトルを生成中（Ollama）...")
                        summary_title = self.generate_summary_title_ollama(final_text)
                if summary_title:
                    update_status(f"タイトル生成完了: {summary_title}")

            # 結果をファイルに保存
            output_path = self._save_result(
                input_file, final_text, process_type, prompts, start_time, update_status,
                save_to_output_dir=save_to_output_dir, save_to_source_dir=save_to_source_dir,
                summary_title=summary_title
            )
            update_progress(100)

            # 全体の処理時間をログに記録
            total_elapsed = (datetime.datetime.now() - start_time).total_seconds()
            audio_dur = self.last_audio_duration_sec or 0
            speed = audio_dur / total_elapsed if total_elapsed > 0 else 0
            logger.info(
                f"処理完了: 全体{total_elapsed:.1f}秒 "
                f"(音声{format_duration(audio_dur)}の{speed:.1f}倍速)"
            )

            return output_path
            
        except (TranscriptionError, AudioProcessingError, ApiConnectionError, FileProcessingError):
            raise
        except Exception as e:
            logger.error(f"処理エラー: {str(e)}", exc_info=True)
            update_status(f"処理エラー: {str(e)}")
            raise FileProcessingError(f"ファイル処理に失敗しました: {str(e)}")

    def _fallback_to_whisper_on_safety(self, exception, audio_path, update_status, whisper_model='turbo',
                                       cached_segments=None, progress_callback=None, cleanup_segments=True):
        """Geminiの安全性ブロック時にWhisperへ自動フォールバックする"""
        root_message = getattr(exception, 'user_message', str(exception))
        fallback_warning = (
            "注意: Gemini が安全性フィルターでブロックされたため、Whisper に自動切り替えしました。\n"
            f"- ブロック内容: {root_message}\n"
            f"- フォールバックモデル: {whisper_model}"
        )
        logger.warning(
            "Gemini安全性ブロックのためWhisperへ自動フォールバック: "
            f"model={whisper_model}, reason={root_message}"
        )
        update_status(fallback_warning)

        # 利用できない場合は元のエラーをそのまま扱いたいため、先に可用性だけ確認する
        self.get_whisper_service()

        self.last_warning = fallback_warning
        self.last_engine_used = 'whisper'
        result = self._perform_whisper_transcription(
            audio_path,
            update_status,
            whisper_model,
            cached_segments,
            progress_callback=progress_callback,
            cleanup_segments=cleanup_segments
        )

        if self.last_warning and self.last_warning != fallback_warning:
            self.last_warning = f"{fallback_warning}\n{self.last_warning}"
        else:
            self.last_warning = fallback_warning

        return result

    def _get_safety_retry_segment_duration(self, audio_path):
        """安全性ブロック時の再試行用セグメント長を返す"""
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path) or self.last_audio_duration_sec
        if not audio_duration_sec or audio_duration_sec <= 0:
            return SEGMENT_DURATION_SEC
        if audio_duration_sec <= SEGMENT_DURATION_SEC:
            return max(60, int(audio_duration_sec / 3))
        return SEGMENT_DURATION_SEC

    def _recover_from_gemini_safety_filter(self, exception, audio_path, api_key, update_status,
                                           preferred_model=None, whisper_model='turbo',
                                           cached_segments=None, progress_callback=None,
                                           cleanup_segments=True, recovery_mode='segment'):
        """Gemini安全性ブロック時に分割再試行し、だめならWhisperへフォールバックする"""
        root_message = getattr(exception, 'user_message', str(exception))
        normalized_recovery_mode = recovery_mode if recovery_mode in ('segment', 'segment-whisper', 'whisper') else 'segment'
        recovery_notice = (
            "注意: Gemini が安全性フィルターでブロックされました。代替経路で処理を継続します。\n"
            f"- ブロック内容: {root_message}"
        )
        logger.warning(f"Gemini安全性ブロックを検出: {root_message}")
        update_status(recovery_notice)

        if normalized_recovery_mode == 'whisper':
            update_status("注意: 設定に従い、セグメント再試行は行わず Whisper に切り替えます。")
            return self._fallback_to_whisper_on_safety(
                exception,
                audio_path,
                update_status,
                whisper_model=whisper_model,
                cached_segments=cached_segments,
                progress_callback=progress_callback,
                cleanup_segments=cleanup_segments
            )

        retry_segments = cached_segments
        retry_cleanup_segments = cleanup_segments

        if retry_segments:
            logger.info(f"安全性ブロック後の再試行にキャッシュ済みセグメントを使用: {len(retry_segments)}個")
        else:
            segment_duration_sec = self._get_safety_retry_segment_duration(audio_path)
            update_status(
                "注意: Gemini の誤ブロックを避けるため、音声を分割して再試行します。\n"
                f"- 分割単位: {format_duration(segment_duration_sec)}"
            )
            retry_segments = self.audio_processor.split_audio(
                audio_path,
                segment_duration_sec=segment_duration_sec,
                callback=update_status
            )
            retry_cleanup_segments = True

        if retry_segments and len(retry_segments) > 1:
            whisper_note = "（ブロック区間はWhisperで補完）" if normalized_recovery_mode == 'segment-whisper' else ""
            segmented_warning = (
                "注意: Gemini が単一ファイルでは安全性フィルターにかかったため、"
                f"セグメント単位で再試行しました。{whisper_note}"
            )
            update_status(f"{segmented_warning}\n- セグメント数: {len(retry_segments)}")

            use_whisper_fallback = (normalized_recovery_mode == 'segment-whisper')
            try:
                result = self._perform_segmented_transcription(
                    audio_path,
                    api_key,
                    update_status,
                    preferred_model,
                    retry_segments,
                    progress_callback=progress_callback,
                    cleanup_segments=retry_cleanup_segments,
                    whisper_fallback_for_blocked=use_whisper_fallback,
                    whisper_model=whisper_model
                )
            except Exception as retry_exception:
                logger.warning(
                    "Gemini安全性ブロック後のセグメント再試行に失敗。Whisperへフォールバック: "
                    f"{type(retry_exception).__name__}: {retry_exception}"
                )
                update_status("注意: Gemini のセグメント再試行でも継続できなかったため、Whisper に切り替えます。")
            else:
                if self.last_warning and self.last_warning != segmented_warning:
                    self.last_warning = f"{segmented_warning}\n{self.last_warning}"
                else:
                    self.last_warning = segmented_warning
                return result
        else:
            logger.info("安全性ブロック後のセグメント再試行をスキップ: 分割結果が1セグメント以下")
            update_status("注意: 問題箇所の切り分けができなかったため、Whisper に切り替えます。")

        return self._fallback_to_whisper_on_safety(
            exception,
            audio_path,
            update_status,
            whisper_model=whisper_model,
            cached_segments=cached_segments,
            progress_callback=progress_callback,
            cleanup_segments=cleanup_segments
        )
    
    def _prepare_audio_file(self, input_file, update_status, engine='gemini',
                            trim_long_silence=DEFAULT_TRIM_LONG_SILENCE,
                            silence_trim_settings=None):
        """音声ファイルの準備（変換・圧縮・分割）

        キャッシュがあれば再利用、なければ処理してキャッシュに保存

        Returns:
            (audio_path, segment_files, from_cache) のタプル
        """
        # 元のファイル情報を取得
        original_size_mb = get_file_size_mb(input_file)
        audio_duration_sec = self.audio_processor.get_audio_duration(input_file)
        duration_str = format_duration(audio_duration_sec) if audio_duration_sec else "不明"

        # 音声長さを記録（ETA算出用）
        self.last_audio_duration_sec = audio_duration_sec

        logger.info(f"音声ファイル準備開始: {os.path.basename(input_file)}, サイズ={original_size_mb:.2f}MB, 長さ={duration_str}")
        update_status(f"処理開始: ファイルサイズ={original_size_mb:.2f}MB, 長さ={duration_str}")

        if silence_trim_settings is None:
            normalized_silence_settings = None
            cache_profile = {
                'preprocess_version': 2,
                'trim_long_silence': bool(trim_long_silence),
            }
        else:
            normalized_silence_settings = self.audio_processor.normalize_silence_trim_settings(
                silence_trim_settings
            )
            cache_profile = {
                'preprocess_version': 3,
                'trim_long_silence': bool(trim_long_silence),
                'silence_trim_mode': (
                    normalized_silence_settings['mode'] if trim_long_silence else 'disabled'
                ),
                'silence_trim_min_silence_sec': (
                    round(normalized_silence_settings['min_silence_sec'], 1) if trim_long_silence else 'n/a'
                ),
                'silence_trim_threshold_db': (
                    round(normalized_silence_settings['threshold_db'], 1)
                    if trim_long_silence and normalized_silence_settings['mode'] == 'manual'
                    else ('auto' if trim_long_silence else 'n/a')
                ),
            }

        # キャッシュをチェック
        if self.enable_cache and self.cache_manager:
            cache_entry = self.cache_manager.get_cache_entry(input_file, cache_profile=cache_profile)
            if cache_entry:
                cache_id = cache_entry['cache_id']
                processed_audio, segments = self.cache_manager.get_cached_files(cache_id)

                if processed_audio:
                    cached_duration = cache_entry.get('duration')
                    if cached_duration:
                        self.last_audio_duration_sec = cached_duration
                    update_status(f"✓ キャッシュから読み込み: {os.path.basename(input_file)}")
                    if trim_long_silence:
                        self._log_cached_silence_trim_summary(audio_duration_sec, cache_entry, update_status)
                    logger.info(f"キャッシュ使用: processed={processed_audio}, segments={len(segments) if segments else 0}")
                    return processed_audio, segments, True

        # キャッシュがない場合は通常処理
        import time as _time
        step_start = _time.time()
        update_status("音声ファイルを変換中...")
        audio_path = self.audio_processor.convert_audio(input_file, trim_long_silence=False)
        convert_elapsed = _time.time() - step_start
        logger.info(f"音声変換完了: {convert_elapsed:.1f}秒")

        processed_duration_sec = self.audio_processor.get_audio_duration(audio_path) or audio_duration_sec

        if trim_long_silence:
            try:
                trimmed_audio_path, pre_trim_duration_sec, trimmed_duration_sec = self.audio_processor.reduce_long_silence(
                    audio_path,
                    callback=update_status,
                    silence_settings=normalized_silence_settings
                )
                reduction_sec = pre_trim_duration_sec - trimmed_duration_sec
                if reduction_sec >= SILENCE_TRIM_MIN_REDUCTION_SEC:
                    update_status(
                        self._build_silence_trim_summary(
                            pre_trim_duration_sec,
                            trimmed_duration_sec
                        )
                    )
                    try:
                        os.unlink(audio_path)
                    except OSError:
                        logger.warning(f"元の変換音声の削除に失敗: {audio_path}")
                    audio_path = trimmed_audio_path
                    processed_duration_sec = trimmed_duration_sec
                else:
                    try:
                        os.unlink(trimmed_audio_path)
                    except OSError:
                        logger.warning(f"無音圧縮の一時ファイル削除に失敗: {trimmed_audio_path}")
                    logger.info(self._build_silence_trim_summary(
                        pre_trim_duration_sec,
                        trimmed_duration_sec,
                        prefix="無音圧縮の効果が小さいため元の音声を使用"
                    ))
            except AudioProcessingError as e:
                logger.warning(f"無音圧縮をスキップ: {str(e)}")
                update_status("注意: 長い無音の圧縮はスキップし、そのまま処理を続行します")

        self.last_audio_duration_sec = processed_duration_sec

        # エンジンごとに、前処理段階で分割が必要かを判定
        file_size_mb = get_file_size_mb(audio_path)
        is_too_long = bool(processed_duration_sec and processed_duration_sec > MAX_AUDIO_DURATION_SEC)
        needs_split = False

        if engine == 'whisper-api':
            needs_split = file_size_mb > WHISPER_API_MAX_AUDIO_SIZE_MB or is_too_long
        elif engine == 'gemini':
            needs_split = is_too_long
        elif engine == 'whisper':
            needs_split = is_too_long

        segment_files = None

        if needs_split:
            # 分割処理
            update_status("音声ファイルを分割中...")
            segment_files = self.audio_processor.split_audio(audio_path, callback=update_status)
            if segment_files:
                update_status(f"{len(segment_files)}個のセグメントに分割しました")

        # キャッシュに保存
        if self.enable_cache and self.cache_manager:
            try:
                self.cache_manager.save_cache_entry(
                    input_file, audio_path, segment_files, processed_duration_sec,
                    cache_profile=cache_profile
                )
                update_status("✓ キャッシュに保存しました")
            except Exception as e:
                logger.warning(f"キャッシュ保存エラー: {str(e)}")

        return audio_path, segment_files, False

    def _build_segment_error_summary(self, total_segments, segment_errors, successful_segments):
        """セグメントエラーの要約を構築する"""
        return {
            'summary': {
                'total_segments': total_segments,
                'failed_segments': len(segment_errors),
                'success_segments': successful_segments,
                'success_rate': f"{(successful_segments / total_segments * 100):.1f}%" if total_segments else "0.0%"
            },
            'errors': segment_errors,
            'recommendations': [
                "失敗したセグメントはそのまま結果に混ぜず、成功分だけを残します。",
                "エラーの詳細はセグメント別ログまたは要約JSONを確認してください。",
                "エラーが続く場合は、音声品質・APIキー・モデル設定を確認してください。"
            ]
        }

    def _save_segment_error_summary(self, audio_path, error_summary):
        """セグメントエラー要約を保存する"""
        try:
            audio_dir = os.path.dirname(audio_path) if audio_path else OUTPUT_DIR
            if audio_dir and os.path.exists(audio_dir):
                error_summary_path = os.path.join(
                    audio_dir,
                    f"transcription_errors_{get_timestamp()}.json"
                )
                with open(error_summary_path, 'w', encoding='utf-8') as f:
                    json.dump(error_summary, f, ensure_ascii=False, indent=2)
                logger.info(f"エラーサマリーを保存: {error_summary_path}")
        except Exception as e:
            logger.error(f"エラーサマリーの保存に失敗: {str(e)}")

    def _re_raise_segment_failure(self, exception, warning_message):
        """全セグメント失敗時に元例外の種類を保って再送出する"""
        root_message = getattr(exception, 'user_message', str(exception))
        combined_message = f"{warning_message}\n\n原因: {root_message}"
        error_code = getattr(exception, 'error_code', None) or "ALL_SEGMENTS_FAILED"
        solution = getattr(exception, 'solution', None) or "詳細はエラーサマリーJSONとログを確認してください。"

        if isinstance(exception, ApiConnectionError):
            raise ApiConnectionError(str(exception), error_code=error_code, user_message=combined_message, solution=solution) from exception
        if isinstance(exception, AudioProcessingError):
            raise AudioProcessingError(str(exception), error_code=error_code, user_message=combined_message, solution=solution) from exception
        if isinstance(exception, FileProcessingError):
            raise FileProcessingError(str(exception), error_code=error_code, user_message=combined_message, solution=solution) from exception
        if isinstance(exception, TranscriptionError):
            raise TranscriptionError(str(exception), error_code=error_code, user_message=combined_message, solution=solution) from exception

        raise TranscriptionError(
            str(exception),
            error_code="ALL_SEGMENTS_FAILED",
            user_message=combined_message,
            solution=solution
        ) from exception

    def _handle_segment_errors(self, audio_path, total_segments, segment_errors, successful_segments,
                               update_status, fatal_exception=None):
        """セグメント失敗時の警告またはエラーを処理する"""
        if not segment_errors:
            return

        error_summary = self._build_segment_error_summary(total_segments, segment_errors, successful_segments)
        logger.warning(f"セグメント処理エラーサマリー: {json.dumps(error_summary, ensure_ascii=False)}")
        self._save_segment_error_summary(audio_path, error_summary)

        warning_message = (
            "一部のセグメントで文字起こしに失敗しました。\n"
            f"- 成功: {error_summary['summary']['success_segments']}/{error_summary['summary']['total_segments']}\n"
            f"- 失敗: {error_summary['summary']['failed_segments']}/{error_summary['summary']['total_segments']}\n"
            "失敗した区間は出力から除外されています。"
        )

        if successful_segments > 0:
            self.last_warning = warning_message
            update_status(warning_message)
            return

        if fatal_exception is not None:
            self._re_raise_segment_failure(fatal_exception, warning_message)

        raise TranscriptionError(
            "全セグメントの文字起こしに失敗しました",
            error_code="ALL_SEGMENTS_FAILED",
            user_message=warning_message,
            solution="詳細はエラーサマリーJSONとログを確認してください。"
        )

    def _perform_transcription(self, audio_path, api_key, update_status, preferred_model=None,
                               cached_segments=None, progress_callback=None, cleanup_segments=True):
        """文字起こしを実行"""
        self.last_engine_used = 'gemini'

        # ファイルサイズと長さを再チェック
        file_size_mb = get_file_size_mb(audio_path)
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path)
        needs_split = bool(audio_duration_sec and audio_duration_sec > MAX_AUDIO_DURATION_SEC)

        # Gemini は 20MB 超で Files API を使うので、サイズだけでは分割しない
        if cached_segments and needs_split:
            logger.info(f"キャッシュされたセグメントを使用: {len(cached_segments)}個")
            return self._perform_segmented_transcription(
                audio_path, api_key, update_status, preferred_model, cached_segments,
                progress_callback=progress_callback,
                cleanup_segments=cleanup_segments
            )

        if needs_split:
            logger.info(f"ファイル分割処理を実行: サイズ={file_size_mb:.2f}MB, 長さ={audio_duration_sec}s")
            return self._perform_segmented_transcription(
                audio_path, api_key, update_status, preferred_model,
                progress_callback=progress_callback
            )
        else:
            logger.info(f"単一ファイル処理を実行: サイズ={file_size_mb:.2f}MB")
            if progress_callback:
                progress_callback(15)
            result = self._perform_single_transcription(audio_path, api_key, update_status, preferred_model)
            if progress_callback:
                progress_callback(80)
            return result
    
    def _perform_whisper_transcription(self, audio_path, update_status, whisper_model='base',
                                       cached_segments=None, progress_callback=None, cleanup_segments=True):
        """Whisperを使用した文字起こしを実行"""
        self.last_engine_used = 'whisper'
        self.last_transcription_model_name = whisper_model

        # キャッシュされたセグメントがある場合は、それを使用
        if cached_segments:
            logger.info(f"キャッシュされたセグメントを使用: {len(cached_segments)}個")
            return self._perform_whisper_segmented_transcription(
                audio_path, update_status, whisper_model, cached_segments,
                progress_callback=progress_callback,
                cleanup_segments=cleanup_segments
            )

        # ファイルサイズと長さをチェック
        file_size_mb = get_file_size_mb(audio_path)
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path)

        # Whisperは大きいファイルも処理できるが、長時間の音声は分割した方が安定
        needs_split = audio_duration_sec and audio_duration_sec > MAX_AUDIO_DURATION_SEC

        if needs_split:
            logger.info(f"Whisper分割処理を実行: 長さ={audio_duration_sec}s")
            return self._perform_whisper_segmented_transcription(
                audio_path, update_status, whisper_model,
                progress_callback=progress_callback
            )
        else:
            logger.info(f"Whisper単一ファイル処理を実行: サイズ={file_size_mb:.2f}MB")
            if progress_callback:
                progress_callback(15)
            result = self._perform_whisper_single_transcription(audio_path, update_status, whisper_model)
            if progress_callback:
                progress_callback(80)
            return result
    
    def _perform_whisper_api_transcription(self, audio_path, api_key, update_status,
                                           cached_segments=None, progress_callback=None,
                                           cleanup_segments=True, whisper_api_model=None):
        """OpenAI 文字起こしAPIを使用した文字起こしを実行"""
        self.last_engine_used = 'whisper-api'

        # APIサービスの初期化（モデル変更時も再初期化）
        current_model = getattr(self.whisper_api_service, 'model', None) if self.whisper_api_service else None
        needs_reinit = (
            not self.whisper_api_service
            or self.whisper_api_service.api_key != api_key
            or (whisper_api_model and current_model != whisper_api_model)
        )
        if needs_reinit:
            self.whisper_api_service = WhisperApiService(api_key=api_key, model=whisper_api_model)

        # モデル名を記録
        active_model = getattr(self.whisper_api_service, 'model', None) or whisper_api_model or 'gpt-4o-mini-transcribe'
        self.last_transcription_model_name = active_model
        update_status(f"使用モデル: {active_model}")

        if cached_segments:
            return self._perform_whisper_api_segmented_transcription(
                audio_path,
                update_status,
                cached_segments=cached_segments,
                progress_callback=progress_callback,
                cleanup_segments=cleanup_segments
            )

        # ファイルサイズをチェック（Whisper APIは25MB以下）
        file_size_mb = get_file_size_mb(audio_path)
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path)

        if file_size_mb > WHISPER_API_MAX_AUDIO_SIZE_MB:
            update_status("Whisper APIの上限を超えるため、分割して処理します...")
            return self._perform_whisper_api_segmented_transcription(
                audio_path,
                update_status,
                progress_callback=progress_callback
            )
        
        logger.info(f"Whisper API文字起こし開始: サイズ={file_size_mb:.2f}MB, 長さ={format_duration(audio_duration_sec)}")
        update_status("Whisper APIで文字起こし中... 応答待ち")
        if progress_callback:
            progress_callback(15)

        try:
            text, metadata = self._run_with_status_heartbeat(
                lambda: self.whisper_api_service.transcribe(audio_path, language='ja'),
                update_status,
                "Whisper APIで文字起こし中..."
            )
            
            # 料金情報を表示
            if audio_duration_sec:
                cost_info = self.whisper_api_service.estimate_cost(audio_duration_sec)
                update_status(
                    f"Whisper API文字起こし完了\n"
                    f"- 料金: ${cost_info['cost_usd']:.4f} (約{cost_info['cost_jpy']:.2f}円)\n"
                    f"- 音声長さ: {format_duration(audio_duration_sec)}"
                )
            
            if progress_callback:
                progress_callback(80)
            return text

        except (ApiConnectionError, AudioProcessingError, TranscriptionError):
            raise
        except Exception as e:
            logger.error(f"Whisper API文字起こしエラー: {str(e)}")
            raise TranscriptionError(f"Whisper API文字起こしに失敗しました: {str(e)}")

    def _perform_whisper_api_segmented_transcription(self, audio_path, update_status,
                                                     cached_segments=None, progress_callback=None,
                                                     cleanup_segments=True):
        """Whisper APIで分割セグメントを順次文字起こしする"""
        if cached_segments:
            segment_files = cached_segments
            update_status(f"キャッシュされたセグメントをWhisper APIで処理します ({len(segment_files)}個)")
        else:
            update_status("Whisper API用に音声ファイルを分割中...")
            segment_files = self.audio_processor.split_audio(audio_path, callback=update_status)
            if not segment_files:
                raise AudioProcessingError("音声ファイルの分割に失敗しました")

        segment_transcriptions = []
        segment_info = []
        segment_errors = []
        first_exception = None
        total = len(segment_files)

        try:
            for i, segment_file in enumerate(segment_files):
                segment_status = f"セグメント {i+1}/{total} をWhisper APIで処理中..."
                update_status(segment_status)
                if progress_callback:
                    pct = 10 + int((i / total) * 70)
                    progress_callback(pct)

                try:
                    text, metadata = self._run_with_status_heartbeat(
                        lambda: self.whisper_api_service.transcribe(segment_file, language='ja'),
                        update_status,
                        segment_status
                    )
                except Exception as e:
                    if first_exception is None:
                        first_exception = e
                    error_category, error_detail = self._classify_segment_error(
                        e, i + 1, segment_file, total, 'whisper-1'
                    )
                    segment_errors.append({
                        'segment_index': i + 1,
                        'error_text': f"[セグメント {i+1} 処理エラー: {error_category} - {error_detail}]",
                        'error_category': error_category,
                        'error_detail': error_detail
                    })
                    continue

                segment_transcriptions.append(text)
                segment_info.append({
                    'segment_index': i,
                    'total_segments': total,
                    'file_path': segment_file,
                    'metadata': metadata
                })
        finally:
            if cleanup_segments:
                self._cleanup_segments(segment_files, audio_path)

        self._handle_segment_errors(
            audio_path,
            total,
            segment_errors,
            len(segment_transcriptions),
            update_status,
            fatal_exception=first_exception
        )

        update_status("セグメントを統合中...")
        merged_text = self.text_merger.merge_segments_with_context(segment_transcriptions, segment_info)
        update_status("セグメント統合完了")
        return merged_text

    def _upload_gemini_audio_file(self, audio_path, update_status):
        """Gemini Files API に音声をアップロードして利用可能状態まで待つ"""
        update_status("Gemini Files API に音声をアップロード中...")

        with GENAI_SDK_LOCK:
            uploaded_file = genai.upload_file(audio_path, mime_type=AUDIO_MIME_TYPE)

        state = getattr(uploaded_file, 'state', None)
        if state == genai.protos.File.State.ACTIVE:
            return uploaded_file

        for _ in range(120):
            time.sleep(2)
            with GENAI_SDK_LOCK:
                uploaded_file = genai.get_file(uploaded_file.name)
            state = getattr(uploaded_file, 'state', None)

            if state == genai.protos.File.State.ACTIVE:
                update_status("Gemini Files API の音声準備が完了しました")
                return uploaded_file
            if state == genai.protos.File.State.FAILED:
                raise TranscriptionError("Gemini Files API で音声ファイルの処理に失敗しました")

        raise TranscriptionError("Gemini Files API の音声処理がタイムアウトしました")

    def _delete_gemini_audio_file(self, uploaded_file):
        """Gemini Files API の一時ファイルを削除する"""
        if not uploaded_file:
            return
        try:
            with GENAI_SDK_LOCK:
                genai.delete_file(uploaded_file)
        except Exception as e:
            logger.warning(f"Gemini Files API 一時ファイルの削除に失敗: {str(e)}")

    def _perform_single_transcription(self, audio_path, api_key, update_status, preferred_model=None):
        """単一ファイルの文字起こし"""
        with GENAI_SDK_LOCK:
            genai.configure(api_key=api_key)
            model_name = self.api_utils.get_best_available_model(api_key, preferred_model)

        # 音声の長さを取得（料金計算用）
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path)
        file_size_mb = get_file_size_mb(audio_path)
        self.last_transcription_model_name = model_name

        # モデル名を目立つように表示
        logger.info(f"✓ 選択されたモデル: {model_name}")
        update_status(f"✓ 使用モデル: {model_name}")
        update_status(f"音声ファイルから文字起こし中...")

        with GENAI_SDK_LOCK:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name,
                generation_config=AI_GENERATION_CONFIG,
                safety_settings=SAFETY_SETTINGS_TRANSCRIPTION  # 文字起こし用に安全性フィルターを緩和
            )

        prompt = """この音声の文字起こしを日本語でお願いします。以下の点を守って正確に書き起こしてください：

1. 話された内容をそのまま文字に起こす
2. 話者が複数いる場合は、話者の区別を表記する
3. 自然な文章の流れを保つ
4. 不明瞭な部分は[不明瞭]と記載する
5. 長い沈黙は[間]と記載する

正確性と一貫性を最優先にしてください。"""

        uploaded_file = None
        try:
            if file_size_mb > MAX_AUDIO_SIZE_MB:
                uploaded_file = self._upload_gemini_audio_file(audio_path, update_status)
                parts = [uploaded_file, prompt]
            else:
                with open(audio_path, 'rb') as audio_file:
                    audio_data = audio_file.read()
                parts = [
                    {"inline_data": {"mime_type": AUDIO_MIME_TYPE, "data": audio_data}},
                    {"text": prompt}
                ]

            with GENAI_SDK_LOCK:
                response = model.generate_content(parts)
        finally:
            self._delete_gemini_audio_file(uploaded_file)

        # レスポンスの安全性チェック
        self._check_response_safety(response)

        if not response.text or response.text.strip() == "":
            raise TranscriptionError("文字起こし結果が空でした")

        # トークン使用量と料金を計算・表示
        process_usage_metadata(
            response, model_name,
            is_audio_input=True,
            audio_duration_seconds=audio_duration_sec,
            update_status=update_status
        )

        return response.text
    
    def _perform_segmented_transcription(self, audio_path, api_key, update_status, preferred_model=None,
                                        cached_segments=None, progress_callback=None, cleanup_segments=True,
                                        whisper_fallback_for_blocked=False, whisper_model='turbo'):
        """分割された音声ファイルの文字起こし（スマート統合付き）"""
        with GENAI_SDK_LOCK:
            genai.configure(api_key=api_key)
            model_name = self.api_utils.get_best_available_model(api_key, preferred_model)
        self.last_transcription_model_name = model_name

        # モデル名を目立つように表示
        logger.info(f"✓ 選択されたモデル: {model_name}")
        update_status(f"✓ 使用モデル: {model_name}")

        # キャッシュされたセグメントを使用
        if cached_segments:
            update_status(f"キャッシュされたセグメントを使用")
            segment_files = cached_segments
            update_status(f"{len(segment_files)}個のセグメントで処理します")
        else:
            update_status(f"音声の長さが長いため、ファイルを分割して処理します")

            # 音声を分割
            segment_files = self.audio_processor.split_audio(audio_path, callback=update_status)
            if not segment_files:
                raise AudioProcessingError("音声ファイルの分割に失敗しました")

            update_status(f"{len(segment_files)}個のセグメントに分割しました")
        
        # モデルインスタンスを一度だけ生成（全セグメントで共有）
        with GENAI_SDK_LOCK:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name,
                generation_config=AI_GENERATION_CONFIG,
                safety_settings=SAFETY_SETTINGS_TRANSCRIPTION
            )

        segment_transcriptions = []
        segment_info = []
        segment_costs = []
        segment_errors = []  # エラー情報を記録
        first_exception = None

        try:
            total = len(segment_files)
            for i, segment_file in enumerate(segment_files):
                update_status(f"セグメント {i+1}/{total} を処理中")
                if progress_callback:
                    # 10%〜80%の範囲でセグメントごとに進捗
                    pct = 10 + int((i / total) * 70)
                    progress_callback(pct)

                # セグメントの文字起こし（改善版）
                segment_transcription, cost_info, error_info = self._transcribe_segment_enhanced(
                    segment_file, api_key, i+1, total, model_name, model=model
                )
                if cost_info:
                    segment_costs.append(cost_info)

                # エラーチェック: エラーテキストは結果に含めない
                if error_info is not None:
                    # 安全性フィルターブロック時にWhisperフォールバック
                    if (whisper_fallback_for_blocked
                            and error_info['category'] == '安全性フィルター'):
                        whisper_text = self._whisper_fallback_single_segment(
                            segment_file, i+1, total, update_status, whisper_model
                        )
                        if whisper_text:
                            segment_transcriptions.append(whisper_text)
                            segment_info.append({
                                'segment_index': i,
                                'total_segments': len(segment_files),
                                'file_path': segment_file
                            })
                            logger.info(f"セグメント {i+1} をWhisperで補完しました")
                            continue

                    if first_exception is None:
                        first_exception = error_info['exception']
                    segment_errors.append({
                        'segment_index': i+1,
                        'error_text': segment_transcription,
                        'error_category': error_info['category'],
                        'error_detail': error_info['detail']
                    })
                    logger.warning(f"セグメント {i+1} をスキップ: {segment_transcription}")
                else:
                    segment_transcriptions.append(segment_transcription)
                    segment_info.append({
                        'segment_index': i,
                        'total_segments': len(segment_files),
                        'file_path': segment_file
                    })
        
        finally:
            if cleanup_segments:
                self._cleanup_segments(segment_files, audio_path)

        self._handle_segment_errors(
            audio_path,
            len(segment_files),
            segment_errors,
            len(segment_transcriptions),
            update_status,
            fatal_exception=first_exception
        )
        
        # セグメントごとのコスト情報を集計
        if segment_costs:
            total_input_tokens = sum(cost["input_tokens"] for cost in segment_costs)
            total_output_tokens = sum(cost["output_tokens"] for cost in segment_costs)
            total_cost = sum(cost["total_cost"] for cost in segment_costs)
            
            combined_cost_info = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_cost": total_cost,
                "input_cost": sum(cost["input_cost"] for cost in segment_costs),
                "output_cost": sum(cost["output_cost"] for cost in segment_costs)
            }
            
            usage_text = format_token_usage(combined_cost_info)
            update_status(f"全セグメント合計トークン使用量: {usage_text}")
        
        # スマート統合を実行
        if SEGMENT_MERGE_CONFIG['enable_smart_merge']:
            update_status("セグメントを統合中...")
            merged_text = self.text_merger.merge_segments_with_context(
                segment_transcriptions, segment_info
            )
            update_status("セグメント統合完了")
            return merged_text
        else:
            # 従来の方法で結合
            return "\n\n".join(segment_transcriptions)
    
    def _transcribe_segment_enhanced(self, segment_file, api_key, segment_num, total_segments, model_name, model=None):
        """改善された単一セグメントの文字起こし"""
        try:
            # セグメントの音声の長さを取得（料金計算用）
            segment_duration_sec = self.audio_processor.get_audio_duration(segment_file)

            # モデルインスタンスが渡されない場合のみ生成
            if model is None:
                with GENAI_SDK_LOCK:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        model_name,
                        generation_config=AI_GENERATION_CONFIG,
                        safety_settings=SAFETY_SETTINGS_TRANSCRIPTION
                    )

            with open(segment_file, 'rb') as audio_file:
                audio_data = audio_file.read()

            # オーバーラップを考慮したプロンプト
            if segment_num == 1:
                context_instruction = "これは音声の最初の部分です。"
            elif segment_num == total_segments:
                context_instruction = "これは音声の最後の部分です。前の部分から自然に続くように文字起こしを行ってください。"
            else:
                context_instruction = f"これは音声の中間部分（{segment_num}/{total_segments}）です。前後の部分と自然に繋がるように文字起こしを行ってください。"

            prompt = f"""この音声の文字起こしを日本語で行ってください。

{context_instruction}

以下の点を守って正確に書き起こしてください：
1. 話された内容をそのまま文字に起こす
2. 話者が複数いる場合は、話者の区別を表記する
3. 自然な文章の流れを保つ
4. 不明瞭な部分は[不明瞭]と記載する
5. 文の途中で切れる場合は、自然な区切りで終わらせる
6. 重複や繰り返しがある場合は適切に処理する

正確性と一貫性を最優先にし、後で他のセグメントと統合されることを考慮してください。"""

            parts = [
                {"inline_data": {"mime_type": AUDIO_MIME_TYPE, "data": audio_data}},
                {"text": prompt}
            ]

            with GENAI_SDK_LOCK:
                response = model.generate_content(parts)

            # レスポンスの安全性チェック
            self._check_response_safety(response, segment_num=segment_num)

            if not response.text or response.text.strip() == "":
                raise TranscriptionError(f"セグメント {segment_num} の文字起こし結果が空でした")

            # トークン使用量を記録（セグメント処理では表示は控えめに）
            input_tokens, output_tokens = extract_usage_metadata(response)
            segment_cost_info = None
            if input_tokens is not None and output_tokens is not None:
                segment_cost_info = calculate_gemini_cost(
                    model_name, input_tokens, output_tokens,
                    is_audio_input=True, audio_duration_seconds=segment_duration_sec
                )

            return response.text.strip(), segment_cost_info, None
        except Exception as e:
            error_category, error_detail = self._classify_segment_error(e, segment_num, segment_file, total_segments, model_name)
            return (
                f"[セグメント {segment_num} 処理エラー: {error_category} - {error_detail}]",
                None,
                {
                    'exception': e,
                    'category': error_category,
                    'detail': error_detail
                }
            )

    def _whisper_fallback_single_segment(self, segment_file, segment_num, total_segments,
                                          update_status, whisper_model='turbo'):
        """安全性フィルターでブロックされた単一セグメントをWhisperで文字起こしする

        Returns:
            str or None: Whisperの文字起こし結果。失敗時はNone
        """
        try:
            update_status(
                f"セグメント {segment_num}/{total_segments} が安全性フィルターでブロック → Whisper で補完中..."
            )
            whisper_service = self.get_whisper_service()
            text, metadata = whisper_service.transcribe(
                segment_file,
                model_name=whisper_model,
                language='ja'
            )
            if text and text.strip():
                update_status(
                    f"セグメント {segment_num}/{total_segments} を Whisper ({whisper_model}) で補完完了"
                )
                return text.strip()
            return None
        except Exception as e:
            logger.warning(f"セグメント {segment_num} のWhisperフォールバック失敗: {e}")
            update_status(f"セグメント {segment_num} のWhisper補完にも失敗しました")
            return None

    def _classify_segment_error(self, exception, segment_num, segment_file, total_segments, model_name):
        """セグメント処理エラーを分類し、ログに記録する

        Returns:
            (error_category, error_detail) のタプル
        """
        error_details = {
            'segment_num': segment_num,
            'total_segments': total_segments,
            'segment_file': segment_file,
            'error_type': type(exception).__name__,
            'error_message': str(exception),
            'model': model_name
        }

        error_str = str(exception).lower()

        if isinstance(exception, TranscriptionError) and exception.error_code == "COPYRIGHT_CONTENT":
            error_category = "著作権保護コンテンツ"
            error_detail = exception.user_message
            solution = exception.solution or "音声に含まれる音楽やBGMを削除するか、別の音声ファイルを使用してください。"
        elif isinstance(exception, TranscriptionError) and exception.error_code == "SAFETY_FILTER":
            error_category = "安全性フィルター"
            error_detail = exception.user_message
            solution = exception.solution or "音声の内容を確認してください。"
        elif 'audio input modality is not enabled' in error_str or 'audio input is not supported' in error_str:
            error_category = "モデル非対応"
            error_detail = "選択されたモデルは音声入力に対応していません"
            solution = "別のモデルを選択してください。Flash系モデル（gemini-2.5-flash等）の使用を推奨します。"
        elif (
            (isinstance(exception, ApiConnectionError) and exception.error_code == "INSUFFICIENT_CREDIT")
            or 'insufficient_quota' in error_str
            or 'current quota' in error_str
            or 'billing' in error_str
            or 'credit balance' in error_str
        ):
            error_category = "利用残高不足"
            error_detail = "OpenAI API の利用残高または請求設定に問題があります"
            solution = "OpenAI の Billing でクレジット残高と支払い方法を確認し、残高が 0 の場合はチャージ後に再実行してください。"
        elif 'rate limit' in error_str or '429' in error_str:
            error_category = "APIレート制限"
            error_detail = "APIの呼び出し回数が上限に達しました"
            solution = "数分待ってから再度実行してください。または、有料プランへのアップグレードをご検討ください。"
        elif 'timeout' in error_str:
            error_category = "タイムアウト"
            error_detail = "API応答に時間がかかりすぎました"
            solution = "音声の内容が複雑すぎる可能性があります。しばらく待ってから再度実行してください。"
        elif 'network' in error_str or 'connection' in error_str:
            error_category = "ネットワーク接続"
            error_detail = "インターネット接続に問題があります"
            solution = "ネットワーク接続を確認してから再度実行してください。"
        elif 'authentication' in error_str or '401' in str(exception) or '403' in str(exception):
            error_category = "認証失敗"
            error_detail = "APIキーが無効または権限がありません"
            solution = "APIキーが正しく設定されているか確認してください。"
        elif 'finish_reason' in error_str and '4' in error_str:
            error_category = "著作権保護コンテンツ"
            error_detail = "音楽や著作権保護されたコンテンツが検出されました"
            solution = "音声に含まれる音楽やBGMを削除するか、別の音声ファイルを使用してください。"
        elif 'copyrighted' in error_str or '著作権' in str(exception):
            error_category = "著作権保護コンテンツ"
            error_detail = "音楽や著作権保護されたコンテンツが検出されました"
            solution = "音声に含まれる音楽やBGMを削除するか、別の音声ファイルを使用してください。"
        elif 'safety' in error_str or '安全性' in str(exception) or 'blocked' in error_str:
            error_category = "安全性フィルター"
            error_detail = "音声の内容が安全性基準に抵触する可能性があります"
            solution = "音声の内容を確認してください。過激な表現や不適切なコンテンツが含まれている場合、処理できません。"
        elif '500' in str(exception) or 'internal' in error_str:
            error_category = "サーバーエラー"
            error_detail = f"{type(exception).__name__}"
            solution = "Google側のサーバーで一時的な問題が発生しています。数分待ってから再度実行してください。"
        else:
            error_category = "予期しないエラー"
            error_detail = f"{type(exception).__name__}: {str(exception)}"
            solution = "エラーが続く場合は、別の音声ファイルを試すか、ログファイルを確認してください。"

        # エラー情報をファイルに保存（デバッグ用）
        try:
            segment_dir = os.path.dirname(segment_file) if segment_file else tempfile.gettempdir()
            if segment_dir and os.path.exists(segment_dir):
                error_log_path = os.path.join(
                    segment_dir,
                    f"segment_{segment_num}_error.log"
                )
                error_details['error_category'] = error_category
                error_details['error_detail'] = error_detail
                error_details['solution'] = solution
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    json.dump(error_details, f, ensure_ascii=False, indent=2)
        except Exception as log_error:
            logger.debug(f"エラーログの保存に失敗: {str(log_error)}")

        logger.error(f"セグメント {segment_num} 処理エラー: {error_category} - {error_detail}")
        logger.debug(f"エラー詳細: {json.dumps(error_details, ensure_ascii=False)}")

        return error_category, error_detail
    
    def _perform_whisper_single_transcription(self, audio_path, update_status, whisper_model='base'):
        """Whisperを使用した単一ファイルの文字起こし"""
        import time as _time
        update_status(f"Whisperで文字起こし中... (モデル: {whisper_model})")

        try:
            # Whisperで文字起こし
            whisper_service = self.get_whisper_service()
            whisper_start = _time.time()
            text, metadata = whisper_service.transcribe(
                audio_path,
                model_name=whisper_model,
                language='ja'
            )
            whisper_elapsed = _time.time() - whisper_start

            # メタデータ情報を表示
            duration = metadata.get('duration', 0)
            segments = metadata.get('segments', 0)
            device = metadata.get('device', 'CPU')

            # 処理速度を計算（音声の何倍速で処理できたか）
            speed_ratio = duration / whisper_elapsed if whisper_elapsed > 0 else 0

            update_status(
                f"Whisper文字起こし完了: "
                f"長さ={format_duration(duration)}, "
                f"セグメント数={segments}, "
                f"デバイス={device}"
            )
            logger.info(
                f"Whisper処理時間: {whisper_elapsed:.1f}秒 "
                f"(音声{format_duration(duration)}の{speed_ratio:.1f}倍速)"
            )
            
            return text
            
        except Exception as e:
            logger.error(f"Whisper文字起こしエラー: {str(e)}")
            raise TranscriptionError(f"Whisper文字起こしに失敗しました: {str(e)}")
    
    def _perform_whisper_segmented_transcription(self, audio_path, update_status, whisper_model='base',
                                                cached_segments=None, progress_callback=None,
                                                cleanup_segments=True):
        """Whisperを使用した分割ファイルの文字起こし"""
        # キャッシュされたセグメントを使用
        if cached_segments:
            update_status(f"キャッシュされたセグメントをWhisperで処理します (モデル: {whisper_model})")
            segment_files = cached_segments
            update_status(f"{len(segment_files)}個のセグメントで処理します")
        else:
            update_status(f"音声が長いため、分割してWhisperで処理します (モデル: {whisper_model})")

            # 音声を分割
            segment_files = self.audio_processor.split_audio(audio_path, callback=update_status)
            if not segment_files:
                raise AudioProcessingError("音声ファイルの分割に失敗しました")

            update_status(f"{len(segment_files)}個のセグメントに分割しました")

        segment_transcriptions = []
        segment_info = []
        segment_errors = []
        total = len(segment_files)
        whisper_service = self.get_whisper_service()

        try:
            for i, segment_file in enumerate(segment_files):
                update_status(f"セグメント {i+1}/{total} をWhisperで処理中")
                if progress_callback:
                    pct = 10 + int((i / total) * 70)
                    progress_callback(pct)
                
                # Whisperでセグメントを文字起こし
                text, metadata = whisper_service.transcribe_segment(
                    segment_file, 
                    segment_num=i+1,
                    total_segments=len(segment_files),
                    model_name=whisper_model,
                    language='ja'
                )

                if metadata.get('is_error'):
                    segment_errors.append({
                        'segment_index': i + 1,
                        'error_text': text
                    })
                    continue

                segment_transcriptions.append(text)
                segment_info.append({
                    'segment_index': i,
                    'total_segments': len(segment_files),
                    'file_path': segment_file,
                    'metadata': metadata
                })
        
        finally:
            if cleanup_segments:
                self._cleanup_segments(segment_files, audio_path)

        self._handle_segment_errors(audio_path, total, segment_errors, len(segment_transcriptions), update_status)
        
        # スマート統合を実行
        if SEGMENT_MERGE_CONFIG['enable_smart_merge']:
            update_status("セグメントを統合中...")
            merged_text = self.text_merger.merge_segments_with_context(
                segment_transcriptions, segment_info
            )
            update_status("セグメント統合完了")
            return merged_text
        else:
            # 従来の方法で結合
            return "\n\n".join(segment_transcriptions)
    
    def _cleanup_segments(self, segment_files, original_audio_path):
        """セグメントファイルをクリーンアップ"""
        for segment_file in segment_files:
            if segment_file != original_audio_path and os.path.exists(segment_file):
                try:
                    os.unlink(segment_file)
                except OSError:
                    logger.warning(f"セグメントファイルの削除に失敗: {segment_file}")
    
    def _perform_additional_processing(self, transcription, process_type, prompts, api_key, update_status, preferred_model=None):
        """追加処理（要約、議事録作成など）"""
        if process_type == "transcription":
            return transcription

        if process_type not in prompts:
            raise FileProcessingError(f"指定された処理タイプ '{process_type}' はプロンプト設定に存在しません")

        # 追加処理はGeminiが必要
        if not api_key:
            raise ApiConnectionError("追加処理（要約・議事録作成など）にはGemini APIキーが必要です")

        process_name = prompts[process_type]["name"]
        with GENAI_SDK_LOCK:
            genai.configure(api_key=api_key)
            model_name = self.api_utils.get_best_available_model(api_key, preferred_model)

        # モデル名を表示
        logger.info(f"✓ {process_name}使用モデル: {model_name}")
        update_status(f"✓ 使用モデル: {model_name}")
        update_status(f"{process_name}を生成中...")
        
        prompt = prompts[process_type]["prompt"].replace("{transcription}", transcription)
        
        with GENAI_SDK_LOCK:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name,
                generation_config=AI_GENERATION_CONFIG,
                safety_settings=SAFETY_SETTINGS_TRANSCRIPTION  # 安全性フィルターを緩和
            )
            response = model.generate_content(prompt)
        if not response.text:
            raise TranscriptionError(f"{process_name}の生成に失敗しました")
        
        # トークン使用量と料金を計算・表示（テキスト処理）
        def update_usage_status(message):
            update_status(f"{process_name}{message}")
        
        process_usage_metadata(
            response, model_name,
            is_audio_input=False,
            update_status=update_usage_status
        )
        
        return response.text
    
    def _get_unique_path(self, file_path):
        """ファイルパスが重複する場合、末尾に連番を付与してユニークなパスを返す"""
        if not os.path.exists(file_path):
            return file_path

        base, ext = os.path.splitext(file_path)
        counter = 2
        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1
        return f"{base}_{counter}{ext}"

    def generate_summary_title(self, text, api_key):
        """文字起こしテキストから要約タイトルを生成する

        Args:
            text: 文字起こしテキスト
            api_key: Gemini APIキー

        Returns:
            str or None: 要約タイトル。失敗時はNone
        """
        try:
            with GENAI_SDK_LOCK:
                genai.configure(api_key=api_key)

            # キャッシュ付きモデルリストを使用（音声処理不向きモデルを除外）
            all_names = self.api_utils._get_available_models(api_key)
            available_names = [
                m for m in all_names
                if not any(kw in m.lower() for kw in ['-tts', 'live', 'thinking'])
            ]

            model_name = None
            for preferred in TITLE_GENERATION_MODELS:
                for available in available_names:
                    if preferred in available:
                        model_name = available
                        break
                if model_name:
                    break

            if not model_name:
                model_name = available_names[0] if available_names else None
            if not model_name:
                logger.warning("タイトル生成: 利用可能なモデルが見つかりません")
                return None

            logger.info(f"タイトル生成モデル: {model_name}")

            # テキストの先頭2000文字を使用
            excerpt = text[:2000]

            prompt = (
                "この文字起こしの内容を15〜25文字で要約してタイトルを付けてください。\n"
                "ファイル名に使うので記号は使わないでください。\n"
                "タイトルのみを出力してください。説明や装飾は不要です。\n\n"
                f"{excerpt}"
            )

            with GENAI_SDK_LOCK:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(
                    model_name,
                    generation_config={
                        'temperature': 0.1,
                        'max_output_tokens': 100,
                        'candidate_count': 1
                    }
                )
                response = model.generate_content(prompt)

            if not response.text or not response.text.strip():
                logger.warning("タイトル生成: 空のレスポンス")
                return None

            title = response.text.strip()
            # 最大文字数で切り詰め
            if len(title) > SUMMARY_TITLE_MAX_LENGTH:
                title = title[:SUMMARY_TITLE_MAX_LENGTH]

            # ファイル名に使えない文字を除去
            title = sanitize_filename(title)
            if not title:
                logger.warning("タイトル生成: サニタイズ後に空になりました")
                return None

            logger.info(f"生成されたタイトル: {title}")
            return title

        except Exception as e:
            logger.warning(f"タイトル生成に失敗（フォールバックで従来のファイル名を使用）: {str(e)}")
            return None

    def generate_summary_title_ollama(self, text, model='gemma3:4b',
                                       base_url='http://localhost:11434'):
        """Ollamaを使用して要約タイトルを生成する（Geminiが使えない場合のフォールバック）"""
        try:
            import urllib.request
            import urllib.error

            excerpt = text[:2000]
            prompt = (
                "この文字起こしの内容を15〜25文字で要約してタイトルを付けてください。\n"
                "ファイル名に使うので記号は使わないでください。\n"
                "タイトルのみを出力してください。説明や装飾は不要です。\n\n"
                f"{excerpt}"
            )

            payload = json.dumps({
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.1,
                    'num_predict': 100,
                }
            }).encode('utf-8')

            req = urllib.request.Request(
                f'{base_url}/api/generate',
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            title = result.get('response', '').strip()
            if not title:
                logger.warning("Ollamaタイトル生成: 空のレスポンス")
                return None

            # 最大文字数で切り詰め
            if len(title) > SUMMARY_TITLE_MAX_LENGTH:
                title = title[:SUMMARY_TITLE_MAX_LENGTH]

            title = sanitize_filename(title)
            if not title:
                logger.warning("Ollamaタイトル生成: サニタイズ後に空になりました")
                return None

            logger.info(f"Ollamaで生成されたタイトル: {title}")
            return title

        except (urllib.error.URLError, ConnectionRefusedError):
            logger.info("Ollamaが起動していないため、タイトル生成をスキップします")
            return None
        except Exception as e:
            logger.warning(f"Ollamaタイトル生成に失敗: {str(e)}")
            return None

    def _save_result(self, input_file, final_text, process_type, prompts, start_time, update_status,
                     save_to_output_dir=True, save_to_source_dir=False, summary_title=None):
        """結果をファイルに保存"""
        if not save_to_output_dir and not save_to_source_dir:
            logger.warning("保存先が未指定のため、outputフォルダに保存します")
            save_to_output_dir = True

        timestamp = get_timestamp()
        base_name = os.path.splitext(os.path.basename(input_file))[0]

        # process_typeがプロンプトに存在しない場合はデフォルト名を使用
        if process_type in prompts:
            process_name = prompts[process_type]["name"]
        else:
            process_name = "文字起こし"

        # ファイル名の生成
        if summary_title:
            # タイトルあり: {要約タイトル}_文字起こし_{元ファイル名}.txt
            output_filename = f"{summary_title}_{process_name}_{base_name}.txt"
        else:
            # タイトルなし: {元ファイル名}_文字起こし_{タイムスタンプ}.txt（従来通り）
            output_filename = f"{base_name}_{process_name}_{timestamp}.txt"

        result_path = None

        # outputフォルダへ保存（重複チェック付き）
        if save_to_output_dir:
            output_path = self._get_unique_path(os.path.join(self.output_dir, output_filename))
            output_filename = os.path.basename(output_path)  # 重複回避後のファイル名に更新
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_text)
            result_path = output_path

        # 元ファイルのフォルダへ保存（重複チェック付き）
        if save_to_source_dir:
            source_dir = os.path.dirname(os.path.abspath(input_file))
            source_path = self._get_unique_path(os.path.join(source_dir, output_filename))
            if save_to_output_dir and result_path:
                shutil.copy2(result_path, source_path)
            else:
                with open(source_path, 'w', encoding='utf-8') as f:
                    f.write(final_text)
            if result_path is None:
                result_path = source_path
            update_status(f"元ファイルのフォルダにも保存: {source_path}")

        # 処理完了のログ
        end_time = datetime.datetime.now()
        self.last_processing_sec = (end_time - start_time).total_seconds()
        process_time_str = format_process_time(start_time, end_time)
        output_size_kb = get_file_size_kb(result_path)
        update_status(
            f"処理完了: {output_filename}\n"
            f"- 処理時間: {process_time_str}\n"
            f"- 出力ファイルサイズ: {output_size_kb:.2f}KB"
        )

        return result_path
    
    def process_transcription_file(self, transcription_file, prompt_key, api_key, prompts, status_callback=None):
        """文字起こしファイルの追加処理を実行"""
        start_time = datetime.datetime.now()
        
        def update_status(message):
            logger.info(message)
            if status_callback:
                status_callback(message)
        
        try:
            # 文字起こしファイルを読み込み
            file_size_kb = get_file_size_kb(transcription_file)
            update_status(f"文字起こしファイル（{file_size_kb:.1f}KB）を読み込み中...")
            
            with open(transcription_file, 'r', encoding='utf-8') as f:
                transcription = f.read()
            
            # プロンプト情報取得
            if prompt_key not in prompts:
                raise FileProcessingError(f"プロンプトキー '{prompt_key}' が見つかりません")
            
            prompt_info = prompts[prompt_key]
            process_name = prompt_info["name"]
            
            # ファイル名のベース部分を抽出（元の文字起こし元のファイル名）
            base_name = os.path.basename(transcription_file)
            match = re.match(r'(.+?)_文字起こし_\d+_\d+\.txt', base_name)
            if match:
                base_name = match.group(1)
            else:
                match = re.match(r'(.+?)_\d+_\d+\.txt', base_name)
                if match:
                    base_name = match.group(1)
            
            # APIを使用して処理
            with GENAI_SDK_LOCK:
                genai.configure(api_key=api_key)
                model_name = self.api_utils.get_best_available_model(api_key)

            # モデル名を表示
            logger.info(f"✓ {process_name}使用モデル: {model_name}")
            update_status(f"✓ 使用モデル: {model_name}")
            update_status(f"{process_name}を生成中...")
            
            # プロンプトに文字起こし結果を埋め込む
            prompt = prompt_info["prompt"].replace("{transcription}", transcription)

            with GENAI_SDK_LOCK:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(
                    model_name,
                    generation_config=AI_GENERATION_CONFIG
                )
                response = model.generate_content(prompt)
            if not response.text:
                raise TranscriptionError(f"{process_name}の生成に失敗しました")
            
            # 出力ファイル名
            timestamp = get_timestamp()
            output_filename = f"{base_name}_{process_name}_{timestamp}.txt"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # ファイル出力
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # 処理完了のログ
            end_time = datetime.datetime.now()
            process_time_str = format_process_time(start_time, end_time)
            output_size_kb = get_file_size_kb(output_path)
            update_status(
                f"処理完了: {os.path.basename(output_path)}\n"
                f"- 元ファイルサイズ: {file_size_kb:.1f}KB\n"
                f"- 処理時間: {process_time_str}\n"
                f"- 使用モデル: {model_name}"
            )
            
            return output_path
            
        except (TranscriptionError, AudioProcessingError, ApiConnectionError, FileProcessingError):
            raise
        except Exception as e:
            update_status(f"処理エラー: {str(e)}")
            raise FileProcessingError(f"文字起こしファイルの処理に失敗しました: {str(e)}")
