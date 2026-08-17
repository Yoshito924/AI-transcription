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
from .ui_recording import create_recording_section
from .waveform_viewer import WaveformViewer
from .whisper_api_service import WhisperApiService
from .engines import ENGINES, get_engine_spec
from .utils import resolve_whisper_model_name
from .constants import (
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    CARD_PADDING, SECTION_SPACING, MAIN_PADDING_X,
    MAIN_PADDING_Y, QUEUE_LISTBOX_HEIGHT,
    DEFAULT_SILENCE_TRIM_MODE,
    DEFAULT_SILENCE_TRIM_THRESHOLD_DB,
    DEFAULT_SILENCE_TRIM_MIN_SILENCE_SEC,
    OLLAMA_DEFAULT_MODEL,
    OLLAMA_MODEL_SUGGESTIONS,
    DEFAULT_TRANSCRIPTION_ENGINE,
    DEFAULT_WHISPER_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_TITLE_GENERATION_ENGINE,
    DEFAULT_ADDITIONAL_PROCESSING_ENGINE,
    WHISPER_MODEL_DISPLAY_NAMES,
    WHISPER_MODEL_DETAILS,
    DEFAULT_PANE_FRACTIONS,
    PANE_FRACTION_MIN,
    PANE_FRACTION_MAX,
)
from .logger import logger


def _bind_dynamic_wraplength(label, padding=0):
    """ラベルの wraplength を親ウィジェットの幅に追従させる"""
    def _update(event=None):
        parent = label.winfo_parent()
        parent_widget = label.nametowidget(parent)
        w = parent_widget.winfo_width()
        if w > 1:
            label.config(wraplength=max(100, w - padding * 2 - 10))
    label.bind('<Configure>', _update)


def _pack_choice_grid(parent, items, variable, columns=2):
    """ラジオボタンを2列グリッドで並べ、狭い幅でもはみ出しにくくする"""
    bg = parent.cget('bg')
    row = tk.Frame(parent, bg=bg)
    row.pack(fill=tk.X, pady=(6, 8))
    for index, (text, value) in enumerate(items):
        r, c = divmod(index, columns)
        ttk.Radiobutton(
            row, text=text,
            variable=variable, value=value,
            style='Modern.TRadiobutton'
        ).grid(row=r, column=c, sticky='w', padx=(0, 16), pady=(0, 4))
        row.grid_columnconfigure(c, weight=1)
    return row


def _clamp_pane_fraction(value, default):
    """保存された分割比率を 0.18〜0.82 に収める"""
    try:
        fraction = float(value)
    except (TypeError, ValueError):
        fraction = default
    return max(PANE_FRACTION_MIN, min(PANE_FRACTION_MAX, fraction))


def _create_split_paned(parent, theme, orient=tk.HORIZONTAL):
    """ドラッグしやすい分割バー付き PanedWindow を作る"""
    horizontal = orient == tk.HORIZONTAL
    return tk.PanedWindow(
        parent,
        orient=orient,
        bg=theme.colors['text_disabled'],
        sashwidth=10 if horizontal else 8,
        sashrelief='flat',
        sashpad=0,
        showhandle=False,
        opaqueresize=True,
        bd=0,
    )


def _paned_sash_fraction(paned, orient):
    try:
        paned.update_idletasks()
        sash_x, sash_y = paned.sash_coord(0)
    except tk.TclError:
        return None
    total = paned.winfo_width() if orient == tk.HORIZONTAL else paned.winfo_height()
    if total <= 1:
        return None
    position = sash_x if orient == tk.HORIZONTAL else sash_y
    return position / total


def _place_paned_sash(paned, fraction, orient, min_total=10):
    try:
        paned.update_idletasks()
        paned.sash_coord(0)
    except tk.TclError:
        return False
    total = paned.winfo_width() if orient == tk.HORIZONTAL else paned.winfo_height()
    if total <= min_total:
        return False
    position = int(total * fraction)
    try:
        if orient == tk.HORIZONTAL:
            paned.sash_place(0, position, 0)
        else:
            paned.sash_place(0, 0, position)
    except tk.TclError:
        return False
    return True


