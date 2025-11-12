#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import hashlib
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from .logger import logger


class AudioCacheManager:
    """音声ファイルの前処理結果をキャッシュして再利用するマネージャー

    キャッシュ構造:
    - cache_dir/
      - metadata.json (キャッシュ一覧とメタデータ)
      - <hash_id>/
        - original_info.json (元ファイル情報)
        - processed.mp3 (変換・圧縮後の音声)
        - segments/ (分割された音声セグメント)
          - segment_000.mp3
          - segment_001.mp3
          - ...
    """

    def __init__(self, cache_dir: Optional[str] = None, max_cache_items: int = 5):
        """
        Args:
            cache_dir: キャッシュディレクトリ（Noneの場合はデフォルト）
            max_cache_items: 最大キャッシュ数（古いものから削除）
        """
        if cache_dir is None:
            # デフォルトは一時ディレクトリ配下
            cache_dir = os.path.join(tempfile.gettempdir(), "ai_transcription_cache")

        self.cache_dir = Path(cache_dir)
        self.max_cache_items = max_cache_items
        self.metadata_file = self.cache_dir / "metadata.json"

        # キャッシュディレクトリを作成
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # メタデータを読み込み
        self._load_metadata()

        logger.info(f"AudioCacheManager初期化: cache_dir={self.cache_dir}, max_items={max_cache_items}")

    def _load_metadata(self):
        """メタデータを読み込み"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"メタデータの読み込みに失敗: {str(e)}")
                self.metadata = {}
        else:
            self.metadata = {}

    def _save_metadata(self):
        """メタデータを保存"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"メタデータの保存に失敗: {str(e)}")

    def _calculate_file_hash(self, file_path: str) -> str:
        """ファイルのハッシュ値を計算（ファイル名+サイズ+更新日時）"""
        stat = os.stat(file_path)
        hash_input = f"{os.path.basename(file_path)}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def get_cache_entry(self, original_file: str) -> Optional[Dict]:
        """キャッシュエントリを取得

        Args:
            original_file: 元の音声ファイルパス

        Returns:
            キャッシュが存在する場合はエントリ情報、なければNone
        """
        file_hash = self._calculate_file_hash(original_file)

        if file_hash in self.metadata:
            entry = self.metadata[file_hash]
            cache_path = self.cache_dir / file_hash

            # キャッシュディレクトリが実際に存在するか確認
            if cache_path.exists():
                logger.info(f"キャッシュヒット: {os.path.basename(original_file)} (hash={file_hash})")
                # アクセス時刻を更新（LRU用）
                entry['last_accessed'] = datetime.now().isoformat()
                self._save_metadata()
                return entry
            else:
                # メタデータはあるがファイルがない場合は削除
                logger.warning(f"キャッシュファイルが見つからないため削除: {file_hash}")
                del self.metadata[file_hash]
                self._save_metadata()

        logger.info(f"キャッシュミス: {os.path.basename(original_file)}")
        return None

    def save_cache_entry(self, original_file: str, processed_audio: str,
                        segments: Optional[List[str]] = None,
                        duration: Optional[float] = None) -> str:
        """キャッシュエントリを保存

        Args:
            original_file: 元の音声ファイルパス
            processed_audio: 変換・圧縮後の音声ファイルパス
            segments: 分割された音声セグメントのパスリスト
            duration: 音声の長さ（秒）

        Returns:
            キャッシュID（ハッシュ値）
        """
        file_hash = self._calculate_file_hash(original_file)
        cache_path = self.cache_dir / file_hash

        try:
            # キャッシュディレクトリを作成
            cache_path.mkdir(parents=True, exist_ok=True)

            # 処理済み音声をコピー
            processed_cache_path = cache_path / "processed.mp3"
            shutil.copy2(processed_audio, processed_cache_path)

            # セグメントをコピー
            segment_paths = []
            if segments:
                segments_dir = cache_path / "segments"
                segments_dir.mkdir(exist_ok=True)

                for i, segment_file in enumerate(segments):
                    segment_cache_path = segments_dir / f"segment_{i:03d}.mp3"
                    shutil.copy2(segment_file, segment_cache_path)
                    segment_paths.append(str(segment_cache_path))

            # メタデータを作成
            entry = {
                'original_file': os.path.basename(original_file),
                'original_size': os.path.getsize(original_file),
                'processed_audio': str(processed_cache_path),
                'segments': segment_paths,
                'segment_count': len(segment_paths) if segment_paths else 0,
                'duration': duration,
                'created': datetime.now().isoformat(),
                'last_accessed': datetime.now().isoformat(),
                'cache_id': file_hash
            }

            # 元ファイル情報を保存
            info_path = cache_path / "original_info.json"
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)

            # メタデータに追加
            self.metadata[file_hash] = entry
            self._save_metadata()

            # キャッシュ数を制限
            self._cleanup_old_cache()

            logger.info(f"キャッシュ保存完了: {os.path.basename(original_file)} (hash={file_hash}, segments={len(segment_paths)})")
            return file_hash

        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {str(e)}", exc_info=True)
            # エラー時はキャッシュディレクトリを削除
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
            raise

    def _cleanup_old_cache(self):
        """古いキャッシュを削除（LRU方式）"""
        if len(self.metadata) <= self.max_cache_items:
            return

        # 最終アクセス時刻でソート
        sorted_entries = sorted(
            self.metadata.items(),
            key=lambda x: x[1].get('last_accessed', ''),
            reverse=False  # 古い順
        )

        # 削除する数を計算
        num_to_delete = len(self.metadata) - self.max_cache_items

        for file_hash, entry in sorted_entries[:num_to_delete]:
            cache_path = self.cache_dir / file_hash
            try:
                if cache_path.exists():
                    shutil.rmtree(cache_path)
                del self.metadata[file_hash]
                logger.info(f"古いキャッシュを削除: {entry.get('original_file', 'unknown')} (hash={file_hash})")
            except Exception as e:
                logger.error(f"キャッシュ削除エラー: {str(e)}")

        self._save_metadata()

    def get_cached_files(self, cache_id: str) -> Tuple[Optional[str], Optional[List[str]]]:
        """キャッシュから処理済みファイルとセグメントを取得

        Args:
            cache_id: キャッシュID

        Returns:
            (処理済み音声パス, セグメントパスリスト) のタプル
        """
        if cache_id not in self.metadata:
            return None, None

        entry = self.metadata[cache_id]
        processed_audio = entry.get('processed_audio')
        segments = entry.get('segments', [])

        # ファイルが実際に存在するか確認
        if processed_audio and os.path.exists(processed_audio):
            # セグメントも確認
            valid_segments = [s for s in segments if os.path.exists(s)]
            return processed_audio, valid_segments if valid_segments else None

        return None, None

    def clear_cache(self):
        """すべてのキャッシュを削除"""
        try:
            if self.cache_dir.exists():
                for item in self.cache_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            self.metadata = {}
            self._save_metadata()
            logger.info("すべてのキャッシュを削除しました")
        except Exception as e:
            logger.error(f"キャッシュクリアエラー: {str(e)}")

    def get_cache_info(self) -> Dict:
        """キャッシュの統計情報を取得"""
        total_size = 0
        for cache_id in self.metadata:
            cache_path = self.cache_dir / cache_id
            if cache_path.exists():
                total_size += sum(f.stat().st_size for f in cache_path.rglob('*') if f.is_file())

        return {
            'cache_count': len(self.metadata),
            'total_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir),
            'max_items': self.max_cache_items,
            'entries': list(self.metadata.values())
        }
