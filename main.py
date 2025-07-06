#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tkinter as tk
from tkinter import messagebox

from src.app import TranscriptionApp
from src.utils import check_ffmpeg, ensure_dir
from src.constants import OUTPUT_DIR

def main():
    # FFmpegの確認
    if not check_ffmpeg():
        print("警告: FFmpegが見つかりません。音声変換機能が使えない可能性があります。")
        messagebox.showwarning(
            "警告", 
            "FFmpegが見つかりません。インストールして、PATHに追加してください。\n" +
            "https://ffmpeg.org/download.html からダウンロードできます。"
        )
    
    # 出力ディレクトリ作成
    app_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(app_dir, OUTPUT_DIR)
    ensure_dir(output_dir)
    
    # TkinterDnDを使用
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        print("ドラッグ＆ドロップ機能を有効化しました")
    except ImportError:
        print("警告: tkinterdnd2が見つかりません。ドラッグ＆ドロップ機能は無効です。")
        root = tk.Tk()
    
    # アプリケーション起動
    app = TranscriptionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
