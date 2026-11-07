from pathlib import Path
from unittest.mock import patch
import pytest
from src.result_document import ResultDocument


def test_unicode_load_edit_save(tmp_path):
    path = tmp_path / 'result.txt'
    path.write_text('文字起こし\n本文', encoding='utf-8-sig')
    doc = ResultDocument()
    assert doc.load(path) == '文字起こし\n本文'
    doc.save('修正した本文')
    assert path.read_text(encoding='utf-8') == '修正した本文'


def test_external_change_is_preserved(tmp_path):
    path = tmp_path / 'result.txt'
    path.write_text('before', encoding='utf-8')
    doc = ResultDocument()
    doc.load(path)
    path.write_text('external edit', encoding='utf-8')
    with pytest.raises(ValueError):
        doc.save('my edit')
    assert path.read_text(encoding='utf-8') == 'external edit'


def test_failed_replace_preserves_original_and_cleans_temporary(tmp_path):
    path = tmp_path / 'result.txt'
    path.write_text('before', encoding='utf-8')
    doc = ResultDocument()
    doc.load(path)
    with patch('src.result_document.os.replace', side_effect=PermissionError):
        with pytest.raises(PermissionError):
            doc.save('after')
    assert path.read_text(encoding='utf-8') == 'before'
    assert list(tmp_path.iterdir()) == [path]


def test_failed_load_preserves_current_document(tmp_path):
    path = tmp_path / 'result.txt'
    path.write_text('before', encoding='utf-8')
    doc = ResultDocument()
    doc.load(path)
    with pytest.raises(OSError):
        doc.load(tmp_path / 'missing.txt')
    assert doc.path == path and doc.text == 'before'
