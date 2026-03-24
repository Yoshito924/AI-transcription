#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
処理時間の記録と終了時刻予測システム

モデルごとに「音声1秒あたりの処理時間」を記録し、
過去の実績から処理完了の予測時刻を算出する。
"""

import json
import os
import datetime
from typing import Dict, List, Optional

from .utils import format_duration


class ProcessingTimeTracker:
    """処理時間の記録・予測クラス"""

    # 直近何件を予測に使うか
    MAX_HISTORY_PER_MODEL = 20

    def __init__(self, app_dir: str):
        self.data_dir = os.path.join(app_dir, 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.data_file = os.path.join(self.data_dir, 'processing_times.json')
        self.data = self._load()

    # ── 永続化 ──

    def _load(self) -> Dict:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"処理時間データの保存に失敗しました: {e}")

    # ── モデルキー正規化 ──

    @staticmethod
    def _model_key(engine: str, model: str) -> str:
        """エンジン+モデル名をキーにする (例: 'gemini/gemini-2.5-flash')"""
        return f"{engine}/{model}"

    # ── 記録 ──

    def record(self, engine: str, model: str,
               audio_duration_sec: float, processing_sec: float,
               file_name: str = ""):
        """処理結果を記録する

        Args:
            engine: 'gemini', 'whisper', 'whisper-api'
            model: モデル名 (例: 'gemini-2.5-flash', 'base', 'whisper-1')
            audio_duration_sec: 音声の長さ（秒）
            processing_sec: 実際の処理時間（秒）
            file_name: ファイル名（参考用）
        """
        if audio_duration_sec <= 0 or processing_sec <= 0:
            return

        key = self._model_key(engine, model)
        if key not in self.data:
            self.data[key] = []

        record = {
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'audio_duration_sec': round(audio_duration_sec, 1),
            'processing_sec': round(processing_sec, 1),
            'ratio': round(processing_sec / audio_duration_sec, 4),
            'file_name': file_name
        }

        self.data[key].append(record)

        # 古いレコードを削除
        if len(self.data[key]) > self.MAX_HISTORY_PER_MODEL:
            self.data[key] = self.data[key][-self.MAX_HISTORY_PER_MODEL:]

        self._save()

    # ── 予測 ──

    def estimate(self, engine: str, model: str,
                 audio_duration_sec: float) -> Optional[Dict]:
        """過去の記録から処理時間を予測する

        Returns:
            None: 記録が無い場合
            dict: {
                'estimated_sec': 予測処理秒数,
                'estimated_end': 予測終了時刻 (datetime),
                'confidence': 'high' | 'medium' | 'low',
                'sample_count': 使用したサンプル数,
                'avg_ratio': 平均処理倍率
            }
        """
        if audio_duration_sec <= 0:
            return None

        key = self._model_key(engine, model)
        records = self.data.get(key, [])

        if not records:
            # 同じエンジンの別モデルから推定を試みる
            records = self._fallback_records(engine)
            if not records:
                return None

        # 直近のレコードから平均倍率を計算
        ratios = [r['ratio'] for r in records[-10:]]
        avg_ratio = sum(ratios) / len(ratios)

        estimated_sec = audio_duration_sec * avg_ratio
        estimated_end = datetime.datetime.now() + datetime.timedelta(seconds=estimated_sec)

        # 信頼度: サンプル数で決定
        sample_count = len(ratios)
        if sample_count >= 5:
            confidence = 'high'
        elif sample_count >= 2:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'estimated_sec': round(estimated_sec, 1),
            'estimated_end': estimated_end,
            'confidence': confidence,
            'sample_count': sample_count,
            'avg_ratio': round(avg_ratio, 4)
        }

    def _fallback_records(self, engine: str) -> List[Dict]:
        """同じエンジンの他モデルから記録を集め、新しい順にソートして返す"""
        prefix = f"{engine}/"
        all_records = []
        for key, records in self.data.items():
            if key.startswith(prefix):
                all_records.extend(records[-5:])
        all_records.sort(key=lambda r: r.get('timestamp', ''))
        return all_records[-10:]

    # ── 表示用ヘルパー ──

    @staticmethod
    def format_estimate(estimate: Optional[Dict]) -> str:
        """予測結果を日本語の表示文字列に変換"""
        if not estimate:
            return ""

        sec = estimate['estimated_sec']
        end_time = estimate['estimated_end']
        confidence = estimate['confidence']

        time_str = f"約{format_duration(sec)}"
        end_str = end_time.strftime('%H:%M')

        conf_label = {'high': '', 'medium': '(参考値) ', 'low': '(初回推定) '}
        prefix = conf_label.get(confidence, '')

        return f"{prefix}予想処理時間: {time_str} → 終了予定 {end_str}頃"

    def get_model_stats(self, engine: str, model: str) -> Optional[Dict]:
        """モデルの統計情報を取得"""
        key = self._model_key(engine, model)
        records = self.data.get(key, [])
        if not records:
            return None

        ratios = [r['ratio'] for r in records]
        return {
            'sample_count': len(records),
            'avg_ratio': round(sum(ratios) / len(ratios), 4),
            'min_ratio': round(min(ratios), 4),
            'max_ratio': round(max(ratios), 4),
            'total_audio_sec': round(sum(r['audio_duration_sec'] for r in records), 1),
            'total_processing_sec': round(sum(r['processing_sec'] for r in records), 1),
        }
