#!/usr/bin/env bash
# Fetch YouTube English subtitles + metadata for LaterCast-style summarization.
#
# Usage:
#   ./run.sh <YouTube URL>
#
# Output:
#   /tmp/ypd-<video_id>/transcript.txt        — cleaned English transcript
#   /tmp/ypd-<video_id>/title.txt             — video title
#   /tmp/ypd-<video_id>/channel.txt           — channel name
#   /tmp/ypd-<video_id>/duration.txt          — duration in seconds
#   /tmp/ypd-<video_id>/upload_date.txt       — upload date YYYYMMDD
#   /tmp/ypd-<video_id>/video_id.txt          — bare video id
#
# After this script finishes, Claude reads transcript.txt + metadata and
# generates the LaterCast-style summary in its own context.

set -euo pipefail

YOUTUBE_URL="${1:-}"
if [[ -z "$YOUTUBE_URL" ]]; then
  echo "Usage: $0 <YouTube URL>" >&2
  exit 1
fi

VIDEO_ID=$(yt-dlp --print "%(id)s" "$YOUTUBE_URL" --cookies-from-browser chrome 2>/dev/null | tail -1)
if [[ -z "$VIDEO_ID" ]]; then
  echo "ERROR: 无法解析 video_id (URL: $YOUTUBE_URL)" >&2
  exit 2
fi

WORKDIR="/tmp/ypd-${VIDEO_ID}"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

echo "[run.sh] video_id: $VIDEO_ID, workdir: $WORKDIR" >&2
echo "[run.sh] fetching subtitles + metadata..." >&2

yt-dlp \
  --skip-download \
  --write-auto-subs \
  --write-subs \
  --sub-langs "en" \
  --sub-format "vtt" \
  --cookies-from-browser chrome \
  --sleep-interval 3 --max-sleep-interval 8 \
  -o "%(id)s.%(ext)s" \
  --print-to-file "%(title)s" title.txt \
  --print-to-file "%(channel)s" channel.txt \
  --print-to-file "%(duration)s" duration.txt \
  --print-to-file "%(upload_date)s" upload_date.txt \
  --print-to-file "%(id)s" video_id.txt \
  "$YOUTUBE_URL" 2>&1 | tail -5 >&2

VTT_FILE="${WORKDIR}/${VIDEO_ID}.en.vtt"
if [[ ! -f "$VTT_FILE" ]]; then
  echo "ERROR: 没拉到英文字幕, 视频可能没有英文字幕" >&2
  exit 3
fi

VTT_SIZE=$(stat -f%z "$VTT_FILE" 2>/dev/null || stat -c%s "$VTT_FILE")
if [[ "$VTT_SIZE" -lt 5000 ]]; then
  echo "ERROR: 字幕文件过小 ($VTT_SIZE 字节), 视频可能太短或字幕不完整" >&2
  exit 4
fi

echo "[run.sh] cleaning vtt → transcript.txt..." >&2
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SKILL_DIR/vtt_to_transcript.py" "$VTT_FILE" --with-timestamps > "$WORKDIR/transcript.txt"

WORD_COUNT=$(wc -w < "$WORKDIR/transcript.txt")
if [[ "$WORD_COUNT" -lt 500 ]]; then
  echo "ERROR: 转录词数过少 ($WORD_COUNT 词), 不足以生成 3500 字总结" >&2
  exit 5
fi

echo "[run.sh] done. transcript words: $WORD_COUNT" >&2
echo "[run.sh] next: Claude reads $WORKDIR/transcript.txt + metadata files" >&2
echo "$WORKDIR"
