# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Japanese AI-powered transcription application that supports two transcription engines:
- **Google Gemini API**: Cloud-based, high-accuracy transcription with advanced processing capabilities
- **OpenAI Whisper**: Local, free, offline transcription with multi-language support

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

## Refactored Architecture (2025)

The application follows a clean, modular architecture with proper separation of concerns:

### Core Structure
- **Entry Point**: `main.py` - System checks and application launch
- **Application Layer**: `src/app.py` - Main application class, UI coordination
- **Controller Layer**: `src/controllers.py` - Business logic, processing coordination  
- **Service Layer**: `src/processor.py` - File processing orchestration
- **Data Layer**: 
  - `src/audio_processor.py` - Audio manipulation
  - `src/api_utils.py` - Gemini API interactions
  - `src/whisper_service.py` - Whisper transcription service

### Configuration & Utilities
- **Constants**: `src/constants.py` - All application constants and configuration values
- **Exceptions**: `src/exceptions.py` - Custom exception classes for better error handling
- **Configuration**: `src/config.py` - Settings and prompt management
- **Utilities**: `src/utils.py` - Common utility functions
- **UI**: `src/ui.py` - User interface setup and layout

### Key Design Patterns
- **MVC Pattern**: Clear separation between UI (View), business logic (Controller), and data processing (Model)
- **Dependency Injection**: Controllers receive dependencies rather than creating them
- **Strategy Pattern**: Different processing strategies for single vs segmented audio files
- **Template Method**: Consistent processing pipeline with customizable steps

### Enhanced Audio Processing Pipeline (2025 Update)
1. **Preparation**: Convert to MP3 (128kbps), compress if >20MB
2. **Analysis**: Check duration (split if >20 minutes) and file size
3. **Processing**: 
   - **Single-file**: Direct transcription with optimized AI parameters
   - **Segmented**: Smart segmentation with 10-second overlaps + intelligent text merging
4. **Text Integration**: Advanced overlap detection and seamless segment joining
5. **Post-processing**: Additional AI processing (summaries, meeting minutes)
6. **Output**: Unified, coherent transcription saved to `output/` directory

### New Smart Merging Features
- **AI Temperature Control**: Low temperature (0.1) for consistent, stable outputs
- **Context-Aware Processing**: Segments understand their position in the full audio
- **Overlap Detection**: Automatic detection and removal of duplicate content
- **Seamless Integration**: Python-side text merging for natural flow
- **Enhanced Prompts**: Detailed instructions for better transcription quality

## Key Implementation Details

- **Constants Management**: All magic numbers and configuration moved to `src/constants.py`
- **Error Handling**: Custom exceptions with proper error propagation
- **Threading**: Background processing with proper UI updates via callbacks
- **File Processing**: Modular pipeline with clear method separation
- **API Integration**: 
  - Gemini: Smart model selection with preference for flash models and optimized generation config
  - Whisper: Local transcription with GPU/CPU detection and multiple model size options
- **Text Merging**: Advanced text merger (`src/text_merger.py`) for intelligent segment combination
- **Cross-platform**: Proper file path handling and utility functions
- **Dual Engine Support**:
  - User can select between Gemini (cloud) and Whisper (local) from UI
  - Whisper models: tiny, base, small, medium, large
  - Automatic GPU detection for faster Whisper processing

### AI Generation Configuration
- **Temperature**: 0.1 (low temperature for stable, consistent outputs)
- **Top-p**: 0.8 (high-quality candidate selection)
- **Top-k**: 20 (limited candidate pool)
- **Max Output Tokens**: 8192
- **Candidate Count**: 1 (single, best output)