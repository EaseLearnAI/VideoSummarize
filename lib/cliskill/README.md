# VideoSummarize

**Skill + CLI** for video-to-transcript workflows. Plug into any AI agent (OpenClaw, Claude Code, etc.) or use standalone from the terminal.

> Video URL &rarr; Download &rarr; Extract Audio &rarr; Whisper Transcription &rarr; Agent Analysis

Everything runs **100% local** &mdash; no LLM API calls, no cloud STT. The CLI handles the heavy lifting (download, audio extraction, speech-to-text); the agent handles analysis, summarization, and Q&A over the transcript.

---

## Why Skill + CLI?

| Layer | Role | What it does |
|-------|------|-------------|
| **CLI** (`videosummarize`) | Infrastructure | Downloads video, extracts audio, runs Whisper locally, saves transcript |
| **Skill** (`skill/SKILL.md`) | Agent interface | Tells any LLM agent how to invoke the CLI, find transcripts, and analyze content |

Any agent that can read a Skill file and run shell commands can use VideoSummarize &mdash; OpenClaw, Claude Code, or your own agent framework. The Skill file is the integration contract.

```
┌─────────────────────────────────────────────────┐
│  Agent (OpenClaw / Claude Code / Custom)        │
│                                                 │
│  1. Read skill/SKILL.md                         │
│  2. Run: videosummarize "URL" -f md             │
│  3. Read: ~/.videosummarize/{project}/transcript.md │
│  4. Summarize / Q&A / Compare / Study Notes     │
└─────────────────────────────────────────────────┘
```

## Features

- **Multi-platform** &mdash; Bilibili, Douyin (TikTok), YouTube, Xigua Video, Xiaohongshu
- **Auto backend selection** &mdash; mlx-whisper (Apple Silicon), faster-whisper (CUDA), openai-whisper (CPU)
- **Long audio parallel transcription** &mdash; Auto-chunks with 30s overlap, deduplicates at merge
- **Project-based workspace** &mdash; `~/.videosummarize/` with one folder per video, `manifest.json` index
- **Multiple output formats** &mdash; Markdown / TXT / JSON / SRT
- **Agent-ready** &mdash; Skill file with clear instructions for any LLM agent to integrate

## Quick Start

### Install

```bash
# macOS Apple Silicon (recommended)
pip install "videosummarize[mlx]"

# Windows/Linux with NVIDIA GPU
pip install "videosummarize[cuda]"

# CPU only (any platform)
pip install "videosummarize[cpu]"

# ffmpeg is required
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Ubuntu/Debian
choco install ffmpeg         # Windows
```

### Use

```bash
# Transcribe a video
videosummarize "https://www.bilibili.com/video/BVxxxxx" -f md

# Multiple videos
videosummarize "URL1" "URL2" "URL3" -f md

# Higher accuracy
videosummarize "URL" -m small -f md

# Save disk space (transcript only)
videosummarize "URL" --no-keep-video --no-keep-audio

# List all projects
videosummarize list

# Check environment
videosummarize doctor
```

## How It Works

```
Video URL
   │
   ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Download │────▶│ Extract  │────▶│Transcribe│────▶│  Save    │
│ (yt-dlp) │     │ (FFmpeg) │     │ (Whisper)│     │transcript│
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                       │
                                  Long audio?
                                       │
                                  ┌────▼────┐
                                  │  Split  │
                                  │ chunks  │
                                  │ overlap │
                                  │ 30s     │
                                  └────┬────┘
                                       │
                                  ┌────▼────┐
                                  │Parallel │
                                  │transcribe│
                                  │+ merge  │
                                  └─────────┘
```

## Workspace Structure

All files live under `~/.videosummarize/`:

```
~/.videosummarize/
├── manifest.json                    # Index of all projects
├── Python_教程_第1集/
│   ├── video.mp4                    # Downloaded video
│   ├── audio.wav                    # Extracted audio (16kHz mono WAV)
│   └── transcript.md                # Transcription result
├── 播客_AI_前沿_EP42/
│   ├── video.mp4
│   ├── audio.wav
│   └── transcript.md
└── ...
```

The transcript file is the core output. Agents read it to answer questions, generate summaries, extract key points, etc.

## Whisper Backend

The CLI auto-selects the best available backend:

| Priority | Backend | Platform | Acceleration |
|----------|---------|----------|-------------|
| 1 | mlx-whisper | macOS Apple Silicon | MLX (fastest on Mac) |
| 2 | faster-whisper | All | CUDA (NVIDIA GPU) or CPU |
| 3 | openai-whisper | All | CPU only (slowest) |

### Model Guide

| Model | Size | Speed | Accuracy | Best for |
|-------|------|-------|----------|----------|
| tiny | 39M | Fastest | Low | Quick test |
| base | 74M | Fast | Good | Chinese/English content |
| small | 244M | Medium | Better | Long-form, mixed languages |
| medium | 769M | Slow | High | Professional use |
| large-v3 | 1.5G | Slowest | Best | Maximum accuracy |

## Long Audio Support

For audio longer than 5 minutes, the CLI automatically:

1. **Splits** audio into chunks (default 5 min) with **30s overlap**
2. **Transcribes** chunks in **parallel** (auto-detected worker count based on RAM + CPU)
3. **Merges** results with overlap deduplication (keeps segments from chunk centers where context is best)

```bash
# Auto chunking (default)
videosummarize "https://example.com/podcast-2h" -m small -f md

# Custom chunk size (10 min)
videosummarize "URL" --chunk-size 600

# Disable chunking
videosummarize "URL" --chunk-size 0
```

## Agent Integration

### For OpenClaw

Install the skill:

```bash
openclaw install videosummarize
```

The skill file (`skill/SKILL.md`) tells the agent exactly how to:
- Invoke the CLI with the right options
- Find the transcript file path from CLI output or `manifest.json`
- Read and re-read the transcript to answer user questions
- Apply analysis templates (summary, Q&A, comparison, study notes)

### For Claude Code

Add as a skill or just reference the SKILL.md in your project.

### For Custom Agents

Any agent that can:
1. Read `skill/SKILL.md` for instructions
2. Run shell commands (`videosummarize "URL" -f md`)
3. Read files (`~/.videosummarize/{project}/transcript.md`)

...can use VideoSummarize. The Skill file is the integration contract.

## CLI Reference

```
videosummarize [OPTIONS] URL [URL...]
videosummarize doctor
videosummarize list

Options:
  -m, --model [tiny|base|small|medium|large-v3]
                          Whisper model size [default: base]
  -o, --output-dir PATH   Workspace root [default: ~/.videosummarize]
  -f, --format [txt|md|json|srt]
                          Output format [default: txt]
  -l, --language TEXT     Language hint: zh/en/ja/auto [default: zh]
  -p, --parallel INT      Parallel workers [default: auto]
  --cookies TEXT           Browser cookies: chrome/safari/edge/firefox
  --no-keep-video          Delete video after transcription
  --no-keep-audio          Delete audio after transcription
  --chunk-size INT         Chunk size in seconds [default: 300], 0=disable
  -v, --verbose            Verbose output
  --version                Show version
```

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Bilibili | Stable | via yt-dlp |
| Douyin | Stable | Built-in downloader |
| YouTube | Stable | via yt-dlp |
| Xigua Video | Stable | via yt-dlp |
| Xiaohongshu | Unstable | May need cookies |

## Requirements

- Python 3.10+
- ffmpeg
- macOS / Windows / Linux

## License

MIT
