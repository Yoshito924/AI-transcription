#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
モダンなUIスタイリング設定
カラーパレット、フォント、スタイル定義
"""

import tkinter as tk
from tkinter import ttk
import platform

from .constants import ACCENT_STRIPE_WIDTH


class ModernTheme:
    """モダンなUIテーマの設定クラス"""

    def __init__(self):
        # インクブルー + ペーパー + アンバーで統一
        self.colors = {
            'primary': '#1F5468',
            'primary_light': '#2E6F86',
            'primary_dark': '#163F4E',
            'secondary': '#C98B2D',
            'secondary_light': '#E0AA54',
            'secondary_dark': '#9F6B1F',
            'accent': '#D9A24C',

            'background': '#ECE7DE',
            'surface': '#FBFAF7',
            'surface_variant': '#F4EFE7',
            'surface_emphasis': '#EEE6D8',
            'outline': '#D2C6B5',
            'card_border': '#D9CDBD',
            'divider': '#E5DDD2',

            'text_primary': '#232526',
            'text_secondary': '#64605A',
            'text_disabled': '#A79F96',
            'text_on_primary': '#FFFFFF',
            'text_on_dark': '#F7F3EC',

            'success': '#4F8B63',
            'success_soft': '#E4F0E7',
            'warning': '#C6882F',
            'warning_soft': '#F8EFDF',
            'error': '#BD5B55',
            'error_soft': '#F8E5E3',
            'info': '#4E7DA5',
            'info_soft': '#E5EDF5',

            'shadow': '#00000015',
            'hover': '#0000000A',
            'focus': '#1F546822',
            'button_hover': '#E8EEF2',
            'drag_drop_bg': '#EFF3F1',
            'drag_drop_border': '#2B667C',
            'drag_drop_hover': '#E2ECE9',
            'hero_bg': '#183845',
            'hero_surface': '#224958',
            'hero_border': '#3B6271',
            'badge_bg': '#E3ECF0',
            'badge_text': '#1F5468',

            'log_bg': '#20252B',
            'log_text': '#ECE7DE',
            'log_timestamp': '#8FA8C0',
            'log_error': '#F1948E',
            'log_success': '#89C098',
            'log_warning': '#E5BF7B',
            'log_separator': '#7B7974',

            'table_row_alt': '#F6F1E9',
            'table_selected': '#D7E5EA',
        }

        self.fonts = self._get_system_fonts()

        self.sizes = {
            'padding_small': 6,
            'padding_medium': 12,
            'padding_large': 18,
            'border_radius': 6,
            'button_height': 32,
            'input_height': 36,
            'header_height': 52,
            'sidebar_width': 300,
        }

        self.animations = {
            'transition_duration': 200,
            'fade_duration': 150,
            'slide_duration': 250,
        }

    def _get_system_fonts(self):
        """システムに最適なフォントを選択"""
        system = platform.system()

        if system == "Windows":
            return {
                'default': ('Segoe UI', 9),
                'app_title': ('Segoe UI Semibold', 18),
                'heading': ('Segoe UI Semibold', 13),
                'subheading': ('Segoe UI Semibold', 10),
                'body': ('Segoe UI', 9),
                'body_bold': ('Segoe UI Semibold', 9),
                'caption': ('Segoe UI', 8),
                'caption_bold': ('Segoe UI Semibold', 8),
                'button': ('Segoe UI Semibold', 9),
                'button_large': ('Segoe UI Semibold', 11),
                'monospace': ('Consolas', 9),
            }
        elif system == "Darwin":
            return {
                'default': ('SF Pro Display', 9),
                'app_title': ('SF Pro Display', 18, 'bold'),
                'heading': ('SF Pro Display', 13, 'bold'),
                'subheading': ('SF Pro Display', 10, 'bold'),
                'body': ('SF Pro Display', 9),
                'body_bold': ('SF Pro Display', 9, 'bold'),
                'caption': ('SF Pro Display', 8),
                'caption_bold': ('SF Pro Display', 8, 'bold'),
                'button': ('SF Pro Display', 9, 'bold'),
                'button_large': ('SF Pro Display', 11, 'bold'),
                'monospace': ('SF Mono', 9),
            }
        else:
            return {
                'default': ('Ubuntu', 9),
                'app_title': ('Ubuntu', 18, 'bold'),
                'heading': ('Ubuntu', 13, 'bold'),
                'subheading': ('Ubuntu', 10, 'bold'),
                'body': ('Ubuntu', 9),
                'body_bold': ('Ubuntu', 9, 'bold'),
                'caption': ('Ubuntu', 8),
                'caption_bold': ('Ubuntu', 8, 'bold'),
                'button': ('Ubuntu', 9, 'bold'),
                'button_large': ('Ubuntu', 11, 'bold'),
                'monospace': ('Ubuntu Mono', 9),
            }

    def apply_theme(self, root):
        """ルートウィンドウにテーマを適用"""
        root.configure(bg=self.colors['background'])

        style = ttk.Style()
        style.theme_use('clam')

        self._configure_frame_styles(style)
        self._configure_button_styles(style)
        self._configure_entry_styles(style)
        self._configure_label_styles(style)
        self._configure_treeview_styles(style)
        self._configure_progressbar_styles(style)
        self._configure_combobox_styles(style)
        self._configure_notebook_styles(style)
        self._configure_toggle_styles(style)
        self._configure_scrollbar_styles(style)

        return style

    def _configure_frame_styles(self, style):
        """フレームスタイルの設定"""
        style.configure('Main.TFrame',
                       background=self.colors['background'],
                       relief='flat')

        style.configure('Card.TFrame',
                       background=self.colors['surface'],
                       relief='flat',
                       borderwidth=1)

        style.configure('Sidebar.TFrame',
                       background=self.colors['surface_variant'],
                       relief='flat')

    def _configure_button_styles(self, style):
        """ボタンスタイルの設定"""
        style.configure('Primary.TButton',
                       background=self.colors['primary'],
                       foreground=self.colors['text_on_primary'],
                       font=self.fonts['button'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat',
                       padding=(12, 7))

        style.map('Primary.TButton',
                 background=[('active', self.colors['primary_light']),
                           ('pressed', self.colors['primary_dark'])],
                 foreground=[('disabled', self.colors['text_on_primary'])])

        style.configure('Large.Primary.TButton',
                       background=self.colors['primary'],
                       foreground=self.colors['text_on_primary'],
                       font=self.fonts['button_large'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat',
                       padding=(20, 10))

        style.map('Large.Primary.TButton',
                 background=[('active', self.colors['primary_light']),
                           ('pressed', self.colors['primary_dark'])])

        style.configure('Secondary.TButton',
                       background=self.colors['surface'],
                       foreground=self.colors['primary'],
                       font=self.fonts['button'],
                       focuscolor='none',
                       borderwidth=1,
                       relief='solid',
                       padding=(10, 6))

        style.map('Secondary.TButton',
                 background=[('active', self.colors['button_hover']),
                           ('pressed', self.colors['focus'])],
                 bordercolor=[('!active', self.colors['outline']),
                            ('active', self.colors['primary'])])

        style.configure('Success.TButton',
                       background=self.colors['success'],
                       foreground=self.colors['text_on_primary'],
                       font=self.fonts['button'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat')

        style.configure('Warning.TButton',
                       background=self.colors['warning'],
                       foreground=self.colors['text_on_primary'],
                       font=self.fonts['button'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat')

    def _configure_entry_styles(self, style):
        """入力フィールドスタイルの設定"""
        style.configure('Modern.TEntry',
                       font=self.fonts['body'],
                       foreground=self.colors['text_primary'],
                       fieldbackground=self.colors['surface'],
                       borderwidth=1,
                       relief='solid',
                       insertcolor=self.colors['primary'],
                       padding=(8, 6))

        style.map('Modern.TEntry',
                 bordercolor=[('!active', self.colors['outline']),
                            ('active', self.colors['primary']),
                            ('focus', self.colors['primary'])])

    def _configure_label_styles(self, style):
        """ラベルスタイルの設定"""
        style.configure('Heading.TLabel',
                       font=self.fonts['heading'],
                       foreground=self.colors['text_primary'],
                       background=self.colors['background'])

        style.configure('Subheading.TLabel',
                       font=self.fonts['subheading'],
                       foreground=self.colors['text_primary'],
                       background=self.colors['background'])

        style.configure('Body.TLabel',
                       font=self.fonts['body'],
                       foreground=self.colors['text_primary'],
                       background=self.colors['background'])

        style.configure('Caption.TLabel',
                       font=self.fonts['caption'],
                       foreground=self.colors['text_secondary'],
                       background=self.colors['background'])

        style.configure('Status.TLabel',
                       font=self.fonts['caption'],
                       foreground=self.colors['text_secondary'],
                       background=self.colors['surface'])

    def _configure_treeview_styles(self, style):
        """ツリービュースタイルの設定"""
        style.configure('Modern.Treeview',
                       background=self.colors['surface'],
                       foreground=self.colors['text_primary'],
                       font=self.fonts['body'],
                       fieldbackground=self.colors['surface'],
                       borderwidth=1,
                       relief='solid',
                       rowheight=26)

        style.configure('Modern.Treeview.Heading',
                       background=self.colors['surface_variant'],
                       foreground=self.colors['text_primary'],
                       font=self.fonts['caption_bold'],
                       relief='flat',
                       borderwidth=1)

        style.map('Modern.Treeview',
                 background=[('selected', self.colors['table_selected'])],
                 foreground=[('selected', self.colors['text_primary'])])

    def _configure_progressbar_styles(self, style):
        """プログレスバースタイルの設定"""
        style.configure('Modern.Horizontal.TProgressbar',
                       background=self.colors['primary'],
                       troughcolor=self.colors['surface_emphasis'],
                       borderwidth=0,
                       lightcolor=self.colors['primary'],
                       darkcolor=self.colors['primary'])

    def _configure_combobox_styles(self, style):
        """コンボボックススタイルの設定"""
        style.configure('Modern.TCombobox',
                       font=self.fonts['body'],
                       foreground=self.colors['text_primary'],
                       fieldbackground=self.colors['surface'],
                       borderwidth=1,
                       relief='solid',
                       padding=(7, 5))

        style.map('Modern.TCombobox',
                 bordercolor=[('!active', self.colors['outline']),
                            ('active', self.colors['primary']),
                            ('focus', self.colors['primary'])])

    def _configure_notebook_styles(self, style):
        """ノートブックスタイルの設定"""
        style.configure('Modern.TNotebook',
                       background=self.colors['background'],
                       borderwidth=0,
                       relief='flat')

        style.configure('Modern.TNotebook.Tab',
                       background=self.colors['surface_variant'],
                       foreground=self.colors['text_secondary'],
                       font=self.fonts['body_bold'],
                       padding=[14, 8],
                       borderwidth=0,
                       relief='flat')

        style.map('Modern.TNotebook.Tab',
                 background=[('selected', self.colors['surface']),
                           ('active', self.colors['button_hover'])],
                 foreground=[('selected', self.colors['text_primary']),
                           ('active', self.colors['text_primary'])],
                 padding=[('selected', [14, 8]),
                         ('!selected', [14, 8])])

    def _configure_toggle_styles(self, style):
        """ラジオボタンとチェックボックスの設定"""
        style.configure('Modern.TRadiobutton',
                       background=self.colors['surface'],
                       foreground=self.colors['text_primary'],
                       font=self.fonts['caption_bold'],
                       focuscolor='none',
                       padding=(2, 2))

        style.map('Modern.TRadiobutton',
                 background=[('active', self.colors['surface'])],
                 foreground=[('selected', self.colors['primary']),
                           ('active', self.colors['primary'])])

        style.configure('Modern.TCheckbutton',
                       background=self.colors['surface'],
                       foreground=self.colors['text_primary'],
                       font=self.fonts['caption'],
                       focuscolor='none',
                       padding=(1, 1))

        style.map('Modern.TCheckbutton',
                 background=[('active', self.colors['surface'])],
                 foreground=[('selected', self.colors['primary']),
                           ('active', self.colors['primary'])])

    def _configure_scrollbar_styles(self, style):
        """スクロールバースタイルの設定"""
        style.configure('Modern.Vertical.TScrollbar',
                       gripcount=0,
                       background=self.colors['surface_emphasis'],
                       darkcolor=self.colors['surface_emphasis'],
                       lightcolor=self.colors['surface_emphasis'],
                       troughcolor=self.colors['surface_variant'],
                       bordercolor=self.colors['surface_variant'],
                       arrowcolor=self.colors['text_secondary'],
                       relief='flat')

        style.configure('Modern.Horizontal.TScrollbar',
                       gripcount=0,
                       background=self.colors['surface_emphasis'],
                       darkcolor=self.colors['surface_emphasis'],
                       lightcolor=self.colors['surface_emphasis'],
                       troughcolor=self.colors['surface_variant'],
                       bordercolor=self.colors['surface_variant'],
                       arrowcolor=self.colors['text_secondary'],
                       relief='flat')


class ModernWidgets:
    """モダンなカスタムウィジェットクラス"""

    def __init__(self, theme: ModernTheme):
        self.theme = theme

    def create_card_frame(self, parent, **kwargs):
        """カードスタイルのフレームを作成（ボーダー付き）"""
        frame = tk.Frame(parent,
                        bg=self.theme.colors['surface'],
                        relief='flat',
                        bd=0,
                        highlightbackground=self.theme.colors['card_border'],
                        highlightthickness=1,
                        **kwargs)
        return frame

    def create_section_header(self, parent, title, bg=None):
        """アクセントストライプ付きセクションヘッダーを作成"""
        if bg is None:
            bg = self.theme.colors['surface']

        header_frame = tk.Frame(parent, bg=bg)

        stripe = tk.Frame(header_frame,
                         bg=self.theme.colors['primary'],
                         width=ACCENT_STRIPE_WIDTH)
        stripe.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        stripe.pack_propagate(False)

        label = tk.Label(header_frame,
                        text=title,
                        font=self.theme.fonts['subheading'],
                        fg=self.theme.colors['text_primary'],
                        bg=bg)
        label.pack(side=tk.LEFT, fill=tk.X)

        return header_frame

    def create_pill_label(self, parent, text, tone='info', bg=None, fg=None, **kwargs):
        """ピル型ラベルを作成"""
        tone_map = {
            'info': (self.theme.colors['badge_bg'], self.theme.colors['badge_text']),
            'success': (self.theme.colors['success_soft'], self.theme.colors['success']),
            'warning': (self.theme.colors['warning_soft'], self.theme.colors['warning']),
            'error': (self.theme.colors['error_soft'], self.theme.colors['error']),
            'dark': (self.theme.colors['hero_surface'], self.theme.colors['text_on_dark']),
        }
        default_bg, default_fg = tone_map.get(tone, tone_map['info'])

        return tk.Label(
            parent,
            text=text,
            bg=bg or default_bg,
            fg=fg or default_fg,
            font=self.theme.fonts['caption_bold'],
            padx=8,
            pady=3,
            **kwargs
        )

    def create_metric_tile(self, parent, title, value, tone='primary'):
        """見出し付きのメトリクスタイルを作成"""
        tone_map = {
            'primary': self.theme.colors['primary'],
            'success': self.theme.colors['success'],
            'warning': self.theme.colors['warning'],
            'info': self.theme.colors['info'],
        }
        accent = tone_map.get(tone, self.theme.colors['primary'])

        tile = tk.Frame(
            parent,
            bg=self.theme.colors['surface_variant'],
            highlightbackground=self.theme.colors['card_border'],
            highlightthickness=1,
            bd=0
        )

        accent_bar = tk.Frame(tile, bg=accent, height=4)
        accent_bar.pack(fill=tk.X)

        body = tk.Frame(tile, bg=self.theme.colors['surface_variant'])
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        title_label = tk.Label(
            body,
            text=title,
            font=self.theme.fonts['caption_bold'],
            fg=self.theme.colors['text_secondary'],
            bg=self.theme.colors['surface_variant']
        )
        title_label.pack(anchor='w')

        value_label = tk.Label(
            body,
            text=value,
            font=self.theme.fonts['heading'],
            fg=self.theme.colors['text_primary'],
            bg=self.theme.colors['surface_variant']
        )
        value_label.pack(anchor='w', pady=(6, 0))

        tile.value_label = value_label
        return tile

    def create_drag_drop_canvas(
        self,
        parent,
        text=None,
        height=128,
        title=None,
        subtitle=None,
        formats_text='MP3 / WAV / MP4 / MOV / M4A / FLAC'
    ):
        """Canvas使用のドラッグ&ドロップエリアを作成"""
        default_title = "クリックしてファイルを選択"
        default_subtitle = "またはこの欄にドラッグ&ドロップ"
        normalized_text = (text or "").strip()

        if title is None and subtitle is None and normalized_text:
            if any(token in normalized_text for token in ('ドラッグ', '/', '\n')):
                title = default_title
                subtitle = default_subtitle
            else:
                title = normalized_text
                subtitle = default_subtitle
        else:
            title = title or default_title
            subtitle = subtitle or default_subtitle

        container = tk.Frame(parent, bg=self.theme.colors['surface_variant'])

        canvas = tk.Canvas(
            container,
            bg=self.theme.colors['drag_drop_bg'],
            highlightthickness=0,
            height=height,
            cursor='hand2'
        )
        canvas.pack(fill=tk.X, expand=True)
        canvas._hovering = False

        def _draw_badge(x1, y1, x2, y2, fill, text_color, badge_text):
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline='')
            canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=badge_text,
                font=self.theme.fonts['caption_bold'],
                fill=text_color
            )

        def _draw(event=None):
            w = canvas.winfo_width()
            if w < 2:
                return

            compact = w < 620
            stacked = w < 470
            min_height = max(height, 168 if stacked else 148 if compact else height)
            current_height = int(canvas.cget('height'))
            if current_height < min_height:
                canvas.configure(height=min_height)
                return

            canvas.delete('all')
            h = canvas.winfo_height()
            if h < 2:
                return

            hovered = canvas._hovering
            canvas.configure(
                bg=self.theme.colors['drag_drop_hover'] if hovered else self.theme.colors['drag_drop_bg']
            )

            panel_pad = 5
            panel_x1 = panel_pad
            panel_y1 = panel_pad
            panel_x2 = w - panel_pad
            panel_y2 = h - panel_pad
            accent = self.theme.colors['primary_light'] if hovered else self.theme.colors['primary']
            button_fill = self.theme.colors['primary_light'] if hovered else self.theme.colors['primary']
            icon_fill = self.theme.colors['surface_emphasis'] if hovered else self.theme.colors['surface_variant']

            canvas.create_rectangle(
                panel_x1,
                panel_y1,
                panel_x2,
                panel_y2,
                fill=self.theme.colors['surface'],
                outline=self.theme.colors['card_border'],
                width=1
            )
            canvas.create_rectangle(
                panel_x1,
                panel_y1,
                panel_x2,
                panel_y1 + 4,
                fill=accent,
                outline=''
            )

            left = panel_x1 + 16
            right = panel_x2 - 16
            top = panel_y1 + 12
            badge_h = 20

            _draw_badge(
                left,
                top,
                left + 80,
                top + badge_h,
                self.theme.colors['badge_bg'],
                self.theme.colors['badge_text'],
                '音声 / 動画'
            )

            if not compact:
                _draw_badge(
                    right - 70,
                    top,
                    right,
                    top + badge_h,
                    self.theme.colors['warning_soft'],
                    self.theme.colors['warning'],
                    '複数選択'
                )

            icon_size = 42
            content_top = top + 34

            if stacked:
                icon_x1 = left
                icon_y1 = content_top
                icon_x2 = icon_x1 + icon_size
                icon_y2 = icon_y1 + icon_size
            else:
                icon_x1 = left
                icon_y1 = content_top + 2
                icon_x2 = icon_x1 + icon_size
                icon_y2 = icon_y1 + icon_size

            canvas.create_oval(
                icon_x1,
                icon_y1,
                icon_x2,
                icon_y2,
                fill=icon_fill,
                outline=self.theme.colors['outline'],
                width=1
            )
            canvas.create_text(
                (icon_x1 + icon_x2) / 2,
                (icon_y1 + icon_y2) / 2 - 1,
                text='\u2191',
                font=(self.theme.fonts['heading'][0], 16, 'bold'),
                fill=accent
            )

            if stacked:
                text_x = left
                title_y = icon_y2 + 12
                text_width = max(180, right - left)
            else:
                text_x = icon_x2 + 16
                title_y = content_top
                text_width = max(220, right - text_x)

            title_id = canvas.create_text(
                text_x,
                title_y,
                text=title,
                anchor='nw',
                width=text_width,
                font=self.theme.fonts['subheading'],
                fill=self.theme.colors['text_primary']
            )
            title_bbox = canvas.bbox(title_id)
            subtitle_y = title_bbox[3] + 8 if title_bbox else title_y + 24

            subtitle_id = canvas.create_text(
                text_x,
                subtitle_y,
                text=subtitle,
                anchor='nw',
                width=text_width,
                font=self.theme.fonts['caption'],
                fill=self.theme.colors['text_secondary']
            )
            subtitle_bbox = canvas.bbox(subtitle_id)

            text_bottom = subtitle_bbox[3] if subtitle_bbox else subtitle_y + 18
            content_bottom = max(icon_y2, text_bottom)

            button_y1 = content_bottom + 16
            button_y2 = button_y1 + 30
            if stacked:
                button_x1 = left
                button_x2 = right
            elif compact:
                button_x1 = text_x
                button_x2 = min(text_x + 160, right)
            else:
                button_x1 = text_x
                button_x2 = min(text_x + 150, right)

            canvas.create_rectangle(
                button_x1,
                button_y1,
                button_x2,
                button_y2,
                fill=button_fill,
                outline=button_fill,
                width=1
            )
            canvas.create_text(
                (button_x1 + button_x2) / 2,
                (button_y1 + button_y2) / 2,
                text='ファイルを選ぶ',
                font=self.theme.fonts['caption_bold'],
                fill=self.theme.colors['text_on_primary']
            )

            formats_y = button_y2 + 14
            formats_id = canvas.create_text(
                left,
                formats_y,
                text=f'対応形式  {formats_text}',
                anchor='nw',
                width=max(180, right - left),
                font=self.theme.fonts['caption'],
                fill=self.theme.colors['text_secondary']
            )

            formats_bbox = canvas.bbox(formats_id)
            required_height = (formats_bbox[3] + 16 + panel_pad) if formats_bbox else min_height
            if required_height > h:
                canvas.configure(height=required_height)
                return

        canvas.bind('<Configure>', _draw)

        def on_enter(event):
            canvas._hovering = True
            _draw()

        def on_leave(event):
            canvas._hovering = False
            _draw()

        canvas.bind('<Enter>', on_enter)
        canvas.bind('<Leave>', on_leave)

        container.canvas = canvas
        container._draw = _draw
        return container

    def create_drag_drop_area(self, parent, text="ファイルをドラッグ&ドロップ", **kwargs):
        """ドラッグ&ドロップエリアを作成（後方互換）"""
        frame = tk.Frame(parent,
                        bg=self.theme.colors['drag_drop_bg'],
                        relief='solid',
                        bd=2,
                        **kwargs)

        label = tk.Label(frame,
                        text=text,
                        bg=self.theme.colors['drag_drop_bg'],
                        fg=self.theme.colors['primary'],
                        font=self.theme.fonts['subheading'],
                        cursor='hand2')

        label.pack(expand=True, fill='both')

        def on_enter(event):
            frame.configure(bg=self.theme.colors['button_hover'])
            label.configure(bg=self.theme.colors['button_hover'],
                          fg=self.theme.colors['primary'])

        def on_leave(event):
            frame.configure(bg=self.theme.colors['drag_drop_bg'])
            label.configure(bg=self.theme.colors['drag_drop_bg'],
                          fg=self.theme.colors['primary'])

        frame.bind('<Enter>', on_enter)
        frame.bind('<Leave>', on_leave)
        label.bind('<Enter>', on_enter)
        label.bind('<Leave>', on_leave)

        return frame, label

    def create_action_button(self, parent, text, command=None):
        """大きなアクションボタン（tk.Button + ホバー効果）"""
        btn = tk.Button(parent,
                       text=text,
                       font=self.theme.fonts['button_large'],
                       bg=self.theme.colors['primary'],
                       fg=self.theme.colors['text_on_primary'],
                       activebackground=self.theme.colors['primary_light'],
                       activeforeground=self.theme.colors['text_on_primary'],
                       relief='flat',
                       bd=0,
                       padx=20,
                       pady=10,
                       cursor='hand2',
                       command=command)

        def on_enter(event):
            btn.configure(bg=self.theme.colors['primary_light'])

        def on_leave(event):
            btn.configure(bg=self.theme.colors['primary'])

        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)

        return btn

    def create_button(self, parent, text, style='Primary', **kwargs):
        """通常のボタンを作成"""
        return ttk.Button(parent, text=text, style=f'{style}.TButton', **kwargs)

    def create_icon_button(self, parent, text, icon=None, style='Primary', **kwargs):
        """アイコン付きボタンを作成"""
        button_text = f"{icon} {text}" if icon else text
        return ttk.Button(parent, text=button_text, style=f'{style}.TButton', **kwargs)

    def create_status_indicator(self, parent, **kwargs):
        """ステータスインジケーターを作成"""
        frame = tk.Frame(parent, bg=self.theme.colors['surface'], **kwargs)

        dot = tk.Label(frame,
                      text="\u25cf",
                      fg=self.theme.colors['text_disabled'],
                      bg=self.theme.colors['surface'],
                      font=(self.theme.fonts['default'][0], 8))
        dot.pack(side='left', padx=(0, 5))

        label = tk.Label(frame,
                        text="待機中",
                        fg=self.theme.colors['text_secondary'],
                        bg=self.theme.colors['surface'],
                        font=self.theme.fonts['caption'])
        label.pack(side='left')

        def update_status(status, color):
            color_map = {
                'idle': self.theme.colors['text_disabled'],
                'processing': self.theme.colors['info'],
                'success': self.theme.colors['success'],
                'error': self.theme.colors['error'],
                'warning': self.theme.colors['warning']
            }
            dot.configure(fg=color_map.get(color, self.theme.colors['text_disabled']))
            label.configure(text=status)

        frame.update_status = update_status
        return frame

    def configure_log_tags(self, log_text):
        """ログテキストウィジェットにカラータグを設定"""
        log_text.tag_configure('timestamp',
                              foreground=self.theme.colors['log_timestamp'])
        log_text.tag_configure('error',
                              foreground=self.theme.colors['log_error'])
        log_text.tag_configure('success',
                              foreground=self.theme.colors['log_success'])
        log_text.tag_configure('warning',
                              foreground=self.theme.colors['log_warning'])
        log_text.tag_configure('separator',
                              foreground=self.theme.colors['log_separator'])
        log_text.tag_configure('normal',
                              foreground=self.theme.colors['log_text'])


# アイコン定義（Unicode文字を使用）
ICONS = {
    'microphone': '\U0001f3a4',
    'file': '\U0001f4c1',
    'upload': '\U0001f4e4',
    'download': '\U0001f4e5',
    'play': '\u25b6\ufe0f',
    'pause': '\u23f8\ufe0f',
    'stop': '\u23f9\ufe0f',
    'settings': '\u2699\ufe0f',
    'refresh': '\U0001f504',
    'check': '\u2705',
    'error': '\u274c',
    'warning': '\u26a0\ufe0f',
    'info': '\u2139\ufe0f',
    'edit': '\u270f\ufe0f',
    'delete': '\U0001f5d1\ufe0f',
    'save': '\U0001f4be',
    'search': '\U0001f50d',
    'menu': '\u2630',
    'close': '\u2716\ufe0f',
    'minimize': '\u2796',
    'maximize': '\U0001f532',
    'folder': '\U0001f4c2',
    'document': '\U0001f4c4',
    'copy': '\U0001f4cb',
    'cut': '\u2702\ufe0f',
    'paste': '\U0001f4cc',
    'undo': '\u21b6',
    'redo': '\u21b7',
    'export': '\U0001f4bc',
    'key': '\U0001f511',
    'clock': '\u23f0',
    'text': '\U0001f4dd',
    'open': '\U0001f4c2',
    'import': '\U0001f4e5',
    'audio': '\U0001f50a',
    'video': '\U0001f3ac',
    'calendar': '\U0001f4c5',
    'user': '\U0001f464',
    'users': '\U0001f465',
    'star': '\u2b50',
    'heart': '\u2764\ufe0f',
    'thumb_up': '\U0001f44d',
    'thumb_down': '\U0001f44e',
    'question': '\u2753',
    'exclamation': '\u2757',
    'plus': '\u2795',
    'minus': '\u2796',
    'multiply': '\u2716\ufe0f',
    'divide': '\u2797',
    'arrow_up': '\u2b06\ufe0f',
    'arrow_down': '\u2b07\ufe0f',
    'arrow_left': '\u2b05\ufe0f',
    'arrow_right': '\u27a1\ufe0f',
}
