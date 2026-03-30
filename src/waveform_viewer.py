#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DAW風オーディオウェーブフォームビューア

tkinter Canvas ベースでズーム・スクロール・クリックシークに対応し、
再生ヘッドと無音区間プレビューを重ねて表示する。
"""

import math
import tkinter as tk
from tkinter import ttk


class WaveformViewer(tk.Frame):
    """DAW風ウェーブフォーム表示ウィジェット"""

    CANVAS_HEIGHT = 88
    TIMELINE_HEIGHT = 18
    MIN_ZOOM = 1.0
    MAX_ZOOM = 50.0
    DEFAULT_SAMPLES = 4000
    DRAG_THRESHOLD_PX = 5

    def __init__(self, parent, theme, **kwargs):
        super().__init__(parent, bg=theme.colors['surface_variant'], **kwargs)
        self.theme = theme
        self._samples = None
        self._duration = 0.0
        self._silence_regions = []
        self._cut_regions = []
        self._cut_summary_text = ""
        self._cut_enabled = False
        self._analysis_text = ""
        self._is_loading = False
        self._loading_message = ""
        self._zoom = 1.0
        self._scroll_offset = 0
        self._drag_start_x = None
        self._drag_start_offset = 0
        self._drag_active = False
        self._hover_time_sec = None
        self._playhead_sec = 0.0
        self._is_playing = False
        self._current_db = -float('inf')
        self._seek_callback = None
        self._play_toggle_callback = None
        self._stop_callback = None

        self._colors = {
            'wave_fill': theme.colors['primary'],
            'wave_outline': theme.colors['primary_dark'],
            'silence_fill': '#FDECEA',
            'silence_stripe': '#D9534F',
            'cut_fill': '#F8D487',
            'cut_outline': '#C97816',
            'center_line': theme.colors['outline'],
            'timeline_text': theme.colors['text_secondary'],
            'timeline_tick': theme.colors['outline'],
            'canvas_bg': theme.colors['surface'],
            'border': theme.colors['card_border'],
            'playhead': '#C97816',
            'playhead_soft': '#F3B15B',
        }

        self._build_ui()
        self._visible = False
        self.pack_forget()

    def _build_ui(self):
        """UIを構築"""
        c = self._colors
        t = self.theme

        header = tk.Frame(self, bg=t.colors['surface_variant'])
        header.pack(fill=tk.X, pady=(0, 2))

        tk.Label(
            header,
            text="\U0001F50A 波形プレビュー",
            font=t.fonts['caption_bold'],
            fg=t.colors['text_secondary'],
            bg=t.colors['surface_variant']
        ).pack(side=tk.LEFT)

        controls = tk.Frame(header, bg=t.colors['surface_variant'])
        controls.pack(side=tk.LEFT, padx=(10, 0))

        self._play_button = ttk.Button(
            controls,
            text="\u25b6 再生",
            width=8,
            command=self._on_play_button
        )
        self._play_button.pack(side=tk.LEFT)

        self._stop_button = ttk.Button(
            controls,
            text="\u23f9 停止",
            width=8,
            command=self._on_stop_button
        )
        self._stop_button.pack(side=tk.LEFT, padx=(4, 0))

        self._playback_label = tk.Label(
            controls,
            text="0:00 / 0:00",
            font=t.fonts['caption'],
            fg=t.colors['text_secondary'],
            bg=t.colors['surface_variant'],
            anchor='w'
        )
        self._playback_label.pack(side=tk.LEFT, padx=(8, 0))

        self._db_meter_canvas = tk.Canvas(
            controls,
            width=60,
            height=14,
            bg=t.colors['surface_variant'],
            highlightthickness=0
        )
        self._db_meter_canvas.pack(side=tk.LEFT, padx=(6, 0))

        self._db_label = tk.Label(
            controls,
            text="---dB",
            font=(t.fonts['default'][0], 8),
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant'],
            width=7,
            anchor='w'
        )
        self._db_label.pack(side=tk.LEFT, padx=(2, 0))

        legend_frame = tk.Frame(header, bg=t.colors['surface_variant'])
        legend_frame.pack(side=tk.LEFT, padx=(12, 0))

        silence_swatch = tk.Canvas(
            legend_frame,
            width=12,
            height=12,
            bg=t.colors['surface_variant'],
            highlightthickness=0
        )
        silence_swatch.create_rectangle(
            1, 1, 11, 11,
            fill=self._colors['silence_fill'],
            outline=self._colors['silence_stripe'],
            width=1
        )
        silence_swatch.pack(side=tk.LEFT)
        tk.Label(
            legend_frame,
            text="無音区間",
            font=t.fonts['caption'],
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant']
        ).pack(side=tk.LEFT, padx=(2, 8))

        cut_swatch = tk.Canvas(
            legend_frame,
            width=12,
            height=12,
            bg=t.colors['surface_variant'],
            highlightthickness=0
        )
        cut_swatch.create_rectangle(
            1, 1, 11, 11,
            fill=self._colors['cut_fill'],
            outline=self._colors['cut_outline'],
            width=1,
            stipple='gray25'
        )
        cut_swatch.pack(side=tk.LEFT)
        tk.Label(
            legend_frame,
            text="短縮候補",
            font=t.fonts['caption'],
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant']
        ).pack(side=tk.LEFT, padx=(2, 8))

        playhead_swatch = tk.Canvas(
            legend_frame,
            width=12,
            height=12,
            bg=t.colors['surface_variant'],
            highlightthickness=0
        )
        playhead_swatch.create_line(
            6, 1, 6, 11,
            fill=self._colors['playhead'],
            width=2
        )
        playhead_swatch.pack(side=tk.LEFT)
        tk.Label(
            legend_frame,
            text="再生位置",
            font=t.fonts['caption'],
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant']
        ).pack(side=tk.LEFT, padx=(2, 0))

        zoom_frame = tk.Frame(header, bg=t.colors['surface_variant'])
        zoom_frame.pack(side=tk.RIGHT)

        tk.Label(
            zoom_frame,
            text="\U0001F50D",
            font=(t.fonts['default'][0], 9),
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant']
        ).pack(side=tk.LEFT)

        self._zoom_var = tk.DoubleVar(value=1.0)
        self._zoom_slider = ttk.Scale(
            zoom_frame,
            from_=self.MIN_ZOOM,
            to=self.MAX_ZOOM,
            orient=tk.HORIZONTAL,
            length=100,
            variable=self._zoom_var,
            command=self._on_zoom_change
        )
        self._zoom_slider.pack(side=tk.LEFT, padx=(2, 4))

        self._zoom_label = tk.Label(
            zoom_frame,
            text="x1.0",
            font=t.fonts['caption'],
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant'],
            width=5,
            anchor='w'
        )
        self._zoom_label.pack(side=tk.LEFT)

        canvas_frame = tk.Frame(self, bg=c['border'], highlightthickness=0, bd=0)
        canvas_frame.pack(fill=tk.X)

        self._canvas = tk.Canvas(
            canvas_frame,
            height=self.CANVAS_HEIGHT,
            bg=c['canvas_bg'],
            highlightthickness=0,
            bd=1,
            relief='flat'
        )
        self._canvas.pack(fill=tk.X, padx=1, pady=1)

        self._timeline = tk.Canvas(
            canvas_frame,
            height=self.TIMELINE_HEIGHT,
            bg=c['canvas_bg'],
            highlightthickness=0,
            bd=0
        )
        self._timeline.pack(fill=tk.X, padx=1, pady=(0, 1))

        self._scrollbar = ttk.Scrollbar(
            self,
            orient=tk.HORIZONTAL,
            command=self._on_scroll
        )
        self._scrollbar.pack(fill=tk.X)

        self._info_label = tk.Label(
            self,
            text="",
            font=t.fonts['caption'],
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant'],
            anchor='w'
        )
        self._info_label.pack(fill=tk.X, pady=(2, 0))

        self._canvas.bind('<Configure>', self._on_canvas_resize)
        self._canvas.bind('<MouseWheel>', self._on_mouse_wheel)
        self._timeline.bind('<MouseWheel>', self._on_mouse_wheel)
        self._canvas.bind('<ButtonPress-1>', self._on_drag_start)
        self._canvas.bind('<B1-Motion>', self._on_drag_motion)
        self._canvas.bind('<ButtonRelease-1>', self._on_drag_end)
        self._canvas.bind('<Motion>', self._on_mouse_move)
        self._canvas.bind('<Leave>', self._on_mouse_leave)
        self._timeline.bind('<ButtonPress-1>', self._on_drag_start)
        self._timeline.bind('<B1-Motion>', self._on_drag_motion)
        self._timeline.bind('<ButtonRelease-1>', self._on_drag_end)
        self._timeline.bind('<Motion>', self._on_mouse_move)
        self._timeline.bind('<Leave>', self._on_mouse_leave)

        self._update_control_state()

    def set_callbacks(self, play_toggle_callback=None, stop_callback=None, seek_callback=None):
        """外部コールバックを設定する"""
        self._play_toggle_callback = play_toggle_callback
        self._stop_callback = stop_callback
        self._seek_callback = seek_callback

    def show(self):
        """ウィジェットを表示"""
        if not self._visible:
            self.pack(fill=tk.X, pady=(8, 4), before=self._get_pack_before())
            self._visible = True

    def hide(self):
        """ウィジェットを非表示"""
        if self._visible:
            self.pack_forget()
            self._visible = False

    def _get_pack_before(self):
        """pack の挿入先を返す（フォールバック用）"""
        return None

    def set_data(self, samples, duration, silence_regions=None, analysis_text="",
                 cut_regions=None, cut_summary_text="", cut_enabled=False,
                 preserve_view=False):
        """波形データと無音区間を設定して描画する"""
        self._is_loading = False
        self._loading_message = ""
        self._samples = samples
        self._duration = max(0.0, float(duration or 0.0))
        self._silence_regions = silence_regions or []
        self._cut_regions = cut_regions or []
        self._cut_summary_text = cut_summary_text or ""
        self._cut_enabled = bool(cut_enabled)
        self._analysis_text = analysis_text or ""

        if not preserve_view:
            self._scroll_offset = 0
            self._zoom = 1.0
            self._zoom_var.set(1.0)
            self._zoom_label.config(text="x1.0")
            self._playhead_sec = 0.0
            self._is_playing = False
        else:
            self._playhead_sec = max(0.0, min(self._playhead_sec, self._duration))

        self._update_control_state()
        self._update_info_label()
        self.show()
        self._canvas.after(10, self._redraw)

    def set_loading(self, message="波形を解析中..."):
        """波形読み込み中のプレースホルダを表示する"""
        self._is_loading = True
        self._loading_message = message or "波形を解析中..."
        self._samples = None
        self._duration = 0.0
        self._silence_regions = []
        self._cut_regions = []
        self._cut_summary_text = ""
        self._cut_enabled = False
        self._analysis_text = ""
        self._playhead_sec = 0.0
        self._is_playing = False
        self._scroll_offset = 0
        self._zoom = 1.0
        self._zoom_var.set(1.0)
        self._zoom_label.config(text="x1.0")
        self._update_control_state()
        self._update_info_label()
        self.show()
        self._canvas.after(10, self._redraw)

    def set_playback_state(self, current_time, is_playing=False, current_db=None):
        """再生位置と再生中フラグを更新する"""
        if self._duration <= 0:
            self._playhead_sec = 0.0
            self._is_playing = False
            self._current_db = -float('inf')
        else:
            self._playhead_sec = max(0.0, min(float(current_time or 0.0), self._duration))
            self._is_playing = bool(is_playing)
            self._current_db = float(current_db) if current_db is not None else -float('inf')
            if self._is_playing:
                self._ensure_time_visible(self._playhead_sec)

        self._update_control_state()
        self._update_db_meter()
        self._update_info_label()
        if self._samples is not None:
            self._redraw()

    def get_current_time(self):
        """現在の再生ヘッド位置を返す"""
        return self._playhead_sec

    def clear(self):
        """データをクリアして非表示にする"""
        self._samples = None
        self._duration = 0.0
        self._silence_regions = []
        self._cut_regions = []
        self._cut_summary_text = ""
        self._cut_enabled = False
        self._analysis_text = ""
        self._is_loading = False
        self._loading_message = ""
        self._playhead_sec = 0.0
        self._is_playing = False
        self._current_db = -float('inf')
        self._hover_time_sec = None
        self._canvas.delete('all')
        self._timeline.delete('all')
        self._scrollbar.set(0, 1)
        self._update_control_state()
        self._update_db_meter()
        self._info_label.config(text="")
        self.hide()

    def _redraw(self):
        """Canvas 全体を再描画"""
        self._canvas.delete('all')
        self._timeline.delete('all')

        if self._samples is None or len(self._samples) == 0:
            if self._is_loading:
                self._draw_loading_placeholder()
            self._scrollbar.set(0, 1)
            return

        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        total_width = max(1, int(w * self._zoom))
        samples = self._samples
        n = len(samples)

        max_offset = max(0, total_width - w)
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))
        offset = self._scroll_offset

        f0 = offset / total_width
        f1 = min(1.0, (offset + w) / total_width)
        self._scrollbar.set(f0, f1)

        mid_y = h / 2

        self._draw_silence_regions(w, h, total_width, offset)

        self._canvas.create_line(
            0, mid_y, w, mid_y,
            fill=self._colors['center_line'],
            dash=(2, 4)
        )

        self._draw_waveform(w, h, total_width, offset, samples, n)
        self._draw_cut_regions(w, h, total_width, offset)
        self._draw_playhead(w, h, total_width, offset)
        self._draw_timeline(w, total_width, offset)

    def _draw_loading_placeholder(self):
        """波形読み込み中のプレースホルダを描画"""
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        self._canvas.create_rectangle(
            0, 0, w, h,
            fill=self._colors['canvas_bg'],
            outline=''
        )
        self._canvas.create_line(
            0, h / 2, w, h / 2,
            fill=self._colors['center_line'],
            dash=(2, 4)
        )

        step = max(18, int(w / 24))
        for x in range(-step, w + step, step):
            self._canvas.create_line(
                x, h * 0.68,
                x + int(step * 0.55), h * 0.32,
                fill=self.theme.colors['surface_emphasis'],
                width=3
            )

        self._canvas.create_text(
            w / 2,
            h / 2 - 2,
            text=self._loading_message,
            font=self.theme.fonts['body_bold'],
            fill=self.theme.colors['text_secondary']
        )
        self._timeline.create_text(
            w / 2,
            self.TIMELINE_HEIGHT / 2 + 2,
            text="読み込み直後にプレースホルダを表示しています",
            font=(self.theme.fonts['default'][0], 7),
            fill=self.theme.colors['text_disabled']
        )

    def _draw_silence_regions(self, w, h, total_width, offset):
        """無音区間を背景にハイライト描画"""
        if not self._silence_regions or self._duration <= 0:
            return

        for start_sec, end_sec in self._silence_regions:
            x0 = int(start_sec / self._duration * total_width) - offset
            x1 = int(end_sec / self._duration * total_width) - offset
            if x1 < 0 or x0 > w:
                continue

            x0 = max(0, x0)
            x1 = min(w, x1)

            self._canvas.create_rectangle(
                x0, 0, x1, h,
                fill=self._colors['silence_fill'],
                outline=''
            )

            if x1 - x0 > 2:
                self._canvas.create_line(
                    x0, 0, x0, h,
                    fill=self._colors['silence_stripe'],
                    width=1,
                    dash=(2, 2)
                )
                self._canvas.create_line(
                    x1, 0, x1, h,
                    fill=self._colors['silence_stripe'],
                    width=1,
                    dash=(2, 2)
                )

    def _draw_cut_regions(self, w, h, total_width, offset):
        """短縮候補の区間を強調描画"""
        if not self._cut_regions or self._duration <= 0:
            return

        for start_sec, end_sec in self._cut_regions:
            x0 = int(start_sec / self._duration * total_width) - offset
            x1 = int(end_sec / self._duration * total_width) - offset
            if x1 < 0 or x0 > w:
                continue

            x0 = max(0, x0)
            x1 = min(w, x1)
            if x1 <= x0:
                continue

            self._canvas.create_rectangle(
                x0, 1, x1, h - 1,
                fill=self._colors['cut_fill'],
                outline=self._colors['cut_outline'],
                width=2 if self._cut_enabled else 1,
                stipple='gray25'
            )
            self._canvas.create_line(
                x0, 3, x1, 3,
                fill=self._colors['cut_outline'],
                width=2 if self._cut_enabled else 1,
                dash=() if self._cut_enabled else (4, 3)
            )

    def _draw_waveform(self, w, h, total_width, offset, samples, n):
        """波形をポリゴンとして描画"""
        mid_y = h / 2
        amp = (h - 4) / 2

        s_start = max(0, int(offset / total_width * n))
        s_end = min(n, int((offset + w) / total_width * n) + 1)
        if s_end <= s_start:
            return

        points_upper = []
        points_lower = []
        samples_per_pixel = max(1.0, (s_end - s_start) / max(1, w))

        for px in range(w):
            si = s_start + int(px * samples_per_pixel)
            ei = s_start + int((px + 1) * samples_per_pixel)
            ei = min(ei, s_end)
            if si >= ei:
                si = max(s_start, ei - 1)

            chunk = samples[si:ei]
            if len(chunk) == 0:
                continue

            peak_max = float(max(chunk))
            peak_min = float(min(chunk))
            y_top = mid_y - peak_max * amp
            y_bot = mid_y - peak_min * amp

            points_upper.append((px, y_top))
            points_lower.append((px, y_bot))

        if not points_upper:
            return

        polygon_points = []
        for x, y in points_upper:
            polygon_points.extend([x, y])
        for x, y in reversed(points_lower):
            polygon_points.extend([x, y])

        if len(polygon_points) >= 6:
            self._canvas.create_polygon(
                polygon_points,
                fill=self._colors['wave_fill'],
                outline=self._colors['wave_outline'],
                width=0.5,
                smooth=False
            )

    def _draw_playhead(self, w, h, total_width, offset):
        """再生ヘッドを描画"""
        if self._duration <= 0:
            return

        x = int((self._playhead_sec / self._duration) * total_width) - offset
        if not (0 <= x <= w):
            return

        self._canvas.create_line(
            x, 0, x, h,
            fill=self._colors['playhead'],
            width=2
        )
        self._canvas.create_line(
            x + 1, 0, x + 1, h,
            fill=self._colors['playhead_soft'],
            width=1
        )

        self._timeline.create_polygon(
            x, 0,
            x - 5, 6,
            x + 5, 6,
            fill=self._colors['playhead'],
            outline=''
        )

    def _draw_timeline(self, w, total_width, offset):
        """タイムラインの目盛りと時刻ラベルを描画"""
        if self._duration <= 0:
            return

        th = self.TIMELINE_HEIGHT
        c = self._colors
        visible_duration = self._duration / self._zoom
        interval = self._calc_tick_interval(visible_duration)
        t_start = offset / total_width * self._duration
        t_end = (offset + w) / total_width * self._duration
        first_tick = math.floor(t_start / interval) * interval

        t = first_tick
        while t <= t_end + interval:
            x = int((t / self._duration) * total_width) - offset
            if 0 <= x <= w:
                self._timeline.create_line(x, 0, x, 5, fill=c['timeline_tick'])
                self._timeline.create_text(
                    x,
                    th // 2 + 3,
                    text=self._format_time_short(t, show_fraction=interval < 1),
                    font=(self.theme.fonts['default'][0], 7),
                    fill=c['timeline_text'],
                    anchor='center'
                )
            t += interval

    def _calc_tick_interval(self, visible_duration):
        """表示範囲の長さに応じた適切な目盛り間隔を返す"""
        target_ticks = 8
        raw_interval = max(0.05, visible_duration / target_ticks)
        nice_intervals = [
            0.1, 0.2, 0.5,
            1, 2, 5, 10, 15, 30,
            60, 120, 300, 600, 1800, 3600
        ]
        for interval in nice_intervals:
            if interval >= raw_interval:
                return interval
        return 3600

    def _update_control_state(self):
        """再生ボタンと時刻表示を更新する"""
        has_data = self._samples is not None and self._duration > 0
        if has_data:
            self._play_button.state(['!disabled'])
            self._stop_button.state(['!disabled'])
        else:
            self._play_button.state(['disabled'])
            self._stop_button.state(['disabled'])

        self._play_button.config(text="\u23f8 一時停止" if self._is_playing else "\u25b6 再生")
        self._playback_label.config(
            text=f"{self._format_time_short(self._playhead_sec)} / {self._format_time_short(self._duration)}"
        )

    def _update_db_meter(self):
        """dBメーターを更新する"""
        canvas = self._db_meter_canvas
        canvas.delete('all')
        cw = 60
        ch = 14

        db = self._current_db
        if self._is_playing and db > -float('inf'):
            # -60dB ~ 0dB の範囲でメーター表示
            db_clamped = max(-60.0, min(0.0, db))
            ratio = (db_clamped + 60.0) / 60.0

            bar_w = int(ratio * cw)
            if bar_w > 0:
                if db_clamped > -6:
                    color = '#E53935'  # 赤（クリッピング付近）
                elif db_clamped > -18:
                    color = '#F9A825'  # 黄
                else:
                    color = '#43A047'  # 緑
                canvas.create_rectangle(0, 1, bar_w, ch - 1, fill=color, outline='')

            # 背景グリッド
            for mark_db in (-48, -36, -24, -12, -6):
                mx = int((mark_db + 60.0) / 60.0 * cw)
                canvas.create_line(mx, 0, mx, ch, fill=self.theme.colors['outline'], width=1)

            self._db_label.config(
                text=f"{db_clamped:.0f}dB",
                fg=self.theme.colors['text_secondary']
            )
        else:
            canvas.create_rectangle(0, 1, cw, ch - 1, fill='', outline=self.theme.colors['outline'], width=1)
            self._db_label.config(text="---dB", fg=self.theme.colors['text_disabled'])

    def _update_info_label(self):
        """下部の情報ラベルを更新する"""
        if self._is_loading:
            self._info_label.config(text=self._loading_message)
            return

        if self._duration <= 0:
            self._info_label.config(text="")
            return

        info_parts = [self._format_duration(self._duration)]

        if self._silence_regions:
            total_silence = sum(end - start for start, end in self._silence_regions)
            pct = total_silence / self._duration * 100 if self._duration > 0 else 0
            info_parts.append(
                f"無音: {self._format_duration(total_silence)} ({pct:.1f}%) × {len(self._silence_regions)}区間"
            )

        if self._cut_summary_text:
            info_parts.append(self._cut_summary_text)

        if self._analysis_text:
            info_parts.append(self._analysis_text)

        position_label = "再生" if self._is_playing else "位置"
        info_parts.append(f"{position_label}: {self._format_time_short(self._playhead_sec)}")

        if self._hover_time_sec is not None:
            in_silence = any(start <= self._hover_time_sec <= end for start, end in self._silence_regions)
            suffix = " [無音区間]" if in_silence else ""
            info_parts.append(f"カーソル: {self._format_time_short(self._hover_time_sec)}{suffix}")

        self._info_label.config(text="  |  ".join(info_parts))

    def _ensure_time_visible(self, sec):
        """再生位置が見えるようスクロール位置を調整する"""
        if self._duration <= 0:
            return

        w = self._canvas.winfo_width()
        if w <= 1:
            return

        total_width = max(1, int(w * self._zoom))
        playhead_x = int((sec / self._duration) * total_width)
        view_left = self._scroll_offset
        view_right = self._scroll_offset + w
        margin = int(w * 0.18)

        if playhead_x < view_left + margin:
            self._scroll_offset = max(0, playhead_x - margin)
        elif playhead_x > view_right - margin:
            self._scroll_offset = max(0, playhead_x - (w - margin))

    def _time_from_x(self, x):
        """Canvas 座標から時刻を計算する"""
        if self._duration <= 0:
            return 0.0

        w = self._canvas.winfo_width()
        total_width = max(1, int(w * self._zoom))
        sec = (self._scroll_offset + x) / total_width * self._duration
        return max(0.0, min(sec, self._duration))

    def _seek_to(self, sec):
        """内部位置を更新し、外部へ seek を通知する"""
        self._playhead_sec = max(0.0, min(sec, self._duration))
        self._update_control_state()
        self._update_info_label()
        self._redraw()
        if self._seek_callback:
            self._seek_callback(self._playhead_sec)

    def _on_canvas_resize(self, event=None):
        """Canvas サイズ変更時に再描画"""
        if self._samples is not None or self._is_loading:
            self._redraw()

    def _on_zoom_change(self, value=None):
        """ズームスライダー変更"""
        new_zoom = float(self._zoom_var.get())
        if abs(new_zoom - self._zoom) < 0.01:
            return

        w = self._canvas.winfo_width()
        if w > 1 and self._zoom > 0:
            center_ratio = (self._scroll_offset + w / 2) / max(1, (w * self._zoom))
            self._zoom = new_zoom
            new_total = w * self._zoom
            self._scroll_offset = int(center_ratio * new_total - w / 2)
        else:
            self._zoom = new_zoom

        self._zoom_label.config(text=f"x{self._zoom:.1f}")
        self._redraw()

    def _on_mouse_wheel(self, event):
        """マウスホイールでズーム"""
        if self._duration <= 0:
            return

        delta = 1 if event.delta > 0 else -1
        step = max(0.1, self._zoom * 0.15)
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self._zoom + delta * step))

        w = self._canvas.winfo_width()
        if w > 1 and self._zoom > 0:
            mouse_ratio = (self._scroll_offset + event.x) / max(1, (w * self._zoom))
            self._zoom = new_zoom
            self._zoom_var.set(new_zoom)
            new_total = w * self._zoom
            self._scroll_offset = int(mouse_ratio * new_total - event.x)
        else:
            self._zoom = new_zoom
            self._zoom_var.set(new_zoom)

        self._zoom_label.config(text=f"x{self._zoom:.1f}")
        self._redraw()

    def _on_scroll(self, *args):
        """スクロールバー操作"""
        w = self._canvas.winfo_width()
        total_width = max(1, int(w * self._zoom))

        if args[0] == 'moveto':
            fraction = float(args[1])
            self._scroll_offset = int(fraction * total_width)
        elif args[0] == 'scroll':
            amount = int(args[1])
            unit = args[2]
            if unit == 'units':
                self._scroll_offset += amount * 20
            else:
                self._scroll_offset += amount * w

        self._redraw()

    def _on_drag_start(self, event):
        """ドラッグ開始"""
        self._drag_start_x = event.x
        self._drag_start_offset = self._scroll_offset
        self._drag_active = False

    def _on_drag_motion(self, event):
        """ドラッグ中のスクロール"""
        if self._drag_start_x is None:
            return

        dx = self._drag_start_x - event.x
        if not self._drag_active and abs(dx) >= self.DRAG_THRESHOLD_PX:
            self._drag_active = True

        if self._drag_active:
            self._scroll_offset = self._drag_start_offset + dx
            self._redraw()

    def _on_drag_end(self, event):
        """ドラッグ終了。短いクリックならシークとして扱う"""
        if self._drag_start_x is not None and not self._drag_active and self._duration > 0:
            self._seek_to(self._time_from_x(event.x))

        self._drag_start_x = None
        self._drag_start_offset = 0
        self._drag_active = False

    def _on_mouse_move(self, event):
        """マウス位置のタイムスタンプ表示"""
        if self._duration <= 0:
            return

        self._hover_time_sec = self._time_from_x(event.x)
        self._update_info_label()

    def _on_mouse_leave(self, event=None):
        """ホバー情報を解除"""
        self._hover_time_sec = None
        self._update_info_label()

    def _on_play_button(self):
        """再生/一時停止ボタン"""
        if self._play_toggle_callback and self._duration > 0:
            self._play_toggle_callback()

    def _on_stop_button(self):
        """停止ボタン"""
        self._is_playing = False
        self._playhead_sec = 0.0
        self._current_db = -float('inf')
        self._update_control_state()
        self._update_db_meter()
        self._update_info_label()
        self._redraw()
        if self._stop_callback:
            self._stop_callback()

    @staticmethod
    def _format_duration(sec):
        """秒数を h:mm:ss 形式に変換"""
        sec = max(0.0, float(sec))
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @staticmethod
    def _format_time_short(sec, show_fraction=False):
        """タイムライン用の短い時刻表記"""
        sec = max(0.0, float(sec))
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60

        if show_fraction and sec < 60:
            return f"{m}:{s:04.1f}"

        whole_sec = int(s)
        if h > 0:
            return f"{h}:{m:02d}:{whole_sec:02d}"
        return f"{m}:{whole_sec:02d}"
