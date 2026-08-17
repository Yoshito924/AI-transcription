#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""録音タブのレイアウト。開始/停止を正面に置き、設定は折りたたみにする。"""

import tkinter as tk
from tkinter import ttk

from .ui_styles import ICONS


def _bind_dynamic_wraplength(label, padding=0):
    """ラベルの wraplength を親ウィジェットの幅に追従させる"""
    def _update(event=None):
        parent = label.winfo_parent()
        parent_widget = label.nametowidget(parent)
        w = parent_widget.winfo_width()
        if w > 1:
            label.config(wraplength=max(100, w - padding * 2 - 10))
    label.bind('<Configure>', _update)


def create_recording_section(parent, app, theme, widgets, pane_persisters=None):
    """録音専用タブを作成する"""
    del pane_persisters  # 呼び出し側のシグネチャ互換用
    frame = tk.Frame(parent, bg=theme.colors['surface'])
    pad = 12

    header_frame = tk.Frame(frame, bg=theme.colors['surface'])
    header_frame.pack(fill=tk.X, padx=pad, pady=(pad, 8))

    widgets.create_section_header(header_frame, "録音").pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )

    recording_badge_label = widgets.create_pill_label(
        header_frame, "待機中", tone='info'
    )
    recording_badge_label.pack(side=tk.RIGHT)

    intro_label = tk.Label(
        frame,
        text="大きなボタンか Space で開始・停止。止めると保存され、設定どおりキューへ回せます。",
        font=theme.fonts['caption'],
        fg=theme.colors['text_secondary'],
        bg=theme.colors['surface'],
        justify='left',
        anchor='w'
    )
    intro_label.pack(fill=tk.X, padx=pad, pady=(0, 8))
    _bind_dynamic_wraplength(intro_label, pad)

    recording_widgets = _create_recording_card(frame, app, theme, widgets, pad)
    recording_widgets['recording_badge_label'] = recording_badge_label

    for key, value in recording_widgets.items():
        setattr(frame, key, value)

    return frame


