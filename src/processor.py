#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import datetime
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
from .text_merger import EnhancedTextMerger
from .utils import get_timestamp, format_duration, calculate_gemini_cost, format_token_usage

class FileProcessor:
    """音声/動画ファイルの処理を行うクラス"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.audio_processor = AudioProcessor()
        self.api_utils = ApiUtils()
        self.text_merger = EnhancedTextMerger(
            overlap_threshold=SEGMENT_MERGE_CONFIG['overlap_threshold'],
            min_overlap_words=SEGMENT_MERGE_CONFIG['min_overlap_words'],
            enable_context_analysis=SEGMENT_MERGE_CONFIG['enable_context_analysis']
        )
    
    def test_api_connection(self, api_key):
        """GeminiAPIの接続テスト"""
        return self.api_utils.test_api_connection(api_key)
    
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
    
    def process_file(self, input_file, process_type, api_key, prompts, status_callback=None, preferred_model=None):
        """ファイルを処理し、結果を返す"""
        start_time = datetime.datetime.now()
        
        def update_status(message):
            print(message)
            if status_callback:
                status_callback(message)
        
        try:
            # 音声ファイルの準備
            audio_path = self._prepare_audio_file(input_file, update_status)
            
            # 文字起こし実行
            transcription = self._perform_transcription(audio_path, api_key, update_status, preferred_model)
            
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
            update_status(f"処理エラー: {str(e)}")
            raise FileProcessingError(f"ファイル処理に失敗しました: {str(e)}")
    
    def _prepare_audio_file(self, input_file, update_status):
        """音声ファイルの準備（変換・圧縮・分割）"""
        # 元のファイル情報を取得
        original_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        audio_duration_sec = self.audio_processor.get_audio_duration(input_file)
        duration_str = format_duration(audio_duration_sec) if audio_duration_sec else "不明"
        
        update_status(f"処理開始: ファイルサイズ={original_size_mb:.2f}MB, 長さ={duration_str}")
        
        # 音声変換
        update_status("音声ファイルを変換中...")
        audio_path = self.audio_processor.convert_audio(input_file)
        
        # 長時間音声や大容量ファイルは分割が必要かチェック
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        needs_split = (
            file_size_mb > MAX_AUDIO_SIZE_MB or 
            (audio_duration_sec and audio_duration_sec > MAX_AUDIO_DURATION_SEC)
        )
        
        if needs_split:
            if file_size_mb > MAX_AUDIO_SIZE_MB:
                update_status(f"ファイルサイズが大きいため圧縮を実行します")
                audio_path = self.audio_processor.compress_audio(
                    audio_path, MAX_AUDIO_SIZE_MB, update_status
                )
                if not audio_path:
                    raise AudioProcessingError("音声ファイルの圧縮に失敗しました")
        
        return audio_path
    
    def _perform_transcription(self, audio_path, api_key, update_status, preferred_model=None):
        """文字起こしを実行"""
        # ファイルサイズと長さを再チェック
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        audio_duration_sec = self.audio_processor.get_audio_duration(audio_path)
        
        needs_split = (
            file_size_mb > MAX_AUDIO_SIZE_MB or 
            (audio_duration_sec and audio_duration_sec > MAX_AUDIO_DURATION_SEC)
        )
        
        if needs_split:
            return self._perform_segmented_transcription(audio_path, api_key, update_status, preferred_model)
        else:
            return self._perform_single_transcription(audio_path, api_key, update_status, preferred_model)
    
    def _perform_single_transcription(self, audio_path, api_key, update_status, preferred_model=None):
        """単一ファイルの文字起こし"""
        genai.configure(api_key=api_key)
        model_name = self.api_utils.get_best_available_model(api_key, preferred_model)
        
        update_status(f"音声ファイルから文字起こし中... (使用モデル: {model_name})")
        
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
        if not response.text or response.text.strip() == "":
            raise TranscriptionError("文字起こし結果が空でした")
        
        # トークン使用量と料金を計算・表示
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0)
            output_tokens = getattr(usage, 'candidates_token_count', 0)
            
            # 音声入力のため is_audio_input=True
            cost_info = calculate_gemini_cost(model_name, input_tokens, output_tokens, is_audio_input=True)
            usage_text = format_token_usage(cost_info)
            update_status(f"トークン使用量: {usage_text}")
        
        return response.text
    
    def _perform_segmented_transcription(self, audio_path, api_key, update_status, preferred_model=None):
        """分割された音声ファイルの文字起こし（スマート統合付き）"""
        genai.configure(api_key=api_key)
        model_name = self.api_utils.get_best_available_model(api_key, preferred_model)
        
        update_status(f"音声の長さが長いため、ファイルを分割して処理します (使用モデル: {model_name})")
        
        # 音声を分割
        segment_files = self.audio_processor.split_audio(audio_path, callback=update_status)
        if not segment_files:
            raise AudioProcessingError("音声ファイルの分割に失敗しました")
        
        update_status(f"{len(segment_files)}個のセグメントに分割しました")
        
        segment_transcriptions = []
        segment_info = []
        segment_costs = []
        
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
                
                # セグメント情報を記録（将来の拡張用）
                segment_info.append({
                    'segment_index': i,
                    'total_segments': len(segment_files),
                    'file_path': segment_file
                })
        
        finally:
            # セグメントファイルをクリーンアップ
            self._cleanup_segments(segment_files, audio_path)
        
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
            if not response.text or response.text.strip() == "":
                raise TranscriptionError(f"セグメント {segment_num} の文字起こし結果が空でした")
            
            # トークン使用量を記録（セグメント処理では表示は控えめに）
            segment_cost_info = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', 0)
                output_tokens = getattr(usage, 'candidates_token_count', 0)
                segment_cost_info = calculate_gemini_cost(model_name, input_tokens, output_tokens, is_audio_input=True)
            
            return response.text.strip(), segment_cost_info
            
        except Exception as e:
            return f"[セグメント {segment_num} 処理エラー: {str(e)}]", None
    
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
        
        process_name = prompts[process_type]["name"]
        genai.configure(api_key=api_key)
        model_name = self.api_utils.get_best_available_model(api_key, preferred_model)
        
        update_status(f"{process_name}を生成中... (使用モデル: {model_name})")
        
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
            print(message)
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
            
            update_status(f"{process_name}を生成中... (使用モデル: {model_name})")
            
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
