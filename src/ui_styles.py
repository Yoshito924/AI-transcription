#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
モダンなUIスタイリング設定
カラーパレット、フォント、スタイル定義
"""

import tkinter as tk
from tkinter import ttk
import platform


class ModernTheme:
    """モダンなUIテーマの設定クラス"""
    
    def __init__(self):
        # カラーパレット（Material Design inspired）
        self.colors = {
            # プライマリーカラー（深いブルー）
            'primary': '#1976D2',
            'primary_light': '#42A5F5',
            'primary_dark': '#0D47A1',
            
            # セカンダリーカラー（アクセント）
            'secondary': '#FFC107',
            'secondary_light': '#FFD54F',
            'secondary_dark': '#FF8F00',
            'accent': '#1976D2',  # プライマリーカラーをアクセントとして使用
            
            # ニュートラルカラー
            'background': '#FAFAFA',
            'surface': '#FFFFFF',
            'surface_variant': '#F5F5F5',
            'outline': '#E0E0E0',
            
            # テキストカラー
            'text_primary': '#212121',
            'text_secondary': '#757575',
            'text_disabled': '#BDBDBD',
            'text_on_primary': '#FFFFFF',
            
            # ステータスカラー
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#F44336',
            'info': '#2196F3',
            
            # 特殊要素
            'shadow': '#00000020',
            'hover': '#0000000A',
            'focus': '#1976D220',
            'button_hover': '#E3F2FD',
            'drag_drop_bg': '#E3F2FD',
            'drag_drop_border': '#1976D2',
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
            'transition_duration': 200,  # ms
            'fade_duration': 150,
            'slide_duration': 250,
        }
    
    def _get_system_fonts(self):
        """システムに最適なフォントを選択"""
        system = platform.system()
        
        if system == "Windows":
            return {
                'default': ('Segoe UI', 10),
                'heading': ('Segoe UI', 14, 'bold'),
                'subheading': ('Segoe UI', 12, 'bold'),
                'body': ('Segoe UI', 10),
                'body_bold': ('Segoe UI', 10, 'bold'),
                'caption': ('Segoe UI', 9),
                'button': ('Segoe UI', 10, 'bold'),
                'monospace': ('Consolas', 9),
            }
        elif system == "Darwin":  # macOS
            return {
                'default': ('SF Pro Display', 10),
                'heading': ('SF Pro Display', 14, 'bold'),
                'subheading': ('SF Pro Display', 12, 'bold'),
                'body': ('SF Pro Display', 10),
                'body_bold': ('SF Pro Display', 10, 'bold'),
                'caption': ('SF Pro Display', 9),
                'button': ('SF Pro Display', 10, 'bold'),
                'monospace': ('SF Mono', 9),
            }
        else:  # Linux
            return {
                'default': ('Ubuntu', 10),
                'heading': ('Ubuntu', 14, 'bold'),
                'subheading': ('Ubuntu', 12, 'bold'),
                'body': ('Ubuntu', 10),
                'body_bold': ('Ubuntu', 10, 'bold'),
                'caption': ('Ubuntu', 9),
                'button': ('Ubuntu', 10, 'bold'),
                'monospace': ('Ubuntu Mono', 9),
            }
    
    def apply_theme(self, root):
        """ルートウィンドウにテーマを適用"""
        # ウィンドウの基本設定
        root.configure(bg=self.colors['background'])
        
        # ttk スタイルの設定
        style = ttk.Style()
        
        # テーマの基本設定
        style.theme_use('clam')  # ベーステーマ
        
        # カスタムスタイルの定義
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
        # メインフレーム
        style.configure('Main.TFrame',
                       background=self.colors['background'],
                       relief='flat')
        
        # カードスタイルフレーム
        style.configure('Card.TFrame',
                       background=self.colors['surface'],
                       relief='flat',
                       borderwidth=1)
        
        # サイドバーフレーム
        style.configure('Sidebar.TFrame',
                       background=self.colors['surface_variant'],
                       relief='flat')
    
    def _configure_button_styles(self, style):
        """ボタンスタイルの設定"""
        # プライマリボタン
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
        
        # 大きなプライマリボタン
        style.configure('Large.Primary.TButton',
                       background=self.colors['primary'],
                       foreground=self.colors['text_on_primary'],
                       font=(self.fonts['button'][0], 12, 'bold'),
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat',
                       padding=(20, 12))
        
        style.map('Large.Primary.TButton',
                 background=[('active', self.colors['primary_light']),
                           ('pressed', self.colors['primary_dark'])])
        
        # セカンダリボタン
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
        
        # 成功ボタン
        style.configure('Success.TButton',
                       background=self.colors['success'],
                       foreground=self.colors['text_on_primary'],
                       font=self.fonts['button'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat')
        
        # 警告ボタン
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
        # 見出し
        style.configure('Heading.TLabel',
                       font=self.fonts['heading'],
                       foreground=self.colors['text_primary'],
                       background=self.colors['background'])
        
        # サブ見出し
        style.configure('Subheading.TLabel',
                       font=self.fonts['subheading'],
                       foreground=self.colors['text_primary'],
                       background=self.colors['background'])
        
        # 本文
        style.configure('Body.TLabel',
                       font=self.fonts['body'],
                       foreground=self.colors['text_primary'],
                       background=self.colors['background'])
        
        # キャプション
        style.configure('Caption.TLabel',
                       font=self.fonts['caption'],
                       foreground=self.colors['text_secondary'],
                       background=self.colors['background'])
        
        # ステータスラベル
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
                       relief='solid')
        
        style.configure('Modern.Treeview.Heading',
                       background=self.colors['surface_variant'],
                       foreground=self.colors['text_primary'],
                       font=self.fonts['subheading'],
                       relief='flat',
                       borderwidth=1)
        
        style.map('Modern.Treeview',
                 background=[('selected', self.colors['primary']),
                           ('active', self.colors['hover'])],
                 foreground=[('selected', self.colors['text_on_primary'])])
    
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
        """カードスタイルのフレームを作成"""
        frame = tk.Frame(parent,
                        bg=self.theme.colors['surface'],
                        relief='flat',
                        bd=0,
                        **kwargs)
        return frame
    
    def create_drag_drop_area(self, parent, text="ファイルをドラッグ&ドロップ", **kwargs):
        """ドラッグ&ドロップエリアを作成"""
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
        
        # ホバー効果
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
        
        # ステータスドット
        dot = tk.Label(frame,
                      text="●",
                      fg=self.theme.colors['text_disabled'],
                      bg=self.theme.colors['surface'],
                      font=(self.theme.fonts['default'][0], 8))
        dot.pack(side='left', padx=(0, 5))
        
        # ステータステキスト
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


# アイコン定義（Unicode文字を使用）
ICONS = {
    'microphone': '🎤',
    'file': '📁',
    'upload': '📤',
    'download': '📥',
    'play': '▶️',
    'pause': '⏸️',
    'stop': '⏹️',
    'settings': '⚙️',
    'refresh': '🔄',
    'check': '✅',
    'error': '❌',
    'warning': '⚠️',
    'info': 'ℹ️',
    'edit': '✏️',
    'delete': '🗑️',
    'save': '💾',
    'search': '🔍',
    'menu': '☰',
    'close': '✖️',
    'minimize': '➖',
    'maximize': '🔲',
    'folder': '📂',
    'document': '📄',
    'copy': '📋',
    'cut': '✂️',
    'paste': '📌',
    'undo': '↶',
    'redo': '↷',
    'export': '💼',
    'key': '🔑',
    'clock': '🕐',
    'text': '📝',
    'open': '📂',
    'import': '📥',
    'audio': '🔊',
    'video': '🎬',
    'text': '📝',
    'clock': '⏰',
    'calendar': '📅',
    'user': '👤',
    'users': '👥',
    'star': '⭐',
    'heart': '❤️',
    'thumb_up': '👍',
    'thumb_down': '👎',
    'question': '❓',
    'exclamation': '❗',
    'plus': '➕',
    'minus': '➖',
    'multiply': '✖️',
    'divide': '➗',
    'arrow_up': '⬆️',
    'arrow_down': '⬇️',
    'arrow_left': '⬅️',
    'arrow_right': '➡️',
}
