"""テスト共通設定。

Windows の Python 3.13 では Tcl インタプリタを繰り返し生成すると
「Can't find a usable init.tcl」でまれに初期化に失敗する。
アプリ側の不具合ではないため、テスト中の Tk/Tcl 生成だけ数回リトライする。
"""
import time
import tkinter

_original_tk_init = tkinter.Tk.__init__


def _tk_init_with_retry(self, *args, **kwargs):
    last_error = None
    for attempt in range(5):
        try:
            return _original_tk_init(self, *args, **kwargs)
        except tkinter.TclError as exc:
            if 'init.tcl' not in str(exc):
                raise
            last_error = exc
            time.sleep(0.05 * (attempt + 1))
    raise last_error


tkinter.Tk.__init__ = _tk_init_with_retry
