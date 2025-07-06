# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Japanese AI-powered transcription application that uses Google Gemini API to convert audio/video files to text with additional processing capabilities (meeting minutes, summarization, etc.).

## Development Commands

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the application:**
```bash
python main.py
```

**Required system dependencies:**
- FFmpeg must be installed and available in PATH

## Architecture

The application follows a modular MVC-like architecture:

- **Entry Points**: `main.py` (checks FFmpeg and launches GUI), `src/app.py` (main application controller)
- **Audio Processing Pipeline**: Files are converted to MP3 (128kbps), compressed if >20MB, and split if >20 minutes with 10-second overlaps
- **API Integration**: `src/api_utils.py` handles Gemini API interactions with smart model selection (prefers flash models)
- **Configuration**: Stored in `config/config.json` (API keys, window settings) and `data/prompts.json` (processing prompts)
- **Threading**: Background processing keeps UI responsive during long operations

## Key Implementation Details

- Prompts use `{transcription}` placeholder for two-stage processing
- Output files are saved to `output/` with timestamp naming
- Supports MP3, WAV, MP4, AVI, MOV, M4A, FLAC, OGG formats
- FFmpeg is used for all audio manipulation
- File paths are handled carefully for cross-platform compatibility