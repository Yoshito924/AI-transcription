#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
モダンなUIレイアウトの実装
カード・セクションヘッダー・ダークログ・キャンバスD&Dを採用
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import sys
import os

from .ui_styles import ModernTheme, ModernWidgets, ICONS
from .constants import (
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    DRAG_DROP_AREA_HEIGHT, CARD_PADDING,
    SECTION_SPACING, MAIN_PADDING_X, MAIN_PADDING_Y
)


def setup_ui(app):
    """UIの構築"""
    root = app.root

    # テーマとウィジェットの初期化
    theme = ModernTheme()
    widgets = ModernWidgets(theme)
    style = theme.apply_theme(root)

    # ウィンドウの基本設定
    root.title("AI 文字起こし - 音声を瞬時にテキスト化")
    root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")
    root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
    root.configure(bg=theme.colors['background'])

    # メインコンテナ
    main_container = tk.Frame(root, bg=theme.colors['background'])
    main_container.pack(fill=tk.BOTH, expand=True, padx=MAIN_PADDING_X, pady=MAIN_PADDING_Y)

    # アプリケーションヘッダー
    app_header = _create_app_header(main_container, theme)
    app_header.pack(fill=tk.X, pady=(0, SECTION_SPACING))

    # 上部：API設定と使用量を横並び
    top_container = tk.Frame(main_container, bg=theme.colors['background'])
    top_container.pack(fill=tk.X, pady=(0, SECTION_SPACING))

    api_section = create_api_section(top_container, app, theme, widgets)
    api_section.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

    usage_section = create_usage_section(top_container, app, theme, widgets)
    usage_section.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0))

    # ファイル入力セクション
    file_section = create_file_section(main_container, app, theme, widgets)
    file_section.pack(fill=tk.X, pady=(0, SECTION_SPACING))

    # 処理履歴とログを横並びに
    bottom_container = tk.Frame(main_container, bg=theme.colors['background'])
    bottom_container.pack(fill=tk.BOTH, expand=True)

    history_section = create_history_section(bottom_container, app, theme, widgets)
    history_section.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

    log_section = create_log_section(bottom_container, app, theme, widgets)
    log_section.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

    # UI要素を収集
    ui_elements = collect_ui_elements(
        api_section, file_section, usage_section, history_section, log_section
    )

    return ui_elements


def _create_app_header(parent, theme):
    """アプリケーションヘッダー（タイトル + サブタイトル）"""
    frame = tk.Frame(parent, bg=theme.colors['background'])

    title = tk.Label(frame,
                    text="AI 文字起こし",
                    font=theme.fonts['app_title'],
                    fg=theme.colors['text_primary'],
                    bg=theme.colors['background'])
    title.pack(side=tk.LEFT)

    subtitle = tk.Label(frame,
                       text="音声・動画ファイルをテキストに変換",
                       font=theme.fonts['caption'],
                       fg=theme.colors['text_secondary'],
                       bg=theme.colors['background'])
    subtitle.pack(side=tk.LEFT, padx=(12, 0), pady=(4, 0))

    return frame


