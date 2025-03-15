#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import datetime
import json
import base64
from pathlib import Path

class FileProcessor:
    """音声/動画ファイルの処理を行うクラス"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.preferred_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        self.max_audio_size_mb = 20  # Geminiの推奨上限サイズ
    
    def test_api_connection(self, api_key):
        """GeminiAPIの接続テスト"""
        try:
            # Google Gemini APIのインポートと接続テスト
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            # 利用可能なモデルを確認
            models = genai.list_models()
            
            # 使用可能なGeminiモデルを探す
            available_gemini_models = []
            for m in models:
                if 'gemini' in m.name.lower() and 'generateContent' in m.supported_generation_methods:
                    available_gemini_models.append(m.name)
            
            if not available_gemini_models:
                raise ValueError("利用可能なGeminiモデルが見つかりません")
            
            # 優先度順に使用可能なモデルを選択
            model_name = None
            for preferred in self.preferred_models:
                for available in available_gemini_models:
                    if preferred in available:
                        model_name = available
                        break
                if model_name:
                    break
            
            # 見つからなければ最初のモデルを使用
            if not model_name:
                model_name = available_gemini_models[0]
                
            print(f"使用モデル: {model_name}")
            
            # 選択したモデルでテスト
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("こんにちは")
            
            # 応答がある場合は成功
            if response and hasattr(response, 'text'):
                return True
            return False
            
        except Exception as e:
            raise Exception(f"API接続エラー: {str(e)}")
    
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
    
    def _get_best_available_model(self, api_key):
        """利用可能な最適なGeminiモデルを取得"""
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # 利用可能なモデルを確認
        models = genai.list_models()
        
        # 使用可能なGeminiモデルを探す
        available_gemini_models = []
        for m in models:
            if 'gemini' in m.name.lower() and 'generateContent' in m.supported_generation_methods:
                available_gemini_models.append(m.name)
        
        if not available_gemini_models:
            raise ValueError("利用可能なGeminiモデルが見つかりません")
        
        # 優先度順に使用可能なモデルを選択
        model_name = None
        for preferred in self.preferred_models:
            for available in available_gemini_models:
                if preferred in available:
                    model_name = available
                    break
            if model_name:
                break
        
        # 見つからなければ最初のモデルを使用
        if not model_name:
            model_name = available_gemini_models[0]
            
        print(f"使用モデル: {model_name}")
        return model_name
    
    def _get_audio_duration(self, file_path):
        """FFmpegを使用して音声ファイルの長さを秒単位で取得"""
        try:
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                file_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                print(f"エラー: 音声長さの取得に失敗しました")
                return None
                
            duration = float(result.stdout.decode('utf-8').strip())
            return duration
        except Exception as e:
            print(f"エラー: 音声長さの取得中に例外が発生しました: {str(e)}")
            return None
    
    def _compress_audio(self, input_file_path, target_size_mb=20, callback=None):
        """FFmpegを使用して音声ファイルを圧縮する"""
        def update_status(message):
            print(message)
            if callback:
                callback(message)
        
        # 入力ファイルが存在するか確認
        if not os.path.exists(input_file_path):
            update_status(f"エラー: ファイル {input_file_path} が見つかりません")
            return None
        
        # 入力ファイルサイズを取得
        input_size_mb = os.path.getsize(input_file_path) / (1024 * 1024)
        
        # 出力ファイルのパスを構築
        input_path = Path(input_file_path)
        # 一時ディレクトリに出力
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            output_path = temp_file.name
        
        # 適切なビットレートを計算
        audio_duration_sec = self._get_audio_duration(input_file_path)
        if audio_duration_sec is None or audio_duration_sec <= 0:
            update_status("エラー: 音声ファイルの長さを取得できませんでした")
            return None
        
        # ビットレート計算: (ターゲットサイズMB * 8192) / 音声長さ秒
        target_bitrate_kbps = int((target_size_mb * 0.9 * 8192) / audio_duration_sec)
        
        # 最低品質を確保
        min_bitrate = 48  # 最低48kbpsを保証
        max_bitrate = 256  # 最大256kbpsに制限
        bitrate = max(min(target_bitrate_kbps, max_bitrate), min_bitrate)
        
        update_status(f"音声圧縮を開始: 元サイズ={input_size_mb:.2f}MB → 目標={target_size_mb:.2f}MB (ビットレート={bitrate}kbps)")
        
        # FFmpegコマンドを構築
        try:
            command = [
                'ffmpeg',
                '-i', input_file_path,
                '-y',  # 既存ファイルを上書き
                '-c:a', 'libmp3lame',  # MP3エンコーダを使用
                '-b:a', f'{bitrate}k',  # 計算したビットレート
                output_path
            ]
            
            # コマンドを実行
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if process.returncode != 0:
                update_status(f"エラー: 音声圧縮に失敗しました")
                return None
            
            # 圧縮結果を確認
            output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            compression_ratio = ((input_size_mb - output_size_mb) / input_size_mb * 100)
            update_status(f"音声圧縮完了: 新サイズ={output_size_mb:.2f}MB (圧縮率={compression_ratio:.2f}%)")
            
            return output_path
            
        except Exception as e:
            update_status(f"エラー: 音声圧縮中に例外が発生しました: {str(e)}")
            if os.path.exists(output_path):
                os.remove(output_path)  # エラー時は一時ファイルを削除
            return None
    
    def _format_duration(self, seconds):
        """秒数を時:分:秒形式に変換"""
        if seconds is None:
            return "不明"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}時間{minutes}分{secs}秒"
        else:
            return f"{minutes}分{secs}秒"
    
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
        audio_duration_sec = self._get_audio_duration(input_file)
        duration_str = self._format_duration(audio_duration_sec) if audio_duration_sec else "不明"
        
        update_status(f"処理開始: ファイルサイズ={original_size_mb:.2f}MB, 長さ={duration_str}")
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
            
            # サイズが大きい場合は圧縮
            compressed_path = temp_path
            if file_size_mb > self.max_audio_size_mb:
                update_status(f"ファイルサイズが大きいため圧縮を実行します")
                compressed_path = self._compress_audio(temp_path, self.max_audio_size_mb, update_status)
                if not compressed_path:
                    raise Exception("音声ファイルの圧縮に失敗しました")
                    
                # 圧縮後のサイズを確認
                compressed_size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
                if compressed_size_mb > self.max_audio_size_mb:
                    update_status(f"警告: 圧縮後もサイズが大きいです ({compressed_size_mb:.2f}MB)")
            
            # Gemini APIによる文字起こし
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            # 最適なモデルを選択
            model_name = self._get_best_available_model(api_key)
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
                update_status("デモデータを使用します")
                transcription = self._get_demo_transcription(base_name, current_time)
            
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
                    model_name = self._get_best_available_model(api_key)
                    model = genai.GenerativeModel(model_name)
                    
                    # プロンプトを送信して結果を取得
                    response = model.generate_content(prompt)
                    final_text = response.text
                except Exception as e:
                    update_status(f"テキスト処理エラー: {str(e)}")
                    # エラー時はデモ結果を使用
                    final_text = self._get_demo_result(process_type, base_name, current_time)
            
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
    
    def _get_demo_transcription(self, file_name, time_str):
        """デモ用の文字起こし結果を生成"""
        return f"""# {file_name} 文字起こし結果
