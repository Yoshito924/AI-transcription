#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time

from .constants import PREFERRED_MODELS, AI_GENERATION_CONFIG
from .exceptions import ApiConnectionError
from .logger import logger

# モデルリストキャッシュのTTL（秒）
_MODEL_LIST_CACHE_TTL = 300  # 5分

class ApiUtils:
    """API接続関連のユーティリティクラス"""

    def __init__(self):
        self.preferred_models = PREFERRED_MODELS
        self._model_list_cache = None
        self._model_list_cache_time = 0
        self._model_list_cache_key = None  # APIキーごとにキャッシュを分離

    def _get_available_models(self, api_key):
        """利用可能なGeminiモデルのリストを取得（キャッシュ付き）"""
        import google.generativeai as genai

        now = time.time()
        if (self._model_list_cache is not None
                and self._model_list_cache_key == api_key
                and now - self._model_list_cache_time < _MODEL_LIST_CACHE_TTL):
            return self._model_list_cache

        genai.configure(api_key=api_key)
        models = genai.list_models()
        available = [
            m.name for m in models
            if 'gemini' in m.name.lower() and 'generateContent' in m.supported_generation_methods
        ]

        self._model_list_cache = available
        self._model_list_cache_time = now
        self._model_list_cache_key = api_key
        logger.info(f"モデルリスト取得・キャッシュ更新 ({len(available)}個)")
        return available
    
    def test_api_connection(self, api_key):
        """GeminiAPIの接続テスト"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            # キャッシュをクリアして最新のリストを取得（接続テストなので）
            self._model_list_cache = None
            available_gemini_models = self._get_available_models(api_key)

            if not available_gemini_models:
                raise ApiConnectionError("利用可能なGeminiモデルが見つかりません")
            
            # 優先度順に使用可能なモデルを選択
            model_name = None
            for preferred in self.preferred_models:
                for available in available_gemini_models:
                    if preferred in available:
                        model_name = available
                        break
                if model_name:
                    break
            
            # 見つからなければ最初のモデルを使用
            if not model_name:
                model_name = available_gemini_models[0]
                logger.warning(f"優先モデルが見つからないため、利用可能な最初のモデルを使用: {model_name}")
            else:
                logger.info(f"使用モデル: {model_name} (優先度リストから選択)")

            logger.info(f"利用可能なGeminiモデル一覧: {', '.join(available_gemini_models)}")
            
            # 選択したモデルでテスト
            model = genai.GenerativeModel(
                model_name,
                generation_config=AI_GENERATION_CONFIG
            )
            response = model.generate_content("こんにちは")
            
            # 応答がある場合は成功（モデル名を返す）
            if response and hasattr(response, 'text'):
                logger.info(f"API接続テスト成功: {model_name}")
                return model_name
            raise ApiConnectionError("API応答が正常ではありません")
            
        except Exception as e:
            raise ApiConnectionError(f"API接続エラー: {str(e)}")
    
    def _rank_models_by_priority(self, available_models):
        """利用可能なモデルを優先順位でランク付け（音声処理用）

        優先順位:
        1. flash-preview-XX-2025 (最新日付、ProとLiveは除外)
        2. flash-lite 系（最軽量）
        3. flash 系安定版（プレビュー・Lite以外）
        4. その他（Proは最後）

        除外: Pro系、Live系、TTS系、Thinking系（音声処理には重すぎる/特殊用途）
        """
        # Pro系、Live系、TTS系、Thinking系を除外
        exclude_keywords = ['pro', 'live', '-tts', 'thinking']
        filtered_models = [
            m for m in available_models
            if not any(kw in m.lower() for kw in exclude_keywords)
        ]

        # 優先度グループを定義: (フィルタ関数, 説明)
        priority_groups = [
            lambda m, ranked: 'flash' in m.lower() and 'preview' in m.lower(),
            lambda m, ranked: 'flash-lite' in m.lower() and m not in ranked,
            lambda m, ranked: 'flash' in m.lower() and 'lite' not in m.lower() and 'preview' not in m.lower() and m not in ranked,
        ]

        ranked = []
        for group_filter in priority_groups:
            matches = [m for m in filtered_models if group_filter(m, ranked)]
            matches.sort(reverse=True)
            ranked.extend(matches)

        # その他のGeminiモデル（上記に含まれないもの）
        ranked.extend(m for m in filtered_models if m not in ranked)

        return ranked

    def get_best_available_model(self, api_key, preferred_model=None):
        """利用可能な最適なGeminiモデルを自動選択

        優先順位:
        1. 手動選択されたモデル（preferred_model）
        2. 最新のプレビュー版
        3. 安定版の最新バージョン
        """
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # キャッシュ付きモデルリスト取得
        all_models = self._get_available_models(api_key)

        # 音声処理に不向きなモデルを除外
        available_gemini_models = [
            m for m in all_models
            if not any(kw in m.lower() for kw in ['-tts', 'live', 'thinking'])
        ]

        if not available_gemini_models:
            raise ApiConnectionError("利用可能なGeminiモデルが見つかりません")

        logger.info(f"API利用可能モデル ({len(available_gemini_models)}個): {', '.join(available_gemini_models)}")

        model_name = None

        # 手動選択されたモデルを優先
        if preferred_model:
            for available in available_gemini_models:
                if preferred_model in available:
                    model_name = available
                    logger.info(f"✓ 使用モデル: {model_name} (手動選択)")
                    return model_name

            logger.warning(f"指定されたモデル '{preferred_model}' が利用できません。自動選択に切り替えます。")

        # 自動選択：スマートランキングで最適なモデルを選択
        ranked_models = self._rank_models_by_priority(available_gemini_models)

        if ranked_models:
            model_name = ranked_models[0]
            # モデルの特徴を判定
            if 'lite' in model_name.lower():
                model_type = "最軽量・高速"
            elif 'preview' in model_name.lower():
                model_type = "最新プレビュー版"
            elif 'flash' in model_name.lower():
                model_type = "Flash系・音声最適化"
            else:
                model_type = "音声処理用"

            logger.info(f"✓ 使用モデル: {model_name} (自動選択: {model_type})")
            if len(ranked_models) > 1:
                logger.info(f"  次候補: {ranked_models[1]}")
            logger.info(f"  ※ Pro/Live/TTS/Thinking系は音声処理には不向きのため除外されています")
        else:
            # フォールバック（理論上は起こらない）
            model_name = available_gemini_models[0]
            logger.warning(f"使用モデル: {model_name} (フォールバック)")

        return model_name