def create_api_section(parent, app, theme, widgets):
    """API設定セクション"""
    card = widgets.create_card_frame(parent)

    # セクションヘッダー
    header = widgets.create_section_header(card, "API 設定")
    header.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 8))

    # API接続状態（ヘッダー右側）
    api_status = tk.Label(
        header,
        text="\u25cf 未接続",
        font=theme.fonts['caption'],
        fg=theme.colors['error'],
        bg=theme.colors['surface']
    )
    api_status.pack(side=tk.RIGHT)

    # Gemini API入力
    gemini_frame = tk.Frame(card, bg=theme.colors['surface'])
    gemini_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 3))

    gemini_label = tk.Label(
        gemini_frame,
        text="Gemini:",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        width=8,
        anchor='w'
    )
    gemini_label.pack(side=tk.LEFT)

    api_entry = ttk.Entry(
        gemini_frame,
        textvariable=app.api_key,
        show="*",
        style='Modern.TEntry',
        width=25
    )
    api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

    # OpenAI API入力
    openai_frame = tk.Frame(card, bg=theme.colors['surface'])
    openai_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 5))

    openai_label = tk.Label(
        openai_frame,
        text="OpenAI:",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        width=8,
        anchor='w'
    )
    openai_label.pack(side=tk.LEFT)

    openai_api_entry = ttk.Entry(
        openai_frame,
        textvariable=app.openai_api_key,
        show="*",
        style='Modern.TEntry',
        width=25
    )
    openai_api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

    # ボタンフレーム
    button_frame = tk.Frame(card, bg=theme.colors['surface'])
    button_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 5))

    toggle_btn = widgets.create_button(
        button_frame, "表示", 'Secondary',
        command=app.toggle_api_key_visibility
    )
    toggle_btn.pack(side=tk.LEFT, padx=(0, 3))

    connect_btn = widgets.create_button(
        button_frame, "接続", 'Primary',
        command=app.check_api_connection
    )
    connect_btn.pack(side=tk.LEFT)

    # モデル情報
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
    card.openai_api_entry = openai_api_entry
    card.api_status = api_status
    card.model_label = model_name

    return card


