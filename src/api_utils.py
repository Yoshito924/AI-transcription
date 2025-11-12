#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .constants import PREFERRED_MODELS, AI_GENERATION_CONFIG
from .exceptions import ApiConnectionError

class ApiUtils:
    """API接続関連のユーティリティクラス"""
    
    def __init__(self):
        self.preferred_models = PREFERRED_MODELS
    
    def test_api_connection(self, api_key):
        """GeminiAPIの接続テスト"""
        try:
            # Google Gemini APIのインポートと接続テスト
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            # 利用可能なモデルを確認
            models = genai.list_models()
            
            # 使用可能なGeminiモデルを探す
            available_gemini_models = []
            for m in models:
                if 'gemini' in m.name.lower() and 'generateContent' in m.supported_generation_methods:
                    available_gemini_models.append(m.name)
            
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
                print(f"警告: 優先モデルが見つからないため、利用可能な最初のモデルを使用: {model_name}")
            else:
                print(f"使用モデル: {model_name} (優先度リストから選択)")
                
            print(f"利用可能なGeminiモデル一覧: {', '.join(available_gemini_models)}")
            
            # 選択したモデルでテスト
            model = genai.GenerativeModel(
                model_name,
                generation_config=AI_GENERATION_CONFIG
            )
            response = model.generate_content("こんにちは")
            
            # 応答がある場合は成功（モデル名を返す）
            if response and hasattr(response, 'text'):
                print(f"API接続テスト成功: {model_name}")
                return model_name
            raise ApiConnectionError("API応答が正常ではありません")
            
        except Exception as e:
            raise ApiConnectionError(f"API接続エラー: {str(e)}")
    
    def _rank_models_by_priority(self, available_models):
        """利用可能なモデルを優先順位でランク付け（音声処理用）

        優先順位:
        1. flash-preview-XX-2025 (最新日付、ProとLiveは除外)
        2. flash / flash-lite 系（軽量・高速）
        3. その他（Proは最後）

        除外: Pro系、Live系、TTS系、Thinking系（音声処理には重すぎる/特殊用途）
        """
        ranked = []

        # Pro系、Live系、TTS系、Thinking系を除外
        # TTS (Text-to-Speech) は音声生成専用で音声入力には非対応
        # Thinking系は推論特化モデルで音声処理には不向き
        filtered_models = [
            m for m in available_models
            if 'pro' not in m.lower()
            and 'live' not in m.lower()
            and '-tts' not in m.lower()
            and 'thinking' not in m.lower()
        ]

        # Flash プレビュー版を日付順でソート（最新が優先）
        flash_preview = [m for m in filtered_models if 'flash' in m.lower() and 'preview' in m.lower()]
        flash_preview.sort(reverse=True)  # 2025-09が2025-08より優先
        ranked.extend(flash_preview)

        # Flash Lite系（最軽量）
        flash_lite = [m for m in filtered_models if 'flash-lite' in m.lower() and m not in ranked]
        flash_lite.sort(reverse=True)  # バージョン順
        ranked.extend(flash_lite)

        # Flash系（プレビュー・Lite以外）
        flash_stable = [
            m for m in filtered_models
            if 'flash' in m.lower() and 'lite' not in m.lower() and 'preview' not in m.lower() and m not in ranked
        ]
        flash_stable.sort(reverse=True)  # バージョン順
        ranked.extend(flash_stable)

        # その他のGeminiモデル（Flash系以外）
        others = [m for m in filtered_models if m not in ranked]
        ranked.extend(others)

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

        # 利用可能なモデルを確認
        models = genai.list_models()

        # 使用可能なGeminiモデルを探す（音声入力対応を確認）
        available_gemini_models = []
        for m in models:
            # generateContentに対応していることを確認
            if 'gemini' not in m.name.lower() or 'generateContent' not in m.supported_generation_methods:
                continue

            # TTS、Live、Thinking系は音声入力に対応していないため除外
            model_name_lower = m.name.lower()
            if '-tts' in model_name_lower or 'live' in model_name_lower or 'thinking' in model_name_lower:
                continue

            available_gemini_models.append(m.name)

        if not available_gemini_models:
            raise ApiConnectionError("利用可能なGeminiモデルが見つかりません")

        print(f"API利用可能モデル ({len(available_gemini_models)}個): {', '.join(available_gemini_models)}")

        model_name = None

        # 手動選択されたモデルを優先
        if preferred_model:
            for available in available_gemini_models:
                if preferred_model in available:
                    model_name = available
                    print(f"✓ 使用モデル: {model_name} (手動選択)")
                    return model_name

            print(f"⚠ 警告: 指定されたモデル '{preferred_model}' が利用できません。自動選択に切り替えます。")

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

            print(f"✓ 使用モデル: {model_name} (自動選択: {model_type})")
            if len(ranked_models) > 1:
                print(f"  次候補: {ranked_models[1]}")
            print(f"  ※ Pro/Live/TTS/Thinking系は音声処理には不向きのため除外されています")
        else:
            # フォールバック（理論上は起こらない）
            model_name = available_gemini_models[0]
            print(f"⚠ 使用モデル: {model_name} (フォールバック)")

        return model_name