def _create_recording_card(parent, app, theme, widgets, pad):
    """録音の主操作・最近のファイル・入力設定を組み立てる"""
    colors = theme.colors
    card = widgets.create_card_frame(parent)
    card.pack(fill=tk.X, padx=pad, pady=(0, 8))

    inner = tk.Frame(card, bg=colors['surface'])
    inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

    stage = tk.Frame(inner, bg=colors['surface'])
    stage.pack(fill=tk.X)

    status_row = tk.Frame(stage, bg=colors['surface'])
    status_row.pack(fill=tk.X)

    recording_status_label = tk.Label(
        status_row,
        textvariable=app.recording_status_var,
        font=theme.fonts['heading'],
        fg=colors['text_primary'],
        bg=colors['surface']
    )
    recording_status_label.pack(side=tk.LEFT)

    recording_device_label = tk.Label(
        status_row,
        textvariable=app.recording_device_var,
        font=theme.fonts['caption'],
        fg=colors['text_secondary'],
        bg=colors['surface'],
        justify='right',
        anchor='e'
    )
    recording_device_label.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(12, 0))
    _bind_dynamic_wraplength(recording_device_label, 8)

    recording_timer_label = tk.Label(
        stage,
        textvariable=app.recording_elapsed_var,
        font=(theme.fonts['app_title'][0], 36),
        fg=colors['text_primary'],
        bg=colors['surface']
    )
    recording_timer_label.pack(anchor='w', pady=(4, 10))

    visual_shell = tk.Frame(
        stage,
        bg=colors['log_bg'],
        highlightbackground=colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    visual_shell.pack(fill=tk.X)

    recording_visual_canvas = tk.Canvas(
        visual_shell,
        bg=colors['log_bg'],
        highlightthickness=0,
        height=148
    )
    recording_visual_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    recording_visual_canvas.draw_visual = _make_visual_drawer(recording_visual_canvas, theme)
    recording_visual_canvas.bind(
        '<Configure>',
        lambda _event: recording_visual_canvas.draw_visual(0.0, 0.0, False, 0.0, [], [], False)
    )

    recording_hint_label = tk.Label(
        stage,
        textvariable=app.recording_hint_var,
        font=theme.fonts['caption'],
        fg=colors['text_secondary'],
        bg=colors['surface'],
        justify='left',
        anchor='w'
    )
    recording_hint_label.pack(anchor='w', fill=tk.X, pady=(8, 10))
    _bind_dynamic_wraplength(recording_hint_label, 8)

    record_button = widgets.create_record_toggle_button(
        stage, command=app.toggle_recording
    )
    record_button.pack(fill=tk.X)

    shortcut_label = tk.Label(
        stage,
        text="Space で開始 / 停止  ·  Esc で停止",
        font=theme.fonts['caption'],
        fg=colors['text_disabled'],
        bg=colors['surface']
    )
    shortcut_label.pack(anchor='w', pady=(6, 0))

    recent_shell = tk.Frame(
        inner,
        bg=colors['surface_variant'],
        highlightbackground=colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    recent_shell.pack(fill=tk.X, pady=(14, 0))

    recent_inner = tk.Frame(recent_shell, bg=colors['surface_variant'])
    recent_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    recent_header = tk.Frame(recent_inner, bg=colors['surface_variant'])
    recent_header.pack(fill=tk.X, pady=(0, 6))

    tk.Label(
        recent_header,
        text="最近の録音",
        font=theme.fonts['caption_bold'],
        fg=colors['text_primary'],
        bg=colors['surface_variant']
    ).pack(side=tk.LEFT)

    tk.Label(
        recent_header,
        text="ダブルクリックでキューへ",
        font=theme.fonts['caption'],
        fg=colors['text_secondary'],
        bg=colors['surface_variant']
    ).pack(side=tk.RIGHT)

    recent_listbox = tk.Listbox(
        recent_inner,
        height=5,
        font=theme.fonts['caption'],
        bg=colors['surface'],
        fg=colors['text_primary'],
        selectbackground=colors['table_selected'],
        selectforeground=colors['text_primary'],
        relief='flat',
        highlightthickness=1,
        highlightbackground=colors['card_border'],
        activestyle='none',
        exportselection=False
    )
    recent_listbox.pack(fill=tk.X)
    recent_listbox.bind('<Double-Button-1>', app.add_selected_recordings_to_queue)
    recent_listbox.bind('<Return>', app.add_selected_recordings_to_queue)

    recent_actions = tk.Frame(recent_inner, bg=colors['surface_variant'])
    recent_actions.pack(fill=tk.X, pady=(8, 0))
    recent_actions.grid_columnconfigure(0, weight=1)
    recent_actions.grid_columnconfigure(1, weight=1)
    recent_actions.grid_columnconfigure(2, weight=1)

    add_selected_recordings_button = widgets.create_icon_button(
        recent_actions, "選択をキューへ", ICONS['plus'], 'Primary',
        command=app.add_selected_recordings_to_queue
    )
    open_recording_folder_button = widgets.create_icon_button(
        recent_actions, "フォルダを開く", ICONS['open'], 'Secondary',
        command=app.open_recording_folder
    )
    queue_recordings_button = widgets.create_icon_button(
        recent_actions, "全部キューへ", ICONS['upload'], 'Secondary',
        command=app.add_recordings_to_queue
    )
    add_selected_recordings_button.grid(row=0, column=0, sticky='ew', padx=(0, 4))
    open_recording_folder_button.grid(row=0, column=1, sticky='ew', padx=4)
    queue_recordings_button.grid(row=0, column=2, sticky='ew', padx=(4, 0))

    settings_toggle = tk.Frame(inner, bg=colors['surface'], cursor='hand2')
    settings_toggle.pack(fill=tk.X, pady=(14, 0))

    settings_toggle_label = tk.Label(
        settings_toggle,
        text="▸ マイクと保存先",
        font=theme.fonts['caption_bold'],
        fg=colors['primary'],
        bg=colors['surface'],
        cursor='hand2'
    )
    settings_toggle_label.pack(side=tk.LEFT)

    settings_body = tk.Frame(
        inner,
        bg=colors['surface'],
        highlightbackground=colors['card_border'],
        highlightthickness=1,
        bd=0
    )
    settings_inner = tk.Frame(settings_body, bg=colors['surface'])
    settings_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    folder_top = tk.Frame(settings_inner, bg=colors['surface'])
    folder_top.pack(fill=tk.X)

    tk.Label(
        folder_top,
        text="録音保存先",
        font=theme.fonts['caption_bold'],
        fg=colors['text_secondary'],
        bg=colors['surface']
    ).pack(side=tk.LEFT)

    ttk.Checkbutton(
        folder_top,
        text="停止後に自動でキューへ追加",
        variable=app.auto_queue_recordings_var,
        command=app.toggle_auto_queue_recordings,
        style='Modern.TCheckbutton'
    ).pack(side=tk.RIGHT)

    recording_folder_label = tk.Label(
        settings_inner,
        textvariable=app.recording_dir_var,
        font=theme.fonts['caption'],
        fg=colors['text_primary'],
        bg=colors['surface'],
        justify='left',
        anchor='w'
    )
    recording_folder_label.pack(anchor='w', fill=tk.X, pady=(6, 8))
    _bind_dynamic_wraplength(recording_folder_label, 8)

    folder_buttons = tk.Frame(settings_inner, bg=colors['surface'])
    folder_buttons.pack(fill=tk.X, pady=(0, 10))
    folder_buttons.grid_columnconfigure(0, weight=1)

    choose_recording_folder_button = widgets.create_icon_button(
        folder_buttons, "保存先を変更", ICONS['folder'], 'Secondary',
        command=app.choose_recording_folder
    )
    choose_recording_folder_button.grid(row=0, column=0, sticky='ew')

    source_row = tk.Frame(settings_inner, bg=colors['surface'])
    source_row.pack(fill=tk.X, pady=(0, 8))
    source_row.grid_columnconfigure(0, weight=3)
    source_row.grid_columnconfigure(1, weight=2)

    device_column = tk.Frame(source_row, bg=colors['surface'])
    device_column.grid(row=0, column=0, sticky='ew', padx=(0, 8))

    tk.Label(
        device_column,
        text="入力デバイス",
        font=theme.fonts['caption_bold'],
        fg=colors['text_secondary'],
        bg=colors['surface']
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

    channel_column = tk.Frame(source_row, bg=colors['surface'])
    channel_column.grid(row=0, column=1, sticky='ew')

    channel_header = tk.Frame(channel_column, bg=colors['surface'])
    channel_header.pack(fill=tk.X)

    tk.Label(
        channel_header,
        text="入力チャンネル",
        font=theme.fonts['caption_bold'],
        fg=colors['text_secondary'],
        bg=colors['surface']
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
        settings_inner,
        text="オーディオIFの 1-2 / 3-4 などは、デバイスとチャンネルの両方で切り替えます。",
        font=theme.fonts['caption'],
        fg=colors['text_secondary'],
        bg=colors['surface'],
        justify='left',
        anchor='w'
    )
    source_note.pack(fill=tk.X, pady=(0, 8))
    _bind_dynamic_wraplength(source_note, 4)

    gain_header = tk.Frame(settings_inner, bg=colors['surface'])
    gain_header.pack(fill=tk.X)

    tk.Label(
        gain_header,
        text="録音レベル",
        font=theme.fonts['caption_bold'],
        fg=colors['text_secondary'],
        bg=colors['surface']
    ).pack(side=tk.LEFT)

    tk.Label(
        gain_header,
        textvariable=app.recording_gain_display_var,
        font=theme.fonts['caption_bold'],
        fg=colors['primary'],
        bg=colors['surface']
    ).pack(side=tk.RIGHT)

    gain_scale = ttk.Scale(
        settings_inner,
        from_=25,
        to=250,
        orient=tk.HORIZONTAL,
        variable=app.recording_gain_percent_var,
        command=app.on_recording_gain_change
    )
    gain_scale.pack(fill=tk.X, pady=(6, 2))
    gain_scale.bind('<ButtonRelease-1>', app.persist_recording_gain)

    gain_note = tk.Label(
        settings_inner,
        text="保存音量のソフトゲインです。100%が原音、上げすぎると割れます。",
        font=theme.fonts['caption'],
        fg=colors['text_secondary'],
        bg=colors['surface'],
        justify='left',
        anchor='w'
    )
    gain_note.pack(fill=tk.X)
    _bind_dynamic_wraplength(gain_note, 4)

    settings_state = {
        'expanded': bool(app.config.get('recording_settings_expanded', False))
    }

    def _apply_settings_visibility():
        if settings_state['expanded']:
            settings_body.pack(fill=tk.X, pady=(8, 0))
            settings_toggle_label.config(text="▾ マイクと保存先")
        else:
            settings_body.pack_forget()
            settings_toggle_label.config(text="▸ マイクと保存先")

    def _toggle_settings(_event=None):
        settings_state['expanded'] = not settings_state['expanded']
        app.config.set('recording_settings_expanded', settings_state['expanded'])
        app.config.save()
        _apply_settings_visibility()

    for widget in (settings_toggle, settings_toggle_label):
        widget.bind('<Button-1>', _toggle_settings)

    _apply_settings_visibility()

    return {
        'recording_status_label': recording_status_label,
        'recording_device_label': recording_device_label,
        'recording_timer_label': recording_timer_label,
        'recording_folder_label': recording_folder_label,
        'record_button': record_button,
        'stop_record_button': None,
        'queue_recordings_button': queue_recordings_button,
        'choose_recording_folder_button': choose_recording_folder_button,
        'open_recording_folder_button': open_recording_folder_button,
        'recording_device_combo': recording_device_combo,
        'recording_channel_combo': recording_channel_combo,
        'refresh_recording_inputs_button': refresh_recording_inputs_button,
        'recording_gain_scale': gain_scale,
        'recording_visual_canvas': recording_visual_canvas,
        'recent_recordings_listbox': recent_listbox,
        'add_selected_recordings_button': add_selected_recordings_button,
    }


def _make_visual_drawer(canvas, theme):
    """入力レベルと周波数バーを描く関数を返す"""
    colors = theme.colors

    def _draw_recording_visual(level=0.0, peak=0.0, is_active=False, phase=0.0,
                               spectrum_bins=None, waveform_points=None, is_live=False):
        del waveform_points
        canvas.delete('all')

        width = max(canvas.winfo_width(), 240)
        height = max(canvas.winfo_height(), 148)
        left_pad = 12
        right_pad = 12
        usable_width = max(80, width - left_pad - right_pad)
        meter_y0 = 28
        meter_height = 10
        meter_y1 = meter_y0 + meter_height

        level = max(0.0, min(1.0, float(level or 0.0)))
        peak = max(0.0, min(1.0, float(peak or 0.0)))
        level_pct = int(round(level * 100))
        peak_pct = int(round(peak * 100))

        if not is_live:
            status_text = "マイク待機中"
        elif level_pct < 8:
            status_text = "音が小さいので、近づけるかレベルを上げてください"
        elif level_pct < 30:
            status_text = "やや小さめです"
        elif level_pct < 70:
            status_text = "ちょうどよい大きさです"
        elif level_pct < 88:
            status_text = "大きめです。少し下げると割れにくいです"
        else:
            status_text = "大きすぎます。すぐレベルを下げてください"

        accent = colors['record'] if is_active else colors['primary_light']
        canvas.create_text(
            left_pad, 8,
            text="入力モニター" if not is_active else "録音中",
            anchor='nw',
            font=theme.fonts['caption_bold'],
            fill='#D7E0E4'
        )
        canvas.create_text(
            width - right_pad, 8,
            text=f"ピーク {peak_pct}%",
            anchor='ne',
            font=theme.fonts['caption_bold'],
            fill='#D7E0E4'
        )

        canvas.create_rectangle(
            left_pad, meter_y0, width - right_pad, meter_y1,
            fill='#29333A',
            outline='#47606A',
            width=1
        )
        fill_x = left_pad + (usable_width * level)
        if is_live and fill_x > left_pad:
            canvas.create_rectangle(
                left_pad, meter_y0 + 1, fill_x, meter_y1 - 1,
                fill=accent,
                outline=''
            )
        elif not is_live:
            pulse_width = usable_width * 0.16
            pulse_center = left_pad + ((((phase * 38) % 100) / 100.0) * usable_width)
            pulse_left = max(left_pad, pulse_center - (pulse_width / 2))
            pulse_right = min(width - right_pad, pulse_center + (pulse_width / 2))
            canvas.create_rectangle(
                pulse_left, meter_y0 + 2, pulse_right, meter_y1 - 2,
                fill='#5B7D88',
                outline=''
            )

        peak_x = left_pad + (usable_width * peak)
        canvas.create_line(
            peak_x, meter_y0 - 3, peak_x, meter_y1 + 3,
            fill='#F4D48C',
            width=2
        )

        bins = list(spectrum_bins or [])
        if len(bins) < 8:
            bins = [0.0] * 28
        bar_top = meter_y1 + 16
        bar_bottom = height - 28
        max_bar_h = max(12, bar_bottom - bar_top)
        gap = 3
        bar_width = max(3, (usable_width - gap * (len(bins) - 1)) / len(bins))

        for index, value in enumerate(bins):
            magnitude = max(0.0, min(1.0, float(value or 0.0)))
            if not is_live:
                magnitude *= 0.18
            x1 = left_pad + index * (bar_width + gap)
            x2 = x1 + bar_width
            bar_h = max(3, magnitude * max_bar_h)
            if magnitude >= 0.88:
                fill = '#D97761'
            elif magnitude >= 0.68:
                fill = '#E8A55B'
            elif is_active:
                fill = '#E07A72'
            else:
                fill = '#7FB3C4'
            canvas.create_rectangle(
                x1, bar_bottom - bar_h, x2, bar_bottom,
                fill=fill,
                outline=''
            )

        canvas.create_text(
            left_pad, height - 8,
            text=status_text,
            anchor='sw',
            font=theme.fonts['caption'],
            fill='#C9D8DE'
        )

    return _draw_recording_visual