def create_file_section(parent, app, theme, widgets):
    """ファイル入力セクションの作成"""
    card = widgets.create_card_frame(parent)

    # セクションヘッダー
    header = widgets.create_section_header(card, "ファイル選択")
    header.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 10))

    # エンジン選択フレーム
    engine_frame = tk.Frame(card, bg=theme.colors['surface'])
    engine_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 10))

    engine_label = tk.Label(
        engine_frame,
        text="文字起こしエンジン:",
        font=theme.fonts['body'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    engine_label.pack(side=tk.LEFT, padx=(0, 10))

    saved_engine = app.config.get("transcription_engine", "gemini")
    engine_var = tk.StringVar(value=saved_engine)

    gemini_radio = ttk.Radiobutton(
        engine_frame,
        text="Gemini (クラウド/高精度)",
        variable=engine_var,
        value="gemini",
        style='Modern.TRadiobutton'
    )
    gemini_radio.pack(side=tk.LEFT, padx=(0, 15))

    whisper_radio = ttk.Radiobutton(
        engine_frame,
        text="Whisper (ローカル/無料)",
        variable=engine_var,
        value="whisper",
        style='Modern.TRadiobutton'
    )
    whisper_radio.pack(side=tk.LEFT, padx=(0, 15))

    whisper_api_radio = ttk.Radiobutton(
        engine_frame,
        text="Whisper API (クラウド/高精度)",
        variable=engine_var,
        value="whisper-api",
        style='Modern.TRadiobutton'
    )
    whisper_api_radio.pack(side=tk.LEFT)

    # Whisperモデル選択
    whisper_model_frame = tk.Frame(card, bg=theme.colors['surface'])
    whisper_model_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 10))

    whisper_model_label = tk.Label(
        whisper_model_frame,
        text="Whisperモデル:",
        font=theme.fonts['body'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    whisper_model_label.pack(side=tk.LEFT, padx=(0, 10))

    model_display_names = {
        'turbo': '\u2b50 turbo（推奨・高速高精度）',
        'large-v3': 'large-v3（最高精度）',
        'medium': 'medium（高精度・軽量）',
        'small': 'small（中精度・軽量）',
        'base': 'base（標準）',
        'tiny': 'tiny（最速・低精度）',
    }
    display_to_model = {v: k for k, v in model_display_names.items()}

    saved_whisper_model = app.config.get("whisper_model", "turbo")
    if saved_whisper_model in ['large-v3-turbo']:
        saved_whisper_model = 'turbo'
    if saved_whisper_model not in model_display_names:
        saved_whisper_model = 'turbo'

    whisper_model_var = tk.StringVar(value=model_display_names.get(saved_whisper_model, model_display_names['turbo']))
    whisper_model_combo = ttk.Combobox(
        whisper_model_frame,
        textvariable=whisper_model_var,
        values=list(model_display_names.values()),
        state='readonly',
        width=28,
        style='Modern.TCombobox'
    )
    whisper_model_combo.pack(side=tk.LEFT, padx=(0, 10))

    model_details = {
        'turbo': '809MB | 高速かつ高精度、日本語対応\u25ce',
        'large-v3': '1.5GB | 99言語対応、最高精度',
        'medium': '769MB | バランス型、日本語対応\u25cb',
        'small': '244MB | 軽量、処理速度重視',
        'base': '74MB | 軽量、テスト用',
        'tiny': '39MB | 最軽量、精度低',
    }

    whisper_model_info = tk.Label(
        whisper_model_frame,
        text=model_details.get(saved_whisper_model, ''),
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    whisper_model_info.pack(side=tk.LEFT)

    def on_engine_change():
        is_whisper = engine_var.get() == "whisper"
        whisper_model_combo.config(state='readonly' if is_whisper else 'disabled')
        whisper_model_label.config(fg=theme.colors['text_secondary'] if is_whisper else theme.colors['text_disabled'])
        whisper_model_info.config(fg=theme.colors['text_secondary'] if is_whisper else theme.colors['text_disabled'])
        app.config.set("transcription_engine", engine_var.get())
        app.config.save()

    def on_model_change(event=None):
        display_name = whisper_model_var.get()
        model_name = display_to_model.get(display_name, 'turbo')
        whisper_model_info.config(text=model_details.get(model_name, ''))
        app.config.set("whisper_model", model_name)
        app.config.save()

    engine_var.trace('w', lambda *args: on_engine_change())
    whisper_model_combo.bind('<<ComboboxSelected>>', on_model_change)
    on_engine_change()

    # ドラッグ&ドロップエリア（Canvas版）
    drop_container = widgets.create_drag_drop_canvas(
        card,
        "ここをクリックして音声/動画ファイルを選択\nまたはファイルをドラッグ&ドロップ",
        height=DRAG_DROP_AREA_HEIGHT
    )
    drop_container.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 10))

    drop_canvas = drop_container.canvas
    drop_canvas.bind("<Button-1>", app.browse_file)
    setup_drag_drop(drop_canvas, drop_canvas, app)

    # ファイル情報
    file_info_frame = tk.Frame(card, bg=theme.colors['surface'])
    file_info_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 8))

    file_label = tk.Label(
        file_info_frame,
        text="選択ファイル: なし",
        font=theme.fonts['body'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    file_label.pack(side=tk.LEFT)

    # ステータス表示
    status_frame = tk.Frame(card, bg=theme.colors['surface'])
    status_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 4))

    status_dot = tk.Label(
        status_frame,
        text="\u25cf",
        font=(theme.fonts['default'][0], 8),
        fg=theme.colors['text_disabled'],
        bg=theme.colors['surface']
    )
    status_dot.pack(side=tk.LEFT, padx=(0, 5))

    status_label = tk.Label(
        status_frame,
        text="準備完了",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    status_label.pack(side=tk.LEFT)

    # プログレスバー（フルワイド、独立行）
    progress_frame = tk.Frame(card, bg=theme.colors['surface'])
    progress_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 10))

    progress = ttk.Progressbar(
        progress_frame,
        orient=tk.HORIZONTAL,
        mode='indeterminate',
        style='Modern.Horizontal.TProgressbar'
    )
    progress.pack(fill=tk.X)

    # 文字起こしボタン（アクションボタン）
    button_frame = tk.Frame(card, bg=theme.colors['surface'])
    button_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, CARD_PADDING))

    transcribe_btn = widgets.create_action_button(
        button_frame,
        "音声を文字起こし開始",
        command=lambda: app.start_process("transcription")
    )
    transcribe_btn.pack(expand=True, fill=tk.X)

    card.drop_area = drop_canvas
    card.file_label = file_label
    card.status_label = status_label
    card.status_dot = status_dot
    card.progress = progress
    card.engine_var = engine_var
    card.whisper_model_var = whisper_model_var
    card.whisper_model_combo = whisper_model_combo

    return card


