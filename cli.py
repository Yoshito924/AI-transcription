"""既存WhisperServiceをGUIなしで使う。文字起こしは1回だけ行いTXT/JSON/SRTを出力。"""
import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

def timestamp(seconds):
    millis = max(0, round(float(seconds) * 1000))
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    seconds, millis = divmod(millis, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{millis:03}'

def save_result(output, text, metadata):
    output.mkdir(parents=True, exist_ok=False)
    (output / 'transcript.txt').write_text(text, encoding='utf-8')
    (output / 'transcript.json').write_text(json.dumps({'text': text, **metadata}, ensure_ascii=False, indent=2), encoding='utf-8')
    blocks = [f"{i}\n{timestamp(segment['start'])} --> {timestamp(segment['end'])}\n{segment['text'].strip()}\n"
        for i, segment in enumerate(metadata['segments'], 1)]
    (output / 'transcript.srt').write_text('\n'.join(blocks), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description='音声・動画をローカルWhisperで文字起こし。TXT/JSON/SRTを同時出力。')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='新しい出力フォルダ')
    parser.add_argument('--model', default='large-v3-turbo')
    parser.add_argument('--language', default='ja')
    args = parser.parse_args()
    if not args.input.is_file() or args.input.suffix.lower() not in {'.wav','.mp3','.m4a','.aac','.flac','.ogg','.mp4','.mov','.mkv','.webm','.avi','.mxf','.mts','.m4v'}:
        parser.error('対応する音声・動画ファイルを指定してください。')
    if args.output.exists(): parser.error('出力フォルダが存在します。別の出力先を指定してください。')
    from src.whisper_service import WhisperService
    text, metadata = WhisperService().transcribe_with_segments(str(args.input.resolve()), args.model, args.language)
    save_result(args.output, text, metadata)
    print(json.dumps({'ok': True, 'directory': str(args.output.resolve()), 'segments': len(metadata['segments'])}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
