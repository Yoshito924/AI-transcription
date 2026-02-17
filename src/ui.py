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
    app_header.pack(fill=tk.X, pady=(0, 8))

    # タブ（文字起こし / API設定・使用量）
    notebook = ttk.Notebook(main_container, style='Modern.TNotebook')
    notebook.pack(fill=tk.X, pady=(0, SECTION_SPACING))

    # タブ1: 文字起こし
    file_tab = tk.Frame(notebook, bg=theme.colors['surface'])
    notebook.add(file_tab, text='  文字起こし  ')
    file_section = create_file_section(file_tab, app, theme, widgets)
    file_section.pack(fill=tk.X)

    # タブ2: API設定・使用量
    settings_tab = tk.Frame(notebook, bg=theme.colors['surface'])
    notebook.add(settings_tab, text='  API設定・使用量  ')
    settings_content = tk.Frame(settings_tab, bg=theme.colors['surface'])
    settings_content.pack(fill=tk.X, padx=8, pady=8)
    api_section = create_api_section(settings_content, app, theme, widgets)
    api_section.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
    usage_section = create_usage_section(settings_content, app, theme, widgets)
    usage_section.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

    # 処理履歴とログを横並びに（ドラッグで幅変更可能）
    paned = tk.PanedWindow(
        main_container, orient=tk.HORIZONTAL,
        bg=theme.colors['background'],
        sashwidth=6, sashrelief='flat',
        opaqueresize=True
    )
    paned.pack(fill=tk.BOTH, expand=True)

    history_section = create_history_section(paned, app, theme, widgets)
    paned.add(history_section, stretch='always', minsize=250)

    log_section = create_log_section(paned, app, theme, widgets)
    paned.add(log_section, stretch='always', minsize=200)

    # 初期比率を 3:2 に設定
    def _set_initial_sash(event=None):
        paned.update_idletasks()
        total = paned.winfo_width()
        if total > 10:
            paned.sash_place(0, int(total * 0.6), 0)
            paned.unbind('<Map>')
    paned.bind('<Map>', _set_initial_sash)

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
    """ファイル入力セクション（コンパクト版・タブ内用）"""
    frame = tk.Frame(parent, bg=theme.colors['surface'])
    pad = 16

    # Row 1: エンジン選択（コンパクト）
    engine_frame = tk.Frame(frame, bg=theme.colors['surface'])
    engine_frame.pack(fill=tk.X, padx=pad, pady=(pad, 4))

    engine_label = tk.Label(
        engine_frame, text="エンジン:",
        font=theme.fonts['body'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    engine_label.pack(side=tk.LEFT, padx=(0, 8))

    saved_engine = app.config.get("transcription_engine", "gemini")
    engine_var = tk.StringVar(value=saved_engine)

    for text, value in [("Gemini", "gemini"), ("Whisper (ローカル)", "whisper"), ("Whisper API", "whisper-api")]:
        ttk.Radiobutton(
            engine_frame, text=text,
            variable=engine_var, value=value,
            style='Modern.TRadiobutton'
        ).pack(side=tk.LEFT, padx=(0, 12))

    # Row 2: Whisperモデル + 保存先（1行に統合）
    options_frame = tk.Frame(frame, bg=theme.colors['surface'])
    options_frame.pack(fill=tk.X, padx=pad, pady=(0, 6))

    whisper_model_label = tk.Label(
        options_frame, text="モデル:",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    whisper_model_label.pack(side=tk.LEFT, padx=(0, 4))

    model_display_names = {
        'turbo': '\u2b50 turbo（推奨）',
        'large-v3': 'large-v3（最高精度）',
        'medium': 'medium（高精度）',
        'small': 'small（軽量）',
        'base': 'base（標準）',
        'tiny': 'tiny（最速）',
    }
    display_to_model = {v: k for k, v in model_display_names.items()}

    saved_whisper_model = app.config.get("whisper_model", "turbo")
    if saved_whisper_model in ['large-v3-turbo']:
        saved_whisper_model = 'turbo'
    if saved_whisper_model not in model_display_names:
        saved_whisper_model = 'turbo'

    whisper_model_var = tk.StringVar(
        value=model_display_names.get(saved_whisper_model, model_display_names['turbo'])
    )
    whisper_model_combo = ttk.Combobox(
        options_frame,
        textvariable=whisper_model_var,
        values=list(model_display_names.values()),
        state='readonly', width=22,
        style='Modern.TCombobox'
    )
    whisper_model_combo.pack(side=tk.LEFT, padx=(0, 8))

    model_details = {
        'turbo': '809MB | 高速高精度',
        'large-v3': '1.5GB | 最高精度',
        'medium': '769MB | バランス型',
        'small': '244MB | 軽量',
        'base': '74MB | テスト用',
        'tiny': '39MB | 最軽量',
    }

    whisper_model_info = tk.Label(
        options_frame,
        text=model_details.get(saved_whisper_model, ''),
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    whisper_model_info.pack(side=tk.LEFT, padx=(0, 16))

    # 区切り線
    tk.Frame(
        options_frame, bg=theme.colors['outline'], width=1
    ).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12), pady=2)

    tk.Label(
        options_frame, text="保存先:",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(side=tk.LEFT, padx=(0, 6))

    save_to_output_var = tk.BooleanVar(value=app.config.get("save_to_output_dir", True))
    save_to_source_var = tk.BooleanVar(value=app.config.get("save_to_source_dir", False))

    def on_output_toggle():
        if not save_to_output_var.get() and not save_to_source_var.get():
            save_to_output_var.set(True)
        app.config.set("save_to_output_dir", save_to_output_var.get())
        app.config.set("save_to_source_dir", save_to_source_var.get())
        app.config.save()

    def on_source_toggle():
        if not save_to_source_var.get() and not save_to_output_var.get():
            save_to_source_var.set(True)
        app.config.set("save_to_output_dir", save_to_output_var.get())
        app.config.set("save_to_source_dir", save_to_source_var.get())
        app.config.save()

    ttk.Checkbutton(
        options_frame, text="output",
        variable=save_to_output_var, command=on_output_toggle,
        style='Modern.TCheckbutton'
    ).pack(side=tk.LEFT, padx=(0, 8))

    ttk.Checkbutton(
        options_frame, text="元ファイル側",
        variable=save_to_source_var, command=on_source_toggle,
        style='Modern.TCheckbutton'
    ).pack(side=tk.LEFT)

    # エンジン切り替えコールバック
    def on_engine_change():
        is_whisper = engine_var.get() == "whisper"
        whisper_model_combo.config(state='readonly' if is_whisper else 'disabled')
        whisper_model_label.config(
            fg=theme.colors['text_secondary'] if is_whisper else theme.colors['text_disabled']
        )
        whisper_model_info.config(
            fg=theme.colors['text_secondary'] if is_whisper else theme.colors['text_disabled']
        )
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

    # Row 3: ドラッグ&ドロップ（コンパクト）
    drop_container = widgets.create_drag_drop_canvas(
        frame,
        "ここをクリックしてファイルを選択  /  ドラッグ&ドロップ",
        height=75
    )
    drop_container.pack(fill=tk.X, padx=pad, pady=(0, 6))

    drop_canvas = drop_container.canvas
    drop_canvas.bind("<Button-1>", app.browse_file)
    setup_drag_drop(drop_canvas, drop_canvas, app)

    # Row 4: ファイル情報 + ステータス（1行に統合）
    info_status_frame = tk.Frame(frame, bg=theme.colors['surface'])
    info_status_frame.pack(fill=tk.X, padx=pad, pady=(0, 4))

    file_label = tk.Label(
        info_status_frame,
        text="選択ファイル: なし",
        font=theme.fonts['body'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    file_label.pack(side=tk.LEFT)

    status_label = tk.Label(
        info_status_frame,
        text="準備完了",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    status_label.pack(side=tk.RIGHT)

    status_dot = tk.Label(
        info_status_frame,
        text="\u25cf",
        font=(theme.fonts['default'][0], 8),
        fg=theme.colors['text_disabled'],
        bg=theme.colors['surface']
    )
    status_dot.pack(side=tk.RIGHT, padx=(0, 4))

    # Row 5: プログレスバー + パーセント表示
    progress_frame = tk.Frame(frame, bg=theme.colors['surface'])
    progress_frame.pack(fill=tk.X, padx=pad, pady=(0, 8))

    progress = ttk.Progressbar(
        progress_frame, orient=tk.HORIZONTAL,
        mode='determinate', maximum=100, value=0,
        style='Modern.Horizontal.TProgressbar'
    )
    progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

    progress_label = tk.Label(
        progress_frame, text="",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        width=5, anchor='e'
    )
    progress_label.pack(side=tk.RIGHT, padx=(4, 0))

    # Row 6: 文字起こしボタン
    transcribe_btn = widgets.create_action_button(
        frame, "文字起こし開始",
        command=lambda: app.start_process("transcription")
    )
    transcribe_btn.pack(fill=tk.X, padx=pad, pady=(0, pad))

    # UI要素の参照を設定
    frame.drop_area = drop_canvas
    frame.file_label = file_label
    frame.status_label = status_label
    frame.status_dot = status_dot
    frame.progress = progress
    frame.progress_label = progress_label
    frame.engine_var = engine_var
    frame.whisper_model_var = whisper_model_var
    frame.whisper_model_combo = whisper_model_combo
    frame.save_to_output_var = save_to_output_var
    frame.save_to_source_var = save_to_source_var

    return frame


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
        height=12
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
        button_frame, "ファイルを開く", ICONS['document'], 'Secondary',
        command=app.open_output_file
    )
    open_btn.pack(side=tk.LEFT, padx=(0, 5))

    source_folder_btn = widgets.create_icon_button(
        button_frame, "元ファイルのフォルダ", ICONS['file'], 'Secondary',
        command=app.open_source_file_folder
    )
    source_folder_btn.pack(side=tk.LEFT, padx=(0, 5))

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
        'progress_label': file_section.progress_label,
        'engine_var': file_section.engine_var,
        'whisper_model_var': file_section.whisper_model_var,
        'whisper_model_combo': file_section.whisper_model_combo,
        'save_to_output_var': file_section.save_to_output_var,
        'save_to_source_var': file_section.save_to_source_var,
        'usage_sessions': usage_section.sessions_value,
        'usage_tokens': usage_section.tokens_value,
        'usage_cost_usd': usage_section.cost_usd_value,
        'usage_cost_jpy': usage_section.cost_jpy_value,
        'history_tree': history_section.history_tree,
        'log_text': log_section.log_text
    }
