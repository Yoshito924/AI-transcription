#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
シンプルなUIレイアウトの実装
文字起こし機能に特化した直感的なインターフェース
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import sys
import os

from .ui_styles import ModernTheme, ModernWidgets, ICONS
from .constants import (
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    DRAG_DROP_AREA_HEIGHT, CARD_PADDING, SECTION_SPACING
)


def setup_ui(app):
    """シンプルなUIの構築"""
    root = app.root
    
    # テーマとウィジェットの初期化
    theme = ModernTheme()
    widgets = ModernWidgets(theme)
    style = theme.apply_theme(root)
    
    # ウィンドウの基本設定
    root.title("🎤 AI文字起こし - 音声を瞬時にテキスト化")
    root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")
    root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
    root.configure(bg=theme.colors['background'])
    
    # メインコンテナ
    main_container = tk.Frame(root, bg=theme.colors['background'])
    main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # 上部：API設定と使用量を横並び
    top_container = tk.Frame(main_container, bg=theme.colors['background'])
    top_container.pack(fill=tk.X, pady=(0, 15))
    
    # API設定セクション（左側、コンパクト）
    api_section = create_api_section(top_container, app, theme, widgets)
    api_section.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    # 使用量表示セクション（右側、コンパクト）
    usage_section = create_usage_section(top_container, app, theme, widgets)
    usage_section.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
    
    # ファイル入力セクション
    file_section = create_file_section(main_container, app, theme, widgets)
    file_section.pack(fill=tk.X, pady=(0, 15))
    
    # 処理履歴とログを横並びに
    bottom_container = tk.Frame(main_container, bg=theme.colors['background'])
    bottom_container.pack(fill=tk.BOTH, expand=True)
    
    # 左側：処理履歴
    history_section = create_history_section(bottom_container, app, theme, widgets)
    history_section.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
    
    # 右側：処理ログ
    log_section = create_log_section(bottom_container, app, theme, widgets)
    log_section.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
    
    # UI要素を収集
    ui_elements = collect_ui_elements(
        api_section, file_section, usage_section, history_section, log_section
    )
    
    return ui_elements


def create_api_section(parent, app, theme, widgets):
    """API設定セクション（コンパクト版）"""
    card = widgets.create_card_frame(parent)
    
    # ヘッダー
    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 5))
    
    header_label = tk.Label(
        header_frame,
        text=f"{ICONS['key']} API設定",
        font=theme.fonts['caption'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface']
    )
    header_label.pack(side=tk.LEFT)
    
    # API接続状態
    api_status = tk.Label(
        header_frame,
        text="● 未接続",
        font=theme.fonts['caption'],
        fg=theme.colors['error'],
        bg=theme.colors['surface']
    )
    api_status.pack(side=tk.RIGHT)
    
    # API入力フレーム
    input_frame = tk.Frame(card, bg=theme.colors['surface'])
    input_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 5))
    
    api_entry = ttk.Entry(
        input_frame,
        textvariable=app.api_key,
        show="*",
        style='Modern.TEntry',
        width=30
    )
    api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    
    # ボタン（小さく）
    toggle_btn = widgets.create_button(
        input_frame, "表示", 'Secondary',
        command=app.toggle_api_key_visibility
    )
    toggle_btn.pack(side=tk.LEFT, padx=(0, 3))
    
    connect_btn = widgets.create_button(
        input_frame, "接続", 'Primary',
        command=app.check_api_connection
    )
    connect_btn.pack(side=tk.LEFT)
    
    # モデル情報（1行で）
    model_frame = tk.Frame(card, bg=theme.colors['surface'])
    model_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, CARD_PADDING))
    
    model_label_text = tk.Label(
        model_frame,
        text="モデル:",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    model_label_text.pack(side=tk.LEFT, padx=(0, 5))
    
    model_name = tk.Label(
        model_frame,
        text="未接続",
        font=theme.fonts['caption'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface']
    )
    model_name.pack(side=tk.LEFT)
    
    card.api_entry = api_entry
    card.api_status = api_status
    card.model_label = model_name
    
    return card


def create_file_section(parent, app, theme, widgets):
    """ファイル入力セクションの作成"""
    card = widgets.create_card_frame(parent)
    
    # ヘッダー
    header = tk.Label(
        card,
        text=f"{ICONS['upload']} ファイル選択",
        font=theme.fonts['subheading'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface']
    )
    header.pack(anchor='w', padx=CARD_PADDING, pady=(CARD_PADDING, 10))
    
    # ドラッグ&ドロップエリア
    drop_area, drop_label = widgets.create_drag_drop_area(
        card,
        f"{ICONS['upload']} ここをクリックして音声/動画ファイルを選択\nまたはファイルをドラッグ&ドロップ",
        height=100
    )
    drop_area.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 10))
    
    # ドラッグ&ドロップの設定
    drop_area.bind("<Button-1>", app.browse_file)
    drop_label.bind("<Button-1>", app.browse_file)
    setup_drag_drop(drop_area, drop_label, app)
    
    # ファイル情報
    file_info_frame = tk.Frame(card, bg=theme.colors['surface'])
    file_info_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 10))
    
    file_label = tk.Label(
        file_info_frame,
        text="選択ファイル: なし",
        font=theme.fonts['body'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    file_label.pack(side=tk.LEFT)
    
    # ステータス表示とプログレスバーを1行に
    status_frame = tk.Frame(card, bg=theme.colors['surface'])
    status_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 8))
    
    status_label = tk.Label(
        status_frame,
        text="準備完了",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    status_label.pack(side=tk.LEFT)
    
    # プログレスバー（小さく）
    progress = ttk.Progressbar(
        status_frame,
        orient=tk.HORIZONTAL,
        mode='indeterminate',
        style='Modern.Horizontal.TProgressbar',
        length=100
    )
    progress.pack(side=tk.RIGHT)
    
    # 文字起こしボタン（大きく目立つように）
    button_frame = tk.Frame(card, bg=theme.colors['surface'])
    button_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, CARD_PADDING))
    
    transcribe_btn = widgets.create_icon_button(
        button_frame,
        "音声を文字起こし開始",
        ICONS['microphone'],
        'Large.Primary',
        command=lambda: app.start_process("transcription")
    )
    transcribe_btn.pack(expand=True)
    
    card.drop_area = drop_area
    card.file_label = file_label
    card.status_label = status_label
    card.progress = progress
    
    return card


