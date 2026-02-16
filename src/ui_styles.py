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
        # カラーパレット（暖色系・洗練されたデザイン）
        self.colors = {
            # プライマリーカラー（柔らかいスチールブルー）
            'primary': '#4A6FA5',
            'primary_light': '#6B8FBF',
            'primary_dark': '#3A5A8A',

            # セカンダリーカラー（アクセント）
            'secondary': '#E8A838',
            'secondary_light': '#F0C060',
            'secondary_dark': '#D09020',
            'accent': '#4A6FA5',

            # ニュートラルカラー（暖かみのあるグレー系）
            'background': '#F3F1EE',
            'surface': '#FFFFFF',
            'surface_variant': '#F7F5F2',
            'outline': '#D8D4CF',
            'card_border': '#E0DCD7',

            # テキストカラー（暖色系グレー）
            'text_primary': '#2C2C2E',
            'text_secondary': '#6B6966',
            'text_disabled': '#B0ACA7',
            'text_on_primary': '#FFFFFF',

            # ステータスカラー（彩度を抑えた調和的な色合い）
            'success': '#5B9A6B',
            'warning': '#D4943A',
            'error': '#C25450',
            'info': '#5586B0',

            # 特殊要素
            'shadow': '#00000015',
            'hover': '#0000000A',
            'focus': '#4A6FA520',
            'button_hover': '#E8EEF5',
            'drag_drop_bg': '#EEF2F7',
            'drag_drop_border': '#4A6FA5',
            'drag_drop_hover': '#E0E8F2',

            # ログエリア（ダークテーマ）
            'log_bg': '#2C2C2E',
            'log_text': '#E8E4DF',
            'log_timestamp': '#8A9FBA',
            'log_error': '#E87C78',
            'log_success': '#7DBF8E',
            'log_warning': '#E8B86A',
            'log_separator': '#6B6966',

            # 履歴テーブル
            'table_row_alt': '#F7F5F2',
            'table_selected': '#D8E4F0',
        }

        # フォント設定
        self.fonts = self._get_system_fonts()

        # サイズ設定
        self.sizes = {
            'padding_small': 8,
            'padding_medium': 16,
            'padding_large': 24,
            'border_radius': 6,
            'button_height': 36,
            'input_height': 40,
            'header_height': 60,
            'sidebar_width': 300,
        }

        # アニメーション設定
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
                'default': ('Segoe UI', 10),
                'app_title': ('Segoe UI Semibold', 16),
                'heading': ('Segoe UI Semibold', 14),
                'subheading': ('Segoe UI Semibold', 11),
                'body': ('Segoe UI', 10),
                'body_bold': ('Segoe UI Semibold', 10),
                'caption': ('Segoe UI', 9),
                'caption_bold': ('Segoe UI Semibold', 9),
                'button': ('Segoe UI Semibold', 10),
                'button_large': ('Segoe UI Semibold', 13),
                'monospace': ('Consolas', 9),
            }
        elif system == "Darwin":
            return {
                'default': ('SF Pro Display', 10),
                'app_title': ('SF Pro Display', 16, 'bold'),
                'heading': ('SF Pro Display', 14, 'bold'),
                'subheading': ('SF Pro Display', 11, 'bold'),
                'body': ('SF Pro Display', 10),
                'body_bold': ('SF Pro Display', 10, 'bold'),
                'caption': ('SF Pro Display', 9),
                'caption_bold': ('SF Pro Display', 9, 'bold'),
                'button': ('SF Pro Display', 10, 'bold'),
                'button_large': ('SF Pro Display', 13, 'bold'),
                'monospace': ('SF Mono', 9),
            }
        else:
            return {
                'default': ('Ubuntu', 10),
                'app_title': ('Ubuntu', 16, 'bold'),
                'heading': ('Ubuntu', 14, 'bold'),
                'subheading': ('Ubuntu', 11, 'bold'),
                'body': ('Ubuntu', 10),
                'body_bold': ('Ubuntu', 10, 'bold'),
                'caption': ('Ubuntu', 9),
                'caption_bold': ('Ubuntu', 9, 'bold'),
                'button': ('Ubuntu', 10, 'bold'),
                'button_large': ('Ubuntu', 13, 'bold'),
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
                       relief='flat')

        style.map('Primary.TButton',
                 background=[('active', self.colors['primary_light']),
                           ('pressed', self.colors['primary_dark'])])

        style.configure('Large.Primary.TButton',
                       background=self.colors['primary'],
                       foreground=self.colors['text_on_primary'],
                       font=self.fonts['button_large'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat',
                       padding=(24, 14))

        style.map('Large.Primary.TButton',
                 background=[('active', self.colors['primary_light']),
                           ('pressed', self.colors['primary_dark'])])

        style.configure('Secondary.TButton',
                       background=self.colors['surface'],
                       foreground=self.colors['primary'],
                       font=self.fonts['button'],
                       focuscolor='none',
                       borderwidth=1,
                       relief='solid')

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
                       insertcolor=self.colors['primary'])

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
                       rowheight=28)

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
                       troughcolor=self.colors['outline'],
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
                       relief='solid')

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
                       font=self.fonts['body'],
                       padding=[16, 8],
                       borderwidth=0,
                       relief='flat')

        style.map('Modern.TNotebook.Tab',
                 background=[('selected', self.colors['surface']),
                           ('active', self.colors['button_hover'])],
                 foreground=[('selected', self.colors['text_primary']),
                           ('active', self.colors['text_primary'])],
                 padding=[('selected', [16, 8]),
                         ('!selected', [16, 8])])


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

        # 左側アクセントストライプ
        stripe = tk.Frame(header_frame,
                         bg=self.theme.colors['primary'],
                         width=ACCENT_STRIPE_WIDTH)
        stripe.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        stripe.pack_propagate(False)

        # ヘッダーテキスト
        label = tk.Label(header_frame,
                        text=title,
                        font=self.theme.fonts['subheading'],
                        fg=self.theme.colors['text_primary'],
                        bg=bg)
        label.pack(side=tk.LEFT, fill=tk.X)

        return header_frame

    def create_drag_drop_canvas(self, parent, text="ここをクリックして音声/動画ファイルを選択\nまたはファイルをドラッグ&ドロップ", height=110):
        """Canvas使用の破線ボーダー付きドラッグ&ドロップエリアを作成"""
        container = tk.Frame(parent, bg=self.theme.colors['surface'])

        canvas = tk.Canvas(container,
                          bg=self.theme.colors['drag_drop_bg'],
                          highlightthickness=0,
                          height=height,
                          cursor='hand2')
        canvas.pack(fill=tk.X, expand=True)

        def _draw(event=None):
            canvas.delete('all')
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 2 or h < 2:
                return

            pad = 6
            canvas.create_rectangle(
                pad, pad, w - pad, h - pad,
                outline=self.theme.colors['drag_drop_border'],
                dash=(8, 4),
                width=2
            )

            # アイコン
            cy = h // 2 - 14
            canvas.create_text(
                w // 2, cy,
                text='\u2191',
                font=(self.theme.fonts['heading'][0], 20),
                fill=self.theme.colors['primary']
            )

            # テキスト
            canvas.create_text(
                w // 2, cy + 34,
                text=text,
                font=self.theme.fonts['body'],
                fill=self.theme.colors['text_secondary'],
                justify='center'
            )

        canvas.bind('<Configure>', _draw)

        # ホバー効果
        def on_enter(event):
            canvas.configure(bg=self.theme.colors['drag_drop_hover'])
            _draw()

        def on_leave(event):
            canvas.configure(bg=self.theme.colors['drag_drop_bg'])
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
                       padx=28,
                       pady=12,
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
        button = ttk.Button(parent, text=text, style=f'{style}.TButton', **kwargs)
        return button

    def create_icon_button(self, parent, text, icon=None, style='Primary', **kwargs):
        """アイコン付きボタンを作成"""
        button_text = f"{icon} {text}" if icon else text
        button = ttk.Button(parent, text=button_text, style=f'{style}.TButton', **kwargs)
        return button

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
