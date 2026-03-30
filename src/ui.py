#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
モダンなUIレイアウトの実装
カード・セクションヘッダー・ダークログ・キャンバスD&Dを採用
"""

import math
import tkinter as tk
from tkinter import ttk, scrolledtext

from .ui_styles import ModernTheme, ModernWidgets, ICONS
from .waveform_viewer import WaveformViewer
from .whisper_api_service import WhisperApiService
from .constants import (
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    CARD_PADDING, SECTION_SPACING, MAIN_PADDING_X,
    MAIN_PADDING_Y, QUEUE_LISTBOX_HEIGHT,
    DEFAULT_SILENCE_TRIM_MODE,
    DEFAULT_SILENCE_TRIM_THRESHOLD_DB,
    DEFAULT_SILENCE_TRIM_MIN_SILENCE_SEC
)


def _bind_dynamic_wraplength(label, padding=0):
    """ラベルの wraplength を親ウィジェットの幅に追従させる"""
    def _update(event=None):
        parent = label.winfo_parent()
        parent_widget = label.nametowidget(parent)
        w = parent_widget.winfo_width()
        if w > 1:
            label.config(wraplength=max(100, w - padding * 2 - 10))
    label.bind('<Configure>', _update)


def _create_scrollable_frame(parent, bg):
    """スクロール可能なフレームを作成。(outer_frame, inner_frame) を返す。

    outer_frame を親にpackし、inner_frame の中にコンテンツを配置する。
    マウスホイールでスクロールでき、コンテンツが収まる場合はスクロールバーを非表示にする。
    """
    outer = tk.Frame(parent, bg=bg)

    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(
        outer, orient=tk.VERTICAL, command=canvas.yview,
        style='Modern.Vertical.TScrollbar'
    )
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    # スクロールバーは必要時のみ表示（初期非表示）

    inner = tk.Frame(canvas, bg=bg)
    canvas_window = canvas.create_window((0, 0), window=inner, anchor='nw')

    def _on_inner_configure(event=None):
        canvas.configure(scrollregion=canvas.bbox('all'))
        _update_scrollbar_visibility()

    def _on_canvas_configure(event):
        canvas.itemconfig(canvas_window, width=event.width)
        _update_scrollbar_visibility()

    def _update_scrollbar_visibility():
        canvas.update_idletasks()
        content_h = inner.winfo_reqheight()
        viewport_h = canvas.winfo_height()
        if content_h > viewport_h + 2:
            if not scrollbar.winfo_ismapped():
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            if scrollbar.winfo_ismapped():
                scrollbar.pack_forget()
            canvas.yview_moveto(0)

    def _on_mousewheel(event):
        # コンテンツが収まっている場合はスクロールしない
        content_h = inner.winfo_reqheight()
        viewport_h = canvas.winfo_height()
        if content_h <= viewport_h + 2:
            return
        canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _bind_wheel(event=None):
        canvas.bind_all('<MouseWheel>', _on_mousewheel)

    def _unbind_wheel(event=None):
        canvas.unbind_all('<MouseWheel>')

    canvas.bind('<Enter>', _bind_wheel)
    canvas.bind('<Leave>', _unbind_wheel)
    inner.bind('<Configure>', _on_inner_configure)
    canvas.bind('<Configure>', _on_canvas_configure)

    outer._scroll_canvas = canvas
    outer._scroll_inner = inner

    return outer, inner


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

    # === 全体: 左右をドラッグで調整できる横PanedWindow ===
    main_paned = tk.PanedWindow(
        main_container, orient=tk.HORIZONTAL,
        bg=theme.colors['background'],
        sashwidth=8, sashrelief='flat',
        showhandle=True, handlesize=10, handlepad=6,
        opaqueresize=True
    )
    main_paned.pack(fill=tk.BOTH, expand=True)

    work_pane = tk.Frame(main_paned, bg=theme.colors['background'])
    side_pane = tk.Frame(main_paned, bg=theme.colors['background'])

    main_paned.add(work_pane, minsize=480)
    main_paned.add(side_pane, minsize=280)

    # === 左側: 作業タブ（折りたたみ可能） ===
    accordion_state = {'expanded': True}

    # アコーディオンのトグルバー
    toggle_bar = tk.Frame(
        work_pane,
        bg=theme.colors['surface_variant'],
        cursor='hand2'
    )
    toggle_bar.pack(fill=tk.X, pady=(0, 2))

    toggle_inner = tk.Frame(toggle_bar, bg=theme.colors['surface_variant'])
    toggle_inner.pack(fill=tk.X, padx=10, pady=4)

    toggle_arrow = tk.Label(
        toggle_inner,
        text='\u25bc',
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    toggle_arrow.pack(side=tk.LEFT, padx=(0, 8))

    toggle_label = tk.Label(
        toggle_inner,
        text='作業パネルを閉じる',
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    toggle_label.pack(side=tk.LEFT)

    # 上部コンテンツ（折りたたみ対象）
    upper_frame = tk.Frame(work_pane, bg=theme.colors['background'])
    upper_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

    # タブ（文字起こし / 録音 / API設定・使用量）
    notebook = ttk.Notebook(upper_frame, style='Modern.TNotebook')
    notebook.pack(fill=tk.BOTH, expand=True, pady=(0, SECTION_SPACING))
    tab_keys = []

    # タブ1: 文字起こし（スクロール可能）
    file_tab = tk.Frame(notebook, bg=theme.colors['surface'])
    notebook.add(file_tab, text='文字起こし')
    tab_keys.append('file')
    file_scroll_outer, file_scroll_inner = _create_scrollable_frame(
        file_tab, theme.colors['surface']
    )
    file_scroll_outer.pack(fill=tk.BOTH, expand=True)
    file_section = create_file_section(file_scroll_inner, app, theme, widgets)
    file_section.pack(fill=tk.X)

    # タブ2: 録音（スクロール可能）
    recording_tab = tk.Frame(notebook, bg=theme.colors['surface'])
    notebook.add(recording_tab, text='録音')
    tab_keys.append('recording')
    recording_scroll_outer, recording_scroll_inner = _create_scrollable_frame(
        recording_tab, theme.colors['surface']
    )
    recording_scroll_outer.pack(fill=tk.BOTH, expand=True)
    recording_section = create_recording_section(recording_scroll_inner, app, theme, widgets)
    recording_section.pack(fill=tk.X)

    # タブ3: API設定・使用量（スクロール可能 + レスポンシブ横並び/縦積み切替）
    settings_tab = tk.Frame(notebook, bg=theme.colors['surface'])
    notebook.add(settings_tab, text='接続・使用量')
    tab_keys.append('settings')
    settings_scroll_outer, settings_scroll_inner = _create_scrollable_frame(
        settings_tab, theme.colors['surface']
    )
    settings_scroll_outer.pack(fill=tk.BOTH, expand=True)
    settings_content = tk.Frame(settings_scroll_inner, bg=theme.colors['surface'])
    settings_content.pack(fill=tk.X, padx=6, pady=6)
    api_section = create_api_section(settings_content, app, theme, widgets)
    usage_section = create_usage_section(settings_content, app, theme, widgets)

    # 幅に応じて横並び/縦積みを切替
    _settings_layout_state = {'is_horizontal': None}

    def _relayout_settings(event=None):
        w = settings_content.winfo_width()
        threshold = 640
        want_horizontal = w >= threshold

        if _settings_layout_state['is_horizontal'] == want_horizontal:
            return
        _settings_layout_state['is_horizontal'] = want_horizontal

        api_section.pack_forget()
        usage_section.pack_forget()

        if want_horizontal:
            api_section.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
            usage_section.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))
        else:
            api_section.pack(fill=tk.X, pady=(0, 8))
            usage_section.pack(fill=tk.X, pady=(8, 0))

    settings_content.bind('<Configure>', _relayout_settings)

    def _save_current_tab(event=None):
        try:
            current_index = notebook.index(notebook.select())
        except tk.TclError:
            return
        if 0 <= current_index < len(tab_keys):
            app.config.set("last_open_tab", tab_keys[current_index])
            app.config.save()

    saved_tab_key = app.config.get("last_open_tab", "file")
    if saved_tab_key in tab_keys:
        notebook.select(tab_keys.index(saved_tab_key))

    notebook.bind('<<NotebookTabChanged>>', _save_current_tab)

    # アコーディオンのトグル処理
    def _toggle_accordion(event=None):
        if accordion_state['expanded']:
            upper_frame.pack_forget()
            toggle_arrow.config(text='\u25b6')
            toggle_label.config(text='作業パネルを開く')
            accordion_state['expanded'] = False
        else:
            # toggle_bar の直後に upper_frame を挿入
            upper_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6), after=toggle_bar)
            toggle_arrow.config(text='\u25bc')
            toggle_label.config(text='作業パネルを閉じる')
            accordion_state['expanded'] = True

    # バー全体をクリック可能に
    for w in (toggle_bar, toggle_inner, toggle_arrow, toggle_label):
        w.bind('<Button-1>', _toggle_accordion)

    # ホバー効果
    def _toggle_enter(event=None):
        for w in (toggle_bar, toggle_inner, toggle_arrow, toggle_label):
            w.config(bg=theme.colors['surface_emphasis'])
    def _toggle_leave(event=None):
        for w in (toggle_bar, toggle_inner, toggle_arrow, toggle_label):
            w.config(bg=theme.colors['surface_variant'])

    toggle_bar.bind('<Enter>', _toggle_enter)
    toggle_bar.bind('<Leave>', _toggle_leave)

    # === 右側: 処理履歴とログを上下に分割 ===
    paned = tk.PanedWindow(
        side_pane, orient=tk.VERTICAL,
        bg=theme.colors['background'],
        sashwidth=6, sashrelief='flat',
        showhandle=True, handlesize=8, handlepad=4,
        opaqueresize=True
    )
    paned.pack(fill=tk.BOTH, expand=True)

    history_section = create_history_section(paned, app, theme, widgets)
    paned.add(history_section, stretch='always', minsize=220)

    log_section = create_log_section(paned, app, theme, widgets)
    paned.add(log_section, stretch='always', minsize=180)

    # 右側PanedWindow の初期比率を設定
    def _set_initial_side_sash(event=None):
        paned.update_idletasks()
        total_h = paned.winfo_height()
        if total_h > 10:
            paned.sash_place(0, 0, int(total_h * 0.58))
            paned.unbind('<Map>')
    paned.bind('<Map>', _set_initial_side_sash)

    # 全体の左右比率を設定
    def _set_initial_main_sash(event=None):
        main_paned.update_idletasks()
        total_w = main_paned.winfo_width()
        if total_w > 10:
            main_paned.sash_place(0, int(total_w * 0.70), 0)
            main_paned.unbind('<Map>')
    main_paned.bind('<Map>', _set_initial_main_sash)

    # UI要素を収集
    ui_elements = collect_ui_elements(
        api_section, file_section, recording_section, usage_section, history_section, log_section
    )

    return ui_elements



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

    api_desc = tk.Label(
        card,
        text="利用するエンジンに応じて認証情報を登録します。Gemini は要約やタイトル生成、Whisper API は OpenAI 側の音声認識に使います。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    api_desc.pack(anchor='w', fill=tk.X, padx=CARD_PADDING, pady=(0, 12))
    _bind_dynamic_wraplength(api_desc, CARD_PADDING)

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
    pad = 12

    header_frame = tk.Frame(frame, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=pad, pady=(pad, 8))

    widgets.create_section_header(header_frame, "作業フロー").pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )
    widgets.create_pill_label(
        header_frame, "3ステップ", tone='success'
    ).pack(side=tk.RIGHT)

    intro_label = tk.Label(
        frame,
        text="既存ファイルの文字起こし用です。マイク録音は「録音」タブに分けています。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    intro_label.pack(fill=tk.X, padx=pad, pady=(0, 8))
    _bind_dynamic_wraplength(intro_label, pad)

    step_strip = tk.Frame(frame, bg=theme.colors['surface'])
    step_strip.pack(fill=tk.X, padx=pad, pady=(0, 8))
    step_strip.grid_columnconfigure(0, weight=1)
    step_strip.grid_columnconfigure(1, weight=1)
    step_strip.grid_columnconfigure(2, weight=1)

    def _create_step_card(parent_widget, title, body, accent):
        card = tk.Frame(
            parent_widget,
            bg=theme.colors['surface_variant'],
            highlightbackground=theme.colors['card_border'],
            highlightthickness=1,
            bd=0
        )
        stripe = tk.Frame(card, bg=accent, height=4)
        stripe.pack(fill=tk.X)
        body_frame = tk.Frame(card, bg=theme.colors['surface_variant'])
        body_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        tk.Label(
            body_frame,
            text=title,
            font=theme.fonts['caption_bold'],
            fg=theme.colors['text_primary'],
            bg=theme.colors['surface_variant']
        ).pack(anchor='w')
        text_label = tk.Label(
            body_frame,
            text=body,
            font=theme.fonts['caption'],
            fg=theme.colors['text_secondary'],
            bg=theme.colors['surface_variant'],
            justify='left',
            anchor='w'
        )
        text_label.pack(fill=tk.X, pady=(6, 0))
        _bind_dynamic_wraplength(text_label, 12)
        return card

    _create_step_card(
        step_strip,
        "1. ファイルを追加",
        "音声や動画ファイルをドラッグ&ドロップ、または選択します。",
        theme.colors['error']
    ).grid(row=0, column=0, sticky='ew', padx=(0, 6))
    _create_step_card(
        step_strip,
        "2. 処理条件を決める",
        "エンジンと保存先だけ確認すれば実行できます。",
        theme.colors['primary']
    ).grid(row=0, column=1, sticky='ew', padx=6)
    _create_step_card(
        step_strip,
        "3. 開始する",
        "キューにたまったファイルをまとめて文字起こしします。",
        theme.colors['warning']
    ).grid(row=0, column=2, sticky='ew', padx=(6, 0))

    quick_action_row = tk.Frame(frame, bg=theme.colors['surface'])
    quick_action_row.pack(fill=tk.X, padx=pad, pady=(0, 10))

    quick_file_btn = widgets.create_icon_button(
        quick_action_row, "ファイルを追加", ICONS['folder'], 'Primary',
        command=app.browse_file
    )
    quick_file_btn.pack(side=tk.LEFT, padx=(0, 6))

    quick_run_btn = widgets.create_icon_button(
        quick_action_row, "文字起こし開始", ICONS['play'], 'Secondary',
        command=lambda: app.start_process("transcription")
    )
    quick_run_btn.pack(side=tk.LEFT)

    config_strip = tk.Frame(frame, bg=theme.colors['surface'])
    config_strip.pack(fill=tk.X, padx=pad, pady=(0, 8))

    left_panel = tk.Frame(
        config_strip,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )

    right_panel = tk.Frame(
        config_strip,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )

    # 幅に応じて横並び/縦積みを切替
    _config_layout_state = {'is_horizontal': None}

    def _relayout_config(event=None):
        w = config_strip.winfo_width()
        threshold = 540
        want_horizontal = w >= threshold

        if _config_layout_state['is_horizontal'] == want_horizontal:
            return
        _config_layout_state['is_horizontal'] = want_horizontal

        left_panel.pack_forget()
        right_panel.pack_forget()

        if want_horizontal:
            left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
            right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        else:
            left_panel.pack(fill=tk.X, pady=(0, 6))
            right_panel.pack(fill=tk.X, pady=(6, 0))

    config_strip.bind('<Configure>', _relayout_config)

    left_inner = tk.Frame(left_panel, bg=theme.colors['surface_variant'])
    left_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    tk.Label(
        left_inner,
        text="エンジン",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    saved_engine = app.config.get("transcription_engine", "gemini")
    engine_var = tk.StringVar(value=saved_engine)

    engine_row = tk.Frame(left_inner, bg=theme.colors['surface_variant'])
    engine_row.pack(fill=tk.X, pady=(6, 8))

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

    # Whisper API モデル選択
    whisper_api_model_label = tk.Label(
        left_inner,
        text="Whisper API モデル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    whisper_api_model_label.pack(anchor='w', pady=(10, 0))

    whisper_api_display_names = WhisperApiService.MODEL_DESCRIPTIONS
    whisper_api_display_to_model = {v: k for k, v in whisper_api_display_names.items()}

    saved_whisper_api_model = app.config.get(
        "whisper_api_model", WhisperApiService.DEFAULT_MODEL
    )
    if saved_whisper_api_model not in whisper_api_display_names:
        saved_whisper_api_model = WhisperApiService.DEFAULT_MODEL

    whisper_api_model_var = tk.StringVar(
        value=whisper_api_display_names.get(saved_whisper_api_model, '')
    )
    whisper_api_model_combo = ttk.Combobox(
        left_inner,
        textvariable=whisper_api_model_var,
        values=list(whisper_api_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    whisper_api_model_combo.pack(fill=tk.X, pady=(6, 0))

    whisper_api_pricing_text = {
        k: f"${v}/分" for k, v in WhisperApiService.MODEL_PRICING.items()
    }
    whisper_api_model_info = tk.Label(
        left_inner,
        text=whisper_api_pricing_text.get(saved_whisper_api_model, ''),
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    whisper_api_model_info.pack(anchor='w', pady=(4, 0))

    gemini_recovery_label = tk.Label(
        left_inner,
        text="Gemini ブロック時の動作",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    gemini_recovery_label.pack(anchor='w', pady=(10, 0))

    gemini_recovery_display_names = {
        'segment-whisper': '分割再試行 + ブロック区間をWhisperで補完（推奨）',
        'segment': '音声を分割して再試行（ブロック区間は除外）',
        'whisper': 'Whisper に自動切替',
    }
    gemini_recovery_display_to_mode = {v: k for k, v in gemini_recovery_display_names.items()}
    gemini_recovery_details = {
        'segment-whisper': 'Geminiで再試行し、弾かれた区間だけWhisperで補完',
        'segment': 'Geminiで細かく再試行し、弾かれた区間だけ除外して継続',
        'whisper': 'Geminiで弾かれたらすぐローカルWhisperへ切替',
    }
    saved_gemini_recovery = app.config.get("gemini_safety_filter_recovery", "segment")
    if saved_gemini_recovery not in gemini_recovery_display_names:
        saved_gemini_recovery = 'segment'

    gemini_recovery_var = tk.StringVar(
        value=gemini_recovery_display_names.get(saved_gemini_recovery, '')
    )
    gemini_recovery_combo = ttk.Combobox(
        left_inner,
        textvariable=gemini_recovery_var,
        values=list(gemini_recovery_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    gemini_recovery_combo.pack(fill=tk.X, pady=(6, 0))

    gemini_recovery_info = tk.Label(
        left_inner,
        text=gemini_recovery_details.get(saved_gemini_recovery, ''),
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    gemini_recovery_info.pack(anchor='w', pady=(4, 0))

    # タイトル生成エンジン選択
    title_engine_label = tk.Label(
        left_inner,
        text="タイトル生成エンジン",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    title_engine_label.pack(anchor='w', pady=(10, 0))

    title_engine_display_names = {
        'auto': '自動（Gemini → Ollama）',
        'ollama': 'Ollama（ローカル）',
        'gemini': 'Gemini API',
        'disabled': '無効',
    }
    title_engine_display_to_mode = {v: k for k, v in title_engine_display_names.items()}

    saved_title_engine = app.config.get("title_generation_engine", "auto")
    title_engine_var = tk.StringVar(
        value=title_engine_display_names.get(saved_title_engine, title_engine_display_names['auto'])
    )
    title_engine_combo = ttk.Combobox(
        left_inner,
        textvariable=title_engine_var,
        values=list(title_engine_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    title_engine_combo.pack(fill=tk.X, pady=(6, 0))

    right_inner = tk.Frame(right_panel, bg=theme.colors['surface_variant'])
    right_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    tk.Label(
        right_inner,
        text="保存先",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    save_desc = tk.Label(
        right_inner,
        text="出力先は複数指定できます。どちらもオフにした場合は output に戻します。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant'],
        justify='left',
        anchor='w'
    )
    save_desc.pack(anchor='w', fill=tk.X, pady=(2, 6))
    _bind_dynamic_wraplength(save_desc, 24)

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

    rename_source_var = tk.BooleanVar(value=app.config.get("rename_source_file", False))
    ttk.Checkbutton(
        right_inner, text="元ファイルを要約タイトルでリネーム",
        variable=rename_source_var,
        command=lambda: (
            app.config.set("rename_source_file", rename_source_var.get()),
            app.config.save()
        ),
        style='Modern.TCheckbutton'
    ).pack(anchor='w', pady=(4, 0))

    trim_long_silence_var = tk.BooleanVar(
        value=app.config.get("trim_long_silence", True)
    )

    ttk.Checkbutton(
        right_inner, text="長い無音を自動圧縮",
        variable=trim_long_silence_var, command=lambda: on_trim_long_silence_toggle(),
        style='Modern.TCheckbutton'
    ).pack(anchor='w', pady=(10, 0))

    trim_long_silence_desc = tk.Label(
        right_inner,
        text="会話が無い長めの区間を短く詰めます。下の判定条件は波形プレビューと実処理の両方に反映されます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant'],
        justify='left',
        anchor='w'
    )
    trim_long_silence_desc.pack(anchor='w', fill=tk.X, pady=(2, 0))
    _bind_dynamic_wraplength(trim_long_silence_desc, 24)

    silence_settings_shell = tk.Frame(
        right_inner,
        bg=theme.colors['surface'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    silence_settings_shell.pack(fill=tk.X, pady=(10, 0))

    silence_settings_inner = tk.Frame(silence_settings_shell, bg=theme.colors['surface'])
    silence_settings_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    silence_mode_header = tk.Frame(silence_settings_inner, bg=theme.colors['surface'])
    silence_mode_header.pack(fill=tk.X)

    tk.Label(
        silence_mode_header,
        text="無音カット判定",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(side=tk.LEFT)

    tk.Label(
        silence_mode_header,
        text="波形へ自動反映",
        font=theme.fonts['caption'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface']
    ).pack(side=tk.RIGHT)

    silence_trim_mode_display_to_value = {
        "自動判定（推奨）": "auto",
        "手動しきい値": "manual",
    }
    silence_trim_mode_value_to_display = {
        value: display for display, value in silence_trim_mode_display_to_value.items()
    }
    silence_trim_mode_var = tk.StringVar(
        value=silence_trim_mode_value_to_display.get(
            app.config.get("silence_trim_mode", DEFAULT_SILENCE_TRIM_MODE),
            "自動判定（推奨）"
        )
    )
    silence_trim_threshold_db_var = tk.DoubleVar(
        value=float(app.config.get("silence_trim_threshold_db", DEFAULT_SILENCE_TRIM_THRESHOLD_DB))
    )
    silence_trim_min_silence_sec_var = tk.DoubleVar(
        value=float(app.config.get("silence_trim_min_silence_sec", DEFAULT_SILENCE_TRIM_MIN_SILENCE_SEC))
    )

    silence_trim_mode_combo = ttk.Combobox(
        silence_settings_inner,
        textvariable=silence_trim_mode_var,
        values=list(silence_trim_mode_display_to_value.keys()),
        state='readonly',
        style='Modern.TCombobox'
    )
    silence_trim_mode_combo.pack(fill=tk.X, pady=(6, 8))

    threshold_header = tk.Frame(silence_settings_inner, bg=theme.colors['surface'])
    threshold_header.pack(fill=tk.X)

    tk.Label(
        threshold_header,
        text="しきい値 (dB)",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(side=tk.LEFT)

    silence_trim_threshold_value_label = tk.Label(
        threshold_header,
        text="",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface']
    )
    silence_trim_threshold_value_label.pack(side=tk.RIGHT)

    silence_trim_threshold_scale = ttk.Scale(
        silence_settings_inner,
        from_=-60,
        to=-18,
        orient=tk.HORIZONTAL,
        variable=silence_trim_threshold_db_var
    )
    silence_trim_threshold_scale.pack(fill=tk.X, pady=(4, 8))

    min_silence_header = tk.Frame(silence_settings_inner, bg=theme.colors['surface'])
    min_silence_header.pack(fill=tk.X)

    tk.Label(
        min_silence_header,
        text="無音とみなす長さ",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(side=tk.LEFT)

    silence_trim_min_value_label = tk.Label(
        min_silence_header,
        text="",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface']
    )
    silence_trim_min_value_label.pack(side=tk.RIGHT)

    silence_trim_min_scale = ttk.Scale(
        silence_settings_inner,
        from_=0.5,
        to=5.0,
        orient=tk.HORIZONTAL,
        variable=silence_trim_min_silence_sec_var
    )
    silence_trim_min_scale.pack(fill=tk.X, pady=(4, 4))

    silence_trim_note = tk.Label(
        silence_settings_inner,
        text="",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    silence_trim_note.pack(fill=tk.X, pady=(2, 0))
    _bind_dynamic_wraplength(silence_trim_note, 12)

    summary_grid = tk.Frame(frame, bg=theme.colors['surface'])
    summary_grid.pack(fill=tk.X, padx=pad, pady=(0, 8))
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
    drop_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    drop_header = tk.Frame(drop_inner, bg=theme.colors['surface_variant'])
    drop_header.pack(fill=tk.X, pady=(0, 6))

    tk.Label(
        drop_header,
        text="既存ファイルを追加",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(side=tk.LEFT)

    widgets.create_pill_label(
        drop_header,
        "クリックまたはドラッグ",
        tone='info',
        bg=theme.colors['surface'],
        fg=theme.colors['primary']
    ).pack(side=tk.RIGHT)

    drop_container = widgets.create_drag_drop_canvas(
        drop_inner,
        title="クリックしてファイルを選択",
        subtitle="またはこの欄にドラッグ&ドロップ",
        height=128
    )
    drop_container.pack(fill=tk.X)

    drop_canvas = drop_container.canvas
    drop_canvas.bind("<Button-1>", app.browse_file)
    setup_drag_drop(drop_canvas, drop_canvas, app)

    queue_frame = widgets.create_card_frame(frame)

    queue_header = tk.Frame(queue_frame, bg=theme.colors['surface'])
    queue_header.pack(fill=tk.X, padx=10, pady=(8, 4))

    queue_count_label = tk.Label(
        queue_header,
        text="現在のキュー: 0件",
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

    queue_tree_shell = tk.Frame(queue_frame, bg=theme.colors['surface'])
    queue_tree_shell.pack(fill=tk.X, padx=10, pady=(0, 10))

    queue_tree = ttk.Treeview(
        queue_tree_shell,
        columns=('order', 'name', 'location', 'state'),
        show='headings',
        height=QUEUE_LISTBOX_HEIGHT,
        style='Modern.Treeview',
        selectmode='extended'
    )
    queue_tree.heading('order', text='#')
    queue_tree.heading('name', text='ファイル')
    queue_tree.heading('location', text='場所')
    queue_tree.heading('state', text='状態')
    queue_tree.column('order', width=42, minwidth=42, stretch=False, anchor='center')
    queue_tree.column('name', width=240, minwidth=140, stretch=True)
    queue_tree.column('location', width=280, minwidth=140, stretch=True)
    queue_tree.column('state', width=132, minwidth=110, stretch=False)
    queue_tree.tag_configure('queue_ready', background=theme.colors['surface'])
    queue_tree.tag_configure(
        'queue_missing',
        background=theme.colors['error_soft'],
        foreground=theme.colors['error']
    )
    queue_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)

    queue_scrollbar = ttk.Scrollbar(
        queue_tree_shell,
        orient=tk.VERTICAL,
        command=queue_tree.yview,
        style='Modern.Vertical.TScrollbar'
    )
    queue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    queue_tree.configure(yscrollcommand=queue_scrollbar.set)
    queue_tree.bind('<Delete>', lambda _event: app.remove_from_queue())

    # 入力導線を先に見せるため、詳細設定はファイル追加の後ろへ並べ直す
    config_strip.pack_forget()
    summary_grid.pack_forget()
    config_strip.pack(fill=tk.X, padx=pad, pady=(0, 8))
    summary_grid.pack(fill=tk.X, padx=pad, pady=(0, 8))

    status_card = tk.Frame(
        frame,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    status_card.pack(fill=tk.X, padx=pad, pady=(0, 8))

    status_inner = tk.Frame(status_card, bg=theme.colors['surface_variant'])
    status_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

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
        text="開始待ち",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    status_label.pack(side=tk.LEFT)

    # ウェーブフォームビューア（プログレスバーの上に配置）
    waveform_viewer = WaveformViewer(status_inner, theme)
    # show() 呼び出しまで非表示

    progress_caption = tk.Frame(status_inner, bg=theme.colors['surface_variant'])
    progress_caption.pack(fill=tk.X, pady=(8, 4))

    tk.Label(
        progress_caption,
        text="実行状況",
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

    def _save_silence_trim_settings():
        mode_value = silence_trim_mode_display_to_value.get(
            silence_trim_mode_var.get(),
            DEFAULT_SILENCE_TRIM_MODE
        )
        app.config.set("silence_trim_mode", mode_value)
        app.config.set("silence_trim_threshold_db", round(float(silence_trim_threshold_db_var.get()), 1))
        app.config.set("silence_trim_min_silence_sec", round(float(silence_trim_min_silence_sec_var.get()), 1))
        app.config.save()

    def _update_silence_trim_controls():
        mode_value = silence_trim_mode_display_to_value.get(
            silence_trim_mode_var.get(),
            DEFAULT_SILENCE_TRIM_MODE
        )
        is_manual = mode_value == 'manual'
        threshold_value = round(float(silence_trim_threshold_db_var.get()), 1)
        min_silence_value = round(float(silence_trim_min_silence_sec_var.get()), 1)
        silence_trim_threshold_db_var.set(threshold_value)
        silence_trim_min_silence_sec_var.set(min_silence_value)

        silence_trim_threshold_value_label.config(
            text=f"{threshold_value:.1f} dB" if is_manual else "自動推定"
        )
        silence_trim_min_value_label.config(text=f"{min_silence_value:.1f} 秒")
        silence_trim_threshold_scale.configure(state='normal' if is_manual else 'disabled')

        if trim_long_silence_var.get():
            if is_manual:
                note_text = "手動値をそのまま使います。波形を見ながら詰めすぎを避けたいとき向けです。"
            else:
                note_text = "音量分布からしきい値を推定します。環境音が変わる素材でも合わせやすくなります。"
        else:
            note_text = "現在は圧縮OFFです。波形プレビューだけ確認し、良さそうならオンにできます。"

        silence_trim_note.config(text=note_text)

    def on_silence_trim_mode_change(event=None):
        _update_silence_trim_controls()
        _save_silence_trim_settings()
        app.on_silence_trim_settings_changed(immediate=True)

    def on_silence_trim_threshold_change(value=None):
        _update_silence_trim_controls()
        app.on_silence_trim_settings_changed(immediate=False)

    def on_silence_trim_min_change(value=None):
        _update_silence_trim_controls()
        app.on_silence_trim_settings_changed(immediate=False)

    def persist_silence_trim_settings(event=None):
        _save_silence_trim_settings()
        app.on_silence_trim_settings_changed(immediate=False)

    def on_trim_long_silence_toggle():
        app.config.set("trim_long_silence", trim_long_silence_var.get())
        app.config.save()
        _update_silence_trim_controls()
        app.on_silence_trim_settings_changed(immediate=True)

    def on_engine_change():
        engine_value = engine_var.get()
        is_gemini = engine_value == "gemini"
        is_whisper = engine_value == "whisper"
        is_whisper_api = engine_value == "whisper-api"

        whisper_model_combo.config(state='readonly' if is_whisper else 'disabled')
        whisper_model_info.config(
            fg=theme.colors['text_secondary'] if is_whisper else theme.colors['text_disabled']
        )

        # Whisper APIモデル選択の有効/無効切り替え
        whisper_api_model_combo.config(state='readonly' if is_whisper_api else 'disabled')
        api_label_color = theme.colors['text_secondary'] if is_whisper_api else theme.colors['text_disabled']
        whisper_api_model_label.config(fg=api_label_color)
        whisper_api_model_info.config(fg=api_label_color)

        gemini_recovery_combo.config(state='readonly' if is_gemini else 'disabled')
        recovery_label_color = theme.colors['text_secondary'] if is_gemini else theme.colors['text_disabled']
        gemini_recovery_label.config(fg=recovery_label_color)
        gemini_recovery_info.config(fg=recovery_label_color)

        engine_map = {
            'gemini': 'Gemini',
            'whisper': 'Whisper',
            'whisper-api': 'Whisper API'
        }
        engine_tile.value_label.config(text=engine_map.get(engine_value, 'Gemini'))

        if engine_value == 'gemini':
            model_tile.value_label.config(text="自動選択")
        elif engine_value == 'whisper-api':
            api_display = whisper_api_model_var.get()
            api_model = whisper_api_display_to_model.get(api_display, WhisperApiService.DEFAULT_MODEL)
            model_tile.value_label.config(text=api_model)
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

    def on_whisper_api_model_change(event=None):
        display_name = whisper_api_model_var.get()
        model_name = whisper_api_display_to_model.get(display_name, WhisperApiService.DEFAULT_MODEL)
        whisper_api_model_info.config(text=whisper_api_pricing_text.get(model_name, ''))
        if engine_var.get() == 'whisper-api':
            model_tile.value_label.config(text=model_name)
        app.config.set("whisper_api_model", model_name)
        app.config.save()

    def on_gemini_recovery_change(event=None):
        display_name = gemini_recovery_var.get()
        recovery_mode = gemini_recovery_display_to_mode.get(display_name, 'segment-whisper')
        gemini_recovery_info.config(text=gemini_recovery_details.get(recovery_mode, ''))
        app.config.set("gemini_safety_filter_recovery", recovery_mode)
        app.config.save()

    def on_title_engine_change(event=None):
        display_name = title_engine_var.get()
        mode = title_engine_display_to_mode.get(display_name, 'auto')
        app.config.set("title_generation_engine", mode)
        app.config.save()

    engine_var.trace('w', lambda *args: on_engine_change())
    whisper_model_combo.bind('<<ComboboxSelected>>', on_model_change)
    whisper_api_model_combo.bind('<<ComboboxSelected>>', on_whisper_api_model_change)
    gemini_recovery_combo.bind('<<ComboboxSelected>>', on_gemini_recovery_change)
    title_engine_combo.bind('<<ComboboxSelected>>', on_title_engine_change)
    silence_trim_mode_combo.bind('<<ComboboxSelected>>', on_silence_trim_mode_change)
    silence_trim_threshold_scale.configure(command=on_silence_trim_threshold_change)
    silence_trim_threshold_scale.bind('<ButtonRelease-1>', persist_silence_trim_settings)
    silence_trim_min_scale.configure(command=on_silence_trim_min_change)
    silence_trim_min_scale.bind('<ButtonRelease-1>', persist_silence_trim_settings)
    waveform_viewer.set_callbacks(
        play_toggle_callback=app.toggle_waveform_playback,
        stop_callback=lambda: app.stop_waveform_playback(reset_position=True, silent=True),
        seek_callback=app.seek_waveform_playback
    )
    update_save_summary()
    _update_silence_trim_controls()
    on_engine_change()
    on_model_change()
    on_whisper_api_model_change()
    on_gemini_recovery_change()

    frame.drop_area = drop_canvas
    frame.file_label = file_label
    frame.status_label = status_label
    frame.status_dot = status_dot
    frame.progress = progress
    frame.progress_label = progress_label
    frame.waveform_viewer = waveform_viewer
    frame.engine_var = engine_var
    frame.whisper_model_var = whisper_model_var
    frame.whisper_model_combo = whisper_model_combo
    frame.whisper_api_model_var = whisper_api_model_var
    frame.whisper_api_display_to_model = whisper_api_display_to_model
    frame.gemini_safety_filter_recovery_var = gemini_recovery_var
    frame.gemini_safety_filter_recovery_display_to_mode = gemini_recovery_display_to_mode
    frame.title_engine_var = title_engine_var
    frame.title_engine_display_to_mode = title_engine_display_to_mode
    frame.trim_long_silence_var = trim_long_silence_var
    frame.silence_trim_mode_var = silence_trim_mode_var
    frame.silence_trim_mode_display_to_value = silence_trim_mode_display_to_value
    frame.silence_trim_threshold_db_var = silence_trim_threshold_db_var
    frame.silence_trim_min_silence_sec_var = silence_trim_min_silence_sec_var
    frame.save_to_output_var = save_to_output_var
    frame.save_to_source_var = save_to_source_var
    frame.rename_source_var = rename_source_var
    frame.queue_frame = queue_frame
    frame.queue_tree = queue_tree
    frame.queue_count_label = queue_count_label

    return frame


def create_recording_section(parent, app, theme, widgets):
    """録音専用タブを作成する"""
    frame = tk.Frame(parent, bg=theme.colors['surface'])
    pad = 12

    header_frame = tk.Frame(frame, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=pad, pady=(pad, 8))

    widgets.create_section_header(header_frame, "録音").pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )
    widgets.create_pill_label(
        header_frame, "マイク専用", tone='warning'
    ).pack(side=tk.RIGHT)

    intro_label = tk.Label(
        frame,
        text="電話や会話をその場で録音し、保存後そのままキューへ回せます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    intro_label.pack(fill=tk.X, padx=pad, pady=(0, 8))
    _bind_dynamic_wraplength(intro_label, pad)

    recording_widgets = _create_recording_card(frame, app, theme, widgets, pad)

    frame.recording_status_label = recording_widgets['recording_status_label']
    frame.recording_badge_label = recording_widgets['recording_badge_label']
    frame.recording_device_label = recording_widgets['recording_device_label']
    frame.recording_timer_label = recording_widgets['recording_timer_label']
    frame.recording_folder_label = recording_widgets['recording_folder_label']
    frame.record_button = recording_widgets['record_button']
    frame.stop_record_button = recording_widgets['stop_record_button']
    frame.queue_recordings_button = recording_widgets['queue_recordings_button']
    frame.choose_recording_folder_button = recording_widgets['choose_recording_folder_button']
    frame.open_recording_folder_button = recording_widgets['open_recording_folder_button']
    frame.recording_device_combo = recording_widgets['recording_device_combo']
    frame.recording_channel_combo = recording_widgets['recording_channel_combo']
    frame.refresh_recording_inputs_button = recording_widgets['refresh_recording_inputs_button']
    frame.recording_gain_scale = recording_widgets['recording_gain_scale']
    frame.recording_visual_canvas = recording_widgets['recording_visual_canvas']

    return frame


def _create_recording_card(parent, app, theme, widgets, pad):
    """録音UIカードを作成する"""
    card = tk.Frame(
        parent,
        bg=theme.colors['hero_bg'],
        highlightbackground=theme.colors['hero_border'],
        highlightthickness=1,
        bd=0
    )
    card.pack(fill=tk.X, padx=pad, pady=(0, 8))

    inner = tk.Frame(card, bg=theme.colors['hero_bg'])
    inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    header = tk.Frame(inner, bg=theme.colors['hero_bg'])
    header.pack(fill=tk.X)

    tk.Label(
        header,
        text="その場で録音",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['secondary_light'],
        bg=theme.colors['hero_bg']
    ).pack(side=tk.LEFT)

    recording_badge_label = tk.Label(
        header,
        text="STANDBY",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['info'],
        bg=theme.colors['info_soft'],
        padx=10,
        pady=4
    )
    recording_badge_label.pack(side=tk.RIGHT)

    desc = tk.Label(
        inner,
        text="突然の電話や会話をそのまま録音する入口です。止めるとすぐキューへ回せます。",
        font=theme.fonts['caption'],
        fg='#D7E0E4',
        bg=theme.colors['hero_bg'],
        justify='left',
        anchor='w'
    )
    desc.pack(anchor='w', fill=tk.X, pady=(6, 10))
    _bind_dynamic_wraplength(desc, 28)

    action_shell = tk.Frame(
        inner,
        bg=theme.colors['hero_surface'],
        highlightbackground=theme.colors['hero_border'],
        highlightthickness=1,
        bd=0
    )
    action_shell.pack(fill=tk.X, pady=(0, 10))

    action_inner = tk.Frame(action_shell, bg=theme.colors['hero_surface'])
    action_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

    action_header = tk.Frame(action_inner, bg=theme.colors['hero_surface'])
    action_header.pack(fill=tk.X)

    tk.Label(
        action_header,
        text="クイック操作",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['secondary_light'],
        bg=theme.colors['hero_surface']
    ).pack(side=tk.LEFT)

    tk.Label(
        action_header,
        text="まずここから",
        font=theme.fonts['caption'],
        fg='#C9D8DE',
        bg=theme.colors['hero_surface']
    ).pack(side=tk.RIGHT)

    controls = tk.Frame(action_inner, bg=theme.colors['hero_surface'])
    controls.pack(fill=tk.X, pady=(8, 0))
    controls.grid_columnconfigure(0, weight=1)
    controls.grid_columnconfigure(1, weight=1)
    controls.grid_columnconfigure(2, weight=1)

    record_button = widgets.create_icon_button(
        controls, "録音開始", ICONS['microphone'], 'Primary',
        command=app.start_recording
    )
    record_button.idle_text = f"{ICONS['microphone']} 録音開始"
    record_button.active_text = f"{ICONS['microphone']} 録音中..."

    stop_record_button = widgets.create_icon_button(
        controls, "停止して保存", ICONS['stop'], 'Secondary',
        command=app.stop_recording
    )
    stop_record_button.idle_text = f"{ICONS['stop']} 停止して保存"
    stop_record_button.active_text = f"{ICONS['stop']} 保存して停止"

    queue_recordings_button = widgets.create_icon_button(
        controls, "録音をキュー追加", ICONS['plus'], 'Secondary',
        command=app.add_recordings_to_queue
    )

    action_layout_state = {'wide': None}

    def _relayout_action_controls(event=None):
        width = controls.winfo_width()
        want_wide = width >= 660
        if action_layout_state['wide'] == want_wide:
            return
        action_layout_state['wide'] = want_wide

        for button in (record_button, stop_record_button, queue_recordings_button):
            button.grid_forget()

        if want_wide:
            record_button.grid(row=0, column=0, sticky='ew', padx=(0, 6))
            stop_record_button.grid(row=0, column=1, sticky='ew', padx=6)
            queue_recordings_button.grid(row=0, column=2, sticky='ew', padx=(6, 0))
        else:
            record_button.grid(row=0, column=0, sticky='ew', padx=(0, 4))
            stop_record_button.grid(row=0, column=1, sticky='ew', padx=(4, 0))
            queue_recordings_button.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(8, 0))

    controls.bind('<Configure>', _relayout_action_controls)
    controls.after_idle(_relayout_action_controls)

    folder_actions = tk.Frame(action_inner, bg=theme.colors['hero_surface'])
    folder_actions.pack(fill=tk.X, pady=(8, 0))
    folder_actions.grid_columnconfigure(0, weight=1)
    folder_actions.grid_columnconfigure(1, weight=1)

    choose_recording_folder_button = widgets.create_icon_button(
        folder_actions, "保存先変更", ICONS['folder'], 'Secondary',
        command=app.choose_recording_folder
    )
    open_recording_folder_button = widgets.create_icon_button(
        folder_actions, "録音フォルダを開く", ICONS['open'], 'Secondary',
        command=app.open_recording_folder
    )

    folder_action_layout_state = {'wide': None}

    def _relayout_folder_actions(event=None):
        width = folder_actions.winfo_width()
        want_wide = width >= 540
        if folder_action_layout_state['wide'] == want_wide:
            return
        folder_action_layout_state['wide'] = want_wide

        choose_recording_folder_button.grid_forget()
        open_recording_folder_button.grid_forget()

        if want_wide:
            choose_recording_folder_button.grid(row=0, column=0, sticky='ew', padx=(0, 6))
            open_recording_folder_button.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        else:
            choose_recording_folder_button.grid(row=0, column=0, columnspan=2, sticky='ew')
            open_recording_folder_button.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))

    folder_actions.bind('<Configure>', _relayout_folder_actions)
    folder_actions.after_idle(_relayout_folder_actions)

    main_strip = tk.Frame(inner, bg=theme.colors['hero_bg'])
    main_strip.pack(fill=tk.X)

    left_panel = tk.Frame(
        main_strip,
        bg=theme.colors['hero_surface'],
        highlightbackground=theme.colors['hero_border'],
        highlightthickness=1,
        bd=0
    )

    right_panel = tk.Frame(
        main_strip,
        bg=theme.colors['hero_surface'],
        highlightbackground=theme.colors['hero_border'],
        highlightthickness=1,
        bd=0
    )

    layout_state = {'horizontal': None}

    def _relayout_recording(event=None):
        width = main_strip.winfo_width()
        want_horizontal = width >= 720
        if layout_state['horizontal'] == want_horizontal:
            return
        layout_state['horizontal'] = want_horizontal

        left_panel.pack_forget()
        right_panel.pack_forget()

        if want_horizontal:
            left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
            right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        else:
            left_panel.pack(fill=tk.X, pady=(0, 6))
            right_panel.pack(fill=tk.X)

    main_strip.bind('<Configure>', _relayout_recording)

    left_inner = tk.Frame(left_panel, bg=theme.colors['hero_surface'])
    left_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    tk.Label(
        left_inner,
        text="録音タイマー",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['secondary_light'],
        bg=theme.colors['hero_surface']
    ).pack(anchor='w')

    recording_timer_label = tk.Label(
        left_inner,
        textvariable=app.recording_elapsed_var,
        font=(theme.fonts['app_title'][0], 22),
        fg=theme.colors['text_on_dark'],
        bg=theme.colors['hero_surface']
    )
    recording_timer_label.pack(anchor='w', pady=(6, 4))

    recording_status_label = tk.Label(
        left_inner,
        textvariable=app.recording_status_var,
        font=theme.fonts['heading'],
        fg=theme.colors['text_on_dark'],
        bg=theme.colors['hero_surface']
    )
    recording_status_label.pack(anchor='w')

    recording_hint_label = tk.Label(
        left_inner,
        textvariable=app.recording_hint_var,
        font=theme.fonts['caption'],
        fg='#D7E0E4',
        bg=theme.colors['hero_surface'],
        justify='left',
        anchor='w'
    )
    recording_hint_label.pack(anchor='w', fill=tk.X, pady=(8, 0))
    _bind_dynamic_wraplength(recording_hint_label, 14)

    metrics_row = tk.Frame(left_inner, bg=theme.colors['hero_surface'])
    metrics_row.pack(fill=tk.X, pady=(10, 0))
    metrics_row.grid_columnconfigure(0, weight=1)
    metrics_row.grid_columnconfigure(1, weight=1)
    metrics_row.grid_columnconfigure(2, weight=1)

    def _create_dark_metric(parent_widget, title, value_var):
        tile = tk.Frame(
            parent_widget,
            bg='#2A5463',
            highlightbackground=theme.colors['hero_border'],
            highlightthickness=1,
            bd=0
        )
        tk.Label(
            tile,
            text=title,
            font=theme.fonts['caption_bold'],
            fg='#C9D8DE',
            bg='#2A5463'
        ).pack(anchor='w', padx=8, pady=(7, 0))
        value = tk.Label(
            tile,
            textvariable=value_var,
            font=theme.fonts['body_bold'],
            fg=theme.colors['text_on_dark'],
            bg='#2A5463',
            justify='left',
            anchor='w'
        )
        value.pack(anchor='w', fill=tk.X, padx=8, pady=(3, 7))
        return tile, value

    input_tile, input_value = _create_dark_metric(metrics_row, "INPUT", app.recording_level_var)
    input_tile.grid(row=0, column=0, sticky='ew', padx=(0, 6))

    peak_tile, peak_value = _create_dark_metric(metrics_row, "PEAK", app.recording_peak_var)
    peak_tile.grid(row=0, column=1, sticky='ew', padx=6)

    format_tile, format_value = _create_dark_metric(metrics_row, "FORMAT", app.recording_format_var)
    format_tile.grid(row=0, column=2, sticky='ew', padx=(6, 0))
    _bind_dynamic_wraplength(format_value, 10)

    right_inner = tk.Frame(right_panel, bg=theme.colors['hero_surface'])
    right_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    visual_header = tk.Frame(right_inner, bg=theme.colors['hero_surface'])
    visual_header.pack(fill=tk.X)

    tk.Label(
        visual_header,
        text="入力レベル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['secondary_light'],
        bg=theme.colors['hero_surface']
    ).pack(side=tk.LEFT)

    tk.Label(
        visual_header,
        text="LEVEL / PEAK",
        font=theme.fonts['caption'],
        fg='#C9D8DE',
        bg=theme.colors['hero_surface']
    ).pack(side=tk.RIGHT)

    visual_shell = tk.Frame(
        right_inner,
        bg=theme.colors['log_bg'],
        highlightbackground=theme.colors['hero_border'],
        highlightthickness=1,
        bd=0
    )
    visual_shell.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

    recording_visual_canvas = tk.Canvas(
        visual_shell,
        bg=theme.colors['log_bg'],
        highlightthickness=0,
        height=124
    )
    recording_visual_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _draw_recording_visual(level=0.0, peak=0.0, is_active=False, phase=0.0,
                               spectrum_bins=None, waveform_points=None, is_live=False):
        canvas = recording_visual_canvas
        canvas.delete('all')

        width = max(canvas.winfo_width(), 260)
        height = max(canvas.winfo_height(), 124)
        left_pad = 18
        right_pad = 18
        meter_y0 = 34
        meter_height = 24
        meter_y1 = meter_y0 + meter_height
        usable_width = max(80, width - left_pad - right_pad)

        meter_bg = '#29333A'
        grid_color = '#3C4E56'
        text_soft = '#C9D8DE'
        level_pct = int(max(0, min(100, round(level * 100))))
        peak_pct = int(max(0, min(100, round(peak * 100))))
        if not is_live:
            status_text = "待機中: マイク監視"
        elif level_pct < 8:
            status_text = "かなり小さい: レベルを上げる"
        elif level_pct < 30:
            status_text = "小さめ: 少し上げる"
        elif level_pct < 70:
            status_text = "適正: このままでOK"
        elif level_pct < 88:
            status_text = "高め: 少し下げる"
        else:
            status_text = "大きすぎる: すぐ下げる"

        canvas.create_text(
            left_pad, 10,
            text="INPUT LEVEL",
            anchor='nw',
            font=theme.fonts['caption_bold'],
            fill=text_soft
        )
        canvas.create_text(
            width - right_pad, 10,
            text=f"PEAK {peak_pct:02d}%",
            anchor='ne',
            font=theme.fonts['caption_bold'],
            fill=text_soft
        )

        green_end = left_pad + (usable_width * 0.68)
        yellow_end = left_pad + (usable_width * 0.88)

        canvas.create_rectangle(
            left_pad, meter_y0, width - right_pad, meter_y1,
            fill=meter_bg,
            outline='#47606A',
            width=1
        )
        canvas.create_rectangle(left_pad, meter_y0, green_end, meter_y1, fill='#284133', outline='')
        canvas.create_rectangle(green_end, meter_y0, yellow_end, meter_y1, fill='#4A3C22', outline='')
        canvas.create_rectangle(yellow_end, meter_y0, width - right_pad, meter_y1, fill='#4D2D29', outline='')

        fill_x = left_pad + (usable_width * level)
        if is_live:
            if fill_x > left_pad:
                if fill_x > yellow_end:
                    canvas.create_rectangle(left_pad, meter_y0 + 3, green_end, meter_y1 - 3, fill='#67B47A', outline='')
                    canvas.create_rectangle(green_end, meter_y0 + 3, yellow_end, meter_y1 - 3, fill='#E8A55B', outline='')
                    canvas.create_rectangle(yellow_end, meter_y0 + 3, fill_x, meter_y1 - 3, fill='#D97761', outline='')
                elif fill_x > green_end:
                    canvas.create_rectangle(left_pad, meter_y0 + 3, green_end, meter_y1 - 3, fill='#67B47A', outline='')
                    canvas.create_rectangle(green_end, meter_y0 + 3, fill_x, meter_y1 - 3, fill='#E8A55B', outline='')
                else:
                    canvas.create_rectangle(left_pad, meter_y0 + 3, fill_x, meter_y1 - 3, fill='#67B47A', outline='')
        else:
            pulse_width = usable_width * 0.18
            pulse_center = left_pad + ((((phase * 38) % 100) / 100.0) * usable_width)
            pulse_left = max(left_pad, pulse_center - (pulse_width / 2))
            pulse_right = min(width - right_pad, pulse_center + (pulse_width / 2))
            canvas.create_rectangle(
                pulse_left, meter_y0 + 4, pulse_right, meter_y1 - 4,
                fill='#5B7D88', outline=''
            )

        for tick in (0.0, 0.25, 0.5, 0.75, 0.9, 1.0):
            x = left_pad + (usable_width * tick)
            canvas.create_line(x, meter_y0, x, meter_y1, fill=grid_color)

        peak_x = left_pad + (usable_width * peak)
        canvas.create_line(
            peak_x, meter_y0 - 4, peak_x, meter_y1 + 4,
            fill='#F4D48C',
            width=2
        )

        tick_values = [(0.0, "0"), (0.5, "50"), (0.9, "90"), (1.0, "100")]
        for ratio, label in tick_values:
            x = left_pad + (usable_width * ratio)
            canvas.create_text(
                x, meter_y1 + 6,
                text=label,
                anchor='n',
                font=theme.fonts['caption'],
                fill='#91A8B0'
            )

        if level_pct >= 88:
            value_color = '#D97761'
        elif level_pct >= 68:
            value_color = '#E8A55B'
        else:
            value_color = '#8ED3A0' if is_live else '#9FD3E0'
        canvas.create_text(
            width - right_pad, meter_y0 + (meter_height / 2),
            text=f"{level_pct:02d}%",
            anchor='e',
            font=theme.fonts['heading'],
            fill=value_color
        )

        canvas.create_text(
            left_pad, meter_y1 + 22,
            text=status_text,
            anchor='nw',
            font=theme.fonts['body_bold'],
            fill=value_color
        )

        footer_text = "Recording" if is_active else ("Mic Monitor" if is_live else "Standby")
        canvas.create_text(
            left_pad, height - 8,
            text=footer_text,
            anchor='sw',
            font=theme.fonts['caption'],
            fill=text_soft
        )

    recording_visual_canvas.draw_visual = _draw_recording_visual
    recording_visual_canvas.bind(
        '<Configure>',
        lambda event: recording_visual_canvas.draw_visual(0.0, 0.0, False, 0.0, [], [], False)
    )

    recording_device_label = tk.Label(
        right_inner,
        textvariable=app.recording_device_var,
        font=theme.fonts['caption'],
        fg='#D7E0E4',
        bg=theme.colors['hero_surface'],
        justify='left',
        anchor='w'
    )
    recording_device_label.pack(anchor='w', fill=tk.X)
    _bind_dynamic_wraplength(recording_device_label, 12)

    folder_shell = tk.Frame(
        inner,
        bg=theme.colors['surface'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    folder_shell.pack(fill=tk.X, pady=(10, 0))

    folder_inner = tk.Frame(folder_shell, bg=theme.colors['surface'])
    folder_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    folder_top = tk.Frame(folder_inner, bg=theme.colors['surface'])
    folder_top.pack(fill=tk.X)

    tk.Label(
        folder_top,
        text="録音保存先",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(side=tk.LEFT)

    ttk.Checkbutton(
        folder_top,
        text="停止後に自動でキューへ追加",
        variable=app.auto_queue_recordings_var,
        command=app.toggle_auto_queue_recordings,
        style='Modern.TCheckbutton'
    ).pack(side=tk.RIGHT)

    source_row = tk.Frame(folder_inner, bg=theme.colors['surface'])
    source_row.pack(fill=tk.X, pady=(6, 8))
    source_row.grid_columnconfigure(0, weight=3)
    source_row.grid_columnconfigure(1, weight=2)

    device_column = tk.Frame(source_row, bg=theme.colors['surface'])
    device_column.grid(row=0, column=0, sticky='ew', padx=(0, 6))

    tk.Label(
        device_column,
        text="入力デバイス",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w')

    recording_device_combo = ttk.Combobox(
        device_column,
        textvariable=app.recording_input_device_var,
        values=[],
        state='readonly',
        style='Modern.TCombobox'
    )
    recording_device_combo.pack(fill=tk.X, pady=(4, 0))
    recording_device_combo.bind('<<ComboboxSelected>>', app.on_recording_device_selected)

    channel_column = tk.Frame(source_row, bg=theme.colors['surface'])
    channel_column.grid(row=0, column=1, sticky='ew')
    channel_column.grid_columnconfigure(0, weight=1)

    channel_header = tk.Frame(channel_column, bg=theme.colors['surface'])
    channel_header.pack(fill=tk.X)

    tk.Label(
        channel_header,
        text="入力チャンネル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(side=tk.LEFT)

    refresh_recording_inputs_button = widgets.create_icon_button(
        channel_header, "更新", ICONS['refresh'], 'Secondary',
        command=app.refresh_recording_inputs
    )
    refresh_recording_inputs_button.pack(side=tk.RIGHT)

    recording_channel_combo = ttk.Combobox(
        channel_column,
        textvariable=app.recording_input_channels_var,
        values=[],
        state='readonly',
        style='Modern.TCombobox'
    )
    recording_channel_combo.pack(fill=tk.X, pady=(4, 0))
    recording_channel_combo.bind('<<ComboboxSelected>>', app.on_recording_channel_selected)

    source_note = tk.Label(
        folder_inner,
        text="オーディオIFの 1-2 / 3-4 などはデバイス名と入力チャンネルの両方で切り替えます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    source_note.pack(fill=tk.X, pady=(0, 8))
    _bind_dynamic_wraplength(source_note, 4)

    recording_folder_label = tk.Label(
        folder_inner,
        textvariable=app.recording_dir_var,
        font=theme.fonts['caption'],
        fg=theme.colors['text_primary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    recording_folder_label.pack(anchor='w', fill=tk.X, pady=(6, 10))
    _bind_dynamic_wraplength(recording_folder_label, 20)

    gain_row = tk.Frame(folder_inner, bg=theme.colors['surface'])
    gain_row.pack(fill=tk.X, pady=(0, 8))

    gain_header = tk.Frame(gain_row, bg=theme.colors['surface'])
    gain_header.pack(fill=tk.X)

    tk.Label(
        gain_header,
        text="録音レベル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(side=tk.LEFT)

    tk.Label(
        gain_header,
        textvariable=app.recording_gain_display_var,
        font=theme.fonts['caption_bold'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface']
    ).pack(side=tk.RIGHT)

    gain_scale = ttk.Scale(
        gain_row,
        from_=25,
        to=250,
        orient=tk.HORIZONTAL,
        variable=app.recording_gain_percent_var,
        command=app.on_recording_gain_change
    )
    gain_scale.pack(fill=tk.X, pady=(6, 2))
    gain_scale.bind('<ButtonRelease-1>', app.persist_recording_gain)

    gain_note = tk.Label(
        gain_row,
        text="保存音量に掛かるソフトゲインです。100%が原音、上げすぎると割れます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    gain_note.pack(fill=tk.X)
    _bind_dynamic_wraplength(gain_note, 4)

    return {
        'recording_status_label': recording_status_label,
        'recording_badge_label': recording_badge_label,
        'recording_device_label': recording_device_label,
        'recording_timer_label': recording_timer_label,
        'recording_folder_label': recording_folder_label,
        'record_button': record_button,
        'stop_record_button': stop_record_button,
        'queue_recordings_button': queue_recordings_button,
        'choose_recording_folder_button': choose_recording_folder_button,
        'open_recording_folder_button': open_recording_folder_button,
        'recording_device_combo': recording_device_combo,
        'recording_channel_combo': recording_channel_combo,
        'refresh_recording_inputs_button': refresh_recording_inputs_button,
        'recording_gain_scale': gain_scale,
        'recording_visual_canvas': recording_visual_canvas,
    }


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

    open_selected_dir_btn = widgets.create_icon_button(
        header_frame, "保存先", ICONS['folder'], 'Secondary',
        command=app.open_selected_output_directory
    )
    open_selected_dir_btn.pack(side=tk.RIGHT, padx=(0, 6))

    history_desc = tk.Label(
        card,
        text="出力済みテキストの一覧です。ダブルクリックで開けます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        anchor='w'
    )
    history_desc.pack(anchor='w', fill=tk.X, padx=CARD_PADDING, pady=(0, 10))
    _bind_dynamic_wraplength(history_desc, CARD_PADDING)

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

    history_tree.column('filename', width=200, minwidth=120, stretch=True)
    history_tree.column('date', width=150, minwidth=100, stretch=False)
    history_tree.column('size', width=80, minwidth=60, stretch=False)

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

    for col in range(3):
        button_frame.grid_columnconfigure(col, weight=1, uniform='history_actions')

    open_btn = widgets.create_icon_button(
        button_frame, "開く", ICONS['document'], 'Secondary',
        command=app.open_output_file
    )
    open_btn.grid(row=0, column=0, sticky='ew', padx=(0, 4), pady=(0, 6))

    source_folder_btn = widgets.create_icon_button(
        button_frame, "元フォルダ", ICONS['file'], 'Secondary',
        command=app.open_source_file_folder
    )
    source_folder_btn.grid(row=0, column=1, sticky='ew', padx=4, pady=(0, 6))

    history_folder_btn = widgets.create_icon_button(
        button_frame, "履歴データ", ICONS['folder'], 'Secondary',
        command=app.open_history_directory
    )
    history_folder_btn.grid(row=0, column=2, sticky='ew', padx=(4, 0), pady=(0, 6))

    delete_btn = widgets.create_icon_button(
        button_frame, "削除", ICONS['delete'], 'Secondary',
        command=app.delete_output_file
    )
    delete_btn.grid(row=1, column=2, sticky='ew', padx=(4, 0), pady=(0, 0))

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

    usage_desc = tk.Label(
        card,
        text="トークン数と料金は概算値です。ローカル Whisper はここには加算されません。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        anchor='w'
    )
    usage_desc.pack(anchor='w', fill=tk.X, padx=CARD_PADDING, pady=(0, 10))
    _bind_dynamic_wraplength(usage_desc, CARD_PADDING)

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

    log_desc = tk.Label(
        card,
        text="処理経過、使用モデル、エラー詳細をここに表示します。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        anchor='w'
    )
    log_desc.pack(anchor='w', fill=tk.X, padx=CARD_PADDING, pady=(0, 10))
    _bind_dynamic_wraplength(log_desc, CARD_PADDING)

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


def collect_ui_elements(api_section, file_section, recording_section, usage_section, history_section, log_section):
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
        'waveform_viewer': file_section.waveform_viewer,
        'engine_var': file_section.engine_var,
        'whisper_model_var': file_section.whisper_model_var,
        'whisper_model_combo': file_section.whisper_model_combo,
        'whisper_api_model_var': file_section.whisper_api_model_var,
        'whisper_api_display_to_model': file_section.whisper_api_display_to_model,
        'gemini_safety_filter_recovery_var': file_section.gemini_safety_filter_recovery_var,
        'gemini_safety_filter_recovery_display_to_mode': file_section.gemini_safety_filter_recovery_display_to_mode,
        'title_engine_var': file_section.title_engine_var,
        'title_engine_display_to_mode': file_section.title_engine_display_to_mode,
        'trim_long_silence_var': file_section.trim_long_silence_var,
        'silence_trim_mode_var': file_section.silence_trim_mode_var,
        'silence_trim_mode_display_to_value': file_section.silence_trim_mode_display_to_value,
        'silence_trim_threshold_db_var': file_section.silence_trim_threshold_db_var,
        'silence_trim_min_silence_sec_var': file_section.silence_trim_min_silence_sec_var,
        'save_to_output_var': file_section.save_to_output_var,
        'save_to_source_var': file_section.save_to_source_var,
        'rename_source_var': file_section.rename_source_var,
        'recording_status_label': recording_section.recording_status_label,
        'recording_badge_label': recording_section.recording_badge_label,
        'recording_device_label': recording_section.recording_device_label,
        'recording_timer_label': recording_section.recording_timer_label,
        'recording_folder_label': recording_section.recording_folder_label,
        'record_button': recording_section.record_button,
        'stop_record_button': recording_section.stop_record_button,
        'queue_recordings_button': recording_section.queue_recordings_button,
        'choose_recording_folder_button': recording_section.choose_recording_folder_button,
        'open_recording_folder_button': recording_section.open_recording_folder_button,
        'recording_device_combo': recording_section.recording_device_combo,
        'recording_channel_combo': recording_section.recording_channel_combo,
        'refresh_recording_inputs_button': recording_section.refresh_recording_inputs_button,
        'recording_gain_scale': getattr(recording_section, 'recording_gain_scale', None),
        'recording_visual_canvas': recording_section.recording_visual_canvas,
        'queue_frame': file_section.queue_frame,
        'queue_tree': file_section.queue_tree,
        'queue_count_label': file_section.queue_count_label,
        'usage_sessions': usage_section.sessions_value,
        'usage_tokens': usage_section.tokens_value,
        'usage_cost_usd': usage_section.cost_usd_value,
        'usage_cost_jpy': usage_section.cost_jpy_value,
        'history_tree': history_section.history_tree,
        'log_text': log_section.log_text
    }
