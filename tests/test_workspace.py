import tkinter as tk
from unittest.mock import Mock, patch
import pytest
from src.ui_workspace import ResultEditor
from src.ui_styles import ModernTheme
from src.controllers import TranscriptionController


@pytest.fixture(scope='module')
def root():
    window = tk.Tk()
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def editor(root):
    widget = ResultEditor(root, ModernTheme())
    yield widget
    widget.destroy()


def test_automatic_result_does_not_replace_unsaved_edit(editor, tmp_path):
    first, second = tmp_path / 'a.txt', tmp_path / 'b.txt'
    first.write_text('first', encoding='utf-8')
    second.write_text('second', encoding='utf-8')
    assert editor.load(first)
    editor.text.insert('end', ' edited')
    assert editor.dirty
    assert not editor.load(second, automatic=True)
    assert editor.document.path == first
    assert editor.text.get('1.0','end-1c') == 'first edited'


def test_cancel_navigation_preserves_unsaved_edit(editor, tmp_path):
    path = tmp_path / 'a.txt'
    path.write_text('first', encoding='utf-8')
    editor.load(path)
    editor.text.insert('end',' edited')
    with patch('src.ui_workspace.messagebox.askyesnocancel', return_value=None):
        assert not editor.load(tmp_path / 'other.txt')
    assert editor.dirty


def test_save_resolves_dirty_state(editor, tmp_path):
    path = tmp_path / 'a.txt'
    path.write_text('first', encoding='utf-8')
    editor.load(path)
    editor.text.insert('end',' edited')
    assert editor.save()
    assert not editor.dirty
    assert path.read_text(encoding='utf-8') == 'first edited'


def test_cannot_restart_during_queue_preparation():
    controller = TranscriptionController(Mock(), Mock(), Mock(), {})
    controller.queue_processing = True
    controller.is_processing = False
    controller.start_transcription = Mock()
    with patch('src.controllers.messagebox.showinfo'):
        controller.start_queue_processing()
    controller.start_transcription.assert_not_called()


def test_completed_job_keeps_result_location():
    controller = TranscriptionController(Mock(), Mock(), Mock(), {})
    controller.update_queue_callback = Mock()
    controller._set_job_state('audio.mp4','処理中')
    controller._set_job_state('audio.mp4','完了','result.txt')
    assert controller.session_jobs['audio.mp4'] == {'state':'完了','output':'result.txt'}
    assert controller.update_queue_callback.call_count == 2
