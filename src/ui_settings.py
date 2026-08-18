#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""処理設定（エンジン・保存先・要約）のタブ用レイアウト。"""

import tkinter as tk
from tkinter import ttk

from .engines import ENGINES, get_engine_spec
from .utils import resolve_whisper_model_name
from .whisper_api_service import WhisperApiService
from .constants import (
    CARD_PADDING,
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
)


def _bind_dynamic_wraplength(label, padding=0):
    """ラベルの wraplength を自身の幅に追従させる（自己発火で縦に伸びない）"""
    def _update(event=None):
        w = label.winfo_width()
        if w <= 1:
            return
        new_wrap = max(80, w - max(0, padding))
        try:
            current = int(float(label.cget('wraplength') or 0))
        except (TypeError, ValueError):
            current = 0
        if abs(current - new_wrap) > 2:
            label.config(wraplength=new_wrap)
    label.bind('<Configure>', _update)


def _pack_choice_grid(parent, items, variable, columns=2):
    """ラジオボタンを2列グリッドで並べる"""
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


def _create_settings_card(parent, widgets, theme, title, intro=None):
    """設定タブ用のカードと本文フレームを作る"""
    card = widgets.create_card_frame(parent)
    card.pack(fill=tk.X, pady=(0, 8))

    header = tk.Frame(card, bg=theme.colors['surface'])
    header.pack(fill=tk.X, padx=CARD_PADDING, pady=(CARD_PADDING, 8))
    widgets.create_section_header(header, title).pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )

    inner = tk.Frame(card, bg=theme.colors['surface'])
    inner.pack(fill=tk.X, padx=CARD_PADDING, pady=(0, CARD_PADDING))

    if intro:
        intro_label = tk.Label(
            inner,
            text=intro,
            font=theme.fonts['caption'],
            fg=theme.colors['text_secondary'],
            bg=theme.colors['surface'],
            justify='left',
            anchor='w'
        )
        intro_label.pack(fill=tk.X, pady=(0, 8))
        _bind_dynamic_wraplength(intro_label)
    return inner