def create_history_section(parent, app, theme, widgets):
    """処理履歴セクションの作成"""
    card = widgets.create_card_frame(parent)

    # セクションヘッダー
    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 10))

    header = widgets.create_section_header(header_frame, "処理履歴")
    header.pack(side=tk.LEFT, fill=tk.X, expand=True)

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

    # 交互行色タグ
    history_tree.tag_configure('row_even', background=theme.colors['surface'])
    history_tree.tag_configure('row_odd', background=theme.colors['table_row_alt'])

    history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(
        tree_frame,
        orient=tk.VERTICAL,
        command=history_tree.yview,
        style='Modern.Vertical.TScrollbar'
    )
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    history_tree.configure(yscrollcommand=scrollbar.set)

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
    """使用量表示セクション"""
    card = widgets.create_card_frame(parent)

    # セクションヘッダー
    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 5))

    header = widgets.create_section_header(header_frame, "今月使用量（概算）",
                                          bg=theme.colors['surface'])
    header.pack(side=tk.LEFT, fill=tk.X, expand=True)

    refresh_btn = widgets.create_button(
        header_frame, "更新", 'Secondary',
        command=app.update_usage_display
    )
    refresh_btn.pack(side=tk.RIGHT)

    # 使用量情報
    stats_frame = tk.Frame(card, bg=theme.colors['surface'])
    stats_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 5))

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
        text="\xa50",
        font=theme.fonts['caption'],
        fg=theme.colors['success'],
        bg=theme.colors['surface']
    )
    cost_jpy_text.pack(side=tk.RIGHT)

    card.sessions_value = sessions_text
    card.tokens_value = tokens_text
    card.cost_usd_value = cost_usd_text
    card.cost_jpy_value = cost_jpy_text

    return card


def create_log_section(parent, app, theme, widgets):
    """処理ログセクション（ダークテーマ）"""
    card = widgets.create_card_frame(parent)

    # セクションヘッダー
    header = widgets.create_section_header(card, "処理ログ")
    header.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 10))

    # ログテキスト（ダークテーマ）
    log_text = scrolledtext.ScrolledText(
        card,
        wrap=tk.WORD,
        font=theme.fonts['monospace'],
        bg=theme.colors['log_bg'],
        fg=theme.colors['log_text'],
        insertbackground=theme.colors['primary_light'],
        selectbackground=theme.colors['primary'],
        selectforeground=theme.colors['text_on_primary'],
        relief='flat',
        borderwidth=0,
        height=10
    )
    log_text.pack(fill=tk.BOTH, expand=True, padx=CARD_PADDING, pady=(0, CARD_PADDING))
    log_text.config(state=tk.DISABLED)

    # ログタグの設定
    widgets.configure_log_tags(log_text)

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
        'openai_api_entry': api_section.openai_api_entry,
        'api_status': api_section.api_status,
        'model_label': api_section.model_label,
        'drop_area': file_section.drop_area,
        'file_label': file_section.file_label,
        'status_label': file_section.status_label,
        'status_dot': file_section.status_dot,
        'progress': file_section.progress,
        'engine_var': file_section.engine_var,
        'whisper_model_var': file_section.whisper_model_var,
        'whisper_model_combo': file_section.whisper_model_combo,
        'usage_sessions': usage_section.sessions_value,
        'usage_tokens': usage_section.tokens_value,
        'usage_cost_usd': usage_section.cost_usd_value,
        'usage_cost_jpy': usage_section.cost_jpy_value,
        'history_tree': history_section.history_tree,
        'log_text': log_section.log_text
    }
