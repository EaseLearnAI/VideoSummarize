"""
输出格式化模块

支持 4 种输出格式：txt、md、json、srt
"""

import json
from datetime import datetime
from pathlib import Path


def _format_timestamp(seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _format_srt_timestamp(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_txt(title: str, text: str, segments: list[dict]) -> str:
    """纯文本格式（带时间戳分段）"""
    lines = [f"Title: {title}", f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    if segments:
        lines.append("=== Timestamped Segments ===")
        lines.append("")
        for seg in segments:
            ts = _format_timestamp(seg["start"])
            lines.append(f"[{ts}] {seg['text']}")
        lines.append("")

    lines.append("=== Full Text ===")
    lines.append("")
    lines.append(text)
    lines.append("")

    return "\n".join(lines)


def format_md(title: str, text: str, segments: list[dict], url: str = "") -> str:
    """Markdown 格式（含 YAML frontmatter，推荐给 agent 使用）"""
    lines = [
        "---",
        f"title: \"{title}\"",
        f"date: {datetime.now().strftime('%Y-%m-%d')}",
    ]
    if url:
        lines.append(f"source: \"{url}\"")
    lines.extend([
        "type: transcript",
        "---",
        "",
        f"# {title}",
        "",
    ])

    if segments:
        lines.append("## Timestamped Transcript")
        lines.append("")
        for seg in segments:
            ts = _format_timestamp(seg["start"])
            lines.append(f"**[{ts}]** {seg['text']}")
            lines.append("")

    lines.append("## Full Text")
    lines.append("")
    lines.append(text)
    lines.append("")

    return "\n".join(lines)


def format_json(title: str, text: str, segments: list[dict], url: str = "") -> str:
    """JSON 格式（机器可读）"""
    data = {
        "title": title,
        "date": datetime.now().isoformat(),
        "source": url,
        "text": text,
        "segments": segments,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_srt(segments: list[dict]) -> str:
    """SRT 字幕格式"""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _format_srt_timestamp(seg["start"])
        end = _format_srt_timestamp(seg["end"])
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


FORMATTERS = {
    "txt": format_txt,
    "md": format_md,
    "json": format_json,
    "srt": format_srt,
}


def save_transcript(
    title: str,
    text: str,
    segments: list[dict],
    output_dir: Path,
    fmt: str = "txt",
    url: str = "",
    filename: str | None = None,
) -> Path:
    """
    将转录结果保存为指定格式

    参数:
        title: 视频标题
        text: 完整转录文本
        segments: 时间戳分段列表
        output_dir: 输出目录
        fmt: 输出格式 (txt/md/json/srt)
        url: 源视频 URL（可选）
        filename: 固定文件名（不含扩展名）。为 None 时使用 safe_title

    返回:
        输出文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        base_name = filename
    else:
        # 清理文件名
        base_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        if len(base_name) > 80:
            base_name = base_name[:80]

    ext = "srt" if fmt == "srt" else fmt
    output_path = output_dir / f"{base_name}.{ext}"

    if fmt == "srt":
        content = format_srt(segments)
    elif fmt == "json":
        content = format_json(title, text, segments, url)
    elif fmt == "md":
        content = format_md(title, text, segments, url)
    else:
        content = format_txt(title, text, segments)

    output_path.write_text(content, encoding="utf-8")
    return output_path
