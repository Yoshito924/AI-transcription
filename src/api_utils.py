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
    
    def get_best_available_model(self, api_key, preferred_model=None):
        """利用可能な最適なGeminiモデルを取得"""
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
        
        model_name = None
        
        # 手動選択されたモデルを優先
        if preferred_model:
            for available in available_gemini_models:
                if preferred_model in available:
                    model_name = available
                    print(f"使用モデル: {model_name} (手動選択)")
                    break
            
            if not model_name:
                print(f"警告: 指定されたモデル '{preferred_model}' が利用できません。自動選択に切り替えます。")
        
        # 自動選択：優先度順に使用可能なモデルを選択
        if not model_name:
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
            if not preferred_model:
                print(f"使用モデル: {model_name} (自動選択)")
            
        print(f"利用可能なGeminiモデル一覧: {', '.join(available_gemini_models)}")
        return model_name
