#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ctypes
import os
import tkinter as tk

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

    from src.constants import OUTPUT_DIR
    from src.utils import ensure_dir

    app_dir = os.path.dirname(os.path.abspath(__file__))
    ensure_dir(os.path.join(app_dir, OUTPUT_DIR))

    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        print("ドラッグ＆ドロップ機能を有効化しました")
    except ImportError:
        print("警告: tkinterdnd2が見つかりません。ドラッグ＆ドロップ機能は無効です。")
        root = tk.Tk()

    _apply_app_icon(root, app_dir)
    root.title("AI 文字起こし")
    try:
        root.update_idletasks()
    except tk.TclError:
        pass

    from src.app import TranscriptionApp
    TranscriptionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
