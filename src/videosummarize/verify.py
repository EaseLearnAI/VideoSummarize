"""
确定性质量验证模块

转录完成后自动运行，用脚本做确定性检查（不依赖模型）。
脚本负责检测问题，模型负责决策如何处理。
"""


def verify_transcript(
    segments: list[dict],
    audio_duration: float,
) -> dict:
    """
    对转录结果做确定性质量检查。

    参数:
        segments: 转录段落列表 [{"start", "end", "text"}, ...]
        audio_duration: 音频总时长（秒）

    返回:
        {
            "passed": bool,
            "checks": dict,
            "warnings": [str],
        }
    """
    warnings = []
    checks = {}

    if not segments or audio_duration <= 0:
        return {
            "passed": False,
            "checks": {},
            "warnings": ["转录结果为空"],
        }

    # 1. 时间覆盖率：最后一个 segment 的 end / audio_duration
    last_end = max(seg["end"] for seg in segments)
    coverage = last_end / audio_duration if audio_duration > 0 else 0
    checks["coverage"] = {"value": round(coverage, 3), "threshold": 0.8}
    if coverage < 0.8:
        warnings.append(
            f"时间覆盖率偏低: {coverage:.1%}（最后段落结束于 {last_end:.0f}s / 总时长 {audio_duration:.0f}s）"
        )

    # 2. 空段落数
    empty_count = sum(1 for seg in segments if not seg["text"].strip())
    empty_ratio = empty_count / len(segments) if segments else 0
    checks["empty_segments"] = {"count": empty_count, "ratio": round(empty_ratio, 3)}
    if empty_ratio > 0.05:
        warnings.append(f"空段落过多: {empty_count}/{len(segments)} ({empty_ratio:.1%})")

    # 3. 重复段落：相邻 segment 文本完全相同
    dup_count = 0
    for i in range(1, len(segments)):
        if segments[i]["text"].strip() == segments[i - 1]["text"].strip():
            dup_count += 1
    checks["duplicates"] = {"count": dup_count}
    if dup_count > 0:
        warnings.append(f"发现 {dup_count} 个相邻重复段落")

    # 4. 文本密度：总字数 / 分钟数
    total_chars = sum(len(seg["text"].strip()) for seg in segments)
    duration_minutes = audio_duration / 60
    density = total_chars / duration_minutes if duration_minutes > 0 else 0
    checks["density"] = {
        "chars_per_minute": round(density, 1),
        "total_chars": total_chars,
    }
    if density < 50:
        warnings.append(
            f"文本密度偏低: {density:.0f} 字/分钟（正常语音约 150-200 字/分钟，可能含大量音乐/静音）"
        )

    # 5. 时间戳连续性：相邻 segment 间 gap > 30s
    large_gaps = 0
    for i in range(1, len(segments)):
        gap = segments[i]["start"] - segments[i - 1]["end"]
        if gap > 30:
            large_gaps += 1
    checks["timestamp_gaps"] = {"large_gaps": large_gaps}
    if large_gaps > 3:
        warnings.append(f"时间戳不连续: {large_gaps} 处间隔超过 30 秒")

    # 6. 首尾完整性
    first_start = segments[0]["start"] if segments else 0
    checks["completeness"] = {
        "first_start": round(first_start, 2),
        "last_end": round(last_end, 2),
    }
    if first_start > 30:
        warnings.append(f"开头可能截断: 第一个段落从 {first_start:.0f}s 开始")
    if audio_duration > 60 and last_end < audio_duration - 60:
        warnings.append(
            f"结尾可能截断: 最后段落结束于 {last_end:.0f}s，音频总时长 {audio_duration:.0f}s"
        )

    return {
        "passed": len(warnings) == 0,
        "checks": checks,
        "warnings": warnings,
    }
