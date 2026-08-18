#!/usr/bin/env python
# -*- coding: utf-8 -*-

from src.audio_recorder import build_sample_rate_candidates, match_saved_input_device
from src.constants import RECORDING_SAMPLE_RATE_AUTO


def _device(index, name, hostapi='Windows WASAPI', default=False):
    return {
        'index': index,
        'name': name,
        'hostapi_name': hostapi,
        'max_input_channels': 2,
        'default_samplerate': 48000,
        'is_default': default,
    }


def test_match_saved_device_prefers_name_when_index_changes():
    devices = [
        _device(1, 'Headphones', default=True),
        _device(7, 'Steinberg UR22C'),
    ]

    matched = match_saved_input_device(
        devices,
        saved_id=3,
        saved_name='Steinberg UR22C',
        saved_hostapi='Windows WASAPI',
    )

    assert matched['index'] == 7
    assert matched['name'] == 'Steinberg UR22C'


def test_match_saved_device_uses_hostapi_to_disambiguate():
    devices = [
        _device(2, 'UR22C', hostapi='MME'),
        _device(8, 'UR22C', hostapi='Windows WASAPI'),
    ]

    matched = match_saved_input_device(
        devices,
        saved_id=2,
        saved_name='UR22C',
        saved_hostapi='Windows WASAPI',
    )

    assert matched['index'] == 8
    assert matched['hostapi_name'] == 'Windows WASAPI'


def test_match_saved_device_falls_back_to_index():
    devices = [_device(4, 'USB Mic')]
    matched = match_saved_input_device(devices, saved_id=4, saved_name='Old Name')
    assert matched['index'] == 4


def test_sample_rate_candidates_prefer_interface_clock_over_16k():
    candidates = build_sample_rate_candidates(reported_rate=16000)
    assert candidates[0] == 48000
    assert 44100 in candidates
    assert 16000 in candidates


def test_sample_rate_candidates_keep_trusted_reported_rate_first_after_preferred():
    candidates = build_sample_rate_candidates(reported_rate=48000, preferred_rate=RECORDING_SAMPLE_RATE_AUTO)
    assert candidates[0] == 48000


def test_sample_rate_candidates_put_explicit_preference_first():
    candidates = build_sample_rate_candidates(reported_rate=48000, preferred_rate=44100)
    assert candidates[0] == 44100
    assert candidates[1] == 48000
