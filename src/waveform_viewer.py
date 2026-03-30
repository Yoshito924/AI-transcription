#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DAW風オーディオウェーブフォームビューア
tkinter Canvas ベースでズーム・スクロール対応、無音区間のハイライト表示
"""

import tkinter as tk
from tkinter import ttk
import math


class WaveformViewer(tk.Frame):
    """DAW風ウェーブフォーム表示ウィジェット"""

    # 定数
    CANVAS_HEIGHT = 80
    TIMELINE_HEIGHT = 18
    MIN_ZOOM = 1.0
    MAX_ZOOM = 50.0
    DEFAULT_SAMPLES = 4000

    def __init__(self, parent, theme, **kwargs):
        super().__init__(parent, bg=theme.colors['surface_variant'], **kwargs)
        self.theme = theme
        self._samples = None
        self._duration = 0.0
        self._silence_regions = []
        self._zoom = 1.0
        self._drag_start_x = None
        self._scroll_offset = 0  # pixels

        self._colors = {
            'wave_fill': theme.colors['primary'],
            'wave_outline': theme.colors['primary_dark'],
            'silence': '#E8433520',  # semi-transparent red
            'silence_fill': '#FDECEA',
            'silence_stripe': '#D9534F',
            'center_line': theme.colors['outline'],
            'timeline_text': theme.colors['text_secondary'],
            'timeline_tick': theme.colors['outline'],
            'canvas_bg': theme.colors['surface'],
            'border': theme.colors['card_border'],
        }

        self._build_ui()
        self._visible = False
        # 初期状態は非表示
        self.pack_forget()

    def _build_ui(self):
        """UIを構築"""
        c = self._colors
        t = self.theme

        # ヘッダー（タイトル＋ズームコントロール）
        header = tk.Frame(self, bg=t.colors['surface_variant'])
        header.pack(fill=tk.X, pady=(0, 2))

        tk.Label(
            header, text="\U0001F50A 波形プレビュー",
            font=t.fonts['caption_bold'],
            fg=t.colors['text_secondary'],
            bg=t.colors['surface_variant']
        ).pack(side=tk.LEFT)

        # 凡例
        legend_frame = tk.Frame(header, bg=t.colors['surface_variant'])
        legend_frame.pack(side=tk.LEFT, padx=(12, 0))

        # 無音区間の凡例
        silence_swatch = tk.Canvas(
            legend_frame, width=12, height=12,
            bg=t.colors['surface_variant'], highlightthickness=0
        )
        silence_swatch.create_rectangle(1, 1, 11, 11, fill='#FDECEA', outline='#D9534F', width=1)
        silence_swatch.pack(side=tk.LEFT)
        tk.Label(
            legend_frame, text="無音区間",
            font=t.fonts['caption'],
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant']
        ).pack(side=tk.LEFT, padx=(2, 0))

        # ズームコントロール（右寄せ）
        zoom_frame = tk.Frame(header, bg=t.colors['surface_variant'])
        zoom_frame.pack(side=tk.RIGHT)

        tk.Label(
            zoom_frame, text="\U0001F50D",
            font=(t.fonts['default'][0], 9),
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant']
        ).pack(side=tk.LEFT)

        self._zoom_var = tk.DoubleVar(value=1.0)
        self._zoom_slider = ttk.Scale(
            zoom_frame, from_=self.MIN_ZOOM, to=self.MAX_ZOOM,
            orient=tk.HORIZONTAL, length=100,
            variable=self._zoom_var,
            command=self._on_zoom_change
        )
        self._zoom_slider.pack(side=tk.LEFT, padx=(2, 4))

        self._zoom_label = tk.Label(
            zoom_frame, text="x1.0",
            font=t.fonts['caption'],
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant'],
            width=5, anchor='w'
        )
        self._zoom_label.pack(side=tk.LEFT)

        # ウェーブフォーム Canvas
        canvas_frame = tk.Frame(
            self, bg=c['border'],
            highlightthickness=0, bd=0
        )
        canvas_frame.pack(fill=tk.X)

        self._canvas = tk.Canvas(
            canvas_frame,
            height=self.CANVAS_HEIGHT,
            bg=c['canvas_bg'],
            highlightthickness=0, bd=1,
            relief='flat'
        )
        self._canvas.pack(fill=tk.X, padx=1, pady=1)

        # タイムライン Canvas
        self._timeline = tk.Canvas(
            canvas_frame,
            height=self.TIMELINE_HEIGHT,
            bg=c['canvas_bg'],
            highlightthickness=0, bd=0
        )
        self._timeline.pack(fill=tk.X, padx=1, pady=(0, 1))

        # 水平スクロールバー
        self._scrollbar = ttk.Scrollbar(
            self, orient=tk.HORIZONTAL,
            command=self._on_scroll
        )
        self._scrollbar.pack(fill=tk.X)

        # 情報ラベル
        self._info_label = tk.Label(
            self, text="",
            font=t.fonts['caption'],
            fg=t.colors['text_disabled'],
            bg=t.colors['surface_variant'],
            anchor='w'
        )
        self._info_label.pack(fill=tk.X, pady=(2, 0))

        # イベントバインド
        self._canvas.bind('<Configure>', self._on_canvas_resize)
        self._canvas.bind('<MouseWheel>', self._on_mouse_wheel)
        self._canvas.bind('<ButtonPress-1>', self._on_drag_start)
        self._canvas.bind('<B1-Motion>', self._on_drag_motion)
        self._canvas.bind('<ButtonRelease-1>', self._on_drag_end)
        self._canvas.bind('<Motion>', self._on_mouse_move)

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
        """packの挿入先を返す（フォールバック用）"""
        return None

    def set_data(self, samples, duration, silence_regions=None):
        """波形データと無音区間を設定して描画

        Args:
            samples: numpy array of normalized samples (-1.0 to 1.0)
            duration: audio duration in seconds
            silence_regions: list of (start_sec, end_sec) tuples
        """
        self._samples = samples
        self._duration = duration
        self._silence_regions = silence_regions or []
        self._scroll_offset = 0
        self._zoom = 1.0
        self._zoom_var.set(1.0)
        self._zoom_label.config(text="x1.0")

        # 情報テキスト更新
        info_parts = [self._format_duration(duration)]
        if silence_regions:
            total_silence = sum(e - s for s, e in silence_regions)
            pct = total_silence / duration * 100 if duration > 0 else 0
            info_parts.append(
                f"無音: {self._format_duration(total_silence)} "
                f"({pct:.1f}%) × {len(silence_regions)}区間"
            )
        self._info_label.config(text="  |  ".join(info_parts))

        self.show()
        self._canvas.after(10, self._redraw)

    def clear(self):
        """データをクリアして非表示にする"""
        self._samples = None
        self._duration = 0.0
        self._silence_regions = []
        self._canvas.delete('all')
        self._timeline.delete('all')
        self.hide()

    # --- 描画 ---

    def _redraw(self):
        """Canvas 全体を再描画"""
        self._canvas.delete('all')
        self._timeline.delete('all')

        if self._samples is None or len(self._samples) == 0:
            return

        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        total_width = int(w * self._zoom)
        samples = self._samples
        n = len(samples)

        # スクロールオフセットをクランプ
        max_offset = max(0, total_width - w)
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))
        offset = self._scroll_offset

        # スクロールバー更新
        if total_width > 0:
            f0 = offset / total_width
            f1 = min(1.0, (offset + w) / total_width)
            self._scrollbar.set(f0, f1)

        mid_y = h / 2

        # 無音区間を背景に描画
        self._draw_silence_regions(w, h, total_width, offset)

        # 中心線
        self._canvas.create_line(
            0, mid_y, w, mid_y,
            fill=self._colors['center_line'], dash=(2, 4)
        )

        # 波形描画（表示範囲のみ）
        self._draw_waveform(w, h, total_width, offset, samples, n)

        # タイムライン描画
        self._draw_timeline(w, total_width, offset)

    def _draw_silence_regions(self, w, h, total_width, offset):
        """無音区間を背景にハイライト描画"""
        if not self._silence_regions or self._duration <= 0:
            return

        for start_sec, end_sec in self._silence_regions:
            x0 = int(start_sec / self._duration * total_width) - offset
            x1 = int(end_sec / self._duration * total_width) - offset

            # 画面外ならスキップ
            if x1 < 0 or x0 > w:
                continue

            x0 = max(0, x0)
            x1 = min(w, x1)

            # 背景塗りつぶし
            self._canvas.create_rectangle(
                x0, 0, x1, h,
                fill=self._colors['silence_fill'],
                outline='', stipple=''
            )

            # 左右ボーダーライン
            if x1 - x0 > 2:
                self._canvas.create_line(
                    x0, 0, x0, h,
                    fill=self._colors['silence_stripe'], width=1, dash=(2, 2)
                )
                self._canvas.create_line(
                    x1, 0, x1, h,
                    fill=self._colors['silence_stripe'], width=1, dash=(2, 2)
                )

    def _draw_waveform(self, w, h, total_width, offset, samples, n):
        """波形をポリゴンとして描画"""
        mid_y = h / 2
        amp = (h - 4) / 2  # 上下2pxマージン

        # 表示範囲に対応するサンプル範囲
        s_start = max(0, int(offset / total_width * n))
        s_end = min(n, int((offset + w) / total_width * n) + 1)

        if s_end <= s_start:
            return

        # 表示ピクセルごとのサンプルをまとめてポリゴンを構築
        points_upper = []
        points_lower = []

        pixels = min(w, s_end - s_start)
        if pixels <= 0:
            return

        samples_per_pixel = max(1, (s_end - s_start) / w)

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

        # ポリゴン（上辺→下辺の逆順で閉じた形）
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

    def _draw_timeline(self, w, total_width, offset):
        """タイムラインの目盛りと時刻ラベルを描画"""
        if self._duration <= 0:
            return

        th = self.TIMELINE_HEIGHT
        c = self._colors

        # 適切な目盛り間隔を決定
        visible_duration = self._duration / self._zoom
        interval = self._calc_tick_interval(visible_duration)

        # 表示範囲の時間
        t_start = offset / total_width * self._duration
        t_end = (offset + w) / total_width * self._duration

        # 最初の目盛り位置
        first_tick = math.floor(t_start / interval) * interval

        t = first_tick
        while t <= t_end + interval:
            x = int((t / self._duration) * total_width) - offset

            if 0 <= x <= w:
                # 目盛り線
                self._timeline.create_line(
                    x, 0, x, 5,
                    fill=c['timeline_tick']
                )
                # 時刻ラベル
                self._timeline.create_text(
                    x, th // 2 + 3,
                    text=self._format_time_short(t),
                    font=(self.theme.fonts['default'][0], 7),
                    fill=c['timeline_text'],
                    anchor='center'
                )
            t += interval

    def _calc_tick_interval(self, visible_duration):
        """表示範囲の長さに応じた適切な目盛り間隔を返す"""
        # 目盛りは画面に5〜15本くらいが適切
        target_ticks = 8
        raw_interval = visible_duration / target_ticks

        # きれいな間隔に丸める
        nice_intervals = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600]
        for iv in nice_intervals:
            if iv >= raw_interval:
                return iv
        return 3600

    # --- イベントハンドラ ---

    def _on_canvas_resize(self, event=None):
        """Canvasサイズ変更時に再描画"""
        if self._samples is not None:
            self._redraw()

    def _on_zoom_change(self, value=None):
        """ズームスライダー変更"""
        new_zoom = float(self._zoom_var.get())
        if abs(new_zoom - self._zoom) < 0.01:
            return

        # ズーム中心を画面中央に維持
        w = self._canvas.winfo_width()
        if w > 1 and self._zoom > 0:
            center_ratio = (self._scroll_offset + w / 2) / (w * self._zoom)
            self._zoom = new_zoom
            new_total = w * self._zoom
            self._scroll_offset = int(center_ratio * new_total - w / 2)
        else:
            self._zoom = new_zoom

        self._zoom_label.config(text=f"x{self._zoom:.1f}")
        self._redraw()

    def _on_mouse_wheel(self, event):
        """マウスホイールでズーム"""
        delta = 1 if event.delta > 0 else -1
        step = max(0.1, self._zoom * 0.15)
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self._zoom + delta * step))

        # マウス位置を中心にズーム
        w = self._canvas.winfo_width()
        if w > 1 and self._zoom > 0:
            mouse_ratio = (self._scroll_offset + event.x) / (w * self._zoom)
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
        total_width = int(w * self._zoom)

        if args[0] == 'moveto':
            fraction = float(args[1])
            self._scroll_offset = int(fraction * total_width)
        elif args[0] == 'scroll':
            amount = int(args[1])
            unit = args[2]
            if unit == 'units':
                self._scroll_offset += amount * 20
            else:  # pages
                self._scroll_offset += amount * w

        self._redraw()

    def _on_drag_start(self, event):
        """ドラッグ開始"""
        self._drag_start_x = event.x
        self._drag_start_offset = self._scroll_offset

    def _on_drag_motion(self, event):
        """ドラッグ中のスクロール"""
        if self._drag_start_x is not None:
            dx = self._drag_start_x - event.x
            self._scroll_offset = self._drag_start_offset + dx
            self._redraw()

    def _on_drag_end(self, event):
        """ドラッグ終了"""
        self._drag_start_x = None

    def _on_mouse_move(self, event):
        """マウス位置のタイムスタンプ表示"""
        if self._samples is None or self._duration <= 0:
            return

        w = self._canvas.winfo_width()
        total_width = int(w * self._zoom)
        if total_width <= 0:
            return

        t = (self._scroll_offset + event.x) / total_width * self._duration
        t = max(0, min(t, self._duration))

        # 無音区間内かチェック
        in_silence = any(s <= t <= e for s, e in self._silence_regions)
        suffix = " [無音区間]" if in_silence else ""

        info_parts = [
            self._format_duration(self._duration),
            f"カーソル: {self._format_time_short(t)}{suffix}"
        ]
        if self._silence_regions:
            total_silence = sum(e - s for s, e in self._silence_regions)
            pct = total_silence / self._duration * 100 if self._duration > 0 else 0
            info_parts.insert(1,
                f"無音: {self._format_duration(total_silence)} "
                f"({pct:.1f}%) × {len(self._silence_regions)}区間"
            )
        self._info_label.config(text="  |  ".join(info_parts))

    # --- ユーティリティ ---

    @staticmethod
    def _format_duration(sec):
        """秒数を h:mm:ss 形式に変換"""
        sec = max(0, sec)
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @staticmethod
    def _format_time_short(sec):
        """タイムライン用の短い時刻表記"""
        sec = max(0, sec)
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
