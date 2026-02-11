#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import numpy as np
from typing import Optional, Dict, Any, Tuple

from .constants import AI_GENERATION_CONFIG
from .exceptions import TranscriptionError, AudioProcessingError
from .logger import logger
from .utils import format_duration

# Whisperライブラリの選択（自動フォールバック）
WHISPER_BACKEND = None
try:
    import torch
    import whisper
    WHISPER_BACKEND = "openai-whisper"
    logger.info("OpenAI Whisper backend loaded")
except ImportError:
    try:
        from faster_whisper import WhisperModel
        WHISPER_BACKEND = "faster-whisper"
        logger.info("Faster Whisper backend loaded")
    except ImportError:
        logger.error("No Whisper backend found. Please install openai-whisper or faster-whisper")
        WHISPER_BACKEND = None


class WhisperService:
    """OpenAI Whisperを使用した文字起こしサービス"""
    
    # Whisperモデルサイズとその特性（2025年最新）
    # 参考: https://github.com/openai/whisper
    # 推奨順: turbo > large-v3 > medium > small > base > tiny
    MODEL_INFO = {
        'turbo': {
            'size': '809M',
            'description': '⭐推奨：高速かつ高精度',
            'params': '809M',
            'recommended': True
        },
        'large-v3': {
            'size': '1550M',
            'description': '最高精度（99言語対応）',
            'params': '1550M',
            'recommended': False
        },
        'medium': {
            'size': '769M',
            'description': '高精度・軽量バランス型',
            'params': '769M',
            'recommended': False
        },
        'small': {
            'size': '244M',
            'description': '中精度・軽量',
            'params': '244M',
            'recommended': False
        },
        'base': {
            'size': '74M',
            'description': '標準モデル',
            'params': '74M',
            'recommended': False
        },
        'tiny': {
            'size': '39M',
            'description': '最速・低精度（テスト用）',
            'params': '39M',
            'recommended': False
        },
        # 互換性のための別名（内部でturboに変換）
        'large-v3-turbo': {
            'size': '809M',
            'description': 'turboの別名',
            'params': '809M',
            'alias_of': 'turbo'
        },
    }
    
    def __init__(self):
        if WHISPER_BACKEND is None:
            raise AudioProcessingError("Whisperライブラリが見つかりません。openai-whisper または faster-whisper をインストールしてください。")

        self.backend = WHISPER_BACKEND
        self.model = None
        self.current_model_name = None

        # Whisperキャッシュディレクトリを設定（書き込み可能な場所を確保）
        self._setup_cache_directory()

        # デバイス検出（torchの可用性を確認）
        try:
            if self.backend == "openai-whisper":
                # openai-whisperの場合、既にtorchがインポートされている
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                # faster-whisperの場合は独自にtorchをインポート
                import torch as torch_check
                self.device = "cuda" if torch_check.cuda.is_available() else "cpu"
        except (NameError, ImportError):
            # torchが利用できない場合はCPUにフォールバック
            self.device = "cpu"
            logger.warning("PyTorchが見つからないため、CPUモードで動作します")

        logger.info(f"WhisperService初期化: backend={self.backend}, デバイス={self.device}")

    def _setup_cache_directory(self):
        """Whisperのキャッシュディレクトリを設定"""
        try:
            # ユーザーホームディレクトリに.whisperキャッシュを作成
            home_dir = os.path.expanduser("~")
            cache_dir = os.path.join(home_dir, ".cache", "whisper")

            # ディレクトリが存在しない場合は作成
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
                logger.info(f"Whisperキャッシュディレクトリを作成: {cache_dir}")

            # 環境変数を設定（Whisperがこれを使用する）
            os.environ['XDG_CACHE_HOME'] = os.path.join(home_dir, ".cache")

            # 書き込みテスト
            test_file = os.path.join(cache_dir, ".write_test")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logger.debug(f"キャッシュディレクトリの書き込み確認完了: {cache_dir}")
            except Exception as e:
                logger.warning(f"キャッシュディレクトリへの書き込みに問題: {str(e)}")
                # 一時ディレクトリにフォールバック
                temp_cache = os.path.join(tempfile.gettempdir(), "whisper_cache")
                os.makedirs(temp_cache, exist_ok=True)
                os.environ['XDG_CACHE_HOME'] = tempfile.gettempdir()
                logger.info(f"一時ディレクトリをキャッシュに使用: {temp_cache}")

        except Exception as e:
            logger.warning(f"キャッシュディレクトリの設定に失敗: {str(e)}")
    
    def get_available_models(self):
        """利用可能なモデルのリストを取得"""
        return list(self.MODEL_INFO.keys())
    
    def get_model_description(self, model_name: str) -> str:
        """モデルの説明を取得"""
        if model_name in self.MODEL_INFO:
            info = self.MODEL_INFO[model_name]
            return f"{model_name} - {info['description']} (サイズ: {info['size']})"
        return model_name
    
    def load_model(self, model_name: str = 'base', force_reload: bool = False):
        """Whisperモデルをロード

        サポートされるモデル名:
        - tiny, base, small, medium: 標準モデル
        - large, large-v2, large-v3: Largeシリーズ
        - large-v3-turbo, turbo: 高速版（推奨）
        """
        # エイリアス解決: MODEL_INFOにalias_ofが定義されている場合、実際のモデル名に変換
        if model_name in self.MODEL_INFO:
            actual_name = self.MODEL_INFO[model_name].get('alias_of')
            if actual_name:
                logger.info(f"モデルエイリアス解決: {model_name} -> {actual_name}")
                model_name = actual_name

        if self.model is None or self.current_model_name != model_name or force_reload:
            logger.info(f"Whisperモデルをロード中: {model_name}")
            try:
                if self.backend == "openai-whisper":
                    # モデル名の正規化
                    # turboとlarge-v3-turboは同じモデル
                    actual_model_name = model_name
                    
                    # turbo系モデルの処理
                    if model_name in ['turbo', 'large-v3-turbo']:
                        # 優先順位: turbo → large-v3-turbo → large-v3 → large
                        for turbo_variant in ['turbo', 'large-v3-turbo', 'large-v3', 'large']:
                            try:
                                self.model = whisper.load_model(turbo_variant, device=self.device)
                                actual_model_name = turbo_variant
                                logger.info(f"モデル（{turbo_variant}）のロードに成功")
                                break
                            except Exception as e:
                                logger.warning(f"{turbo_variant}のロードに失敗: {str(e)}")
                                continue
                        
                        # すべて失敗した場合
                        if self.model is None:
                            raise AudioProcessingError("turbo系モデルのロードに失敗しました")
                    # large-v3の処理
                    elif model_name == 'large-v3':
                        for variant in ['large-v3', 'large']:
                            try:
                                self.model = whisper.load_model(variant, device=self.device)
                                actual_model_name = variant
                                logger.info(f"モデル（{variant}）のロードに成功")
                                break
                            except Exception as e:
                                logger.warning(f"{variant}のロードに失敗: {str(e)}")
                                continue
                    # large-v2の処理
                    elif model_name == 'large-v2':
                        for variant in ['large-v2', 'large']:
                            try:
                                self.model = whisper.load_model(variant, device=self.device)
                                actual_model_name = variant
                                logger.info(f"モデル（{variant}）のロードに成功")
                                break
                            except Exception as e:
                                logger.warning(f"{variant}のロードに失敗: {str(e)}")
                                continue
                    else:
                        self.model = whisper.load_model(actual_model_name, device=self.device)
                    
                    model_name = actual_model_name  # 実際にロードされたモデル名を記録
                else:  # faster-whisper
                    device = "cuda" if self.device == "cuda" else "cpu"
                    compute_type = "float16" if device == "cuda" else "int8"
                    
                    # faster-whisperでのモデル名マッピング
                    # faster-whisperはlarge-v3, large-v3-turboを直接サポート
                    fw_model_map = {
                        'turbo': 'large-v3-turbo',
                        'large': 'large-v3',  # largeは最新のlarge-v3を使用
                    }
                    fw_model_name = fw_model_map.get(model_name, model_name)
                    
                    try:
                        self.model = WhisperModel(fw_model_name, device=device, compute_type=compute_type)
                        model_name = fw_model_name
                    except Exception as e:
                        logger.warning(f"{fw_model_name}のロードに失敗: {str(e)}")
                        # フォールバック: large-v3 → large-v2 → large
                        for fallback in ['large-v3', 'large-v2', 'large']:
                            if fallback == fw_model_name:
                                continue
                            try:
                                self.model = WhisperModel(fallback, device=device, compute_type=compute_type)
                                model_name = fallback
                                logger.info(f"フォールバックモデル（{fallback}）のロードに成功")
                                break
                            except Exception:
                                continue
                
                self.current_model_name = model_name
                logger.info(f"モデルロード完了: {model_name} (デバイス: {self.device})")
            except Exception as e:
                logger.error(f"モデルロードエラー: {str(e)}", exc_info=True)
                # より詳細なエラー情報を提供
                if "RuntimeError" in str(type(e)):
                    raise AudioProcessingError(f"Whisperモデルのロードに失敗しました。メモリ不足の可能性があります: {str(e)}")
                else:
                    raise AudioProcessingError(f"Whisperモデルのロードに失敗しました: {str(e)}")
        return self.model
    
    def transcribe(self, audio_path: str, model_name: str = 'base', 
                  language: Optional[str] = 'ja', **kwargs) -> Tuple[str, Dict[str, Any]]:
        """音声ファイルを文字起こし"""
        try:
            # モデルをロード
            model = self.load_model(model_name)
            
            logger.info(f"Whisper文字起こし開始: {os.path.basename(audio_path)}")
            logger.info(f"使用モデル: {model_name}, 言語: {language or '自動検出'}")
            
            # 文字起こしオプション
            options = {
                'language': language,
                'task': 'transcribe',  # transcribeは元の言語のまま、translateは英語に翻訳
                'verbose': None,  # Noneでtqdmを完全に無効化
                'fp16': self.device == 'cuda',  # GPUの場合はFP16を使用
            }
            
            # 追加オプションがあれば適用
            options.update(kwargs)
            
            # 文字起こし実行
            result = model.transcribe(audio_path, **options)
            
            if not result or 'text' not in result:
                raise TranscriptionError("Whisperからの応答が不正です")
            
            text = result['text'].strip()
            if not text:
                raise TranscriptionError("文字起こし結果が空でした")
            
            # メタデータを構築
            metadata = {
                'model': model_name,
                'language': result.get('language', language),
                'duration': result.get('duration', 0),
                'segments': len(result.get('segments', [])),
                'device': self.device
            }
            
            logger.info(f"Whisper文字起こし完了: テキスト長={len(text)}文字")
            
            return text, metadata
            
        except Exception as e:
            logger.error(f"Whisper文字起こしエラー: {str(e)}")
            raise TranscriptionError(f"Whisper文字起こしに失敗しました: {str(e)}")
    
    def transcribe_with_segments(self, audio_path: str, model_name: str = 'base',
                                language: Optional[str] = 'ja', **kwargs) -> Tuple[str, Dict[str, Any]]:
        """セグメント情報付きで文字起こし"""
        try:
            # モデルをロード
            model = self.load_model(model_name)
            
            logger.info(f"Whisperセグメント文字起こし開始: {os.path.basename(audio_path)}")
            
            # 文字起こしオプション
            options = {
                'language': language,
                'task': 'transcribe',
                'verbose': None,  # Noneでtqdmを完全に無効化
                'fp16': self.device == 'cuda',
            }
            options.update(kwargs)
            
            # 文字起こし実行
            result = model.transcribe(audio_path, **options)
            
            if not result or 'text' not in result:
                raise TranscriptionError("Whisperからの応答が不正です")
            
            # セグメントごとの詳細情報を構築
            segments_info = []
            if 'segments' in result:
                for seg in result['segments']:
                    segments_info.append({
                        'start': seg['start'],
                        'end': seg['end'],
                        'text': seg['text'].strip(),
                        'id': seg.get('id', 0)
                    })
            
            # メタデータを構築
            metadata = {
                'model': model_name,
                'language': result.get('language', language),
                'duration': result.get('duration', 0),
                'segments': segments_info,
                'total_segments': len(segments_info),
                'device': self.device
            }
            
            text = result['text'].strip()
            logger.info(f"Whisperセグメント文字起こし完了: セグメント数={len(segments_info)}")
            
            return text, metadata
            
        except Exception as e:
            logger.error(f"Whisperセグメント文字起こしエラー: {str(e)}")
            raise TranscriptionError(f"Whisperセグメント文字起こしに失敗しました: {str(e)}")
    
    def transcribe_segment(self, segment_file: str, segment_num: int, 
                          total_segments: int, model_name: str = 'base',
                          language: Optional[str] = 'ja') -> Tuple[str, Dict[str, Any]]:
        """セグメントファイルの文字起こし（分割処理用）"""
        try:
            # モデルをロード
            model = self.load_model(model_name)
            
            logger.info(f"セグメント {segment_num}/{total_segments} を処理中")
            
            # コンテキスト情報を設定
            if segment_num == 1:
                initial_prompt = "これは音声の最初の部分です。"
            elif segment_num == total_segments:
                initial_prompt = "これは音声の最後の部分です。"
            else:
                initial_prompt = f"これは音声の中間部分（{segment_num}/{total_segments}）です。"
            
            # 文字起こしオプション
            options = {
                'language': language,
                'task': 'transcribe',
                'verbose': None,  # Noneでtqdmを完全に無効化
                'fp16': self.device == 'cuda',
                'initial_prompt': initial_prompt,  # コンテキストヒント
            }
            
            # 文字起こし実行
            result = model.transcribe(segment_file, **options)
            
            if not result or 'text' not in result:
                raise TranscriptionError(f"セグメント {segment_num} の文字起こし結果が不正です")
            
            text = result['text'].strip()
            if not text:
                # 空の結果の場合は警告のみ
                logger.warning(f"セグメント {segment_num} の文字起こし結果が空でした")
                text = f"[セグメント {segment_num}: 音声なし]"
            
            # メタデータ
            metadata = {
                'segment_num': segment_num,
                'total_segments': total_segments,
                'model': model_name,
                'language': result.get('language', language),
                'duration': result.get('duration', 0)
            }
            
            return text, metadata
            
        except Exception as e:
            # エラーの種類を判別
            error_type = type(e).__name__
            error_str = str(e)

            # より詳細なエラー情報を記録
            error_details = {
                'segment_num': segment_num,
                'total_segments': total_segments,
                'error_type': error_type,
                'error_message': error_str,
                'segment_file': segment_file
            }

            # エラーの種類に応じた分類
            if 'NoneType' in error_str and 'write' in error_str:
                error_category = "ファイル書き込みエラー"
                logger.error(f"セグメント {segment_num}: {error_category} - キャッシュディレクトリへのアクセス問題の可能性")
            elif 'CUDA' in error_str or 'GPU' in error_str:
                error_category = "GPUエラー"
                logger.error(f"セグメント {segment_num}: {error_category} - GPUメモリ不足の可能性")
            elif 'memory' in error_str.lower():
                error_category = "メモリエラー"
                logger.error(f"セグメント {segment_num}: {error_category} - システムメモリ不足")
            elif 'timeout' in error_str.lower():
                error_category = "タイムアウトエラー"
                logger.error(f"セグメント {segment_num}: {error_category}")
            else:
                error_category = error_type
                logger.error(f"セグメント {segment_num}: {error_category} - {error_str}")

            # スタックトレースを詳細ログに記録
            logger.debug(f"セグメント {segment_num} エラー詳細:", exc_info=True)

            # エラーでも続行できるようにエラーメッセージを返す
            error_msg = f"セグメント {segment_num} 処理エラー: {error_category}"
            return f"[{error_msg}]", error_details
    
    def test_whisper_availability(self) -> Tuple[bool, str]:
        """Whisperの利用可能性をテスト"""
        try:
            # 小さいモデルでテスト
            logger.info("Whisper利用可能性テスト開始")
            
            # tinyモデルをロード（最小サイズ）
            test_model = whisper.load_model('tiny', device=self.device)
            
            # 簡単なテスト音声を作成（無音）
            import tempfile
            import wave
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                # 1秒の無音WAVファイルを作成
                with wave.open(tmp.name, 'wb') as wav:
                    wav.setnchannels(1)  # モノラル
                    wav.setsampwidth(2)  # 16bit
                    wav.setframerate(16000)  # 16kHz
                    wav.writeframes(np.zeros(16000, dtype=np.int16).tobytes())
                
                # テスト文字起こし
                result = test_model.transcribe(tmp.name, language='ja')
                
                # 一時ファイルを削除
                os.unlink(tmp.name)
            
            device_info = f"GPU ({torch.cuda.get_device_name(0)})" if self.device == 'cuda' else "CPU"
            message = f"Whisper利用可能 (デバイス: {device_info})"
            logger.info(message)
            return True, message
            
        except Exception as e:
            error_msg = f"Whisper利用不可: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_device_info(self) -> str:
        """デバイス情報を取得"""
        if self.device == 'cuda':
            try:
                if self.backend == "openai-whisper":
                    gpu_name = torch.cuda.get_device_name(0)
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    return f"GPU: {gpu_name} (メモリ: {gpu_memory:.1f}GB)"
                else:
                    import torch as torch_check
                    gpu_name = torch_check.cuda.get_device_name(0)
                    gpu_memory = torch_check.cuda.get_device_properties(0).total_memory / (1024**3)
                    return f"GPU: {gpu_name} (メモリ: {gpu_memory:.1f}GB)"
            except (NameError, ImportError):
                return "GPU (詳細不明)"
        else:
            return "CPU"
    
    def estimate_processing_time(self, audio_duration_sec: float, model_name: str = 'base') -> float:
        """処理時間の推定（秒）"""
        # 大まかな推定値（デバイスとモデルサイズに基づく）
        # 参考: 音声時間に対する処理時間の比率
        base_factor = {
            'tiny': 0.1,
            'base': 0.15,
            'small': 0.25,
            'medium': 0.5,
            'large': 1.0,
            'large-v2': 1.0,
            'large-v3': 1.0,
            'large-v3-turbo': 0.4,  # turboは約40%高速
            'turbo': 0.4,
        }.get(model_name, 0.2)
        
        # CPUの場合は3-5倍遅い
        if self.device == 'cpu':
            base_factor *= 4
        
        return audio_duration_sec * base_factor