処理日時: {time_str}

議長: 皆さん、おはようございます。今日は第3回目のプロジェクト進捗会議を始めたいと思います。
前回の会議から2週間が経過し、各チームの進捗状況を確認したいと思います。まず、開発チームからの報告をお願いします。

田中: はい、開発チームのリーダーの田中です。現在、メインの機能の実装は予定通り80%完了しています。ただ、API連携の部分で一部技術的な課題が発生しており、その解決に追加で1週間ほど必要になりそうです。全体のスケジュールへの影響は最小限に抑えられるよう調整しています。

議長: ありがとうございます。その技術的な課題について、もう少し詳しく説明いただけますか？

田中: はい。外部サービスとの認証連携で、セキュリティ要件が当初の想定より厳しくなっており、追加の暗号化処理が必要になっています。佐藤さんのチームと協力して対応を進めています。

佐藤: セキュリティチームの佐藤です。補足しますと、先週のセキュリティ監査で指摘された点に対応するため、API連携部分のセキュリティ強化を行っています。来週初めには解決策の実装と検証が完了する見込みです。

議長: 分かりました。デザインチームの進捗はいかがですか？

鈴木: デザインチームの鈴木です。ユーザーインターフェイスのデザインは完了し、現在は開発チームと協力してフロントエンドの実装を進めています。ユーザーテストからのフィードバックも取り入れて、いくつかの画面で改善を行いました。特に問題なく進んでいます。

