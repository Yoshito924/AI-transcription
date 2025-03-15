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
    
    # ファイル入力エリア
    file_input_frame = ttk.Frame(input_frame)
    file_input_frame.pack(fill=tk.X, pady=5)
    
    # ドラッグ＆ドロップエリア（高さ固定）と選択ボタン
    drop_frame = ttk.Frame(input_frame)
    drop_frame.pack(fill=tk.X, pady=5)
    
    # 高さを60に変更（元は40）
    drop_area = tk.Frame(drop_frame, bg="#e0e0e0", bd=2, relief=tk.GROOVE, height=60)
    drop_area.pack(fill=tk.X, expand=False)
    drop_area.pack_propagate(False)  # サイズ固定
    
    # ファイル選択ボタンのスタイルを目立たせる - テキストを2行に変更
    drop_label = tk.Label(drop_area, 
                        text="ここをクリックしてファイルを選択\nまたは ファイルをドラッグ＆ドロップ", 
                        bg="#e0e0e0", fg="#0066CC", 
                        font=("", 10, "bold"), 
                        cursor="hand2")
    drop_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    drop_area.bind("<Button-1>", app.browse_file)
    drop_label.bind("<Button-1>", app.browse_file)
    
    # 明示的なファイル選択ボタン
    file_button_frame = ttk.Frame(input_frame)
    file_button_frame.pack(fill=tk.X, pady=5)
    ttk.Button(file_button_frame, text="ファイルを選択", command=app.browse_file).pack(side=tk.LEFT, padx=5)
    
    # ドラッグ＆ドロップ機能の設定
    try:
        # TkinterDnDライブラリをインポート試行
        from tkinterdnd2 import DND_FILES, TkinterDnD
        
        # ルートウィンドウをTkinterDnDに対応させる
        if not isinstance(root, TkinterDnD.Tk):
            print("警告: ドラッグ＆ドロップを有効にするには、ルートウィンドウをTkinterDnD.Tkとして作成する必要があります")
        else:
            # ドラッグ＆ドロップの設定
            drop_area.drop_target_register(DND_FILES)
            drop_area.dnd_bind('<<Drop>>', lambda e: app.load_file(e.data.strip('{}').replace('\\', '/')))
    except ImportError:
        print("警告: tkinterdnd2が見つかりません。ドラッグ＆ドロップ機能は無効です。")
    except Exception as e:
        print(f"ドラッグ＆ドロップの設定中にエラーが発生しました: {str(e)}")
    
    # 選択されたファイル表示
    file_label = ttk.Label(input_frame, text="ファイル: 未選択")
    file_label.pack(fill=tk.X, padx=5, pady=5)
    
    # ステータスラベル（高さ固定）
    status_frame = ttk.Frame(input_frame, height=20)
    status_frame.pack(fill=tk.X, padx=5, pady=5)
    status_frame.pack_propagate(False)
    
    status_label = ttk.Label(status_frame, text="待機中...", font=("", 9, "italic"))
    status_label.pack(fill=tk.X, expand=True)
    
    # 文字起こしボタン - 単独表示
    transcription_button_frame = ttk.Frame(input_frame)
    transcription_button_frame.pack(fill=tk.X, pady=5)
    
    ttk.Button(
        transcription_button_frame, 
        text="音声を文字起こし", 
        command=lambda: app.start_process("transcription"),
        style="Accent.TButton"
    ).pack(side=tk.LEFT, padx=5, pady=5)
    
    # ボタンのスタイル設定
    style = ttk.Style()
    style.configure("Accent.TButton", font=("", 10, "bold"))
    
    # プログレスバー
    progress = ttk.Progressbar(input_frame, orient=tk.HORIZONTAL, mode='indeterminate')
    progress.pack(fill=tk.X, padx=5, pady=5)
    
    # ログ出力エリア
    log_frame = ttk.LabelFrame(left_frame, text="処理ログ", padding=10)
    log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, width=40)
    log_text.pack(fill=tk.BOTH, expand=True, pady=5)
    log_text.config(state=tk.DISABLED)  # 読み取り専用に設定
    
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
    
    # 選択した文字起こしに対する追加処理フレーム
    postprocess_frame = ttk.LabelFrame(history_frame, text="選択した文字起こしの追加処理", padding=10)
    postprocess_frame.pack(fill=tk.X, pady=5)
    
    # 選択ファイル表示
    selected_file_frame = ttk.Frame(postprocess_frame)
    selected_file_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(selected_file_frame, text="選択ファイル:").pack(side=tk.LEFT, padx=(0, 5))
    selected_file_label = ttk.Label(selected_file_frame, text="未選択")
    selected_file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    # 処理プロンプト選択
    process_select_frame = ttk.Frame(postprocess_frame)
    process_select_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(process_select_frame, text="処理タイプ:").pack(side=tk.LEFT, padx=(0, 5))
    process_var = tk.StringVar()
    process_combo = ttk.Combobox(process_select_frame, textvariable=process_var, state="readonly")
    process_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    # 追加処理実行ボタン
    process_button_frame = ttk.Frame(postprocess_frame)
    process_button_frame.pack(fill=tk.X, pady=5)
    
    process_button = ttk.Button(
        process_button_frame, 
        text="追加処理を実行", 
        command=app.process_selected_transcription,
        state=tk.DISABLED
    )
    process_button.pack(side=tk.LEFT, padx=5)
    
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
        'prompt_text': prompt_text,
        'selected_file_label': selected_file_label,
        'process_var': process_var,
        'process_combo': process_combo,
        'process_button': process_button,
        'log_text': log_text
    }
    
    # ステータスラベルを先に設定
    app.ui_elements = {'status_label': status_label}
    
    return ui_elements