def _forget_paned_panes(paned, *panes):
    for pane in panes:
        try:
            paned.forget(pane)
        except tk.TclError:
            pass


def _bind_pane_fraction(
    app, paned, config_key, default, orient=tk.HORIZONTAL, restore_every_map=False
):
    """分割位置を復元し、ドラッグ後に保存する"""
    restored = {'done': False}

    def _persist(_event=None):
        fraction = _paned_sash_fraction(paned, orient)
        if fraction is None:
            return
        app.config.set(config_key, round(_clamp_pane_fraction(fraction, default), 4))

    def _restore(_event=None):
        if restored['done'] and not restore_every_map:
            return
        fraction = _clamp_pane_fraction(app.config.get(config_key, default), default)
        min_total = 200 if orient == tk.HORIZONTAL else 120

        def _try_place(retries=8):
            if _place_paned_sash(paned, fraction, orient, min_total=min_total):
                restored['done'] = True
                return
            if retries > 0:
                paned.after(50, lambda: _try_place(retries - 1))

        paned.after_idle(_try_place)

    paned.bind('<Map>', _restore, add='+')
    paned.bind('<ButtonRelease-1>', _persist, add='+')
    return _persist


def _setup_responsive_h_split(
    app,
    theme,
    strip,
    left,
    right,
    config_key,
    pane_persisters,
    threshold,
    minsize_left=220,
    minsize_right=200,
):
    """広いときはドラッグ可能な左右分割、狭いときは縦積みにする"""
    default = DEFAULT_PANE_FRACTIONS[config_key]
    paned = _create_split_paned(strip, theme)
    persist = _bind_pane_fraction(
        app, paned, config_key, default, restore_every_map=True
    )
    pane_persisters.append(persist)
    state = {'is_horizontal': None}

    def _relayout(_event=None):
        width = strip.winfo_width()
        if width <= 1:
            return
        want_horizontal = width >= threshold
        if state['is_horizontal'] == want_horizontal:
            return
        if state['is_horizontal']:
            persist()
        state['is_horizontal'] = want_horizontal

        left.pack_forget()
        right.pack_forget()
        _forget_paned_panes(paned, left, right)
        paned.pack_forget()

        if want_horizontal:
            paned.pack(fill=tk.BOTH, expand=True)
            paned.add(left, minsize=minsize_left, stretch='always')
            paned.add(right, minsize=minsize_right, stretch='always')
            fraction = _clamp_pane_fraction(app.config.get(config_key, default), default)
            paned.after_idle(lambda: _place_paned_sash(paned, fraction, tk.HORIZONTAL))
        else:
            left.pack(fill=tk.X, pady=(0, 6))
            right.pack(fill=tk.X, pady=(6, 0))

    strip.bind('<Configure>', _relayout)
    return persist


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

    pane_persisters = []

    # === 全体: 左右をドラッグで調整できる横PanedWindow ===
    main_paned = _create_split_paned(main_container, theme, orient=tk.HORIZONTAL)
    main_paned.pack(fill=tk.BOTH, expand=True)

    work_pane = tk.Frame(main_paned, bg=theme.colors['background'])
    side_pane = tk.Frame(main_paned, bg=theme.colors['background'])

    main_paned.add(work_pane, minsize=480, stretch='always')
    main_paned.add(side_pane, minsize=280, stretch='never')
    pane_persisters.append(_bind_pane_fraction(
        app, main_paned, 'pane_main_fraction',
        DEFAULT_PANE_FRACTIONS['pane_main_fraction']
    ))

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
    file_section = create_file_section(
        file_scroll_inner, app, theme, widgets, pane_persisters
    )
    file_section.pack(fill=tk.X)

    # タブ2: 録音（スクロール可能）
    recording_tab = tk.Frame(notebook, bg=theme.colors['surface'])
    notebook.add(recording_tab, text='録音')
    tab_keys.append('recording')
    recording_scroll_outer, recording_scroll_inner = _create_scrollable_frame(
        recording_tab, theme.colors['surface']
    )
    recording_scroll_outer.pack(fill=tk.BOTH, expand=True)
    recording_section = create_recording_section(
        recording_scroll_inner, app, theme, widgets, pane_persisters
    )
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
    _setup_responsive_h_split(
        app, theme, settings_content, api_section, usage_section,
        'pane_settings_fraction', pane_persisters, threshold=640,
        minsize_left=280, minsize_right=240,
    )

    def _save_current_tab(event=None):
        try:
            current_index = notebook.index(notebook.select())
        except tk.TclError:
            return
        if 0 <= current_index < len(tab_keys):
            app.config.set("last_open_tab", tab_keys[current_index])
            app.config.save()
            if tab_keys[current_index] == 'recording':
                app.refresh_recent_recordings()

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
    paned = _create_split_paned(side_pane, theme, orient=tk.VERTICAL)
    paned.pack(fill=tk.BOTH, expand=True)

    history_section = create_history_section(paned, app, theme, widgets)
    paned.add(history_section, stretch='always', minsize=220)

    log_section = create_log_section(paned, app, theme, widgets)
    paned.add(log_section, stretch='never', minsize=180)
    pane_persisters.append(_bind_pane_fraction(
        app, paned, 'pane_side_fraction',
        DEFAULT_PANE_FRACTIONS['pane_side_fraction'],
        orient=tk.VERTICAL
    ))

    # UI要素を収集
    ui_elements = collect_ui_elements(
        api_section, file_section, recording_section, usage_section, history_section, log_section
    )
    ui_elements['notebook'] = notebook
    ui_elements['tab_keys'] = tab_keys
    ui_elements['persist_pane_fractions'] = lambda: [
        persist() for persist in pane_persisters
    ]

    return ui_elements



