"""
YouTube 字幕直接提取模块

不下载视频，直接从 YouTube 获取字幕：
1. youtube-transcript-api（主路径，需 pip install youtube-transcript-api）
2. yt-dlp 字幕提取（备用路径，下载字幕文件但不下载视频）
"""

import json
import re
import tempfile
from pathlib import Path


def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _build_lang_prefs(language: str) -> list[str]:
    mapping = {
        "zh": ["zh-Hans", "zh-CN", "zh-TW", "zh", "zh-Hant"],
        "en": ["en", "en-US", "en-GB"],
        "ja": ["ja"],
    }
    prefs = mapping.get(language, [language])
    if "en" not in prefs:
        prefs = prefs + ["en"]
    return prefs


def _fetch_video_title(url: str) -> str:
    """通过 yt-dlp 获取视频标题（不下载视频）"""
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("title", "YouTube Video") if info else "YouTube Video"
    except Exception:
        return "YouTube Video"


def _try_youtube_transcript_api(video_id: str, language: str) -> list[dict] | None:
    """
    使用 youtube-transcript-api 获取字幕。
    返回 segments 列表，或 None（不可用/未安装时）。
    """
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi,
            NoTranscriptFound,
            TranscriptsDisabled,
        )
    except ImportError:
        return None

    lang_prefs = _build_lang_prefs(language)

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None

        for lang in lang_prefs:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except NoTranscriptFound:
                continue

        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(lang_prefs)
            except NoTranscriptFound:
                pass

        if transcript is None:
            for t in transcript_list:
                transcript = t
                break

        if transcript is None:
            return None

        data = transcript.fetch()
        segments = [
            {
                "start": float(item["start"]),
                "end": float(item["start"]) + float(item["duration"]),
                "text": item["text"].strip(),
            }
            for item in data
            if item.get("text", "").strip()
        ]
        return segments if segments else None

    except (TranscriptsDisabled, Exception):
        return None


def _try_ytdlp_subtitles(url: str, language: str) -> dict | None:
    """
    使用 yt-dlp 提取字幕，不下载视频。
    返回 {"segments", "title", "via"} 或 None。
    """
    try:
        import yt_dlp
    except ImportError:
        return None

    lang_prefs = _build_lang_prefs(language)

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": lang_prefs + ["en"],
            "subtitlesformat": "json3",
            "outtmpl": str(Path(tmpdir) / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "YouTube Video") if info else "YouTube Video"

            sub_files = list(Path(tmpdir).glob("*.json3"))
            if not sub_files:
                return None

            with open(sub_files[0], encoding="utf-8") as f:
                sub_data = json.load(f)

            segments = []
            for event in sub_data.get("events", []):
                if "segs" not in event:
                    continue
                start_ms = event.get("tStartMs", 0)
                dur_ms = event.get("dDurationMs", 0)
                text = "".join(seg.get("utf8", "") for seg in event["segs"]).strip()
                if text and text != "\n":
                    segments.append({
                        "start": start_ms / 1000,
                        "end": (start_ms + dur_ms) / 1000,
                        "text": text,
                    })

            if not segments:
                return None

            return {"segments": segments, "title": title, "via": "yt-dlp-subtitles"}

        except Exception:
            return None


def fetch_youtube_transcript(url: str, language: str = "zh") -> dict | None:
    """
    直接获取 YouTube 字幕，不下载视频。

    优先用 youtube-transcript-api，失败则回退到 yt-dlp 字幕提取。

    返回:
        {"text": str, "segments": list, "title": str, "via": str}
        或 None（所有方式均失败时）
    """
    video_id = _extract_video_id(url)
    if not video_id:
        return None

    segments = _try_youtube_transcript_api(video_id, language)
    if segments is not None:
        title = _fetch_video_title(url)
        full_text = " ".join(s["text"] for s in segments)
        return {
            "text": full_text,
            "segments": segments,
            "title": title,
            "via": "youtube-transcript-api",
        }

    result = _try_ytdlp_subtitles(url, language)
    if result is not None:
        result["text"] = " ".join(s["text"] for s in result["segments"])
        return result

    return None