def create_history_section(parent, app, theme, widgets):
    """処理履歴セクションの作成"""
    card = widgets.create_card_frame(parent)
    
    # ヘッダー
    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 10))
    
    header_label = tk.Label(
        header_frame,
        text=f"{ICONS['clock']} 処理履歴",
        font=theme.fonts['subheading'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface']
    )
    header_label.pack(side=tk.LEFT)
    
    # 更新ボタン
    refresh_btn = widgets.create_button(
        header_frame, "更新", 'Secondary',
        command=app.update_history
    )
    refresh_btn.pack(side=tk.RIGHT, padx=(0, 5))
    
    # 履歴ツリー
    tree_frame = tk.Frame(card, bg=theme.colors['surface'])
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=CARD_PADDING, pady=(0, 10))
    
    columns = ('filename', 'date', 'size')
    history_tree = ttk.Treeview(
        tree_frame,
        columns=columns,
        show='headings',
        style='Modern.Treeview',
        height=8
    )
    
    history_tree.heading('filename', text='ファイル名')
    history_tree.heading('date', text='日時')
    history_tree.heading('size', text='サイズ')
    
    history_tree.column('filename', width=200)
    history_tree.column('date', width=150)
    history_tree.column('size', width=80)
    
    history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar = ttk.Scrollbar(
        tree_frame,
        orient=tk.VERTICAL,
        command=history_tree.yview,
        style='Modern.Vertical.TScrollbar'
    )
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    history_tree.configure(yscrollcommand=scrollbar.set)
    
    # ダブルクリックでファイルを開く
    history_tree.bind('<Double-1>', app.open_output_file)
    
    # 操作ボタン
    button_frame = tk.Frame(card, bg=theme.colors['surface'])
    button_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, CARD_PADDING))
    
    open_btn = widgets.create_icon_button(
        button_frame, "ファイルを開く", ICONS['open'], 'Secondary',
        command=app.open_output_file
    )
    open_btn.pack(side=tk.LEFT, padx=(0, 5))
    
    folder_btn = widgets.create_icon_button(
        button_frame, "出力フォルダを開く", ICONS['folder'], 'Secondary',
        command=app.open_output_folder
    )
    folder_btn.pack(side=tk.LEFT)
    
    card.history_tree = history_tree
    
    return card


