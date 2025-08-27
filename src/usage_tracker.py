#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
使用量と料金の追跡システム
"""

import json
import os
import datetime
from typing import Dict, List, Optional


class UsageTracker:
    """使用量と料金の追跡クラス"""
    
    # Gemini API料金（2024年時点の概算）
    PRICING = {
        'gemini-1.5-flash': {
            'input_per_1k': 0.000075,    # $0.075 per 1K tokens
            'output_per_1k': 0.0003,     # $0.30 per 1K tokens
        },
        'gemini-1.5-pro': {
            'input_per_1k': 0.00125,     # $1.25 per 1K tokens
            'output_per_1k': 0.005,      # $5.00 per 1K tokens
        },
        'gemini-1.0-pro': {
            'input_per_1k': 0.0005,      # $0.50 per 1K tokens
            'output_per_1k': 0.0015,     # $1.50 per 1K tokens
        }
    }
    
    def __init__(self, app_dir: str):
        # dataフォルダに保存（個人データなのでgitignore対象）
        self.data_dir = os.path.join(app_dir, 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.usage_file = os.path.join(self.data_dir, 'usage_data.json')
        self.usage_data = self._load_usage_data()
    
    def _load_usage_data(self) -> Dict:
        """使用量データを読み込む"""
        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _save_usage_data(self):
        """使用量データを保存"""
        try:
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(self.usage_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"使用量データの保存に失敗しました: {e}")
    
    def record_usage(self, model: str, input_tokens: int, output_tokens: int, 
                    file_name: str = "", file_size_mb: float = 0.0):
        """使用量を記録"""
        now = datetime.datetime.now()
        month_key = now.strftime('%Y-%m')
        date_key = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # 月別データの初期化
        if month_key not in self.usage_data:
            self.usage_data[month_key] = {
                'sessions': [],
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_cost_usd': 0.0
            }
        
        # 料金計算
        cost_usd = self._calculate_cost(model, input_tokens, output_tokens)
        
        # セッション記録
        session = {
            'timestamp': date_key,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_usd': cost_usd,
            'file_name': file_name,
            'file_size_mb': file_size_mb
        }
        
        # データ更新
        month_data = self.usage_data[month_key]
        month_data['sessions'].append(session)
        month_data['total_input_tokens'] += input_tokens
        month_data['total_output_tokens'] += output_tokens
        month_data['total_cost_usd'] += cost_usd
        
        self._save_usage_data()
        return cost_usd
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """料金を計算"""
        # モデル名の正規化
        model_key = self._normalize_model_name(model)
        
        if model_key not in self.PRICING:
            # 不明なモデルの場合は平均的な料金を使用
            model_key = 'gemini-1.5-flash'
        
        pricing = self.PRICING[model_key]
        input_cost = (input_tokens / 1000) * pricing['input_per_1k']
        output_cost = (output_tokens / 1000) * pricing['output_per_1k']
        
        return input_cost + output_cost
    
    def _normalize_model_name(self, model: str) -> str:
        """モデル名を正規化"""
        model_lower = model.lower()
        
        if 'flash' in model_lower:
            return 'gemini-1.5-flash'
        elif '1.5' in model_lower and 'pro' in model_lower:
            return 'gemini-1.5-pro'
        elif '1.0' in model_lower and 'pro' in model_lower:
            return 'gemini-1.0-pro'
        else:
            return 'gemini-1.5-flash'  # デフォルト
    
    def get_current_month_usage(self) -> Dict:
        """今月の使用量を取得"""
        current_month = datetime.datetime.now().strftime('%Y-%m')
        
        if current_month not in self.usage_data:
            return {
                'total_sessions': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_cost_usd': 0.0,
                'total_cost_jpy': 0.0
            }
        
        month_data = self.usage_data[current_month]
        # USD to JPY conversion (概算レート: 1USD = 150JPY)
        usd_to_jpy_rate = 150
        
        return {
            'total_sessions': len(month_data['sessions']),
            'total_input_tokens': month_data['total_input_tokens'],
            'total_output_tokens': month_data['total_output_tokens'],
            'total_cost_usd': month_data['total_cost_usd'],
            'total_cost_jpy': month_data['total_cost_usd'] * usd_to_jpy_rate
        }
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """最近のセッション履歴を取得"""
        all_sessions = []
        
        # 全ての月のセッションを収集
        for month_key in sorted(self.usage_data.keys(), reverse=True):
            month_data = self.usage_data[month_key]
            all_sessions.extend(month_data['sessions'])
        
        # タイムスタンプでソート（新しい順）
        all_sessions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return all_sessions[:limit]
    
    def estimate_cost_for_tokens(self, model: str, input_tokens: int, output_tokens: int) -> Dict:
        """トークン数から料金を推定"""
        cost_usd = self._calculate_cost(model, input_tokens, output_tokens)
        usd_to_jpy_rate = 150
        
        return {
            'cost_usd': cost_usd,
            'cost_jpy': cost_usd * usd_to_jpy_rate,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        }