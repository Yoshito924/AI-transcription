#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, scrolledtext
import sys
import os

def setup_ui(app):
    """UIの構築"""
    root = app.root
    
    # メインフレーム
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # 左側フレーム (APIキー設定と操作パネル)
    left_frame = ttk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    
    # API設定フレーム
    api_frame = ttk.LabelFrame(left_frame, text="Gemini API設定", padding=10)
    api_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(api_frame, text="APIキー:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
    api_entry = ttk.Entry(api_frame, textvariable=app.api_key, width=40, show="*")
    api_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
    
    api_button_frame = ttk.Frame(api_frame)
    api_button_frame.grid(row=0, column=2, padx=5, pady=5)
    
    ttk.Button(api_button_frame, text="表示", command=app.toggle_api_key_visibility).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(api_button_frame, text="接続確認", command=app.check_api_connection).pack(side=tk.LEFT)
    
    # 入力フレーム
    input_frame = ttk.LabelFrame(left_frame, text="ファイル入力", padding=10)
    input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    # ドラッグ＆ドロップエリア
    drop_area = tk.Frame(input_frame, bg="#e0e0e0", bd=2, relief=tk.GROOVE)
    drop_area.pack(fill=tk.BOTH, expand=True, pady=10)
    
    drop_label = tk.Label(drop_area, text="音声/動画ファイルをここにドラッグ＆ドロップ\nまたはクリックして選択", 
                         bg="#e0e0e0", fg="#555555", font=("", 12))
    drop_label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    drop_area.bind("<Button-1>", app.browse_file)
    
    # ドラッグ＆ドロップ機能の設定
    try:
        # TkinterDnDライブラリをインポート試行
        from tkinterdnd2 import DND_FILES, TkinterDnD
        
        # ルートウィンドウをTkinterDnDに対応させる
        if not isinstance(root, TkinterDnD.Tk):
            print("警告: ドラッグ＆ドロップを有効にするには、ルートウィンドウをTkinterDnD.Tkとして作成する必要があります")
            app.ui_elements['status_label'].config(text="ドラッグ＆ドロップが無効です。Tkinterdnd2をインストールしてください。")
        else:
            # ドラッグ＆ドロップの設定
            drop_area.drop_target_register(DND_FILES)
            drop_area.dnd_bind('<<Drop>>', lambda e: app.load_file(e.data.strip('{}').replace('\\', '/')))
            drop_label.config(text="音声/動画ファイルをここにドラッグ＆ドロップ\nまたはクリックして選択\n(D&D有効)")
    except ImportError:
        print("警告: tkinterdnd2が見つかりません。ドラッグ＆ドロップ機能は無効です。")
        app.ui_elements['status_label'].config(text="ドラッグ＆ドロップが無効です。Tkinterdnd2をインストールしてください。")
    except Exception as e:
        print(f"ドラッグ＆ドロップの設定中にエラーが発生しました: {str(e)}")
        app.ui_elements['status_label'].config(text=f"ドラッグ＆ドロップエラー: {str(e)}")
    
    # 選択されたファイル表示
    file_label = ttk.Label(input_frame, text="ファイル: 未選択")
    file_label.pack(fill=tk.X, padx=5, pady=5)
    
    # 処理ボタンフレーム
    button_frame = ttk.Frame(input_frame)
    button_frame.pack(fill=tk.X, pady=10)
    
    ttk.Button(button_frame, text="文字起こしのみ", 
               command=lambda: app.start_process("transcription")).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="文字起こし→議事録", 
               command=lambda: app.start_process("meeting_minutes")).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="文字起こし→要約", 
               command=lambda: app.start_process("summary")).pack(side=tk.LEFT, padx=5)
    
    # プログレスバー
    progress = ttk.Progressbar(input_frame, orient=tk.HORIZONTAL, length=100, mode='indeterminate')
    progress.pack(fill=tk.X, padx=5, pady=5)
    
    # ステータスラベル
    status_label = ttk.Label(input_frame, text="待機中...", font=("", 10, "italic"))
    status_label.pack(fill=tk.X, padx=5, pady=5)
    
    # 右側フレーム (履歴とプロンプト編集)
    right_frame = ttk.Frame(main_frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    # 履歴フレーム
    history_frame = ttk.LabelFrame(right_frame, text="処理履歴", padding=10)
    history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    # 履歴リスト
    history_frame_inner = ttk.Frame(history_frame)
    history_frame_inner.pack(fill=tk.BOTH, expand=True)
    
    columns = ('filename', 'date', 'size')
    history_tree = ttk.Treeview(history_frame_inner, columns=columns, show='headings')
    history_tree.heading('filename', text='ファイル名')
    history_tree.heading('date', text='日時')
    history_tree.heading('size', text='サイズ')
    
    history_tree.column('filename', width=150)
    history_tree.column('date', width=120)
    history_tree.column('size', width=80)
    
    history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar = ttk.Scrollbar(history_frame_inner, orient=tk.VERTICAL, command=history_tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    history_tree.configure(yscrollcommand=scrollbar.set)
    
    history_tree.bind('<Double-1>', app.open_output_file)
    
    # 履歴操作ボタン
    history_buttons = ttk.Frame(history_frame)
    history_buttons.pack(fill=tk.X, pady=5)
    
    ttk.Button(history_buttons, text="更新", command=app.update_history).pack(side=tk.LEFT, padx=5)
    ttk.Button(history_buttons, text="ファイルを開く", command=app.open_output_file).pack(side=tk.LEFT, padx=5)
    ttk.Button(history_buttons, text="出力フォルダを開く", command=app.open_output_folder).pack(side=tk.LEFT, padx=5)
    
    # プロンプト編集フレーム
    prompt_frame = ttk.LabelFrame(right_frame, text="プロンプト編集", padding=10)
    prompt_frame.pack(fill=tk.BOTH, expand=True)
    
    # プロンプト選択
    prompt_select_frame = ttk.Frame(prompt_frame)
    prompt_select_frame.pack(fill=tk.X, pady=(0, 5))
    
    ttk.Label(prompt_select_frame, text="プロンプト:").pack(side=tk.LEFT, padx=(0, 5))
    
    prompt_var = tk.StringVar()
    prompt_combo = ttk.Combobox(prompt_select_frame, textvariable=prompt_var, state="readonly")
    prompt_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
    prompt_combo.bind("<<ComboboxSelected>>", app.load_selected_prompt)
    
    # プロンプト名編集
    prompt_name_frame = ttk.Frame(prompt_frame)
    prompt_name_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(prompt_name_frame, text="名前:").pack(side=tk.LEFT, padx=(0, 5))
    prompt_name_var = tk.StringVar()
    prompt_name_entry = ttk.Entry(prompt_name_frame, textvariable=prompt_name_var)
    prompt_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    # プロンプト編集エリア
    prompt_text = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD, height=10)
    prompt_text.pack(fill=tk.BOTH, expand=True, pady=5)
    
    # プロンプト操作ボタン
    prompt_buttons = ttk.Frame(prompt_frame)
    prompt_buttons.pack(fill=tk.X, pady=5)
    
    ttk.Button(prompt_buttons, text="保存", command=app.save_current_prompt).pack(side=tk.LEFT, padx=5)
    ttk.Button(prompt_buttons, text="新規作成", command=app.create_new_prompt).pack(side=tk.LEFT, padx=5)
    ttk.Button(prompt_buttons, text="削除", command=app.delete_current_prompt).pack(side=tk.LEFT, padx=5)
    
    # UIコンポーネントを返す
    ui_elements = {
        'api_entry': api_entry,
        'drop_area': drop_area,
        'file_label': file_label,
        'progress': progress,
        'status_label': status_label,
        'history_tree': history_tree,
        'prompt_var': prompt_var,
        'prompt_combo': prompt_combo,
        'prompt_name_var': prompt_name_var,
        'prompt_text': prompt_text
    }
    
    # ステータスラベルを先に設定
    app.ui_elements = {'status_label': status_label}
    
    return ui_elements