def create_api_section(parent, app, theme, widgets):
    """API設定セクション"""
    card = widgets.create_card_frame(parent)

    header_frame = tk.Frame(card, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 8))

    header = widgets.create_section_header(header_frame, "API 設定（任意）")
    header.pack(side=tk.LEFT, fill=tk.X, expand=True)

    api_status = widgets.create_pill_label(
        header_frame, "\u25cf ローカルOK", tone='info'
    )
    api_status.pack(side=tk.RIGHT)

    api_desc = tk.Label(
        card,
        text="ローカルだけで使うなら API キーは不要です。クラウドの Gemini や OpenAI を使うときだけ登録してください。",
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
        text="Gemini のクラウド文字起こしやクラウド要約・タイトル生成で使用",
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
        text="OpenAI のクラウド文字起こしで使用",
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
        text="クラウド接続先",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    model_name = tk.Label(
        model_inner,
        text="ローカル運用 / 未確認",
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


def create_file_section(parent, app, theme, widgets, pane_persisters=None):
    """ファイル入力セクション"""
    frame = widgets.create_card_frame(parent)
    pad = 12

    header_frame = tk.Frame(frame, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=pad, pady=(pad, 8))

    widgets.create_section_header(header_frame, "文字起こし").pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )

    intro_label = tk.Label(
        frame,
        text="音声や動画を追加して文字起こしします。その場で録る場合は「録音」タブへ。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    intro_label.pack(fill=tk.X, padx=pad, pady=(0, 8))
    _bind_dynamic_wraplength(intro_label, pad)

    # （重複していたクイック操作ボタンは削除。ドロップ領域と最下部の実行ボタンに集約）

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

    _setup_responsive_h_split(
        app, theme, config_strip, left_panel, right_panel,
        'pane_file_config_fraction', pane_persisters or [],
        threshold=540, minsize_left=220, minsize_right=200,
    )

    left_inner = tk.Frame(left_panel, bg=theme.colors['surface_variant'])
    left_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    tk.Label(
        left_inner,
        text="文字起こしエンジン",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w')

    saved_engine = app.config.get("transcription_engine", DEFAULT_TRANSCRIPTION_ENGINE)
    if saved_engine not in ("gemini", "whisper", "whisper-api"):
        saved_engine = DEFAULT_TRANSCRIPTION_ENGINE
    engine_var = tk.StringVar(value=saved_engine)

    _pack_choice_grid(
        left_inner,
        [
            (ENGINES['whisper'].choice_label, "whisper"),
            (ENGINES['gemini'].choice_label, "gemini"),
            (ENGINES['whisper-api'].choice_label, "whisper-api"),
        ],
        engine_var
    )

    engine_desc = tk.Label(
        left_inner,
        text=get_engine_spec(saved_engine).help_text,
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant'],
        justify='left',
        anchor='w'
    )
    engine_desc.pack(anchor='w', fill=tk.X, pady=(0, 4))
    _bind_dynamic_wraplength(engine_desc, 24)

    # === Whisper (ローカル) 専用設定 ===
    whisper_local_panel = tk.Frame(left_inner, bg=theme.colors['surface_variant'])

    tk.Label(
        whisper_local_panel,
        text="ローカルモデル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(anchor='w', pady=(10, 0))

    model_display_names = dict(WHISPER_MODEL_DISPLAY_NAMES)
    display_to_model = {v: k for k, v in model_display_names.items()}
    model_details = dict(WHISPER_MODEL_DETAILS)

    saved_whisper_model = resolve_whisper_model_name(
        app.config.get("whisper_model", DEFAULT_WHISPER_MODEL)
    )
    whisper_model_var = tk.StringVar(
        value=model_display_names.get(saved_whisper_model, model_display_names[DEFAULT_WHISPER_MODEL])
    )
    whisper_model_combo = ttk.Combobox(
        whisper_local_panel,
        textvariable=whisper_model_var,
        values=list(model_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    whisper_model_combo.pack(fill=tk.X, pady=(6, 0))

    whisper_model_info = tk.Label(
        whisper_local_panel,
        text=model_details.get(saved_whisper_model, ''),
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    whisper_model_info.pack(anchor='w', pady=(2, 0))

    # === Whisper API 専用設定 ===
    whisper_api_panel = tk.Frame(left_inner, bg=theme.colors['surface_variant'])

    whisper_api_model_label = tk.Label(
        whisper_api_panel,
        text="OpenAI モデル",
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
        whisper_api_panel,
        textvariable=whisper_api_model_var,
        values=list(whisper_api_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    whisper_api_model_combo.pack(fill=tk.X, pady=(6, 0))

    whisper_api_pricing_text = dict(WhisperApiService.MODEL_HINTS)
    whisper_api_model_info = tk.Label(
        whisper_api_panel,
        text=whisper_api_pricing_text.get(saved_whisper_api_model, ''),
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    whisper_api_model_info.pack(anchor='w', pady=(4, 0))

    # === Gemini 専用設定（ブロック時の動作） ===
    gemini_recovery_panel = tk.Frame(left_inner, bg=theme.colors['surface_variant'])

    gemini_intro = tk.Label(
        gemini_recovery_panel,
        text=f"モデルは {DEFAULT_GEMINI_MODEL.replace('gemini-', '').replace('-flash', ' Flash')} を優先して自動選択します。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant'],
        justify='left',
        anchor='w'
    )
    gemini_intro.pack(anchor='w', fill=tk.X, pady=(10, 0))
    _bind_dynamic_wraplength(gemini_intro, 24)

    gemini_recovery_label = tk.Label(
        gemini_recovery_panel,
        text="弾かれたときの動作",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    gemini_recovery_label.pack(anchor='w', pady=(8, 0))

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
    saved_gemini_recovery = app.config.get("gemini_safety_filter_recovery", "segment-whisper")
    if saved_gemini_recovery not in gemini_recovery_display_names:
        saved_gemini_recovery = 'segment-whisper'

    gemini_recovery_var = tk.StringVar(
        value=gemini_recovery_display_names.get(saved_gemini_recovery, '')
    )
    gemini_recovery_combo = ttk.Combobox(
        gemini_recovery_panel,
        textvariable=gemini_recovery_var,
        values=list(gemini_recovery_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    gemini_recovery_combo.pack(fill=tk.X, pady=(6, 0))

    gemini_recovery_info = tk.Label(
        gemini_recovery_panel,
        text=gemini_recovery_details.get(saved_gemini_recovery, ''),
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    gemini_recovery_info.pack(anchor='w', pady=(4, 0))

    # ===== テキスト処理 LLM（要約・議事録・タイトル生成） =====
    # 要約・議事録エンジン（additional_processing_engine）
    additional_engine_label = tk.Label(
        left_inner,
        text="要約・議事録 LLM",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    additional_engine_label.pack(anchor='w', pady=(14, 0))

    additional_engine_desc = tk.Label(
        left_inner,
        text="文字起こし後の要約・議事録です。通常は Ollama、クラウドに出すときだけ Gemini です。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant'],
        justify='left',
        anchor='w'
    )
    additional_engine_desc.pack(anchor='w', fill=tk.X, pady=(2, 4))
    _bind_dynamic_wraplength(additional_engine_desc, 24)

    saved_additional_engine = app.config.get("additional_processing_engine", DEFAULT_ADDITIONAL_PROCESSING_ENGINE)
    if saved_additional_engine not in ("gemini", "ollama"):
        saved_additional_engine = DEFAULT_ADDITIONAL_PROCESSING_ENGINE
    additional_engine_var = tk.StringVar(value=saved_additional_engine)

    _pack_choice_grid(
        left_inner,
        [
            ("Ollama", "ollama"),
            ("Gemini", "gemini"),
        ],
        additional_engine_var
    )

    # タイトル生成エンジン選択
    title_engine_label = tk.Label(
        left_inner,
        text="タイトル生成 LLM",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    title_engine_label.pack(anchor='w', pady=(10, 0))

    title_engine_desc = tk.Label(
        left_inner,
        text="ファイル名用の短いタイトルです。通常は Ollama のまま使えます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant'],
        justify='left',
        anchor='w'
    )
    title_engine_desc.pack(anchor='w', fill=tk.X, pady=(2, 4))
    _bind_dynamic_wraplength(title_engine_desc, 24)

    title_engine_display_names = {
        'ollama': 'Ollama（ローカルLLM）',
        'auto': '自動（Ollama → Gemini）',
        'gemini': 'Gemini API（クラウド）',
        'disabled': '無効（タイトル生成しない）',
    }
    title_engine_display_to_mode = {v: k for k, v in title_engine_display_names.items()}

    saved_title_engine = app.config.get("title_generation_engine", DEFAULT_TITLE_GENERATION_ENGINE)
    title_engine_var = tk.StringVar(
        value=title_engine_display_names.get(saved_title_engine, title_engine_display_names['ollama'])
    )
    title_engine_combo = ttk.Combobox(
        left_inner,
        textvariable=title_engine_var,
        values=list(title_engine_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    title_engine_combo.pack(fill=tk.X, pady=(6, 0))

    # === Ollama モデル選択（タイトル生成が ollama/auto の時のみ表示） ===
    ollama_panel = tk.Frame(left_inner, bg=theme.colors['surface_variant'])

    ollama_model_label = tk.Label(
        ollama_panel,
        text="Ollama モデル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    ollama_model_label.pack(anchor='w', pady=(10, 0))

    saved_ollama_model = app.config.get("ollama_model", OLLAMA_DEFAULT_MODEL) or OLLAMA_DEFAULT_MODEL
    ollama_model_var = tk.StringVar(value=saved_ollama_model)
    ollama_model_combo = ttk.Combobox(
        ollama_panel,
        textvariable=ollama_model_var,
        values=OLLAMA_MODEL_SUGGESTIONS,
        state='normal',
        style='Modern.TCombobox'
    )
    ollama_model_combo.pack(fill=tk.X, pady=(6, 0))

    ollama_model_details = {
        'gemma4:e4b': 'Gemma 4 E4B | 軽量・推奨',
        'gemma4:26b': 'Gemma 4 26B | 高品質',
        'gemma4:31b': 'Gemma 4 31B | 高品質・高負荷',
        'gemma4:e2b': 'Gemma 4 E2B | 最軽量',
        'gemma3:4b': 'Gemma 3 4B | 旧構成互換',
    }
    ollama_model_info = tk.Label(
        ollama_panel,
        text="",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    )
    ollama_model_info.pack(anchor='w', pady=(4, 0))
    ollama_panel.pack(fill=tk.X)  # 初期表示。on_title_engine_change で必要に応じて畳む

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

    engine_tile = widgets.create_metric_tile(summary_grid, "エンジン", ENGINES[saved_engine].label, tone='primary')
    engine_tile.grid(row=0, column=0, sticky='ew', padx=(0, 6))

    model_tile = widgets.create_metric_tile(
        summary_grid, "モデル",
        WHISPER_MODEL_DISPLAY_NAMES.get(saved_whisper_model, WHISPER_MODEL_DISPLAY_NAMES[DEFAULT_WHISPER_MODEL]),
        tone='info'
    )
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

    # 最終並びは status_card / transcribe_btn 生成後にまとめて確定する

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

    # 主要動線を集約: drop → queue → 現在の設定サマリー → 状態 → 開始ボタン → 詳細設定
    for w in (config_strip, summary_grid, status_card, transcribe_btn):
        w.pack_forget()
    summary_grid.pack(fill=tk.X, padx=pad, pady=(0, 8))
    status_card.pack(fill=tk.X, padx=pad, pady=(0, 8))
    transcribe_btn.pack(fill=tk.X, padx=pad, pady=(0, 8))
    config_strip.pack(fill=tk.X, padx=pad, pady=(0, pad))

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

    def _summary_model_text():
        engine_value = engine_var.get()
        if engine_value == 'gemini':
            return DEFAULT_GEMINI_MODEL.replace('gemini-', '').replace('-flash', ' Flash')
        if engine_value == 'whisper-api':
            return whisper_api_model_var.get() or WhisperApiService.MODEL_DESCRIPTIONS[WhisperApiService.DEFAULT_MODEL]
        return whisper_model_var.get()

    def on_engine_change():
        engine_value = engine_var.get()
        spec = get_engine_spec(engine_value)

        # 関係ないエンジンの設定パネルは非表示にして画面を軽くする
        # 文字起こしエンジン関連の補助パネルは、要約・議事録 LLM セクションの直前に配置する
        for panel in (whisper_local_panel, whisper_api_panel, gemini_recovery_panel):
            panel.pack_forget()
        if spec.key == "whisper":
            whisper_local_panel.pack(fill=tk.X, before=additional_engine_label)
        elif spec.key == "whisper-api":
            whisper_api_panel.pack(fill=tk.X, before=additional_engine_label)
        elif spec.key == "gemini":
            gemini_recovery_panel.pack(fill=tk.X, before=additional_engine_label)

        engine_desc.config(text=spec.help_text)
        engine_tile.value_label.config(text=spec.label)
        model_tile.value_label.config(text=_summary_model_text())

        app.config.set("transcription_engine", engine_value)
        app.config.save()

    def on_model_change(event=None):
        display_name = whisper_model_var.get()
        model_name = display_to_model.get(display_name, DEFAULT_WHISPER_MODEL)
        whisper_model_info.config(text=model_details.get(model_name, ''))
        if engine_var.get() == 'whisper':
            model_tile.value_label.config(text=display_name)
        app.config.set("whisper_model", model_name)
        app.config.save()

    def on_whisper_api_model_change(event=None):
        display_name = whisper_api_model_var.get()
        model_name = whisper_api_display_to_model.get(display_name, WhisperApiService.DEFAULT_MODEL)
        whisper_api_model_info.config(text=whisper_api_pricing_text.get(model_name, ''))
        if engine_var.get() == 'whisper-api':
            model_tile.value_label.config(text=display_name)
        app.config.set("whisper_api_model", model_name)
        app.config.save()

    def on_gemini_recovery_change(event=None):
        display_name = gemini_recovery_var.get()
        recovery_mode = gemini_recovery_display_to_mode.get(display_name, 'segment-whisper')
        gemini_recovery_info.config(text=gemini_recovery_details.get(recovery_mode, ''))
        app.config.set("gemini_safety_filter_recovery", recovery_mode)
        app.config.save()

    def _update_ollama_panel_visibility():
        """タイトル生成 or 要約・議事録 のいずれかで Ollama を使う時だけ表示する"""
        title_display = title_engine_var.get()
        title_mode = title_engine_display_to_mode.get(title_display, 'ollama')
        uses_ollama = (
            title_mode in ('auto', 'ollama')
            or additional_engine_var.get() == 'ollama'
        )
        ollama_panel.pack_forget()
        if uses_ollama:
            ollama_panel.pack(fill=tk.X)

    def on_title_engine_change(event=None):
        display_name = title_engine_var.get()
        mode = title_engine_display_to_mode.get(display_name, 'ollama')
        app.config.set("title_generation_engine", mode)
        app.config.save()
        _update_ollama_panel_visibility()

    def on_additional_engine_change(*_args):
        value = additional_engine_var.get()
        if value not in ("gemini", "ollama"):
            value = "ollama"
            additional_engine_var.set(value)
        app.config.set("additional_processing_engine", value)
        app.config.save()
        _update_ollama_panel_visibility()

    def on_ollama_model_change(event=None):
        model_name = ollama_model_var.get().strip() or OLLAMA_DEFAULT_MODEL
        if ollama_model_var.get() != model_name:
            ollama_model_var.set(model_name)
        ollama_model_info.config(
            text=ollama_model_details.get(model_name, 'カスタムモデル')
        )
        app.config.set("ollama_model", model_name)
        app.config.save()

    engine_var.trace('w', lambda *args: on_engine_change())
    additional_engine_var.trace('w', on_additional_engine_change)
    whisper_model_combo.bind('<<ComboboxSelected>>', on_model_change)
    whisper_api_model_combo.bind('<<ComboboxSelected>>', on_whisper_api_model_change)
    gemini_recovery_combo.bind('<<ComboboxSelected>>', on_gemini_recovery_change)
    title_engine_combo.bind('<<ComboboxSelected>>', on_title_engine_change)
    ollama_model_combo.bind('<<ComboboxSelected>>', on_ollama_model_change)
    ollama_model_combo.bind('<FocusOut>', on_ollama_model_change)
    ollama_model_combo.bind('<Return>', on_ollama_model_change)
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
    on_ollama_model_change()
    _update_ollama_panel_visibility()

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
    frame.additional_engine_var = additional_engine_var
    frame.ollama_model_var = ollama_model_var
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

    output_folder_btn = widgets.create_icon_button(
        button_frame, "保存先", ICONS['folder'], 'Secondary',
        command=app.open_selected_output_directory
    )
    output_folder_btn.grid(row=0, column=1, sticky='ew', padx=4, pady=(0, 6))

    source_folder_btn = widgets.create_icon_button(
        button_frame, "元フォルダ", ICONS['file'], 'Secondary',
        command=app.open_source_file_folder
    )
    source_folder_btn.grid(row=0, column=2, sticky='ew', padx=(4, 0), pady=(0, 6))

    history_folder_btn = widgets.create_icon_button(
        button_frame, "履歴データ", ICONS['folder'], 'Secondary',
        command=app.open_history_directory
    )
    history_folder_btn.grid(row=1, column=0, sticky='ew', padx=(0, 4), pady=(0, 0))

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
            logger.warning("ドラッグ&ドロップを有効にするには、ルートウィンドウをTkinterDnD.Tkとして作成する必要があります")
    except ImportError:
        logger.warning("tkinterdnd2が見つかりません。ドラッグ&ドロップ機能は無効です。")
    except Exception as e:
        logger.error(f"ドラッグ&ドロップの設定中にエラーが発生しました: {str(e)}", exc_info=True)


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
        'additional_engine_var': file_section.additional_engine_var,
        'ollama_model_var': file_section.ollama_model_var,
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
        'recent_recordings_listbox': getattr(recording_section, 'recent_recordings_listbox', None),
        'add_selected_recordings_button': getattr(recording_section, 'add_selected_recordings_button', None),
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
