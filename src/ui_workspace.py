"""文字起こしの作業画面。推論処理とは独立して表示と結果編集を扱う。"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from .result_document import ResultDocument
from .waveform_viewer import WaveformViewer
from .engines import get_engine_spec


class ResultEditor(tk.Frame):
    def __init__(self, parent, theme):
        super().__init__(parent, bg=theme.colors['surface'])
        from .ui import _bind_dynamic_wraplength
        self.document = ResultDocument()
        self.title = tk.Label(self, text='完了した結果がここに表示されます', wraplength=500, anchor='w', bg=theme.colors['surface'], font=theme.fonts['body_bold'])
        self.title.pack(fill='x', padx=12, pady=12)
        _bind_dynamic_wraplength(self.title)
        toolbar = tk.Frame(self, bg=theme.colors['surface'])
        toolbar.pack(side='bottom', fill='x', padx=12, pady=12)
        self.save_button = ttk.Button(toolbar, style='Secondary.TButton', text='修正を保存', command=self.save, state='disabled')
        self.save_button.pack(side='right')
        ttk.Button(toolbar, style='Secondary.TButton', text='全文コピー', command=self.copy).pack(side='right', padx=8)
        self.status = tk.Label(toolbar, text='履歴から過去の結果も開けます', bg=theme.colors['surface'], font=theme.fonts['caption'])
        self.status.pack(side='left')
        self.text = scrolledtext.ScrolledText(self, wrap='word', undo=True, font=('Yu Gothic UI', 11),
                                             bg=theme.colors['surface'], fg=theme.colors['text_primary'],
                                             insertbackground=theme.colors['text_primary'], relief='flat', padx=12, pady=12)
        self.text.pack(fill='both', expand=True, padx=12)
        self.text.config(state='disabled')
        self.text.bind('<<Modified>>', self._modified)
        self.text.bind('<Control-s>', lambda e: (self.save(), 'break')[1])

    def _modified(self, _event=None):
        if self.text.edit_modified():
            self.status.config(text='未保存の修正があります' if self.dirty else '保存済み')
            self.text.edit_modified(False)

    @property
    def dirty(self):
        return self.document.path is not None and self.text.get('1.0', 'end-1c') != self.document.text

    def confirm_discard(self):
        if not self.dirty:
            return True
        choice = messagebox.askyesnocancel('未保存の修正', '修正を保存して続けますか？', parent=self)
        return self.save() if choice else choice is False

    def load(self, path, automatic=False):
        # 自動完了通知では編集中の文書を上書きしない。
        if self.dirty and automatic:
            self.status.config(text='新しい結果は履歴から開けます')
            return False
        if not self.confirm_discard():
            return False
        try:
            text = self.document.load(path)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror('結果を開けません', str(exc), parent=self)
            return False
        self.text.config(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.title.config(text=self.document.path.name)
        self.save_button.config(state='normal')
        self.status.config(text='保存済み')
        return True

    def save(self):
        try:
            self.document.save(self.text.get('1.0', 'end-1c'))
        except (OSError, ValueError) as exc:
            messagebox.showerror('保存できません', str(exc), parent=self)
            return False
        self.status.config(text='保存しました')
        return True

    def copy(self):
        if self.document.path is not None:
            self.clipboard_clear()
            self.clipboard_append(self.text.get('1.0', 'end-1c'))
            self.status.config(text='全文をコピーしました')


def create_workspace(parent, app, theme, widgets, settings, open_settings):
    from .ui import setup_drag_drop, _create_scrollable_frame, _bind_dynamic_wraplength
    frame = tk.Frame(parent, bg=theme.colors['surface'])
    footer = tk.Frame(frame, bg=theme.colors['surface_variant'], padx=14, pady=10)
    footer.pack(side='bottom', fill='x')
    actions = tk.Frame(footer, bg=theme.colors['surface_variant'])
    actions.pack(side='right', padx=(12, 0))
    frame.start_button = widgets.create_action_button(actions, '文字起こしを開始', command=lambda: app.start_process('transcription'))
    frame.start_button.pack()
    progress_area = tk.Frame(footer, bg=theme.colors['surface_variant'])
    progress_area.pack(side='left', fill='x', expand=True)
    frame.status_label = tk.Label(progress_area, text='音声・動画を追加してください', anchor='w', bg=theme.colors['surface_variant'], font=theme.fonts['body'])
    frame.status_label.pack(fill='x')
    _bind_dynamic_wraplength(frame.status_label)
    frame.progress_label = tk.Label(progress_area, text='', bg=theme.colors['surface_variant'])
    frame.progress_label.pack(side='right')
    frame.progress = ttk.Progressbar(progress_area, maximum=100, style='Modern.Horizontal.TProgressbar')
    frame.progress.pack(fill='x', expand=True, pady=(6, 0))
    frame.status_dot = tk.Label(progress_area)  # 既存コントローラーとの互換

    split = tk.PanedWindow(frame, orient='horizontal', sashwidth=8, bg=theme.colors['divider'], bd=0)
    split.pack(fill='both', expand=True)
    left = tk.Frame(split, bg=theme.colors['surface_variant'], padx=12, pady=12)
    right = tk.Frame(split, bg=theme.colors['surface'], padx=12, pady=12)
    split.add(left, minsize=280, width=320, stretch='never')
    split.add(right, minsize=420, stretch='always')
    tk.Label(left, text='今回のファイル', bg=theme.colors['surface_variant'], font=theme.fonts['heading']).pack(anchor='w', pady=(0, 10))
    ttk.Button(left, style='Secondary.TButton', text='＋ 音声・動画を追加', command=app.browse_file).pack(fill='x', pady=(0, 8))
    frame.drop_area = tk.Label(left, text='⤓\nここにドラッグ＆ドロップ\n複数ファイルをまとめて追加できます',
                               bg=theme.colors['drag_drop_bg'], fg=theme.colors['primary'], font=theme.fonts['caption'],
                               padx=10, pady=18, cursor='hand2', justify='center',
                               highlightthickness=1, highlightbackground=theme.colors['outline'])
    frame.drop_area.pack(fill='x', pady=(0, 12))
    frame.drop_area.bind('<Button-1>', app.browse_file)
    frame.drop_area.bind('<Enter>', lambda e: frame.drop_area.config(bg=theme.colors['drag_drop_hover'], highlightbackground=theme.colors['drag_drop_border']))
    frame.drop_area.bind('<Leave>', lambda e: frame.drop_area.config(bg=theme.colors['drag_drop_bg'], highlightbackground=theme.colors['outline']))
    setup_drag_drop(frame.drop_area, frame.drop_area, app)
    frame.queue_frame = tk.Frame(left, bg=theme.colors['surface_variant'])
    frame.queue_frame.pack(fill='both', expand=True)
    frame.queue_count_label = tk.Label(frame.queue_frame, text='現在のキュー: 0件', wraplength=280, bg=theme.colors['surface_variant'], font=theme.fonts['caption'])
    frame.queue_count_label.pack(anchor='w', pady=(0, 8))
    queue_actions = tk.Frame(frame.queue_frame, bg=theme.colors['surface_variant'])
    queue_actions.pack(side='bottom', fill='x', pady=(8, 0))
    ttk.Button(queue_actions, style='Secondary.TButton', text='一覧から外す', command=app.remove_from_queue).pack(side='left')
    ttk.Button(queue_actions, style='Secondary.TButton', text='待機分をクリア', command=app.clear_queue).pack(side='right')
    frame.queue_tree = ttk.Treeview(frame.queue_frame, columns=('order','name','location','state'), displaycolumns=('name','state'), show='headings', height=7, selectmode='extended', style='Modern.Treeview')
    frame.queue_tree.heading('name', text='ファイル')
    frame.queue_tree.heading('state', text='状態')
    frame.queue_tree.column('name', width=160, minwidth=100)
    frame.queue_tree.column('state', width=110, minwidth=90)
    frame.queue_tree.tag_configure('queue_missing', foreground=theme.colors['error'])
    scrollbar = ttk.Scrollbar(frame.queue_frame, command=frame.queue_tree.yview)
    scrollbar.pack(side='right', fill='y')
    frame.queue_tree.config(yscrollcommand=scrollbar.set)
    frame.queue_tree.pack(fill='both', expand=True)
    frame.queue_tree.bind('<Delete>', lambda e: app.remove_from_queue())

    summary = tk.Label(right, text='', anchor='w', wraplength=600, bg=theme.colors['surface'], font=theme.fonts['body'])
    summary.pack(fill='x', pady=(0, 8))
    def refresh_summary():
        summary.config(text=f'{get_engine_spec(settings.engine_var.get()).label} · {settings.summary_model_text()}  |  保存先: {settings.summary_save_text()}')
    settings.notify_summary.append(refresh_summary)
    refresh_summary()
    tabs = ttk.Notebook(right, style='Modern.TNotebook')
    tabs.pack(fill='both', expand=True)
    audio_tab = tk.Frame(tabs, bg=theme.colors['surface'])
    result = ResultEditor(tabs, theme)
    tabs.add(audio_tab, text='音声を確認')
    tabs.add(result, text='結果を確認・修正')
    outer, inner = _create_scrollable_frame(audio_tab, theme.colors['surface'])
    outer.pack(fill='both', expand=True)
    frame.file_label = tk.Label(inner, text='左の一覧から音声を選択', anchor='w', bg=theme.colors['surface'], font=theme.fonts['body_bold'])
    frame.file_label.pack(fill='x', padx=12, pady=16)
    _bind_dynamic_wraplength(frame.file_label)
    guide = tk.Frame(inner, bg=theme.colors['surface_variant'], padx=16, pady=14,
                     highlightthickness=1, highlightbackground=theme.colors['divider'])
    tk.Label(guide, text='はじめかた', bg=theme.colors['surface_variant'], fg=theme.colors['primary'],
             font=theme.fonts['subheading']).pack(anchor='w', pady=(0, 6))
    for step in ('1.  左の「＋ 音声・動画を追加」かドラッグ＆ドロップでファイルを入れる',
                 '2.  一覧で選ぶと、ここに波形が表示され再生して確認できる',
                 '3.  右下の「文字起こしを開始」を押す。結果は「結果を確認・修正」タブで編集できる'):
        tk.Label(guide, text=step, anchor='w', justify='left', bg=theme.colors['surface_variant'],
                 fg=theme.colors['text_secondary'], font=theme.fonts['body']).pack(fill='x', pady=2)
    guide.pack(fill='x', padx=12, pady=(0, 8))
    frame.empty_guide = guide

    # コントローラーは file_label.config(text=...) で選択状態を伝えるので、それに連動してガイドを出し入れする
    label_config = frame.file_label.config

    def config_with_guide(cnf=None, **kwargs):
        result = label_config(cnf, **kwargs)
        text = kwargs.get('text') if 'text' in kwargs else (cnf or {}).get('text')
        if text is not None:
            has_file = text.startswith(('選択ファイル:', '処理中')) and not text.endswith('なし')
            if has_file and guide.winfo_manager():
                guide.pack_forget()
            elif not has_file and not guide.winfo_manager():
                guide.pack(fill='x', padx=12, pady=(0, 8), after=frame.file_label)
        return result
    frame.file_label.config = frame.file_label.configure = config_with_guide
    frame.waveform_viewer = WaveformViewer(inner, theme)
    frame.waveform_viewer.set_callbacks(play_toggle_callback=app.toggle_waveform_playback,
        stop_callback=lambda: app.stop_waveform_playback(reset_position=True, silent=True), seek_callback=app.seek_waveform_playback)
    ttk.Button(inner, style='Secondary.TButton', text='モデル・無音カット・保存先を変更', command=open_settings).pack(anchor='w', padx=12, pady=12)

    def preview(_event=None):
        if not app.controller:
            return
        selection = frame.queue_tree.selection()
        if len(selection) != 1:
            return
        item_id = selection[0]
        index = int(item_id.split(':')[-1])
        if item_id.startswith('job:'):
            jobs = getattr(app, '_workspace_jobs', [])
            if index < len(jobs) and jobs[index][1].get('output'):
                if result.load(jobs[index][1]['output']):
                    tabs.select(result)
            return
        if app.controller.is_processing or app.controller.queue_processing:
            return
        if index < len(app.controller.file_queue):
            path = app.controller.file_queue[index]
            if path != app.controller.current_file:
                app.load_file(path)
            tabs.select(audio_tab)
    frame.queue_tree.bind('<<TreeviewSelect>>', preview)
    frame.result_editor = result
    frame.detail_tabs = tabs
    return frame
