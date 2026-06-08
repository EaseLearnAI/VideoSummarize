#!/usr/bin/env python3
"""Clean a YouTube WEBVTT auto-caption file into a single deduplicated transcript.

YouTube auto-captions use a 3-cue rolling format where each spoken line appears
in up to 3 consecutive cues (current + previous 2). This script collapses them
into a flat token stream, then re-paragraphs at sentence boundaries.

Usage:
    python3 vtt_to_transcript.py INPUT.vtt > OUTPUT.txt
    python3 vtt_to_transcript.py INPUT.vtt --with-timestamps > OUTPUT.txt
"""
import argparse
import re
import sys
from pathlib import Path


TAG_RE = re.compile(r"<[^>]+>")
TIMESTAMP_RE = re.compile(
    r"^(\d{2}:\d{2}:\d{2})\.\d{3}\s+-->\s+(\d{2}:\d{2}:\d{2})\.\d{3}"
)


def parse_vtt_to_tokens(vtt_text: str) -> list[tuple[str, str]]:
    """Return list of (start_timestamp_HH:MM:SS, line_text) for every cue with non-empty text."""
    cues: list[tuple[str, list[str]]] = []
    current_start: str | None = None
    current_lines: list[str] = []

    for raw in vtt_text.splitlines():
        line = raw.rstrip()
        m = TIMESTAMP_RE.match(line)
        if m:
            if current_start is not None:
                cues.append((current_start, current_lines))
            current_start = m.group(1)
            current_lines = []
            continue
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        clean = TAG_RE.sub("", line).strip()
        if clean:
            current_lines.append(clean)

    if current_start is not None:
        cues.append((current_start, current_lines))

    return cues


def dedupe_rolling(cues: list[tuple[str, list[str]]]) -> list[tuple[str, str]]:
    """YouTube rolling caption: each cue has 1-3 lines, last line is the "new" one.

    Strategy: walk cues in order, track which sentence-like lines we've already emitted,
    and only emit the LAST line of each cue if it's new.
    """
    emitted: list[tuple[str, str]] = []
    seen: set[str] = set()

    for ts, lines in cues:
        if not lines:
            continue
        for line in lines:
            normalized = re.sub(r"\s+", " ", line).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            emitted.append((ts, normalized))

    return emitted


def join_partial_lines(lines: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """YouTube caption lines are word-wrapped at ~40 chars and split mid-sentence.

    Greedily join consecutive lines until we hit a sentence-ending punctuation,
    keeping the timestamp of the first line in the joined block.
    """
    SENTENCE_END = re.compile(r"[.!?。!?]\s*$")
    joined: list[tuple[str, str]] = []
    buf_ts: str | None = None
    buf_text: list[str] = []

    for ts, text in lines:
        if buf_ts is None:
            buf_ts = ts
        buf_text.append(text)
        if SENTENCE_END.search(text):
            joined.append((buf_ts, " ".join(buf_text).strip()))
            buf_ts = None
            buf_text = []

    if buf_text:
        joined.append((buf_ts or "00:00:00", " ".join(buf_text).strip()))

    return joined


def format_output(
    sentences: list[tuple[str, str]],
    with_timestamps: bool,
    minute_interval: int = 2,
) -> str:
    """Group sentences into paragraphs; insert [HH:MM] markers if requested."""
    if not sentences:
        return ""

    out: list[str] = []
    last_marker_min = -minute_interval
    paragraph_buf: list[str] = []

    def flush() -> None:
        if paragraph_buf:
            out.append(" ".join(paragraph_buf).strip())
            paragraph_buf.clear()

    for ts, sent in sentences:
        hh, mm, _ss = ts.split(":")
        total_min = int(hh) * 60 + int(mm)
        if with_timestamps and total_min >= last_marker_min + minute_interval:
            flush()
            out.append(f"[{hh}:{mm}]")
            last_marker_min = total_min

        paragraph_buf.append(sent)
        if len(" ".join(paragraph_buf)) > 800:
            flush()

    flush()

    cleaned: list[str] = []
    for block in out:
        block = re.sub(r"\s+", " ", block).strip()
        if block:
            cleaned.append(block)

    return "\n\n".join(cleaned)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vtt_path", type=Path)
    ap.add_argument(
        "--with-timestamps",
        action="store_true",
        help="Insert [HH:MM] markers every 2 minutes for citation",
    )
    args = ap.parse_args()

    vtt = args.vtt_path.read_text(encoding="utf-8")
    cues = parse_vtt_to_tokens(vtt)
    dedup = dedupe_rolling(cues)
    sentences = join_partial_lines(dedup)
    text = format_output(sentences, with_timestamps=args.with_timestamps)
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
