#!/usr/bin/env python
# -*- coding: utf-8 -*-

class ApiUtils:
    """API接続関連のユーティリティクラス"""
    
    def __init__(self):
        self.preferred_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
    
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
                raise ValueError("利用可能なGeminiモデルが見つかりません")
            
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
                
            print(f"使用モデル: {model_name}")
            
            # 選択したモデルでテスト
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("こんにちは")
            
            # 応答がある場合は成功
            if response and hasattr(response, 'text'):
                return True
            return False
            
        except Exception as e:
            raise Exception(f"API接続エラー: {str(e)}")
    
    def get_best_available_model(self, api_key):
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
            raise ValueError("利用可能なGeminiモデルが見つかりません")
        
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
            
        print(f"使用モデル: {model_name}")
        return model_name
