#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import datetime
import subprocess
from pathlib import Path

from src.audio_processor import AudioProcessor
from src.api_utils import ApiUtils

class FileProcessor:
    """音声/動画ファイルの処理を行うクラス"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.max_audio_size_mb = 20  # Geminiの推奨上限サイズ
        self.max_audio_duration_sec = 1200  # 20分（1200秒）を超える場合は分割
        self.audio_processor = AudioProcessor(self.max_audio_size_mb)
        self.api_utils = ApiUtils()
    
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
    
    def process_file(self, input_file, process_type, api_key, prompts, status_callback=None):
        """ファイルを処理し、結果を返す"""
        # 開始時間を記録
        start_time = datetime.datetime.now()
        
        # ステータス更新ユーティリティ
        def update_status(message):
            print(message)  # コンソール出力
            if status_callback:
                status_callback(message)
        
        # 元のファイルサイズを取得
        original_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        
        # 音声の長さを取得
        audio_duration_sec = self.audio_processor.get_audio_duration(input_file)
        duration_str = self.audio_processor.format_duration(audio_duration_sec) if audio_duration_sec else "不明"
        
        # 音声の長さが20分を超えるかチェック
        needs_split_by_duration = audio_duration_sec and audio_duration_sec > self.max_audio_duration_sec
        
        update_status(f"処理開始: ファイルサイズ={original_size_mb:.2f}MB, 長さ={duration_str}")
        if needs_split_by_duration:
            update_status(f"音声の長さが{self.audio_processor.format_duration(self.max_audio_duration_sec)}を超えるため、分割処理が必要です")
        update_status("音声ファイルを変換中...")
        
        # 一時ファイル作成
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # FFmpegで音声変換（128kbps MP3）
            result = subprocess.run([
                'ffmpeg', '-y', '-i', input_file, 
                '-vn', '-ar', '44100', '-ac', '2', '-b:a', '128k', temp_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='replace')
                raise Exception(f"FFmpeg変換エラー: {error_msg}")
            
            update_status("文字起こし中...")
            
            # ファイルサイズをチェック
            file_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
            update_status(f"音声ファイルサイズ: {file_size_mb:.2f}MB")
            
            # サイズが大きい場合は圧縮（目標サイズに達するまで繰り返し圧縮）
            compressed_path = temp_path
            if file_size_mb > self.max_audio_size_mb:
                update_status(f"ファイルサイズが大きいため圧縮を実行します")
                compressed_path = self.audio_processor.compress_audio(temp_path, self.max_audio_size_mb, update_status, max_attempts=3)
                if not compressed_path:
                    raise Exception("音声ファイルの圧縮に失敗しました")
                    
                # 圧縮後の最終サイズを確認
                compressed_size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
                update_status(f"最終圧縮サイズ: {compressed_size_mb:.2f}MB")
                
                # 圧縮後もサイズが大きい場合、または音声の長さが長い場合は分割処理
                if compressed_size_mb > self.max_audio_size_mb or needs_split_by_duration:
                    if compressed_size_mb > self.max_audio_size_mb:
                        update_status(f"圧縮後もサイズが大きいため、ファイルを分割して処理します")
                    elif needs_split_by_duration:
                        update_status(f"音声の長さが長いため、ファイルを分割して処理します")
                    
                    # 音声ファイルを分割（10分ごと）
                    segment_files = self.audio_processor.split_audio(compressed_path, 600, update_status)
                    if not segment_files:
                        raise Exception("音声ファイルの分割に失敗しました")
                    
                    update_status(f"{len(segment_files)}個のセグメントに分割しました")
                    
                    # 各セグメントを処理
                    all_transcriptions = []
                    
                    for i, segment_file in enumerate(segment_files):
                        segment_size_mb = os.path.getsize(segment_file) / (1024 * 1024)
                        update_status(f"セグメント {i+1}/{len(segment_files)} を処理中（サイズ: {segment_size_mb:.2f}MB）")
                        
                        # セグメントが大きい場合は圧縮
                        segment_compressed = segment_file
                        if segment_size_mb > self.max_audio_size_mb:
                            update_status(f"セグメント {i+1} のサイズが大きいため圧縮します")
                            segment_compressed = self.audio_processor.compress_audio(segment_file, self.max_audio_size_mb, update_status, max_attempts=2)
                            if not segment_compressed:
                                update_status(f"警告: セグメント {i+1} の圧縮に失敗しました。元のセグメントを使用します。")
                                segment_compressed = segment_file
                        
                        # セグメントの文字起こし
                        try:
                            # 音声データを読み込み
                            with open(segment_compressed, 'rb') as audio_file:
                                audio_data = audio_file.read()
                            
                            # MIMEタイプを決定
                            mime_type = 'audio/mpeg'  # MP3形式を想定
                            
                            # プロンプト準備
                            transcription_prompt = f"この音声（セグメント {i+1}/{len(segment_files)}）の文字起こしを日本語でお願いします。できるだけ正確に書き起こしてください。話者が複数いる場合は、話者の区別を表記してください。"
                            
                            # インラインデータ形式でリクエスト
                            parts = [
                                {"inline_data": {"mime_type": mime_type, "data": audio_data}},
                                {"text": transcription_prompt}
                            ]
                            
                            # 文字起こしを実行
                            import google.generativeai as genai
                            model = genai.GenerativeModel(self.api_utils.get_best_available_model(api_key))
                            response = model.generate_content(parts)
                            segment_transcription = response.text
                            
                            if not segment_transcription or segment_transcription.strip() == "":
                                raise Exception(f"セグメント {i+1} の文字起こし結果が空でした")
                            
                            # セグメント番号を追加
                            segment_header = f"\n\n## セグメント {i+1}/{len(segment_files)}\n\n"
                            all_transcriptions.append(segment_header + segment_transcription)
                            
                        except Exception as segment_err:
                            update_status(f"セグメント {i+1} の文字起こしエラー: {str(segment_err)}")
                            all_transcriptions.append(f"\n\n## セグメント {i+1}/{len(segment_files)} (エラー)\n\n処理中にエラーが発生しました: {str(segment_err)}")
                        
                        # 使用済みのセグメントファイルを削除（最初の入力ファイルは除く）
                        if segment_file != compressed_path and os.path.exists(segment_file):
                            try:
                                os.unlink(segment_file)
                            except:
                                pass
                        if segment_compressed != segment_file and segment_compressed != compressed_path and os.path.exists(segment_compressed):
                            try:
                                os.unlink(segment_compressed)
                            except:
                                pass
                    
                    # 全セグメントの文字起こし結果を結合
                    base_name = os.path.splitext(os.path.basename(input_file))[0]
                    current_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
                    
                    # ヘッダーを追加
                    header = f"# {base_name} 文字起こし結果（分割処理）\n処理日時: {current_time}\n\n"
                    transcription = header + "".join(all_transcriptions)
                    
                    update_status("全セグメントの文字起こしが完了しました")
                    
                    # 以降の処理をスキップするためのフラグ
                    is_segmented = True
                else:
                    is_segmented = False
            
            # 分割処理を行わなかった場合は通常の文字起こし処理
            is_segmented = False
            if 'is_segmented' not in locals() or not is_segmented:
                # Gemini APIによる文字起こし
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # 最適なモデルを選択
                model_name = self.api_utils.get_best_available_model(api_key)
                model = genai.GenerativeModel(model_name)
                
                # ファイル名と時間情報
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                current_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
                
                # 文字起こし処理
                update_status("音声ファイルから文字起こし中...")
                
                try:
                    # 音声データを読み込み
                    with open(compressed_path, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    # MIMEタイプを決定
                    mime_type = 'audio/mpeg'  # MP3形式を想定
                    
                    # プロンプト準備
                    transcription_prompt = "この音声の文字起こしを日本語でお願いします。できるだけ正確に書き起こしてください。話者が複数いる場合は、話者の区別を表記してください。"
                    
                    # インラインデータ形式でリクエスト
                    parts = [
                        {"inline_data": {"mime_type": mime_type, "data": audio_data}},
                        {"text": transcription_prompt}
                    ]
                    
                    # 文字起こしを実行
                    response = model.generate_content(parts)
                    transcription = response.text
                    
                    if not transcription or transcription.strip() == "":
                        raise Exception("文字起こし結果が空でした")
                    
                except Exception as audio_err:
                    update_status(f"文字起こしエラー: {str(audio_err)}")
                    raise Exception(f"文字起こし処理に失敗しました: {str(audio_err)}")
                
                update_status("文字起こし完了、結果を処理中...")
            
            # 追加処理が必要な場合
            final_text = transcription
            if process_type != "transcription":
                # この部分で、process_typeがpromptsに存在するか確認
                if process_type not in prompts:
                    raise Exception(f"指定された処理タイプ '{process_type}' はプロンプト設定に存在しません")
                
                process_name = prompts[process_type]["name"]
                update_status(f"{process_name}を生成中...")
                
                # プロンプトに文字起こし結果を埋め込む
                prompt = prompts[process_type]["prompt"].replace("{transcription}", transcription)
                
                # 実際のAPIコール
                try:
                    # 最適なモデルを使用
                    model_name = self.api_utils.get_best_available_model(api_key)
                    model = genai.GenerativeModel(model_name)
                    
                    # プロンプトを送信して結果を取得
                    response = model.generate_content(prompt)
                    final_text = response.text
                except Exception as e:
                    update_status(f"テキスト処理エラー: {str(e)}")
                    raise Exception(f"テキスト処理に失敗しました: {str(e)}")
            
            # 出力ファイルパス
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # process_typeがプロンプトに存在しない場合はデフォルト名を使用
            if process_type in prompts:
                process_name = prompts[process_type]["name"]
            else:
                process_name = "文字起こし"
                
            output_filename = f"{base_name}_{process_name}_{timestamp}.txt"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # ファイル出力
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_text)
            
            # 処理完了時間を記録
            end_time = datetime.datetime.now()
            process_time = end_time - start_time
            process_seconds = process_time.total_seconds()
            
            # 処理時間を分:秒形式に
            process_time_str = f"{int(process_seconds // 60)}分{int(process_seconds % 60)}秒"
            
            # 詳細なログメッセージ
            log_message = (
                f"処理完了: {output_filename}\n"
                f"- 元ファイルサイズ: {original_size_mb:.2f}MB\n"
                f"- 音声の長さ: {duration_str}\n"
                f"- 処理時間: {process_time_str}\n"
                f"- 使用モデル: {model_name}"
            )
            
            update_status(log_message)
            
            return output_path
            
        except Exception as e:
            update_status(f"処理エラー: {str(e)}")
            raise e
        finally:
            # 一時ファイルの削除
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                if 'compressed_path' in locals() and compressed_path != temp_path and os.path.exists(compressed_path):
                    os.unlink(compressed_path)
            except:
                pass
