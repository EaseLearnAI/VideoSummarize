"""Verify subtitle integrity for a YouTube video.

Checks:
1. yt-dlp metadata duration vs transcript last timestamp
2. Time-stamp gaps (jumps > 3 min suggest a missing chunk)
3. Word density per minute (sparse minutes = missing content)
4. Gibberish/empty paragraphs

Usage:
    python3 subtitle_integrity_check.py URL TRANSCRIPT_PATH
"""
import re
import subprocess
import sys
from pathlib import Path


def get_youtube_duration(url):
    """Returns video duration in seconds from yt-dlp metadata."""
    try:
        out = subprocess.run(
            ["yt-dlp", "--print", "%(duration)s", "--cookies-from-browser", "chrome", "--no-warnings", url],
            capture_output=True, text=True, timeout=60
        )
        return int(out.stdout.strip())
    except Exception as e:
        return None


def parse_timestamps(text):
    """Extract [HH:MM] timestamps and return list of (minute_int, line_index)."""
    timestamps = []
    for i, line in enumerate(text.split("\n")):
        m = re.match(r"^\[(\d{2}):(\d{2})\]\s*$", line.strip())
        if m:
            timestamps.append((int(m.group(1)) * 60 + int(m.group(2)), i))
    return timestamps


def main():
    if len(sys.argv) < 3:
        print("Usage: subtitle_integrity_check.py URL TRANSCRIPT_PATH")
        return 1

    url = sys.argv[1]
    tpath = Path(sys.argv[2])
    text = tpath.read_text(encoding="utf-8")
    lines = text.split("\n")

    print(f"=== Subtitle integrity for {url} ===\n")

    # 1. YouTube metadata duration
    yt_duration_sec = get_youtube_duration(url)
    if yt_duration_sec is None:
        print("[WARN] could not fetch YouTube duration")
        yt_duration_min = None
    else:
        yt_duration_min = yt_duration_sec / 60.0
        print(f"YouTube metadata duration: {yt_duration_sec}s = {yt_duration_min:.1f} min")

    # 2. Transcript timestamp coverage
    timestamps = parse_timestamps(text)
    if not timestamps:
        print("[FAIL] no [HH:MM] timestamps found")
        return 2

    first_min = timestamps[0][0]
    last_min = timestamps[-1][0]
    coverage_min = last_min - first_min
    print(f"Transcript timestamp coverage: [{first_min // 60:02d}:{first_min % 60:02d}] → [{last_min // 60:02d}:{last_min % 60:02d}] = {coverage_min} min")

    # 3. Compare
    if yt_duration_min:
        gap = yt_duration_min - last_min
        print(f"Gap (yt duration - last timestamp): {gap:.1f} min")
        if gap > 2:
            print(f"[WARN] last transcript timestamp is {gap:.1f} min before video end — may be missing tail content")
        elif gap < -2:
            print(f"[WARN] transcript extends {-gap:.1f} min beyond video duration — odd")
        else:
            print(f"[OK] transcript covers nearly full video duration (gap = {gap:.1f} min)")

    # 4. Look for jumps in timestamps (gap > 3 min)
    print(f"\nTotal timestamps: {len(timestamps)}")
    jumps = []
    for i in range(1, len(timestamps)):
        gap = timestamps[i][0] - timestamps[i-1][0]
        if gap > 3:
            jumps.append({
                "from_min": timestamps[i-1][0],
                "to_min": timestamps[i][0],
                "gap_min": gap,
                "line_start": timestamps[i-1][1],
                "line_end": timestamps[i][1],
            })

    if jumps:
        print(f"[WARN] {len(jumps)} timestamp jumps > 3 min:")
        for j in jumps:
            print(f"  - [{j['from_min'] // 60:02d}:{j['from_min'] % 60:02d}] → [{j['to_min'] // 60:02d}:{j['to_min'] % 60:02d}] (gap {j['gap_min']} min, lines {j['line_start']}-{j['line_end']})")
    else:
        print("[OK] no timestamp jumps > 3 min")

    # 5. Word density per segment between timestamps
    print(f"\n=== Per-2-min segment word density ===")
    word_counts = []
    for i in range(len(timestamps)):
        start_line = timestamps[i][1]
        end_line = timestamps[i+1][1] if i+1 < len(timestamps) else len(lines)
        segment_text = "\n".join(lines[start_line+1:end_line])
        words = re.findall(r"\b[a-zA-Z]+\b", segment_text)
        word_counts.append({
            "ts_min": timestamps[i][0],
            "next_ts_min": timestamps[i+1][0] if i+1 < len(timestamps) else None,
            "word_count": len(words),
        })

    word_avg = sum(w["word_count"] for w in word_counts) / len(word_counts)
    print(f"Average words per segment: {word_avg:.0f}")

    suspicious_thin = [w for w in word_counts if w["word_count"] < word_avg * 0.3]
    if suspicious_thin:
        print(f"[WARN] {len(suspicious_thin)} segments with < 30% of average word density (possible missing content):")
        for w in suspicious_thin[:10]:
            print(f"  - [{w['ts_min'] // 60:02d}:{w['ts_min'] % 60:02d}] - words: {w['word_count']} (avg: {word_avg:.0f})")
    else:
        print("[OK] all segments have reasonable word density")

    # 6. Overall verdict — v4.1: 字幕完整度 >= 95% 才 PASS, < 95% 直接 FAIL
    issues = []
    fail_issues = []  # FAIL 级 (字幕不完整, 必须重拉)

    if yt_duration_min:
        coverage_pct = (last_min / yt_duration_min) * 100
        print(f"\n字幕完整度: {coverage_pct:.1f}% (last_min {last_min} / yt {yt_duration_min:.1f})")
        if coverage_pct < 95.0:
            fail_issues.append(
                f"字幕完整度 {coverage_pct:.1f}% < 95% (硬阈值) — 必须重新拉字幕或确认 transcript 完整"
            )
        elif coverage_pct < 97.0:
            issues.append(f"字幕完整度 {coverage_pct:.1f}% < 97% (建议, 可继续但要注意)")

    if len(jumps) > 0:
        issues.append(f"{len(jumps)} timestamp jumps")
    if len(suspicious_thin) > 3:
        issues.append(f"{len(suspicious_thin)} sparse segments")

    if fail_issues:
        print(f"\n=== Verdict: FAIL ({'; '.join(fail_issues)}) ===")
        return 2
    print(f"\n=== Verdict: {'PASS' if not issues else 'WARN (' + '; '.join(issues) + ')'} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
