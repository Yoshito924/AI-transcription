#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
セグメント化された文字起こしテキストを統合するクラス
オーバーラップ部分の重複除去とスムーズな接続を行う
"""

import re
from difflib import SequenceMatcher
from typing import List, Tuple, Optional


class TextMerger:
    """セグメントテキストの統合とスムーズな接続を行うクラス"""
    
    def __init__(self, overlap_threshold: float = 0.6, min_overlap_words: int = 3):
        """
        Args:
            overlap_threshold: 重複判定の閾値（0.0-1.0）
            min_overlap_words: 重複判定に必要な最小単語数
        """
        self.overlap_threshold = overlap_threshold
        self.min_overlap_words = min_overlap_words
    
    def merge_segments(self, segments: List[str]) -> str:
        """
        セグメントリストを統合して一つの連続したテキストにする
        
        Args:
            segments: 文字起こしセグメントのリスト
            
        Returns:
            統合されたテキスト
        """
        if not segments:
            return ""
        
        if len(segments) == 1:
            return self._clean_text(segments[0])
        
        # 最初のセグメントから開始
        merged_text = self._clean_text(segments[0])
        
        # 各セグメントを順次統合
        for i in range(1, len(segments)):
            current_segment = self._clean_text(segments[i])
            merged_text = self._merge_two_segments(merged_text, current_segment)
        
        # 最終的なクリーンアップ
        return self._final_cleanup(merged_text)
    
    def _merge_two_segments(self, text1: str, text2: str) -> str:
        """
        2つのテキストセグメントを統合する
        
        Args:
            text1: 前のセグメントのテキスト
            text2: 次のセグメントのテキスト
            
        Returns:
            統合されたテキスト
        """
        # 両方のテキストを文に分割
        sentences1 = self._split_into_sentences(text1)
        sentences2 = self._split_into_sentences(text2)
        
        if not sentences1 or not sentences2:
            return text1 + "\n" + text2
        
        # オーバーラップ部分を検出
        overlap_start, overlap_end = self._find_overlap(
            sentences1, sentences2
        )
        
        if overlap_start != -1 and overlap_end != -1:
            # オーバーラップが見つかった場合、重複部分を除去して統合
            result_sentences = sentences1[:overlap_start]
            
            # オーバーラップ部分の最良の表現を選択
            overlap_text = self._choose_better_overlap(
                sentences1[overlap_start:],
                sentences2[:overlap_end + 1]
            )
            result_sentences.extend(overlap_text)
            
            # 残りの部分を追加
            result_sentences.extend(sentences2[overlap_end + 1:])
            
            return " ".join(result_sentences)
        else:
            # オーバーラップが見つからない場合、スムーズに接続
            return self._smooth_connection(text1, text2)
    
    def _find_overlap(self, sentences1: List[str], sentences2: List[str]) -> Tuple[int, int]:
        """
        2つの文リスト間のオーバーラップを検出
        
        Returns:
            (overlap_start_in_text1, overlap_end_in_text2) または (-1, -1)
        """
        # 後ろの方から数文を取って、前の方の数文と比較
        max_check = min(5, len(sentences1), len(sentences2))  # 最大5文まで確認
        
        for i in range(1, max_check + 1):
            # text1の後ろi文とtext2の前i文を比較
            tail_sentences = sentences1[-i:]
            head_sentences = sentences2[:i]
            
            similarity = self._calculate_similarity(
                " ".join(tail_sentences),
                " ".join(head_sentences)
            )
            
            if similarity >= self.overlap_threshold:
                return len(sentences1) - i, i - 1
        
        return -1, -1
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        2つのテキストの類似度を計算（0.0-1.0）
        """
        # 単語レベルでの比較
        words1 = self._extract_words(text1)
        words2 = self._extract_words(text2)
        
        if not words1 or not words2:
            return 0.0
        
        # 最小単語数チェック
        if len(words1) < self.min_overlap_words or len(words2) < self.min_overlap_words:
            return 0.0
        
        # SequenceMatcherを使用して類似度を計算
        matcher = SequenceMatcher(None, words1, words2)
        return matcher.ratio()
    
    def _choose_better_overlap(self, overlap1: List[str], overlap2: List[str]) -> List[str]:
        """
        重複部分のより良い表現を選択
        """
        text1 = " ".join(overlap1)
        text2 = " ".join(overlap2)
        
        # より長い方を選択（一般的により完全な情報を含む）
        if len(text2) > len(text1):
            return overlap2
        else:
            return overlap1
    
    def _smooth_connection(self, text1: str, text2: str) -> str:
        """
        オーバーラップがない場合のスムーズな接続
        """
        # 文の境界を検出して適切に接続
        text1 = text1.rstrip()
        text2 = text2.lstrip()
        
        # 文末記号がない場合は追加
        if text1 and not text1.endswith(('.', '。', '!', '！', '?', '？')):
            text1 += "。"
        
        # 適切な区切りで接続
        return text1 + " " + text2
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        テキストを文に分割
        """
        # 日本語の文区切りに対応
        sentence_pattern = r'[。！？.!?]+\s*'
        sentences = re.split(sentence_pattern, text)
        
        # 空の文を除去し、区切り文字を復元
        result = []
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if sentence:
                # 最後の文以外は適切な句読点を復元
                if i < len(sentences) - 1:
                    # 元のテキストから対応する句読点を探す
                    sentence += "。"  # デフォルトで句点を追加
                result.append(sentence)
        
        return result
    
    def _extract_words(self, text: str) -> List[str]:
        """
        テキストから単語を抽出（日本語対応）
        """
        # 句読点と空白で分割し、空文字列を除去
        words = re.findall(r'[^\s\.,。、！？!?]+', text)
        return [word for word in words if word.strip()]
    
    def _clean_text(self, text: str) -> str:
        """
        テキストの基本的なクリーンアップ
        """
        if not text:
            return ""
        
        # 複数の空白を単一に
        text = re.sub(r'\s+', ' ', text)
        
        # 前後の空白を削除
        text = text.strip()
        
        return text
    
    def _final_cleanup(self, text: str) -> str:
        """
        統合後の最終的なテキストクリーンアップ
        """
        # 複数の改行を単一に
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # 連続する句読点を修正
        text = re.sub(r'[。]+', '。', text)
        text = re.sub(r'[、]+', '、', text)
        
        # 前後の空白を削除
        text = text.strip()
        
        return text


class EnhancedTextMerger(TextMerger):
    """より高度な統合機能を持つTextMergerの拡張版"""
    
    def __init__(self, overlap_threshold: float = 0.6, min_overlap_words: int = 3, 
                 enable_context_analysis: bool = True):
        super().__init__(overlap_threshold, min_overlap_words)
        self.enable_context_analysis = enable_context_analysis
    
    def merge_segments_with_context(self, segments: List[str], 
                                   segment_info: Optional[List[dict]] = None) -> str:
        """
        コンテキスト情報を考慮したセグメント統合
        
        Args:
            segments: 文字起こしセグメントのリスト
            segment_info: 各セグメントの追加情報（時間、話者など）
            
        Returns:
            統合されたテキスト
        """
        if not self.enable_context_analysis or not segment_info:
            return self.merge_segments(segments)
        
        # 基本的な統合を実行
        merged_text = self.merge_segments(segments)
        
        # コンテキスト情報を使用した後処理
        if segment_info:
            merged_text = self._apply_context_improvements(merged_text, segment_info)
        
        return merged_text
    
    def _apply_context_improvements(self, text: str, segment_info: List[dict]) -> str:
        """
        コンテキスト情報を使用してテキストを改善
        """
        # 話者情報がある場合は適切な改行を追加
        # 長い無音区間がある場合は段落分けを追加
        # その他のコンテキストベースの改善
        
        # ここでは基本的な実装のみ
        return text
