#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ctypes
import os
import tkinter as tk
from tkinter import messagebox

from src.app import TranscriptionApp
from src.utils import check_ffmpeg, ensure_dir
from src.constants import OUTPUT_DIR

WINDOWS_APP_ID = "Kimum.AITranscription"


def _set_windows_app_user_model_id():
    """Windowsタスクバーで独自アプリとして扱えるようにする"""
    if os.name != "nt":
        return

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except Exception as exc:
        print(f"警告: AppUserModelIDを設定できませんでした: {exc}")


def _apply_app_icon(root, app_dir):
    """タイトルバーとタスクバーの両方にアプリアイコンを適用する"""
    icon_ico_path = os.path.join(app_dir, "icon.ico")
    icon_png_path = os.path.join(app_dir, "icon.png")

    if os.path.exists(icon_ico_path):
        try:
            root.iconbitmap(default=icon_ico_path)
        except tk.TclError as exc:
            print(f"警告: icon.icoを適用できませんでした: {exc}")

    if os.path.exists(icon_png_path):
        try:
            root._app_icon_image = tk.PhotoImage(file=icon_png_path)
            root.iconphoto(True, root._app_icon_image)
        except tk.TclError as exc:
            print(f"警告: icon.pngを適用できませんでした: {exc}")


def main():
    _set_windows_app_user_model_id()

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
    
    # アイコン設定
    _apply_app_icon(root, app_dir)

    # アプリケーション起動
    app = TranscriptionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
