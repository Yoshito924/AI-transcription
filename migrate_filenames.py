#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
既存の文字起こしファイルのファイル名に要約タイトルを付けるマイグレーションスクリプト

使い方:
  python migrate_filenames.py              # ドライラン（変更内容を表示するだけ）
  python migrate_filenames.py --execute    # 実際にリネームを実行
"""

import os
import re
import sys
import time

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import google.generativeai as genai
from src.constants import SUMMARY_TITLE_MAX_LENGTH, TITLE_GENERATION_MODELS
from src.utils import sanitize_filename


OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# 旧形式のパターン: {元ファイル名}_文字起こし_{YYYYMMDD}_{HHMMSS}.txt
OLD_PATTERN = re.compile(r'^(.+?)_(文字起こし)_(\d{8}_\d{6})\.txt$')


def get_api_key():
    """Gemini APIキーを取得"""
    # 設定ファイルから読み込み
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
    if os.path.exists(config_path):
        import json
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        api_key = config.get("api_key", "") or config.get("gemini_api_key", "")
        if api_key:
            return api_key

    # 環境変数から
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        return api_key

    # 手動入力
    api_key = input("Gemini APIキーを入力してください: ").strip()
    return api_key


def select_model(api_key):
    """タイトル生成用の軽量モデルを選択"""
    genai.configure(api_key=api_key)
    models = genai.list_models()
    available_names = [
        m.name for m in models
        if 'gemini' in m.name.lower() and 'generateContent' in m.supported_generation_methods
    ]

    for preferred in TITLE_GENERATION_MODELS:
        for available in available_names:
            if preferred in available:
                return available

    return available_names[0] if available_names else None


def generate_title(model_name, text):
    """テキストから要約タイトルを生成"""
    excerpt = text[:2000]

    prompt = (
        "この文字起こしの内容を15〜25文字で要約してタイトルを付けてください。\n"
        "ファイル名に使うので記号は使わないでください。\n"
        "タイトルのみを出力してください。説明や装飾は不要です。\n\n"
        f"{excerpt}"
    )

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
        return None

    title = response.text.strip()
    if len(title) > SUMMARY_TITLE_MAX_LENGTH:
        title = title[:SUMMARY_TITLE_MAX_LENGTH]

    title = sanitize_filename(title)
    return title


def get_unique_path(file_path):
    """重複しないファイルパスを返す"""
    if not os.path.exists(file_path):
        return file_path

    base, ext = os.path.splitext(file_path)
    counter = 2
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    return f"{base}_{counter}{ext}"


def find_target_files():
    """リネーム対象のファイルを検索"""
    targets = []
    for filename in os.listdir(OUTPUT_DIR):
        match = OLD_PATTERN.match(filename)
        if match:
            base_name = match.group(1)
            process_name = match.group(2)
            timestamp = match.group(3)
            targets.append({
                'filename': filename,
                'filepath': os.path.join(OUTPUT_DIR, filename),
                'base_name': base_name,
                'process_name': process_name,
                'timestamp': timestamp,
            })
    return targets


def main():
    execute = '--execute' in sys.argv

    print("=" * 60)
    print("文字起こしファイル名マイグレーション")
    print("=" * 60)

    # 対象ファイル検索
    targets = find_target_files()
    if not targets:
        print("\nリネーム対象のファイルが見つかりませんでした。")
        return

    print(f"\n対象ファイル: {len(targets)}件")

    if not execute:
        print("\n[ドライラン] --execute を付けると実際にリネームします。")

    # APIキー取得
    api_key = get_api_key()
    if not api_key:
        print("エラー: APIキーが設定されていません。")
        return

    # モデル選択
    print("\nモデルを選択中...")
    model_name = select_model(api_key)
    if not model_name:
        print("エラー: 利用可能なモデルが見つかりません。")
        return
    print(f"使用モデル: {model_name}")

    # 処理
    print(f"\n{'─' * 60}")
    success = 0
    skipped = 0
    errors = 0

    for i, target in enumerate(targets):
        print(f"\n[{i+1}/{len(targets)}] {target['filename']}")

        # ファイル読み込み
        try:
            with open(target['filepath'], 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            print(f"  読み込みエラー: {e}")
            errors += 1
            continue

        if not text.strip():
            print("  スキップ: ファイルが空です")
            skipped += 1
            continue

        # タイトル生成
        try:
            title = generate_title(model_name, text)
        except Exception as e:
            print(f"  タイトル生成エラー: {e}")
            errors += 1
            # レート制限の可能性があるので少し待つ
            time.sleep(2)
            continue

        if not title:
            print("  スキップ: タイトルを生成できませんでした")
            skipped += 1
            continue

        # 新しいファイル名
        new_filename = f"{title}_{target['process_name']}_{target['base_name']}.txt"
        new_filepath = get_unique_path(os.path.join(OUTPUT_DIR, new_filename))
        new_filename = os.path.basename(new_filepath)

        print(f"  タイトル: {title}")
        print(f"  → {new_filename}")

        if execute:
            try:
                os.rename(target['filepath'], new_filepath)
                print("  リネーム完了")
                success += 1
            except Exception as e:
                print(f"  リネームエラー: {e}")
                errors += 1
        else:
            success += 1

        # API負荷軽減のため少し待つ
        time.sleep(0.5)

    # サマリー
    print(f"\n{'=' * 60}")
    print(f"結果: 成功={success}, スキップ={skipped}, エラー={errors}")
    if not execute and success > 0:
        print(f"\n実際にリネームするには以下を実行:")
        print(f"  python migrate_filenames.py --execute")
    print("=" * 60)


if __name__ == '__main__':
    main()
