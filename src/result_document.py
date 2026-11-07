"""画面から独立した結果テキストの読み込み・競合検出・保存。"""
import os
from pathlib import Path
import tempfile


class ResultDocument:
    def __init__(self):
        self.path = None
        self.text = ''
        self.original_bytes = None
        self.newline = '\n'

    def load(self, path):
        path = Path(path)
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError('5MBを超える結果は外部エディターで開いてください。')
        data = path.read_bytes()
        text = data.decode('utf-8-sig')
        self.newline = '\r\n' if '\r\n' in text else '\n'
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        self.path, self.text, self.original_bytes = path, text, data
        return text

    def save(self, text):
        if self.path is None:
            raise ValueError('保存する結果を選択してください。')
        if self.path.read_bytes() != self.original_bytes:
            raise ValueError('ファイルが外部で更新されています。修正をコピーしてから結果を開き直してください。')
        data = text.replace('\n', self.newline).encode('utf-8')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as handle:
                temporary = handle.name
                handle.write(data)
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        self.text, self.original_bytes = text, data
