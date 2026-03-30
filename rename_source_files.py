#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文字起こし済みの元ファイル（動画・音声）を要約タイトルでリネームするスクリプト

出力ファイル名のパターン:
  {要約タイトル}_文字起こし_{元ファイル名}.txt
から元ファイル名とタイトルを抽出し、元ファイルをリネームする。

使い方:
  python rename_source_files.py <検索ディレクトリ>     # ドライラン
  python rename_source_files.py <検索ディレクトリ> --execute  # 実行
  python rename_source_files.py                        # outputフォルダをスキャン

検索ディレクトリ内の文字起こし結果ファイルと元ファイルの両方を再帰的に探索します。
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.constants import SUPPORTED_AUDIO_FORMATS
from src.utils import sanitize_filename

# {要約タイトル}_文字起こし_{元ファイル名}.txt
# または {要約タイトル}_{処理名}_{元ファイル名}.txt
TITLED_PATTERN = re.compile(
    r'^(.+?)_(文字起こし|文字起こしから議事録作成プロンプト|要約)_(.+)\.txt$'
)


def find_source_file(original_basename, search_dirs):
    """元ファイルを検索する（拡張子を補完して探す）"""
    # まずそのままの名前で探す
    for search_dir in search_dirs:
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                name_no_ext = os.path.splitext(f)[0]
                if name_no_ext == original_basename:
                    ext = os.path.splitext(f)[1].lower().lstrip('.')
                    if ext in SUPPORTED_AUDIO_FORMATS:
                        return os.path.join(root, f)
    return None


def scan_transcription_files(directory):
    """ディレクトリ内の文字起こし結果ファイルをスキャンし、リネーム候補を返す"""
    candidates = []

    for root, dirs, files in os.walk(directory):
        for f in files:
            if not f.endswith('.txt'):
                continue

            match = TITLED_PATTERN.match(f)
            if not match:
                continue

            title = match.group(1)
            original_basename = match.group(3)

            # タイトルがタイムスタンプっぽい場合はスキップ（タイトル未生成のファイル）
            if re.match(r'^\d{8}_\d{6}$', title):
                continue

            candidates.append({
                'transcription_file': os.path.join(root, f),
                'title': title,
                'original_basename': original_basename,
                'search_dir': root,
            })

    return candidates


def main():
    # 引数の解析
    args = sys.argv[1:]
    execute = '--execute' in args
    args = [a for a in args if a != '--execute']

    if args:
        search_dir = args[0]
    else:
        search_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

    if not os.path.isdir(search_dir):
        print(f"エラー: ディレクトリが見つかりません: {search_dir}")
        sys.exit(1)

    print(f"検索ディレクトリ: {search_dir}")
    print(f"モード: {'実行' if execute else 'ドライラン（--execute で実行）'}")
    print()

    # 文字起こし結果ファイルをスキャン
    candidates = scan_transcription_files(search_dir)
    if not candidates:
        print("リネーム候補が見つかりませんでした。")
        return

    # 各候補について元ファイルを検索
    # 元ファイルの検索先: 文字起こしファイルと同じディレクトリ + 検索ディレクトリ全体
    rename_pairs = []
    skipped = 0
    not_found = 0

    for c in candidates:
        source = find_source_file(
            c['original_basename'],
            [c['search_dir'], search_dir]
        )

        if not source:
            not_found += 1
            continue

        # 既にタイトルでリネーム済みかチェック
        source_name = os.path.splitext(os.path.basename(source))[0]
        safe_title = sanitize_filename(c['title'])
        if not safe_title:
            skipped += 1
            continue

        if source_name == safe_title:
            skipped += 1
            continue

        # リネーム先のパスを構築
        source_dir = os.path.dirname(source)
        source_ext = os.path.splitext(source)[1]
        new_name = f"{safe_title}{source_ext}"
        new_path = os.path.join(source_dir, new_name)

        # 重複チェック
        counter = 2
        while os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(source):
            new_name = f"{safe_title}_{counter}{source_ext}"
            new_path = os.path.join(source_dir, new_name)
            counter += 1

        rename_pairs.append({
            'source': source,
            'new_path': new_path,
            'title': c['title'],
            'original_basename': c['original_basename'],
        })

    # 結果を表示
    print(f"スキャン結果: {len(candidates)}件の文字起こしファイル")
    print(f"  リネーム候補: {len(rename_pairs)}件")
    print(f"  元ファイル未発見: {not_found}件")
    print(f"  スキップ（リネーム済みなど）: {skipped}件")
    print()

    if not rename_pairs:
        print("リネーム対象はありませんでした。")
        return

    # リネーム候補を表示
    for i, pair in enumerate(rename_pairs, 1):
        old_name = os.path.basename(pair['source'])
        new_name = os.path.basename(pair['new_path'])
        print(f"  {i}. {old_name}")
        print(f"     → {new_name}")
        print(f"     場所: {os.path.dirname(pair['source'])}")
        print()

    if not execute:
        print("ドライランモードです。実際にリネームするには --execute を付けてください。")
        return

    # 確認
    answer = input(f"{len(rename_pairs)}件のファイルをリネームしますか？ (y/N): ")
    if answer.lower() != 'y':
        print("キャンセルしました。")
        return

    # リネーム実行
    success = 0
    errors = 0
    for pair in rename_pairs:
        try:
            os.rename(pair['source'], pair['new_path'])
            old_name = os.path.basename(pair['source'])
            new_name = os.path.basename(pair['new_path'])
            print(f"  ✓ {old_name} → {new_name}")
            success += 1
        except Exception as e:
            print(f"  ✗ {os.path.basename(pair['source'])}: {e}")
            errors += 1

    print()
    print(f"完了: {success}件リネーム, {errors}件エラー")


if __name__ == '__main__':
    main()
