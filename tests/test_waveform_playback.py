from types import SimpleNamespace
from unittest.mock import MagicMock

from src.waveform_viewer import WaveformViewer


def make_viewer():
    return SimpleNamespace(
        _duration=100.0, _scroll_offset=0, _samples=[0.1],
        _update_control_state=MagicMock(), _update_db_meter=MagicMock(),
        _update_info_label=MagicMock(), _redraw=MagicMock(),
        _refresh_playhead=MagicMock(), _ensure_time_visible=MagicMock(),
    )


def test_playback_preserves_background_when_view_does_not_scroll():
    viewer = make_viewer()
    WaveformViewer.set_playback_state(viewer, 5, True)
    viewer._redraw.assert_not_called()
    viewer._refresh_playhead.assert_called_once()
    assert viewer._playhead_sec == 5


def test_playback_redraws_background_after_auto_scroll():
    viewer = make_viewer()
    viewer._ensure_time_visible.side_effect = lambda _: setattr(viewer, '_scroll_offset', 50)
    WaveformViewer.set_playback_state(viewer, 80, True)
    viewer._redraw.assert_called_once()
    viewer._refresh_playhead.assert_not_called()
