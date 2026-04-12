---
name: videosummarize
description: |
  视频转录+分析工具。CLI 处理下载/转录（阶段1-3），你来做总结分析（阶段4-5）。
  支持 Bilibili、抖音、YouTube、小红书、西瓜视频。
metadata:
  clawdbot:
    emoji: "🎬"
    requires:
      bins: ["videosummarize", "ffmpeg"]
    install:
      - id: "pipx"
        kind: "pipx"
        package: "videosummarize"
        bins: ["videosummarize", "vs"]
        label: "Install VideoSummarize (pipx)"
      - id: "ffmpeg"
        kind: "brew"
        formula: "ffmpeg"
        bins: ["ffmpeg"]
        label: "Install ffmpeg (brew)"
---

# VideoSummarize

Video URL -> transcript -> you analyze and summarize.

## What This Skill Does

VideoSummarize works in two stages:

**CLI handles (stages 1-3):**
1. **Download video** — from Bilibili, Douyin, YouTube, etc.
2. **Extract audio** — FFmpeg extracts 16kHz mono WAV
3. **Speech-to-text** — Whisper model transcribes with timestamps

**You handle (stages 4-5):**
4. **Analysis** — summarize, extract key points, Q&A, etc.
5. **Multi-video integration** — cross-video comparison, study notes

The CLI only converts video to text. No LLM API calls. Analysis is up to you.

## File Management

All files are stored in a fixed workspace directory:

```
~/.videosummarize/
├── manifest.json              # Index of all projects
├── Project_Title_1/           # One folder per video
│   ├── video.mp4              # Downloaded video
│   ├── audio.wav              # Extracted audio
│   └── transcript.md          # Transcription result
├── Project_Title_2/
│   ├── video.mp4
│   ├── audio.wav
│   └── transcript.txt
└── ...
```

- Each video = one project folder
- Video and audio are kept by default (use `--no-keep-video` / `--no-keep-audio` to delete)
- `manifest.json` tracks all projects with metadata (URL, platform, model, timestamps)
- Use `-o` to override the workspace root path

## Working with Transcripts (Important)

**The transcript file is the core output.** After running `videosummarize`, all subsequent analysis should read from this file.

### Finding the transcript path

After the CLI finishes, it prints the exact transcript path:
```
Done! 1 video(s) transcribed:
  Video Title Here
    project:    ~/.videosummarize/Video_Title_Here
    transcript: ~/.videosummarize/Video_Title_Here/transcript.md
```

You can also find it from `manifest.json`:
```bash
cat ~/.videosummarize/manifest.json
# Each project has: "id" (folder name), "transcript_format" (md/txt/json/srt)
# So the path is: ~/.videosummarize/{id}/transcript.{transcript_format}
```

Or use `videosummarize list` to see all projects and their paths.

### Using the transcript for analysis

The transcript file (especially `-f md` format) is self-contained:
- YAML frontmatter with title, date, source URL
- Timestamped segments (each line has `[HH:MM:SS]` prefix)
- Full concatenated text at the bottom

**Read this file to answer the user's questions about the video content.**
The user may ask many questions about the same video — read the transcript each time.
The transcript stays in the project folder permanently; you can always find and re-read it.

## Prerequisites

- Python 3.10+
- ffmpeg
- Supported OS: macOS, Windows, Linux

## First Time Setup

When using this skill for the first time, run the setup check:

```bash
# 1. Install the CLI + Whisper backend (choose ONE based on your platform)

# macOS Apple Silicon (M1/M2/M3/M4) — MLX acceleration
pip install "videosummarize[mlx]"

# Windows/Linux with NVIDIA GPU — CUDA acceleration
pip install "videosummarize[cuda]"

# Windows/Linux/macOS CPU only — no GPU needed
pip install "videosummarize[cpu]"

# 2. Install ffmpeg
# macOS:
brew install ffmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg
# Windows:
choco install ffmpeg   # or: scoop install ffmpeg

# 3. Run diagnostics
videosummarize doctor
```

The `doctor` command will tell you exactly what's missing and how to fix it.
It auto-detects your platform, GPU, and installed backends.

### Backend Auto-Selection

The CLI automatically picks the best available Whisper backend:

| Priority | Backend | Platform | Acceleration |
|----------|---------|----------|-------------|
| 1 | mlx-whisper | macOS Apple Silicon | MLX (fastest on Mac) |
| 2 | faster-whisper | All platforms | CUDA (NVIDIA GPU) or CPU |
| 3 | openai-whisper | All platforms | CPU only (slowest) |

You don't need to configure anything — just install the right extra for your platform and it works.

## Quick Start

```bash
# Single video -> transcript (saved to ~/.videosummarize/)
videosummarize "https://www.bilibili.com/video/BVxxxxx"

# Markdown output (recommended for analysis)
videosummarize "URL" -f md

# Multiple videos
videosummarize "URL1" "URL2" "URL3" -f md

# Higher accuracy with larger model
videosummarize "URL" -m small -f md

# Don't keep video/audio files (transcript only)
videosummarize "URL" --no-keep-video --no-keep-audio

# Custom workspace directory
videosummarize "URL" -o ~/my-notes

# List all processed projects
videosummarize list
```

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Bilibili (B站) | Stable | via yt-dlp |
| Douyin (抖音) | Stable | Built-in downloader, no yt-dlp dependency |
| YouTube | Stable | via yt-dlp |
| 西瓜视频 | Stable | via yt-dlp |
| 小红书 | Unstable | via yt-dlp, may need cookies |

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
  -p, --parallel INT      Parallel workers (default: auto)
  --cookies TEXT           Browser cookies: chrome/safari/edge/firefox
  --no-keep-video          Delete video after transcription
  --no-keep-audio          Delete audio after transcription
  --chunk-size INT         Audio chunk size in seconds for parallel
                          transcription of long audio [default: 300]
                          Set to 0 to disable chunking
  -v, --verbose            Verbose output
  --version                Show version

