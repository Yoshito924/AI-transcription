#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import datetime
import json
from pathlib import Path

class FileProcessor:
    """音声/動画ファイルの処理を行うクラス"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
    
    def test_api_connection(self, api_key):
        """GeminiAPIの接続テスト"""
        try:
            # ここに実際のAPI接続コードを実装
            # 例:
            # import google.generativeai as genai
            # genai.configure(api_key=api_key)
            # model = genai.GenerativeModel('gemini-pro')
            # response = model.generate_content("Hello, World!")
            
            # テスト用（実際のAPI実装時に置き換える）
            if not api_key or len(api_key) < 10:
                raise ValueError("無効なAPIキーです")
                
            return True
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
    
    def process_file(self, input_file, process_type, api_key, prompts, status_callback=None):
        """ファイルを処理し、結果を返す"""
        # ステータス更新ユーティリティ
        def update_status(message):
            print(message)  # コンソール出力
            if status_callback:
                status_callback(message)
        
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
            
            # ここでGemini APIを使った実際の文字起こし処理を実装
            # 実際のAPIコールは以下のようになります
            # import google.generativeai as genai
            # genai.configure(api_key=api_key)
            # model = genai.GenerativeModel('gemini-pro')
            
            # テスト用のデモ処理（実際のAPI実装時に置き換え）
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            current_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
            
            # デモ用の文字起こし結果
            transcription = self._get_demo_transcription(base_name, current_time)
            
            # 追加処理が必要な場合
            final_text = transcription
            if process_type != "transcription":
                process_name = prompts[process_type]["name"]
                update_status(f"{process_name}を生成中...")
                
                # プロンプトに文字起こし結果を埋め込む
                prompt = prompts[process_type]["prompt"].replace("{transcription}", transcription)
                
                # 実際のAPIコール
                # response = model.generate_content(prompt)
                # final_text = response.text
                
                # デモ用の処理結果
                final_text = self._get_demo_result(process_type, base_name, current_time)
            
            # 出力ファイルパス
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            process_name = prompts[process_type]["name"]
            output_filename = f"{base_name}_{process_name}_{timestamp}.txt"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # ファイル出力
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_text)
            
            update_status(f"処理が完了しました: {output_filename}")
            
            return output_path
            
        finally:
            # 一時ファイルの削除
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _get_demo_transcription(self, file_name, time_str):
        """デモ用の文字起こし結果を生成"""
        return f"""# {file_name} 文字起こし結果
処理日時: {time_str}

これはデモンストレーション用の文字起こし結果です。
実際のアプリケーションでは、Gemini APIを使用して音声ファイルの内容を文字起こしします。

この例では、「{file_name}」という音声ファイルが選択されました。
実際のアプリでは、ここに実際の文字起こし内容が表示されます。

音声ファイルは128kbpsのMP3形式に変換されてから処理されます。
変換された音声データは一時ファイルとして保存され、処理後に削除されます。

---

これはサンプルテキストです。実際の文字起こし結果はGemini APIを使用して生成されます。
"""
    
    def _get_demo_result(self, process_type, file_name, time_str):
        """デモ用の処理結果を生成"""
        if process_type == "meeting_minutes":
            return f"""# {file_name} 議事録
処理日時: {time_str}

## 概要
- これはデモ用の議事録です
- 実際のアプリケーションでは、Gemini APIを使って生成されます

## 重要ポイント
1. 項目1: 重要な議論ポイント
2. 項目2: 議論された主要なトピック
3. 項目3: チームからの質問や懸念事項

## 決定事項
- 決定1: 次のステップについての合意
- 決定2: リソース割り当ての承認

## アクションアイテム
- [ ] アクション1: 担当者A、期限: 2週間以内
- [ ] アクション2: 担当者B、期限: 1ヶ月以内
- [ ] アクション3: 全員、期限: 次回ミーティングまでに

---

これはデモ用の議事録です。実際の議事録はGemini APIによって、元の文字起こしから生成されます。
"""
        elif process_type == "summary":
            return f"""# {file_name} 要約
処理日時: {time_str}

これはデモ用の要約です。実際のアプリケーションでは、Gemini APIを使って文字起こしテキストから300字程度の要約が生成されます。

要約には、ディスカッションの主要ポイント、重要な決定事項、および今後の計画についての簡潔な説明が含まれます。これは長い議事録や会議の内容を素早く把握するために役立ちます。

実際のアプリでは、AIによって生成された、より正確で簡潔な要約が提供されます。
"""
        else:
            return self._get_demo_transcription(file_name, time_str)