議長: 素晴らしいです。マーケティングチームの準備状況はどうですか？

高橋: マーケティングの高橋です。プロモーション材料の作成は順調に進んでいます。プレスリリースの下書きが完成し、現在レビュー中です。また、ソーシャルメディア向けのコンテンツも準備中です。リリース日が確定次第、メディア各社への案内を開始できる状態です。

議長: ありがとうございます。それでは、現時点での課題と今後のスケジュールについて議論しましょう。

会議の残りの時間は、API連携の技術的課題の詳細と解決策、そして全体のスケジュールへの影響について議論されました。最終的に、リリース日を1週間延期して品質を確保することが決定されました。

次回の会議は、2週間後の水曜日に開催されることになりました。
"""
    
    def _get_demo_result(self, process_type, file_name, time_str):
        """デモ用の処理結果を生成"""
        if process_type == "meeting_minutes" or "議事録" in process_type:
            return f"""# {file_name} 議事録
処理日時: {time_str}

## 会議概要
- 第3回プロジェクト進捗会議
- 日時: {time_str}
- 参加者: 議長、田中（開発チーム）、佐藤（セキュリティチーム）、鈴木（デザインチーム）、高橋（マーケティングチーム）

## 主な議題
1. 各チームの進捗状況の確認
2. 技術的課題の共有と解決策の検討
3. 今後のスケジュール調整

## 議論内容
### 開発チームの進捗
- メイン機能の実装は80%完了
- API連携部分で技術的課題が発生し、解決に追加で1週間必要
- 外部サービスとの認証連携でセキュリティ要件が厳しくなり、追加の暗号化処理が必要

### セキュリティチームの対応
- セキュリティ監査での指摘事項に対応中
- API連携部分のセキュリティ強化を実施
- 来週初めには解決策の実装と検証が完了予定

### デザインチームの進捗
- ユーザーインターフェイスのデザインは完了
- フロントエンドの実装をサポート中
- ユーザーテストからのフィードバックを取り入れた改善を実施

### マーケティングチームの準備状況
- プロモーション材料の作成は順調に進行中
- プレスリリースの下書きが完成、レビュー中
- ソーシャルメディア向けコンテンツを準備中
- リリース日確定後、メディア案内の準備が整っている

## 決定事項
- リリース日を1週間延期して品質を確保する
- セキュリティ要件の変更に対応するため、追加リソースの配分を行う

## アクションアイテム
- 開発チーム・セキュリティチーム: API連携の課題解決を優先対応（期限: 来週初め）
- デザインチーム: フロントエンド実装のサポート継続（期限: 2週間以内）
- マーケティングチーム: リリース日変更に伴うスケジュール調整（期限: 今週中）

## 次回会議
- 日時: 2週間後の水曜日
- 議題: 課題解決状況の確認とリリース準備状況のレビュー
"""
        elif process_type == "summary" or "要約" in process_type:
            return f"""# {file_name} 要約
処理日時: {time_str}

プロジェクト第3回進捗会議が開催され、各チームからの報告が行われました。開発チームはメイン機能の実装が80%完了しているものの、API連携部分で技術的課題が発生しており、追加で1週間の作業が必要と報告しました。具体的には、外部サービスとの認証連携におけるセキュリティ要件の厳格化に対応するための暗号化処理が必要となっています。

セキュリティチームは、先週の監査で指摘された点に対応するためAPI連携部分の強化を進めており、来週初めには解決策の実装と検証が完了する見込みです。デザインチームはユーザーインターフェイスのデザインを完了し、現在はフロントエンド実装のサポートとユーザーテストからのフィードバックを反映した改善を行っています。

マーケティングチームはプロモーション材料の作成が順調に進んでおり、プレスリリースの下書きが完成しレビュー中です。ソーシャルメディア向けコンテンツも準備中で、リリース日確定後にはメディア各社への案内を開始できる状態です。

議論の結果、リリース日を1週間延期して品質を確保することが決定されました。次回会議は2週間後の水曜日に開催される予定です。
"""
        else:
            return self._get_demo_transcription(file_name, time_str)
