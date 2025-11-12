#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import json
import datetime
import tempfile
import google.generativeai as genai

from .constants import (
    MAX_AUDIO_SIZE_MB,
    MAX_AUDIO_DURATION_SEC, 
    AUDIO_MIME_TYPE,
    OUTPUT_DIR,
    AI_GENERATION_CONFIG,
    SEGMENT_MERGE_CONFIG
)
from .exceptions import (
    TranscriptionError, 
    AudioProcessingError, 
    ApiConnectionError, 
    FileProcessingError
)
from .audio_processor import AudioProcessor
from .api_utils import ApiUtils
from .whisper_service import WhisperService
from .text_merger import EnhancedTextMerger
from .audio_cache import AudioCacheManager
from .utils import get_timestamp, format_duration, calculate_gemini_cost, format_token_usage
from .logger import logger

class FileProcessor:
    """音声/動画ファイルの処理を行うクラス"""
    
    def __init__(self, output_dir, enable_cache=True, max_cache_items=5):
        self.output_dir = output_dir
        self.audio_processor = AudioProcessor()
        self.api_utils = ApiUtils()
        self.whisper_service = WhisperService()
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
                error_msg = f"{segment_info}応答が安全性フィルターによってブロックされました"
                solution = "音声の内容を確認してください。過激な表現や不適切なコンテンツが含まれている場合、処理できません。"
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
                    preferred_model=None, engine='gemini', whisper_model='base'):
        """ファイルを処理し、結果を返す"""
        start_time = datetime.datetime.now()
        
        def update_status(message):
            logger.info(message)
            if status_callback:
                status_callback(message)
        
        try:
            # 音声ファイルの準備（キャッシュ対応）
            audio_path, cached_segments, from_cache = self._prepare_audio_file(input_file, update_status)

            # 文字起こし実行（エンジンに応じて分岐）
            # キャッシュからセグメントを取得した場合は、それを使用
            if engine == 'whisper':
                transcription = self._perform_whisper_transcription(
                    audio_path, update_status, whisper_model, cached_segments
                )
            else:
                transcription = self._perform_transcription(
                    audio_path, api_key, update_status, preferred_model, cached_segments
                )
            
            # 追加処理（必要な場合）
            final_text = self._perform_additional_processing(
                transcription, process_type, prompts, api_key, update_status, preferred_model
            )
            
            # 結果をファイルに保存
            output_path = self._save_result(
                input_file, final_text, process_type, prompts, start_time, update_status
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"処理エラー: {str(e)}", exc_info=True)
            update_status(f"処理エラー: {str(e)}")
            raise FileProcessingError(f"ファイル処理に失敗しました: {str(e)}")
    
    def _prepare_audio_file(self, input_file, update_status):
        """音声ファイルの準備（変換・圧縮・分割）

        キャッシュがあれば再利用、なければ処理してキャッシュに保存

        Returns:
            (audio_path, segment_files, from_cache) のタプル
        """
        # 元のファイル情報を取得
        original_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        audio_duration_sec = self.audio_processor.get_audio_duration(input_file)
        duration_str = format_duration(audio_duration_sec) if audio_duration_sec else "不明"

        logger.info(f"音声ファイル準備開始: {os.path.basename(input_file)}, サイズ={original_size_mb:.2f}MB, 長さ={duration_str}")
        update_status(f"処理開始: ファイルサイズ={original_size_mb:.2f}MB, 長さ={duration_str}")

        # キャッシュをチェック
        if self.enable_cache and self.cache_manager:
            cache_entry = self.cache_manager.get_cache_entry(input_file)
            if cache_entry:
                cache_id = cache_entry['cache_id']
                processed_audio, segments = self.cache_manager.get_cached_files(cache_id)

                if processed_audio:
                    update_status(f"✓ キャッシュから読み込み: {os.path.basename(input_file)}")
                    logger.info(f"キャッシュ使用: processed={processed_audio}, segments={len(segments) if segments else 0}")
                    return processed_audio, segments, True

        # キャッシュがない場合は通常処理
        update_status("音声ファイルを変換中...")
        audio_path = self.audio_processor.convert_audio(input_file)

        # 長時間音声や大容量ファイルは分割が必要かチェック
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        needs_split = (
            file_size_mb > MAX_AUDIO_SIZE_MB or
            (audio_duration_sec and audio_duration_sec > MAX_AUDIO_DURATION_SEC)
        )

        segment_files = None

        if needs_split:
            if file_size_mb > MAX_AUDIO_SIZE_MB:
                update_status(f"ファイルサイズが大きいため圧縮を実行します")
                audio_path = self.audio_processor.compress_audio(
                    audio_path, MAX_AUDIO_SIZE_MB, update_status
                )
                if not audio_path:
                    raise AudioProcessingError("音声ファイルの圧縮に失敗しました")

            # 分割処理
            update_status("音声ファイルを分割中...")
            segment_files = self.audio_processor.split_audio(audio_path, callback=update_status)
            if segment_files:
                update_status(f"{len(segment_files)}個のセグメントに分割しました")

        # キャッシュに保存
        if self.enable_cache and self.cache_manager:
            try:
                self.cache_manager.save_cache_entry(
                    input_file, audio_path, segment_files, audio_duration_sec
                )
                update_status("✓ キャッシュに保存しました")
            except Exception as e:
                logger.warning(f"キャッシュ保存エラー: {str(e)}")

        return audio_path, segment_files, False
    
    def _perform_transcription(self, audio_path, api_key, update_status, preferred_model=None, cached_segments=None):
        """文字起こしを実行"""
        # キャッシュされたセグメントがある場合は、それを使用
        if cached_segments:
            logger.info(f"キャッシュされたセグメントを使用: {len(cached_segments)}個")
            return self._perform_segmented_transcription(
                audio_path, api_key, update_status, preferred_model, cached_segments
            )

        # ファイルサイズと長さを再チェック
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path)

        needs_split = (
            file_size_mb > MAX_AUDIO_SIZE_MB or
            (audio_duration_sec and audio_duration_sec > MAX_AUDIO_DURATION_SEC)
        )

        if needs_split:
            logger.info(f"ファイル分割処理を実行: サイズ={file_size_mb:.2f}MB, 長さ={audio_duration_sec}s")
            return self._perform_segmented_transcription(audio_path, api_key, update_status, preferred_model)
        else:
            logger.info(f"単一ファイル処理を実行: サイズ={file_size_mb:.2f}MB")
            return self._perform_single_transcription(audio_path, api_key, update_status, preferred_model)
    
    def _perform_whisper_transcription(self, audio_path, update_status, whisper_model='base', cached_segments=None):
        """Whisperを使用した文字起こしを実行"""
        # キャッシュされたセグメントがある場合は、それを使用
        if cached_segments:
            logger.info(f"キャッシュされたセグメントを使用: {len(cached_segments)}個")
            return self._perform_whisper_segmented_transcription(
                audio_path, update_status, whisper_model, cached_segments
            )

        # ファイルサイズと長さをチェック
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path)

        # Whisperは大きいファイルも処理できるが、長時間の音声は分割した方が安定
        needs_split = audio_duration_sec and audio_duration_sec > MAX_AUDIO_DURATION_SEC

        if needs_split:
            logger.info(f"Whisper分割処理を実行: 長さ={audio_duration_sec}s")
            return self._perform_whisper_segmented_transcription(audio_path, update_status, whisper_model)
        else:
            logger.info(f"Whisper単一ファイル処理を実行: サイズ={file_size_mb:.2f}MB")
            return self._perform_whisper_single_transcription(audio_path, update_status, whisper_model)
    
    def _perform_single_transcription(self, audio_path, api_key, update_status, preferred_model=None):
        """単一ファイルの文字起こし"""
        genai.configure(api_key=api_key)
        model_name = self.api_utils.get_best_available_model(api_key, preferred_model)

        # 音声の長さを取得（料金計算用）
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path)

        # モデル名を目立つように表示
        logger.info(f"✓ 選択されたモデル: {model_name}")
        update_status(f"✓ 使用モデル: {model_name}")
        update_status(f"音声ファイルから文字起こし中...")

        model = genai.GenerativeModel(
            model_name,
            generation_config=AI_GENERATION_CONFIG
        )

        with open(audio_path, 'rb') as audio_file:
            audio_data = audio_file.read()

        prompt = """この音声の文字起こしを日本語でお願いします。以下の点を守って正確に書き起こしてください：

1. 話された内容をそのまま文字に起こす
2. 話者が複数いる場合は、話者の区別を表記する
3. 自然な文章の流れを保つ
4. 不明瞭な部分は[不明瞭]と記載する
5. 長い沈黙は[間]と記載する

正確性と一貫性を最優先にしてください。"""

        parts = [
            {"inline_data": {"mime_type": AUDIO_MIME_TYPE, "data": audio_data}},
            {"text": prompt}
        ]

        response = model.generate_content(parts)

        # レスポンスの安全性チェック
        self._check_response_safety(response)

        if not response.text or response.text.strip() == "":
            raise TranscriptionError("文字起こし結果が空でした")

        # トークン使用量と料金を計算・表示
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0)
            output_tokens = getattr(usage, 'candidates_token_count', 0)

            # 音声入力のため is_audio_input=True、Gemini 1.5の場合は秒数も渡す
            cost_info = calculate_gemini_cost(
                model_name, input_tokens, output_tokens,
                is_audio_input=True, audio_duration_seconds=audio_duration_sec
            )
            usage_text = format_token_usage(cost_info)
            update_status(f"トークン使用量: {usage_text}")

        return response.text
    
    def _perform_segmented_transcription(self, audio_path, api_key, update_status, preferred_model=None, cached_segments=None):
        """分割された音声ファイルの文字起こし（スマート統合付き）"""
        genai.configure(api_key=api_key)
        model_name = self.api_utils.get_best_available_model(api_key, preferred_model)

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
        
        segment_transcriptions = []
        segment_info = []
        segment_costs = []
        segment_errors = []  # エラー情報を記録
        
        try:
            for i, segment_file in enumerate(segment_files):
                update_status(f"セグメント {i+1}/{len(segment_files)} を処理中")
                
                # セグメントの文字起こし（改善版）
                result = self._transcribe_segment_enhanced(
                    segment_file, api_key, i+1, len(segment_files), model_name
                )
                
                if isinstance(result, tuple):
                    segment_transcription, cost_info = result
                    if cost_info:
                        segment_costs.append(cost_info)
                else:
                    segment_transcription = result
                
                segment_transcriptions.append(segment_transcription)
                
                # エラーチェックと記録
                if "処理エラー" in segment_transcription:
                    segment_errors.append({
                        'segment_index': i+1,
                        'error_text': segment_transcription
                    })
                
                # セグメント情報を記録（将来の拡張用）
                segment_info.append({
                    'segment_index': i,
                    'total_segments': len(segment_files),
                    'file_path': segment_file
                })
        
        finally:
            # セグメントファイルをクリーンアップ
            self._cleanup_segments(segment_files, audio_path)
            
            # エラーサマリーを記録
            if segment_errors:
                error_summary = {
                    'summary': {
                        'total_segments': len(segment_files),
                        'failed_segments': len(segment_errors),
                        'success_segments': len(segment_files) - len(segment_errors),
                        'success_rate': f"{((len(segment_files) - len(segment_errors)) / len(segment_files) * 100):.1f}%"
                    },
                    'errors': segment_errors,
                    'recommendations': [
                        "エラーが発生したセグメントは文字起こし結果に含まれていません。",
                        "エラーの詳細は各セグメントのエラーログファイルを確認してください。",
                        "エラーが続く場合は、音声ファイルの内容や品質を確認してください。"
                    ]
                }
                logger.warning(f"セグメント処理エラーサマリー: {json.dumps(error_summary, ensure_ascii=False)}")

                # ユーザーにエラーサマリーを表示
                update_status(
                    f"\n⚠️ 一部のセグメントでエラーが発生しました:\n"
                    f"- 成功: {error_summary['summary']['success_segments']}/{error_summary['summary']['total_segments']}\n"
                    f"- 失敗: {error_summary['summary']['failed_segments']}/{error_summary['summary']['total_segments']}\n"
                    f"詳細はエラーログファイルを確認してください。"
                )

                # エラーサマリーをファイルに保存
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
                    else:
                        logger.warning(f"エラーサマリーの保存先ディレクトリが見つかりません: {audio_dir}")
                except Exception as e:
                    logger.error(f"エラーサマリーの保存に失敗: {str(e)}")
        
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
    
    def _transcribe_segment_enhanced(self, segment_file, api_key, segment_num, total_segments, model_name):
        """改善された単一セグメントの文字起こし"""
        try:
            # セグメントの音声の長さを取得（料金計算用）
            segment_duration_sec = self.audio_processor.get_audio_duration(segment_file)

            model = genai.GenerativeModel(
                model_name,
                generation_config=AI_GENERATION_CONFIG
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

            response = model.generate_content(parts)

            # レスポンスの安全性チェック
            self._check_response_safety(response, segment_num=segment_num)

            if not response.text or response.text.strip() == "":
                raise TranscriptionError(f"セグメント {segment_num} の文字起こし結果が空でした")

            # トークン使用量を記録（セグメント処理では表示は控えめに）
            segment_cost_info = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', 0)
                output_tokens = getattr(usage, 'candidates_token_count', 0)
                # Gemini 1.5の場合は秒数も渡す
                segment_cost_info = calculate_gemini_cost(
                    model_name, input_tokens, output_tokens,
                    is_audio_input=True, audio_duration_seconds=segment_duration_sec
                )

            return response.text.strip(), segment_cost_info
            
        except Exception as e:
            # エラーの詳細情報を記録
            error_details = {
                'segment_num': segment_num,
                'total_segments': total_segments,
                'segment_file': segment_file,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'model': model_name
            }
            
            # エラーの種類によって詳細メッセージと対処法を作成
            error_str = str(e).lower()

            if 'audio input modality is not enabled' in error_str or 'audio input is not supported' in error_str:
                error_category = "モデル非対応"
                error_detail = "選択されたモデルは音声入力に対応していません"
                solution = "別のモデルを選択してください。Flash系モデル（gemini-2.5-flash等）の使用を推奨します。"
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
            elif 'authentication' in error_str or '401' in str(e) or '403' in str(e):
                error_category = "認証失敗"
                error_detail = "APIキーが無効または権限がありません"
                solution = "APIキーが正しく設定されているか確認してください。"
            elif 'finish_reason' in error_str and '4' in error_str:
                error_category = "著作権保護コンテンツ"
                error_detail = "音楽や著作権保護されたコンテンツが検出されました"
                solution = "音声に含まれる音楽やBGMを削除するか、別の音声ファイルを使用してください。"
            elif 'copyrighted' in error_str or '著作権' in str(e):
                error_category = "著作権保護コンテンツ"
                error_detail = "音楽や著作権保護されたコンテンツが検出されました"
                solution = "音声に含まれる音楽やBGMを削除するか、別の音声ファイルを使用してください。"
            elif 'safety' in error_str or '安全性' in str(e) or 'blocked' in error_str:
                error_category = "安全性フィルター"
                error_detail = "音声の内容が安全性基準に抵触する可能性があります"
                solution = "音声の内容を確認してください。過激な表現や不適切なコンテンツが含まれている場合、処理できません。"
            elif '500' in str(e) or 'internal' in error_str:
                error_category = "サーバーエラー"
                error_detail = f"{type(e).__name__}"
                solution = "Google側のサーバーで一時的な問題が発生しています。数分待ってから再度実行してください。"
            else:
                error_category = "予期しないエラー"
                error_detail = f"{type(e).__name__}: {str(e)}"
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

            # わかりやすいエラーメッセージを作成
            user_friendly_error = (
                f"\n⚠️ セグメント {segment_num} 処理エラー\n"
                f"エラー種別: {error_category}\n"
                f"詳細: {error_detail}\n"
                f"💡 対処法: {solution}"
            )

            logger.error(f"セグメント {segment_num} 処理エラー: {error_category} - {error_detail}")
            logger.debug(f"エラー詳細: {json.dumps(error_details, ensure_ascii=False)}")

            return f"[セグメント {segment_num} 処理エラー: {error_category} - {error_detail}]", None
    
    def _perform_whisper_single_transcription(self, audio_path, update_status, whisper_model='base'):
        """Whisperを使用した単一ファイルの文字起こし"""
        update_status(f"Whisperで文字起こし中... (モデル: {whisper_model})")
        
        try:
            # Whisperで文字起こし
            text, metadata = self.whisper_service.transcribe(
                audio_path, 
                model_name=whisper_model,
                language='ja'
            )
            
            # メタデータ情報を表示
            duration = metadata.get('duration', 0)
            segments = metadata.get('segments', 0)
            device = metadata.get('device', 'CPU')
            
            update_status(
                f"Whisper文字起こし完了: "
                f"長さ={format_duration(duration)}, "
                f"セグメント数={segments}, "
                f"デバイス={device}"
            )
            
            return text
            
        except Exception as e:
            logger.error(f"Whisper文字起こしエラー: {str(e)}")
            raise TranscriptionError(f"Whisper文字起こしに失敗しました: {str(e)}")
    
    def _perform_whisper_segmented_transcription(self, audio_path, update_status, whisper_model='base', cached_segments=None):
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
        
        try:
            for i, segment_file in enumerate(segment_files):
                update_status(f"セグメント {i+1}/{len(segment_files)} をWhisperで処理中")
                
                # Whisperでセグメントを文字起こし
                text, metadata = self.whisper_service.transcribe_segment(
                    segment_file, 
                    segment_num=i+1,
                    total_segments=len(segment_files),
                    model_name=whisper_model,
                    language='ja'
                )
                
                segment_transcriptions.append(text)
                
                # セグメント情報を記録
                segment_info.append({
                    'segment_index': i,
                    'total_segments': len(segment_files),
                    'file_path': segment_file,
                    'metadata': metadata
                })
        
        finally:
            # セグメントファイルをクリーンアップ
            self._cleanup_segments(segment_files, audio_path)
        
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
                except:
                    pass
    
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
        genai.configure(api_key=api_key)
        model_name = self.api_utils.get_best_available_model(api_key, preferred_model)

        # モデル名を表示
        logger.info(f"✓ {process_name}使用モデル: {model_name}")
        update_status(f"✓ 使用モデル: {model_name}")
        update_status(f"{process_name}を生成中...")
        
        prompt = prompts[process_type]["prompt"].replace("{transcription}", transcription)
        
        model = genai.GenerativeModel(
            model_name,
            generation_config=AI_GENERATION_CONFIG
        )
        
        response = model.generate_content(prompt)
        if not response.text:
            raise TranscriptionError(f"{process_name}の生成に失敗しました")
        
        # トークン使用量と料金を計算・表示（テキスト処理）
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0)
            output_tokens = getattr(usage, 'candidates_token_count', 0)
            
            # テキスト処理のため is_audio_input=False
            cost_info = calculate_gemini_cost(model_name, input_tokens, output_tokens, is_audio_input=False)
            usage_text = format_token_usage(cost_info)
            update_status(f"{process_name}トークン使用量: {usage_text}")
        
        return response.text
    
    def _save_result(self, input_file, final_text, process_type, prompts, start_time, update_status):
        """結果をファイルに保存"""
        timestamp = get_timestamp()
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        
        # process_typeがプロンプトに存在しない場合はデフォルト名を使用
        if process_type in prompts:
            process_name = prompts[process_type]["name"]
        else:
            process_name = "文字起こし"
        
        output_filename = f"{base_name}_{process_name}_{timestamp}.txt"
        output_path = os.path.join(self.output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        # 処理完了のログ
        end_time = datetime.datetime.now()
        process_time = end_time - start_time
        process_seconds = process_time.total_seconds()
        process_time_str = f"{int(process_seconds // 60)}分{int(process_seconds % 60)}秒"
        
        output_size_kb = os.path.getsize(output_path) / 1024
        update_status(
            f"処理完了: {output_filename}\n"
            f"- 処理時間: {process_time_str}\n"
            f"- 出力ファイルサイズ: {output_size_kb:.2f}KB"
        )
        
        return output_path
    
    def process_transcription_file(self, transcription_file, prompt_key, api_key, prompts, status_callback=None):
        """文字起こしファイルの追加処理を実行"""
        start_time = datetime.datetime.now()
        
        def update_status(message):
            logger.info(message)
            if status_callback:
                status_callback(message)
        
        try:
            # 文字起こしファイルを読み込み
            file_size_kb = os.path.getsize(transcription_file) / 1024
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
            genai.configure(api_key=api_key)
            model_name = self.api_utils.get_best_available_model(api_key)

            # モデル名を表示
            logger.info(f"✓ {process_name}使用モデル: {model_name}")
            update_status(f"✓ 使用モデル: {model_name}")
            update_status(f"{process_name}を生成中...")
            
            model = genai.GenerativeModel(
                model_name,
                generation_config=AI_GENERATION_CONFIG
            )
            
            # プロンプトに文字起こし結果を埋め込む
            prompt = prompt_info["prompt"].replace("{transcription}", transcription)
            
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
            process_time = end_time - start_time
            process_seconds = process_time.total_seconds()
            process_time_str = f"{int(process_seconds // 60)}分{int(process_seconds % 60)}秒"
            
            output_size_kb = os.path.getsize(output_path) / 1024
            update_status(
                f"処理完了: {os.path.basename(output_path)}\n"
                f"- 元ファイルサイズ: {file_size_kb:.1f}KB\n"
                f"- 処理時間: {process_time_str}\n"
                f"- 使用モデル: {model_name}"
            )
            
            return output_path
            
        except Exception as e:
            update_status(f"処理エラー: {str(e)}")
            raise FileProcessingError(f"文字起こしファイルの処理に失敗しました: {str(e)}")