def create_processing_settings_section(parent, app, theme, widgets):
    """エンジン・モデル・保存先・要約の設定カードをまとめて作る"""
    frame = tk.Frame(parent, bg=theme.colors['surface'])
    frame.notify_summary = []

    def _notify_summary():
        for callback in list(frame.notify_summary):
            callback()

    engine_inner = _create_settings_card(
        frame, widgets, theme, "文字起こし",
        "使うエンジンとモデルです。文字起こしタブの作業にはすぐ反映されます。"
    )

    saved_engine = app.config.get("transcription_engine", DEFAULT_TRANSCRIPTION_ENGINE)
    if saved_engine not in ("gemini", "whisper", "whisper-api"):
        saved_engine = DEFAULT_TRANSCRIPTION_ENGINE
    engine_var = tk.StringVar(value=saved_engine)

    tk.Label(
        engine_inner,
        text="エンジン",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w')

    _pack_choice_grid(
        engine_inner,
        [
            (ENGINES['whisper'].choice_label, "whisper"),
            (ENGINES['gemini'].choice_label, "gemini"),
            (ENGINES['whisper-api'].choice_label, "whisper-api"),
        ],
        engine_var
    )

    engine_desc = tk.Label(
        engine_inner,
        text=get_engine_spec(saved_engine).help_text,
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    engine_desc.pack(anchor='w', fill=tk.X, pady=(0, 4))
    _bind_dynamic_wraplength(engine_desc)

    whisper_local_panel = tk.Frame(engine_inner, bg=theme.colors['surface'])
    tk.Label(
        whisper_local_panel,
        text="ローカルモデル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
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
        bg=theme.colors['surface']
    )
    whisper_model_info.pack(anchor='w', pady=(2, 0))

    whisper_api_panel = tk.Frame(engine_inner, bg=theme.colors['surface'])
    tk.Label(
        whisper_api_panel,
        text="OpenAI モデル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w', pady=(10, 0))

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
        bg=theme.colors['surface']
    )
    whisper_api_model_info.pack(anchor='w', pady=(4, 0))

    gemini_recovery_panel = tk.Frame(engine_inner, bg=theme.colors['surface'])
    gemini_intro = tk.Label(
        gemini_recovery_panel,
        text=f"モデルは {DEFAULT_GEMINI_MODEL.replace('gemini-', '').replace('-flash', ' Flash')} を優先して自動選択します。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    gemini_intro.pack(anchor='w', fill=tk.X, pady=(10, 0))
    _bind_dynamic_wraplength(gemini_intro)

    tk.Label(
        gemini_recovery_panel,
        text="弾かれたときの動作",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w', pady=(8, 0))

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
        bg=theme.colors['surface']
    )
    gemini_recovery_info.pack(anchor='w', pady=(4, 0))

    save_inner = _create_settings_card(
        frame, widgets, theme, "保存と前処理",
        "出力先と、長い無音の圧縮です。"
    )

    tk.Label(
        save_inner,
        text="保存先",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w')

    save_desc = tk.Label(
        save_inner,
        text="出力先は複数指定できます。どちらもオフにした場合は output に戻します。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    save_desc.pack(anchor='w', fill=tk.X, pady=(2, 6))
    _bind_dynamic_wraplength(save_desc)

    save_to_output_var = tk.BooleanVar(value=app.config.get("save_to_output_dir", True))
    save_to_source_var = tk.BooleanVar(value=app.config.get("save_to_source_dir", False))
    ttk.Checkbutton(
        save_inner, text="output フォルダ",
        variable=save_to_output_var, command=lambda: on_output_toggle(),
        style='Modern.TCheckbutton'
    ).pack(anchor='w')
    ttk.Checkbutton(
        save_inner, text="元ファイル側にも保存",
        variable=save_to_source_var, command=lambda: on_source_toggle(),
        style='Modern.TCheckbutton'
    ).pack(anchor='w', pady=(4, 0))

    rename_source_var = tk.BooleanVar(value=app.config.get("rename_source_file", False))
    ttk.Checkbutton(
        save_inner, text="元ファイルを要約タイトルでリネーム",
        variable=rename_source_var,
        command=lambda: (
            app.config.set("rename_source_file", rename_source_var.get()),
            app.config.save(),
        ),
        style='Modern.TCheckbutton'
    ).pack(anchor='w', pady=(4, 0))

    trim_long_silence_var = tk.BooleanVar(
        value=app.config.get("trim_long_silence", True)
    )
    ttk.Checkbutton(
        save_inner, text="長い無音を自動圧縮",
        variable=trim_long_silence_var, command=lambda: on_trim_long_silence_toggle(),
        style='Modern.TCheckbutton'
    ).pack(anchor='w', pady=(10, 0))

    trim_long_silence_desc = tk.Label(
        save_inner,
        text="会話が無い長めの区間を短く詰めます。判定条件は波形プレビューと実処理の両方に反映されます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    trim_long_silence_desc.pack(anchor='w', fill=tk.X, pady=(2, 0))
    _bind_dynamic_wraplength(trim_long_silence_desc)

    silence_settings_shell = tk.Frame(
        save_inner,
        bg=theme.colors['surface_variant'],
        highlightbackground=theme.colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    silence_settings_shell.pack(fill=tk.X, pady=(10, 0))
    silence_settings_inner = tk.Frame(silence_settings_shell, bg=theme.colors['surface_variant'])
    silence_settings_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    silence_mode_header = tk.Frame(silence_settings_inner, bg=theme.colors['surface_variant'])
    silence_mode_header.pack(fill=tk.X)
    tk.Label(
        silence_mode_header,
        text="無音カット判定",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(side=tk.LEFT)
    tk.Label(
        silence_mode_header,
        text="波形へ自動反映",
        font=theme.fonts['caption'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface_variant']
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

    threshold_header = tk.Frame(silence_settings_inner, bg=theme.colors['surface_variant'])
    threshold_header.pack(fill=tk.X)
    tk.Label(
        threshold_header,
        text="しきい値 (dB)",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(side=tk.LEFT)
    silence_trim_threshold_value_label = tk.Label(
        threshold_header,
        text="",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface_variant']
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

    min_silence_header = tk.Frame(silence_settings_inner, bg=theme.colors['surface_variant'])
    min_silence_header.pack(fill=tk.X)
    tk.Label(
        min_silence_header,
        text="無音とみなす長さ",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface_variant']
    ).pack(side=tk.LEFT)
    silence_trim_min_value_label = tk.Label(
        min_silence_header,
        text="",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['primary'],
        bg=theme.colors['surface_variant']
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
        bg=theme.colors['surface_variant'],
        justify='left',
        anchor='w'
    )
    silence_trim_note.pack(fill=tk.X, pady=(2, 0))
    _bind_dynamic_wraplength(silence_trim_note)

    llm_inner = _create_settings_card(
        frame, widgets, theme, "要約とタイトル",
        "文字起こし後の要約・議事録と、ファイル名用タイトルです。"
    )

    tk.Label(
        llm_inner,
        text="要約・議事録 LLM",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w')
    additional_engine_desc = tk.Label(
        llm_inner,
        text="通常は Ollama、クラウドに出すときだけ Gemini です。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    additional_engine_desc.pack(anchor='w', fill=tk.X, pady=(2, 4))
    _bind_dynamic_wraplength(additional_engine_desc)

    saved_additional_engine = app.config.get(
        "additional_processing_engine", DEFAULT_ADDITIONAL_PROCESSING_ENGINE
    )
    if saved_additional_engine not in ("gemini", "ollama"):
        saved_additional_engine = DEFAULT_ADDITIONAL_PROCESSING_ENGINE
    additional_engine_var = tk.StringVar(value=saved_additional_engine)
    _pack_choice_grid(
        llm_inner,
        [("Ollama", "ollama"), ("Gemini", "gemini")],
        additional_engine_var
    )

    tk.Label(
        llm_inner,
        text="タイトル生成 LLM",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w', pady=(10, 0))
    title_engine_desc = tk.Label(
        llm_inner,
        text="ファイル名用の短いタイトルです。通常は Ollama のまま使えます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    title_engine_desc.pack(anchor='w', fill=tk.X, pady=(2, 4))
    _bind_dynamic_wraplength(title_engine_desc)

    title_engine_display_names = {
        'ollama': 'Ollama（ローカルLLM）',
        'auto': '自動（Ollama → Gemini）',
        'gemini': 'Gemini API（クラウド）',
        'disabled': '無効（タイトル生成しない）',
    }
    title_engine_display_to_mode = {v: k for k, v in title_engine_display_names.items()}
    saved_title_engine = app.config.get(
        "title_generation_engine", DEFAULT_TITLE_GENERATION_ENGINE
    )
    title_engine_var = tk.StringVar(
        value=title_engine_display_names.get(
            saved_title_engine, title_engine_display_names['ollama']
        )
    )
    title_engine_combo = ttk.Combobox(
        llm_inner,
        textvariable=title_engine_var,
        values=list(title_engine_display_names.values()),
        state='readonly',
        style='Modern.TCombobox'
    )
    title_engine_combo.pack(fill=tk.X, pady=(6, 0))

    ollama_panel = tk.Frame(llm_inner, bg=theme.colors['surface'])
    tk.Label(
        ollama_panel,
        text="Ollama モデル",
        font=theme.fonts['caption_bold'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface']
    ).pack(anchor='w', pady=(10, 0))
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
        bg=theme.colors['surface']
    )
    ollama_model_info.pack(anchor='w', pady=(4, 0))
    ollama_panel.pack(fill=tk.X)

    def summary_model_text():
        engine_value = engine_var.get()
        if engine_value == 'gemini':
            return DEFAULT_GEMINI_MODEL.replace('gemini-', '').replace('-flash', ' Flash')
        if engine_value == 'whisper-api':
            return (
                whisper_api_model_var.get()
                or WhisperApiService.MODEL_DESCRIPTIONS[WhisperApiService.DEFAULT_MODEL]
            )
        return whisper_model_var.get()

    def summary_save_text():
        destinations = []
        if save_to_output_var.get():
            destinations.append("output")
        if save_to_source_var.get():
            destinations.append("元フォルダ")
        if not destinations:
            destinations.append("output")
        return " / ".join(destinations)

    def on_output_toggle():
        if not save_to_output_var.get() and not save_to_source_var.get():
            save_to_output_var.set(True)
        app.config.set("save_to_output_dir", save_to_output_var.get())
        app.config.set("save_to_source_dir", save_to_source_var.get())
        app.config.save()
        _notify_summary()

    def on_source_toggle():
        if not save_to_source_var.get() and not save_to_output_var.get():
            save_to_source_var.set(True)
        app.config.set("save_to_output_dir", save_to_output_var.get())
        app.config.set("save_to_source_dir", save_to_source_var.get())
        app.config.save()
        _notify_summary()

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
        spec = get_engine_spec(engine_value)
        for panel in (whisper_local_panel, whisper_api_panel, gemini_recovery_panel):
            panel.pack_forget()
        if spec.key == "whisper":
            whisper_local_panel.pack(fill=tk.X)
        elif spec.key == "whisper-api":
            whisper_api_panel.pack(fill=tk.X)
        elif spec.key == "gemini":
            gemini_recovery_panel.pack(fill=tk.X)
        engine_desc.config(text=spec.help_text)
        app.config.set("transcription_engine", engine_value)
        app.config.save()
        _notify_summary()

    def on_model_change(event=None):
        display_name = whisper_model_var.get()
        model_name = display_to_model.get(display_name, DEFAULT_WHISPER_MODEL)
        whisper_model_info.config(text=model_details.get(model_name, ''))
        app.config.set("whisper_model", model_name)
        app.config.save()
        _notify_summary()

    def on_whisper_api_model_change(event=None):
        display_name = whisper_api_model_var.get()
        model_name = whisper_api_display_to_model.get(
            display_name, WhisperApiService.DEFAULT_MODEL
        )
        whisper_api_model_info.config(text=whisper_api_pricing_text.get(model_name, ''))
        app.config.set("whisper_api_model", model_name)
        app.config.save()
        _notify_summary()

    def on_gemini_recovery_change(event=None):
        display_name = gemini_recovery_var.get()
        recovery_mode = gemini_recovery_display_to_mode.get(display_name, 'segment-whisper')
        gemini_recovery_info.config(text=gemini_recovery_details.get(recovery_mode, ''))
        app.config.set("gemini_safety_filter_recovery", recovery_mode)
        app.config.save()

    def _update_ollama_panel_visibility():
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

    _update_silence_trim_controls()
    on_engine_change()
    on_model_change()
    on_whisper_api_model_change()
    on_gemini_recovery_change()
    on_ollama_model_change()
    _update_ollama_panel_visibility()

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
    frame.summary_model_text = summary_model_text
    frame.summary_save_text = summary_save_text
    frame.saved_engine = saved_engine
    frame.saved_whisper_model = saved_whisper_model
    return frame
