#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import tkinter as tk
from src.app import TranscriptionApp

def check_ffmpeg():
    """FFmpegがインストールされているか確認"""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except:
        return False

def main():
    # FFmpegの確認
    if not check_ffmpeg():
        print("警告: FFmpegが見つかりません。音声変換機能が使えない可能性があります。")
        from tkinter import messagebox
        messagebox.showwarning(
            "警告", 
            "FFmpegが見つかりません。インストールして、PATHに追加してください。\n" +
            "https://ffmpeg.org/download.html からダウンロードできます。"
        )
    
    # 出力ディレクトリ作成
    app_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(app_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
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
