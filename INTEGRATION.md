# 2026-11-07 アプリ連携

`python cli.py 録音.wav --output 新しい出力フォルダ` で既存WhisperServiceを使い、transcript.txt / transcript.json / transcript.srtを一度の処理で出力します。ローカルWhisper環境とモデルが必要です。出力整形は検証済み、今回の変更では実音声のモデル推論は実行していません。

Telop genは環境変数 `AI_TRANSCRIPTION_HOME` でこのフォルダ、`AI_TRANSCRIPTION_PYTHON` でPythonを指定するとこのCLIを利用します。AI CLI Launcherの共通ツール入口は自動設定します。