def create_usage_section(parent, app, theme, widgets):
    """使用量表示セクション（コンパクト版）"""
    card = widgets.create_card_frame(parent)
    
    # ヘッダー
    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 5))
    
    header_label = tk.Label(
        header_frame,
        text=f"{ICONS['info']} 今月使用量（概算）",
        font=theme.fonts['caption'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface']
    )
    header_label.pack(side=tk.LEFT)
    
    # 更新ボタン
    refresh_btn = widgets.create_button(
        header_frame, "更新", 'Secondary',
        command=app.update_usage_display
    )
    refresh_btn.pack(side=tk.RIGHT)
    
    # 使用量情報を縦に2行で表示
    stats_frame = tk.Frame(card, bg=theme.colors['surface'])
    stats_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 5))
    
    # 1行目：処理回数とトークン数
    row1_frame = tk.Frame(stats_frame, bg=theme.colors['surface'])
    row1_frame.pack(fill=tk.X, pady=(0, 3))
    
    sessions_text = tk.Label(
        row1_frame,
        text="回数: 0回",
        font=theme.fonts['caption'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface']
    )
    sessions_text.pack(side=tk.LEFT)
    
    tokens_text = tk.Label(
        row1_frame,
        text="トークン: 0",
        font=theme.fonts['caption'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface']
    )
    tokens_text.pack(side=tk.RIGHT)
    
    # 2行目：料金
    row2_frame = tk.Frame(stats_frame, bg=theme.colors['surface'])
    row2_frame.pack(fill=tk.X, pady=(0, CARD_PADDING))
    
    cost_usd_text = tk.Label(
        row2_frame,
        text="$0.00",
        font=theme.fonts['caption'],
        fg=theme.colors['success'],
        bg=theme.colors['surface']
    )
    cost_usd_text.pack(side=tk.LEFT)
    
    cost_jpy_text = tk.Label(
        row2_frame,
        text="¥0",
        font=theme.fonts['caption'],
        fg=theme.colors['success'],
        bg=theme.colors['surface']
    )
    cost_jpy_text.pack(side=tk.RIGHT)
    
    # UI要素をカードに保存
    card.sessions_value = sessions_text
    card.tokens_value = tokens_text
    card.cost_usd_value = cost_usd_text
    card.cost_jpy_value = cost_jpy_text
    
    return card


def create_log_section(parent, app, theme, widgets):
    """処理ログセクションの作成"""
    card = widgets.create_card_frame(parent)
    
    # ヘッダー
    header = tk.Label(
        card,
        text=f"{ICONS['text']} 処理ログ",
        font=theme.fonts['subheading'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface']
    )
    header.pack(anchor='w', padx=CARD_PADDING, pady=(CARD_PADDING, 10))
    
    # ログテキスト
    log_text = scrolledtext.ScrolledText(
        card,
        wrap=tk.WORD,
        font=theme.fonts['monospace'],
        bg=theme.colors['surface'],
        fg=theme.colors['text_primary'],
        insertbackground=theme.colors['primary'],
        selectbackground=theme.colors['primary'],
        selectforeground=theme.colors['text_on_primary'],
        relief='flat',
        borderwidth=0,
        height=10
    )
    log_text.pack(fill=tk.BOTH, expand=True, padx=CARD_PADDING, pady=(0, CARD_PADDING))
    log_text.config(state=tk.DISABLED)
    
    card.log_text = log_text
    
    return card


def setup_drag_drop(drop_area, drop_label, app):
    """ドラッグ&ドロップ機能の設定"""
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        
        if isinstance(app.root, TkinterDnD.Tk):
            drop_area.drop_target_register(DND_FILES)
            drop_area.dnd_bind('<<Drop>>', lambda e: app.load_file(e.data.strip('{}').replace('\\', '/')))
        else:
            print("警告: ドラッグ&ドロップを有効にするには、ルートウィンドウをTkinterDnD.Tkとして作成する必要があります")
    except ImportError:
        print("警告: tkinterdnd2が見つかりません。ドラッグ&ドロップ機能は無効です。")
    except Exception as e:
        print(f"ドラッグ&ドロップの設定中にエラーが発生しました: {str(e)}")


def collect_ui_elements(api_section, file_section, usage_section, history_section, log_section):
    """UI要素を収集して辞書として返す"""
    return {
        'api_entry': api_section.api_entry,
        'api_status': api_section.api_status,
        'model_label': api_section.model_label,
        'drop_area': file_section.drop_area,
        'file_label': file_section.file_label,
        'status_label': file_section.status_label,
        'progress': file_section.progress,
        'usage_sessions': usage_section.sessions_value,
        'usage_tokens': usage_section.tokens_value,
        'usage_cost_usd': usage_section.cost_usd_value,
        'usage_cost_jpy': usage_section.cost_jpy_value,
        'history_tree': history_section.history_tree,
        'log_text': log_section.log_text
    }