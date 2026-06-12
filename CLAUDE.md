# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Japanese AI-powered transcription application that supports three transcription engines:
- **Whisper (local)**: faster-whisper based, free, offline transcription (default; model fixed to large-v3)
- **Whisper API (OpenAI)**: Cloud transcription via `gpt-4o-transcribe` / `whisper-1` etc.
- **Google Gemini API**: Cloud-based, high-accuracy transcription with advanced processing capabilities

Title generation and additional processing (meeting minutes, summaries) prefer a local LLM via **Ollama**, with Gemini fallback.

## Development Commands

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the application:**
```bash
python main.py
```

**Run tests:**
```bash
python -m pytest tests/ -q
```

**Required system dependencies:**
- FFmpeg must be installed and available in PATH

## Architecture

### Core Structure
- **Entry Point**: `main.py` - System checks and application launch
- **Application Layer**: `src/app.py` - Main application class, UI coordination
- **Controller Layer**: `src/controllers.py` - Business logic, processing coordination
- **Service Layer**: `src/processor.py` - File processing orchestration
- **Engine Registry**: `src/engines.py` - `EngineSpec` definitions and `resolve_api_key()`; add new engines here instead of scattering if/elif branches
- **Data Layer**:
  - `src/audio_processor.py` - Audio manipulation (FFmpeg)
  - `src/api_utils.py` - Gemini API interactions (google-genai SDK; client helpers `create_genai_client` / `build_generation_config`)
  - `src/whisper_service.py` - Local Whisper transcription (faster-whisper only)
  - `src/whisper_api_service.py` - OpenAI speech-to-text API

### Configuration & Utilities
- **Constants**: `src/constants.py` - All application constants, default engine/model values
- **Exceptions**: `src/exceptions.py` - Custom exception classes (`error_code` / `user_message` / `solution`)
- **Configuration**: `src/config.py` - Settings persistence. API keys are stored in the OS keystore via `keyring` (Windows Credential Manager), NOT in config.json. `Config.set()` is write-through (auto-saves on change).
- **Utilities**: `src/utils.py` - Common utility functions (engine value helpers, usage metadata)
- **UI**: `src/ui.py` - User interface setup and layout (Tkinter)

### Key Implementation Notes
- **Gemini SDK**: Uses the new `google-genai` SDK (client-instance based, thread-safe). Do NOT reintroduce the legacy `google.generativeai` patterns (`genai.configure`, `GenerativeModel`, global locks).
- **finish_reason** handling uses the new SDK's str enum (`FinishReason`) names, not integers.
- **Engine dispatch**: `processor.py` routes transcription via `_dispatch_transcription()`; API key validation goes through `engines.resolve_api_key()`.
- **Threading**: Background processing with UI updates via `root.after()` callbacks. App shutdown calls `audio_recorder.close()` / `preview_player.shutdown()` to join threads and release handles.
- **Audio pipeline**: Convert to MP3 (128kbps), compress if >20MB, split if long, smart-merge segment texts with 10-second overlaps (`src/text_merger.py`).
- **Temp files**: Always clean up `NamedTemporaryFile(delete=False)` paths on failure paths (`AudioProcessor._safe_unlink`); files registered in `_extracted_audio_cache` are kept intentionally.
- **One-shot maintenance scripts** live in `scripts/` (not part of the app).

### AI Generation Configuration
- Defined in `constants.py` (`AI_GENERATION_CONFIG`): temperature 0.1, top_p 0.8, top_k 20, max 8192 tokens, 1 candidate. Built into a `GenerateContentConfig` by `api_utils.build_generation_config()`, optionally with relaxed safety settings for transcription.
