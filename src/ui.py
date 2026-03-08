#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
モダンなUIレイアウトの実装
カード・セクションヘッダー・ダークログ・キャンバスD&Dを採用
"""

import tkinter as tk
from tkinter import ttk, scrolledtext

from .ui_styles import ModernTheme, ModernWidgets, ICONS
from .constants import (
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    CARD_PADDING, SECTION_SPACING, MAIN_PADDING_X,
    MAIN_PADDING_Y, QUEUE_LISTBOX_HEIGHT
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
    app_header = _create_app_header(main_container, theme, widgets)
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


def _create_app_header(parent, theme, widgets):
    """アプリケーションヘッダー"""
    frame = tk.Frame(
        parent,
        bg=theme.colors['hero_bg'],
        highlightbackground=theme.colors['hero_border'],
        highlightthickness=1,
        bd=0
    )

    content = tk.Frame(frame, bg=theme.colors['hero_bg'])
    content.pack(fill=tk.X, padx=22, pady=18)

    left = tk.Frame(content, bg=theme.colors['hero_bg'])
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    tk.Label(
        left,
        text="AI TRANSCRIPTION STUDIO",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['secondary_light'],
        bg=theme.colors['hero_bg']
    ).pack(anchor='w')

    tk.Label(
        left,
        text="音声の取り込みから書き起こしまでを、一枚で。",
        font=theme.fonts['app_title'],
        fg=theme.colors['text_on_dark'],
        bg=theme.colors['hero_bg']
    ).pack(anchor='w', pady=(6, 4))

    tk.Label(
        left,
        text="Gemini / Whisper / Whisper API を切り替えながら、単発処理とキュー処理を同じ導線で回せます。",
        font=theme.fonts['body'],
        fg='#D7E0E4',
        bg=theme.colors['hero_bg']
    ).pack(anchor='w')

    badges = tk.Frame(left, bg=theme.colors['hero_bg'])
    badges.pack(anchor='w', pady=(12, 0))

    widgets.create_pill_label(
        badges, "Cloud Gemini", tone='dark',
        bg=theme.colors['hero_surface']
    ).pack(side=tk.LEFT, padx=(0, 8))
    widgets.create_pill_label(
        badges, "Local Whisper", tone='dark',
        bg=theme.colors['hero_surface']
    ).pack(side=tk.LEFT, padx=(0, 8))
    widgets.create_pill_label(
        badges, "Queue Ready", tone='dark',
        bg=theme.colors['hero_surface']
    ).pack(side=tk.LEFT)

    right = tk.Frame(
        content,
        bg=theme.colors['hero_surface'],
        highlightbackground=theme.colors['hero_border'],
        highlightthickness=1,
        bd=0
    )
    right.pack(side=tk.RIGHT, padx=(18, 0))

    right_inner = tk.Frame(right, bg=theme.colors['hero_surface'])
    right_inner.pack(padx=16, pady=14)

    tk.Label(
        right_inner,
        text="Workflow",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['secondary_light'],
        bg=theme.colors['hero_surface']
    ).pack(anchor='w')

    tk.Label(
        right_inner,
        text="取込 → 処理 → 保存",
        font=theme.fonts['heading'],
        fg=theme.colors['text_on_dark'],
        bg=theme.colors['hero_surface']
    ).pack(anchor='w', pady=(6, 4))

    tk.Label(
        right_inner,
        text="ファイルを置いて、そのまま走らせる前提のUIです。",
        font=theme.fonts['caption'],
        fg='#D7E0E4',
        bg=theme.colors['hero_surface']
    ).pack(anchor='w')

    return frame


def create_api_section(parent, app, theme, widgets):
    """API設定セクション"""
    card = widgets.create_card_frame(parent)

    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 8))

    header = widgets.create_section_header(header_frame, "API 設定")
    header.pack(side=tk.LEFT, fill=tk.X, expand=True)

    api_status = widgets.create_pill_label(
        header_frame, "\u25cf 未接続", tone='error',
        bg=theme.colors['error_soft'],
        fg=theme.colors['error']
    )
    api_status.pack(side=tk.RIGHT)

    tk.Label(
        card,
        text="利用するエンジンに応じて認証情報を登録します。Gemini は要約やタイトル生成、Whisper API は OpenAI 側の音声認識に使います。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        wraplength=420
    ).pack(anchor='w', padx=CARD_PADDING, pady=(0, 12))

    gemini_panel = tk.Frame(
        card,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    gemini_panel.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 8))

    gemini_inner = tk.Frame(gemini_panel, bg=theme.colors['surface_variant'])
    gemini_inner.pack(fill=tk.X, padx=12, pady=10)

    tk.Label(
        gemini_inner,
        text="Gemini API Key",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    tk.Label(
        gemini_inner,
        text="Gemini エンジンとタイトル生成で使用",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w', pady=(2, 8))

    api_entry = ttk.Entry(
        gemini_inner,
        textvariable=app.api_key,
        show="*",
        style='Modern.TEntry'
    )
    api_entry.pack(fill=tk.X)

    openai_panel = tk.Frame(
        card,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    openai_panel.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 10))

    openai_inner = tk.Frame(openai_panel, bg=theme.colors['surface_variant'])
    openai_inner.pack(fill=tk.X, padx=12, pady=10)

    tk.Label(
        openai_inner,
        text="OpenAI API Key",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    tk.Label(
        openai_inner,
        text="Whisper API モードで使用",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w', pady=(2, 8))

    openai_api_entry = ttk.Entry(
        openai_inner,
        textvariable=app.openai_api_key,
        show="*",
        style='Modern.TEntry'
    )
    openai_api_entry.pack(fill=tk.X)

    button_frame = tk.Frame(card, bg=theme.colors['surface'])
    button_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, 10))

    toggle_btn = widgets.create_icon_button(
        button_frame, "表示", ICONS['key'], 'Secondary',
        command=app.toggle_api_key_visibility
    )
    toggle_btn.pack(side=tk.LEFT, padx=(0, 6))

    connect_btn = widgets.create_icon_button(
        button_frame, "接続確認", ICONS['check'], 'Primary',
        command=app.check_api_connection
    )
    connect_btn.pack(side=tk.LEFT)

    model_frame = tk.Frame(
        card,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    model_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, CARD_PADDING))

    model_inner = tk.Frame(model_frame, bg=theme.colors['surface_variant'])
    model_inner.pack(fill=tk.X, padx=12, pady=10)

    tk.Label(
        model_inner,
        text="現在の接続先",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    model_name = tk.Label(
        model_inner,
        text="未接続",
        font=theme.fonts['body_bold'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface_variant']
    )
    model_name.pack(anchor='w', pady=(6, 0))

    card.api_entry = api_entry
    card.openai_api_entry = openai_api_entry
    card.api_status = api_status
    card.model_label = model_name

    return card


def create_file_section(parent, app, theme, widgets):
    """ファイル入力セクション"""
    frame = widgets.create_card_frame(parent)
    pad = 16

    header_frame = tk.Frame(frame, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=pad, pady=(pad, 8))

    widgets.create_section_header(header_frame, "文字起こし設定").pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )
    widgets.create_pill_label(
        header_frame, "キュー対応", tone='success'
    ).pack(side=tk.RIGHT)

    config_strip = tk.Frame(frame, bg=theme.colors['surface'])
    config_strip.pack(fill=tk.X, padx=pad, pady=(0, 10))

    left_panel = tk.Frame(
        config_strip,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

    right_panel = tk.Frame(
        config_strip,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

    left_inner = tk.Frame(left_panel, bg=theme.colors['surface_variant'])
    left_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

    tk.Label(
        left_inner,
        text="エンジン選択",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    saved_engine = app.config.get("transcription_engine", "gemini")
    engine_var = tk.StringVar(value=saved_engine)

    engine_row = tk.Frame(left_inner, bg=theme.colors['surface_variant'])
    engine_row.pack(fill=tk.X, pady=(8, 10))

    for text, value in [
        ("Gemini", "gemini"),
        ("Whisper (ローカル)", "whisper"),
        ("Whisper API", "whisper-api")
    ]:
        ttk.Radiobutton(
            engine_row, text=text,
            variable=engine_var, value=value,
            style='Modern.TRadiobutton'
        ).pack(side=tk.LEFT, padx=(0, 12))

    tk.Label(
        left_inner,
        text="Whisper モデル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

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
        left_inner,
        textvariable=whisper_model_var,
        values=list(model_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    whisper_model_combo.pack(fill=tk.X, pady=(8, 0))

    model_details = {
        'turbo': '809MB | 高速高精度',
        'large-v3': '1.5GB | 最高精度',
        'medium': '769MB | バランス型',
        'small': '244MB | 軽量',
        'base': '74MB | テスト向け',
        'tiny': '39MB | 最軽量',
    }

    whisper_model_info = tk.Label(
        left_inner,
        text=model_details.get(saved_whisper_model, ''),
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    whisper_model_info.pack(anchor='w', pady=(6, 0))

    right_inner = tk.Frame(right_panel, bg=theme.colors['surface_variant'])
    right_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

    tk.Label(
        right_inner,
        text="保存と処理モード",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    tk.Label(
        right_inner,
        text="出力先は複数指定できます。どちらもオフにした場合は output に戻します。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant'],
        wraplength=340,
        justify='left'
    ).pack(anchor='w', pady=(2, 8))

    save_to_output_var = tk.BooleanVar(value=app.config.get("save_to_output_dir", True))
    save_to_source_var = tk.BooleanVar(value=app.config.get("save_to_source_dir", False))

    ttk.Checkbutton(
        right_inner, text="output フォルダ",
        variable=save_to_output_var, command=lambda: on_output_toggle(),
        style='Modern.TCheckbutton'
    ).pack(anchor='w')

    ttk.Checkbutton(
        right_inner, text="元ファイル側にも保存",
        variable=save_to_source_var, command=lambda: on_source_toggle(),
        style='Modern.TCheckbutton'
    ).pack(anchor='w', pady=(4, 0))

    summary_grid = tk.Frame(frame, bg=theme.colors['surface'])
    summary_grid.pack(fill=tk.X, padx=pad, pady=(0, 10))
    summary_grid.grid_columnconfigure(0, weight=1)
    summary_grid.grid_columnconfigure(1, weight=1)
    summary_grid.grid_columnconfigure(2, weight=1)

    engine_tile = widgets.create_metric_tile(summary_grid, "エンジン", "Gemini", tone='primary')
    engine_tile.grid(row=0, column=0, sticky='ew', padx=(0, 6))

    model_tile = widgets.create_metric_tile(summary_grid, "モデル", "自動選択", tone='info')
    model_tile.grid(row=0, column=1, sticky='ew', padx=6)

    save_tile = widgets.create_metric_tile(summary_grid, "保存先", "output", tone='warning')
    save_tile.grid(row=0, column=2, sticky='ew', padx=(6, 0))

    drop_wrapper = tk.Frame(
        frame,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    drop_wrapper.pack(fill=tk.X, padx=pad, pady=(0, 8))

    drop_inner = tk.Frame(drop_wrapper, bg=theme.colors['surface_variant'])
    drop_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    tk.Label(
        drop_inner,
        text="ファイル投入",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w', pady=(0, 8))

    drop_container = widgets.create_drag_drop_canvas(
        drop_inner,
        "ここをクリックしてファイルを選択  /  ドラッグ&ドロップ",
        height=96
    )
    drop_container.pack(fill=tk.X)

    drop_canvas = drop_container.canvas
    drop_canvas.bind("<Button-1>", app.browse_file)
    setup_drag_drop(drop_canvas, drop_canvas, app)

    queue_frame = widgets.create_card_frame(frame)

    queue_header = tk.Frame(queue_frame, bg=theme.colors['surface'])
    queue_header.pack(fill=tk.X, padx=12, pady=(10, 6))

    queue_count_label = tk.Label(
        queue_header,
        text="待機ファイル: 0件",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    )
    queue_count_label.pack(side=tk.LEFT)

    queue_clear_btn = widgets.create_icon_button(
        queue_header, "クリア", ICONS['delete'], 'Secondary',
        command=lambda: app.clear_queue()
    )
    queue_clear_btn.pack(side=tk.RIGHT, padx=(6, 0))

    queue_remove_btn = widgets.create_icon_button(
        queue_header, "選択削除", ICONS['minus'], 'Secondary',
        command=lambda: app.remove_from_queue()
    )
    queue_remove_btn.pack(side=tk.RIGHT)

    queue_listbox = tk.Listbox(
        queue_frame,
        height=QUEUE_LISTBOX_HEIGHT,
        selectmode=tk.EXTENDED,
        font=theme.fonts['body'],
        bg=theme.colors['surface_variant'],
        fg=theme.colors['text_primary'],
        selectbackground=theme.colors['table_selected'],
        selectforeground=theme.colors['text_primary'],
        relief='solid',
        borderwidth=1,
        highlightthickness=0
    )
    queue_listbox.pack(fill=tk.X, padx=12, pady=(0, 12))

    status_card = tk.Frame(
        frame,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    status_card.pack(fill=tk.X, padx=pad, pady=(0, 10))

    status_inner = tk.Frame(status_card, bg=theme.colors['surface_variant'])
    status_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

    top_info = tk.Frame(status_inner, bg=theme.colors['surface_variant'])
    top_info.pack(fill=tk.X)

    file_label = tk.Label(
        top_info,
        text="選択ファイル: なし",
        font=theme.fonts['body_bold'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface_variant']
    )
    file_label.pack(side=tk.LEFT)

    status_group = tk.Frame(top_info, bg=theme.colors['surface_variant'])
    status_group.pack(side=tk.RIGHT)

    status_dot = tk.Label(
        status_group,
        text="\u25cf",
        font=(theme.fonts['default'][0], 8),
        fg=theme.colors['text_disabled'],
        bg=theme.colors['surface_variant']
    )
    status_dot.pack(side=tk.LEFT, padx=(0, 4))

    status_label = tk.Label(
        status_group,
        text="準備完了",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    status_label.pack(side=tk.LEFT)

    progress_caption = tk.Frame(status_inner, bg=theme.colors['surface_variant'])
    progress_caption.pack(fill=tk.X, pady=(10, 4))

    tk.Label(
        progress_caption,
        text="進行状況",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(side=tk.LEFT)

    progress_label = tk.Label(
        progress_caption, text="",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface_variant'],
        width=5, anchor='e'
    )
    progress_label.pack(side=tk.RIGHT)

    progress = ttk.Progressbar(
        status_inner, orient=tk.HORIZONTAL,
        mode='determinate', maximum=100, value=0,
        style='Modern.Horizontal.TProgressbar'
    )
    progress.pack(fill=tk.X)

    transcribe_btn = widgets.create_action_button(
        frame, f"{ICONS['play']} 文字起こしを開始",
        command=lambda: app.start_process("transcription")
    )
    transcribe_btn.pack(fill=tk.X, padx=pad, pady=(0, pad))

    def update_save_summary():
        destinations = []
        if save_to_output_var.get():
            destinations.append("output")
        if save_to_source_var.get():
            destinations.append("元フォルダ")
        if not destinations:
            destinations.append("output")
        save_tile.value_label.config(text=" / ".join(destinations))

    def on_output_toggle():
        if not save_to_output_var.get() and not save_to_source_var.get():
            save_to_output_var.set(True)
        app.config.set("save_to_output_dir", save_to_output_var.get())
        app.config.set("save_to_source_dir", save_to_source_var.get())
        app.config.save()
        update_save_summary()

    def on_source_toggle():
        if not save_to_source_var.get() and not save_to_output_var.get():
            save_to_source_var.set(True)
        app.config.set("save_to_output_dir", save_to_output_var.get())
        app.config.set("save_to_source_dir", save_to_source_var.get())
        app.config.save()
        update_save_summary()

    def on_engine_change():
        engine_value = engine_var.get()
        is_whisper = engine_value == "whisper"
        whisper_model_combo.config(state='readonly' if is_whisper else 'disabled')
        whisper_model_info.config(
            fg=theme.colors['text_secondary'] if is_whisper else theme.colors['text_disabled']
        )

        engine_map = {
            'gemini': 'Gemini',
            'whisper': 'Whisper',
            'whisper-api': 'Whisper API'
        }
        engine_tile.value_label.config(text=engine_map.get(engine_value, 'Gemini'))

        if engine_value == 'gemini':
            model_tile.value_label.config(text="自動選択")
        elif engine_value == 'whisper-api':
            model_tile.value_label.config(text="whisper-1")
        else:
            display_name = whisper_model_var.get()
            model_tile.value_label.config(text=display_to_model.get(display_name, 'turbo'))

        app.config.set("transcription_engine", engine_value)
        app.config.save()

    def on_model_change(event=None):
        display_name = whisper_model_var.get()
        model_name = display_to_model.get(display_name, 'turbo')
        whisper_model_info.config(text=model_details.get(model_name, ''))
        if engine_var.get() == 'whisper':
            model_tile.value_label.config(text=model_name)
        app.config.set("whisper_model", model_name)
        app.config.save()

    engine_var.trace('w', lambda *args: on_engine_change())
    whisper_model_combo.bind('<<ComboboxSelected>>', on_model_change)
    update_save_summary()
    on_engine_change()
    on_model_change()

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
    frame.queue_frame = queue_frame
    frame.queue_listbox = queue_listbox
    frame.queue_count_label = queue_count_label

    return frame


def create_history_section(parent, app, theme, widgets):
    """処理履歴セクションの作成"""
    card = widgets.create_card_frame(parent)

    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 6))

    header = widgets.create_section_header(header_frame, "処理履歴")
    header.pack(side=tk.LEFT, fill=tk.X, expand=True)

    refresh_btn = widgets.create_icon_button(
        header_frame, "更新", ICONS['refresh'], 'Secondary',
        command=app.update_history
    )
    refresh_btn.pack(side=tk.RIGHT)

    tk.Label(
        card,
        text="出力済みテキストの一覧です。ダブルクリックで開けます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w', padx=CARD_PADDING, pady=(0, 10))

    tree_shell = tk.Frame(
        card,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    tree_shell.pack(fill=tk.BOTH, expand=True, padx=CARD_PADDING, pady=(0, 10))

    tree_frame = tk.Frame(tree_shell, bg=theme.colors['surface_variant'])
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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

    delete_btn = widgets.create_icon_button(
        button_frame, "削除", ICONS['delete'], 'Secondary',
        command=app.delete_output_file
    )
    delete_btn.pack(side=tk.RIGHT)

    card.history_tree = history_tree

    return card


def create_usage_section(parent, app, theme, widgets):
    """使用量表示セクション"""
    card = widgets.create_card_frame(parent)

    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 6))

    header = widgets.create_section_header(header_frame, "今月使用量", bg=theme.colors['surface'])
    header.pack(side=tk.LEFT, fill=tk.X, expand=True)

    widgets.create_pill_label(
        header_frame, "Geminiのみ概算", tone='warning'
    ).pack(side=tk.RIGHT, padx=(0, 6))

    refresh_btn = widgets.create_icon_button(
        header_frame, "更新", ICONS['refresh'], 'Secondary',
        command=app.update_usage_display
    )
    refresh_btn.pack(side=tk.RIGHT)

    tk.Label(
        card,
        text="トークン数と料金は概算値です。ローカル Whisper はここには加算されません。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w', padx=CARD_PADDING, pady=(0, 10))

    stats_grid = tk.Frame(card, bg=theme.colors['surface'])
    stats_grid.pack(fill=tk.BOTH, expand=True, padx=CARD_PADDING, pady=(0, CARD_PADDING))
    stats_grid.grid_columnconfigure(0, weight=1)
    stats_grid.grid_columnconfigure(1, weight=1)

    sessions_tile = widgets.create_metric_tile(stats_grid, "セッション", "0回", tone='primary')
    sessions_tile.grid(row=0, column=0, sticky='ew', padx=(0, 6), pady=(0, 8))

    tokens_tile = widgets.create_metric_tile(stats_grid, "トークン", "0", tone='info')
    tokens_tile.grid(row=0, column=1, sticky='ew', padx=(6, 0), pady=(0, 8))

    usd_tile = widgets.create_metric_tile(stats_grid, "USD", "$0.000", tone='success')
    usd_tile.grid(row=1, column=0, sticky='ew', padx=(0, 6))

    jpy_tile = widgets.create_metric_tile(stats_grid, "JPY", "\xa50", tone='warning')
    jpy_tile.grid(row=1, column=1, sticky='ew', padx=(6, 0))

    card.sessions_value = sessions_tile.value_label
    card.tokens_value = tokens_tile.value_label
    card.cost_usd_value = usd_tile.value_label
    card.cost_jpy_value = jpy_tile.value_label

    return card


def create_log_section(parent, app, theme, widgets):
    """処理ログセクション（ダークテーマ）"""
    card = widgets.create_card_frame(parent)

    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 6))

    header = widgets.create_section_header(header_frame, "処理ログ")
    header.pack(side=tk.LEFT, fill=tk.X, expand=True)
    widgets.create_pill_label(
        header_frame, "LIVE", tone='info'
    ).pack(side=tk.RIGHT)

    tk.Label(
        card,
        text="処理経過、使用モデル、エラー詳細をここに表示します。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w', padx=CARD_PADDING, pady=(0, 10))

    log_shell = tk.Frame(
        card,
        bg=theme.colors['log_bg'],
        highlightbackground=theme.colors['hero_border'],
        highlightthickness=1,
        bd=0
    )
    log_shell.pack(fill=tk.BOTH, expand=True, padx=CARD_PADDING, pady=(0, CARD_PADDING))

    log_text = scrolledtext.ScrolledText(
        log_shell,
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
    log_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    log_text.config(state=tk.DISABLED)

    widgets.configure_log_tags(log_text)

    card.log_text = log_text

    return card


def setup_drag_drop(drop_area, drop_label, app):
    """ドラッグ&ドロップ機能の設定（複数ファイル対応）"""
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD

        if isinstance(app.root, TkinterDnD.Tk):
            drop_area.drop_target_register(DND_FILES)
            drop_area.dnd_bind('<<Drop>>', lambda e: app.load_files(e.data))
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
        'queue_frame': file_section.queue_frame,
        'queue_listbox': file_section.queue_listbox,
        'queue_count_label': file_section.queue_count_label,
        'usage_sessions': usage_section.sessions_value,
        'usage_tokens': usage_section.tokens_value,
        'usage_cost_usd': usage_section.cost_usd_value,
        'usage_cost_jpy': usage_section.cost_jpy_value,
        'history_tree': history_section.history_tree,
        'log_text': log_section.log_text
    }