Subcommands:
  doctor                   Check all dependencies and show diagnostic report
  list                     List all processed projects
```

### Agent Decision Guide

**Processing a video? Evaluate resources BEFORE running.**

#### Model Selection Matrix

| Video Duration | Available Memory | Recommended Model | Est. Time (Apple Silicon) |
|---------------|-----------------|-------------------|--------------------------|
| < 10 min | any | small | < 1 min |
| 10-30 min | >= 4GB | small | 2-5 min |
| 10-30 min | < 4GB | base | 1-3 min |
| 30 min - 2h | >= 4GB | base | 10-30 min |
| 30 min - 2h | < 4GB | base | 10-20 min |
| > 2 hours | any | base | 30-60+ min |

#### Key Rules

1. **Video > 1 hour**: Tell the user the estimated processing time BEFORE starting
2. **Video > 2 hours**: Use `base` model only, unless the user explicitly asks for higher accuracy
3. The CLI prints a **planning summary** after extracting audio (duration, workers, estimated time). Use this data to inform the user — do NOT guess the duration yourself
4. If estimated time exceeds your execution timeout, tell the user:
   "Transcription will take ~X minutes. If it times out, re-run the same command to auto-resume from where it stopped."
5. **Checkpoint/resume is built-in** — re-running the same command skips completed chunks automatically

#### Quality Report

The CLI runs deterministic quality checks after transcription and prints a report. Interpret it as follows:

| Warning | Meaning | Action |
|---------|---------|--------|
| Coverage low | Transcription doesn't reach end of audio | May need re-download or re-transcribe |
| Density low | Few characters per minute | Normal for music/silence-heavy content |
| Duplicate segments | Same text repeated | Already auto-deduped, but review boundaries |
| Large timestamp gaps | Gaps > 30s between segments | Check if audio has silent sections |
| Head/tail truncated | Missing beginning or end | Re-download may be needed |

If quality checks pass, proceed with analysis. If warnings appear, mention them to the user and let them decide whether to re-process.

### Long Audio / Podcast Support

For audio longer than ~5 minutes, the CLI automatically splits it into overlapping chunks
and transcribes them in parallel. This significantly speeds up processing of long podcasts
(1-2 hours).

- Default chunk size: 300 seconds (5 minutes), auto-adapted for long audio
- Adaptive strategy: workers=1 + long audio → 30-min chunks; many workers → keeps default size
- Overlap ensures no sentence is cut in half — boundary segments are deduplicated
- Parallel workers auto-detected based on hardware (CPU cores, min 2, max 4)
- **Checkpoint/resume**: each chunk saves immediately; if interrupted, re-run to continue
- Use `--chunk-size 600` for larger chunks, `--chunk-size 0` to disable

```bash
# Long podcast — automatically chunked and parallelized
videosummarize "https://example.com/podcast-2h" -m small -f md

# Custom chunk size (10 minutes)
videosummarize "URL" --chunk-size 600

# Disable chunking (process entire audio at once)
videosummarize "URL" --chunk-size 0
```

### Whisper Model Guide

| Model | Size | Speed | Accuracy | RAM |
|-------|------|-------|----------|-----|
| tiny | 39M | Fastest | Low | ~200MB |
| base | 74M | Fast | Good | ~400MB |
| small | 244M | Medium | Better | ~700MB |
| medium | 769M | Slow | High | ~1.8GB |
| large-v3 | 1.5G | Slowest | Best | ~3.5GB |

- **Chinese content**: `base` is usually sufficient, `small` for better accuracy
- **English content**: `base` works well
- **Mixed languages**: use `-l auto` with `small` or above

## After Transcription: Analysis Workflow

Once you have the transcript files, here are templates for common analysis tasks.

### Template 1: Single Video Summary

Read the transcript and produce:

```
## Summary
[2-3 sentence overview]

## Key Points
- [Main takeaway 1]
- [Main takeaway 2]
- ...

## Detailed Notes
[Organized by topic/timestamp]

## Action Items
- [ ] [If applicable]
```

### Template 2: Multi-Video Study Notes

When processing multiple transcripts from a course or series:

```
## Topic Overview
[What these videos collectively cover]

## Consolidated Notes
### [Topic A]
- From Video 1: [key point]
- From Video 3: [related point]

### [Topic B]
...

## Knowledge Gaps
[Topics mentioned but not fully explained]

## Study Questions
1. [Question derived from content]
2. ...
```

### Template 3: Q&A Extraction

```
## Questions & Answers

### Q: [Question from video]
**A:** [Answer with timestamp reference]
**Source:** [HH:MM:SS]

### Q: [Next question]
...
```

### Template 4: Comparative Analysis

For comparing content across videos:

```
## Comparison: [Topic]

| Aspect | Video A | Video B |
|--------|---------|---------|
| [Point] | [View] | [View] |

## Agreements
- ...

## Disagreements
- ...

## Synthesis
[Your integrated understanding]
```

## Tips

- Use `-f md` for analysis — the YAML frontmatter and Markdown structure make it easy to parse
- Use `-f srt` if you need subtitles for video editing
- Use `-f json` for programmatic processing
- Video and audio files are kept by default in the project folder for reference
- Use `--no-keep-video --no-keep-audio` to save disk space (keeps only transcript)
- For long videos (>1 hour), consider using `small` or `medium` model for better accuracy
- Run `videosummarize doctor` anytime to check your environment status
- Run `videosummarize list` to see all processed projects
