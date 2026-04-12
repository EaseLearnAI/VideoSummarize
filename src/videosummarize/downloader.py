"""
视频下载模块

支持 Bilibili、小红书、YouTube、西瓜视频通过 yt-dlp 下载，
抖音通过独立模块下载（yt-dlp 抖音提取器不稳定）。
"""

import re
import urllib.request
from pathlib import Path

import yt_dlp

from .douyin import download_douyin_video

# 平台识别映射
PLATFORM_MAP = {
    "bilibili.com": ("B站", "stable"),
    "b23.tv": ("B站", "stable"),
    "douyin.com": ("抖音", "stable"),
    "iesdouyin.com": ("抖音", "stable"),
    "xiaohongshu.com": ("小红书", "unstable"),
    "xhslink.com": ("小红书", "unstable"),
    "youtube.com": ("YouTube", "stable"),
    "youtu.be": ("YouTube", "stable"),
    "ixigua.com": ("西瓜视频", "stable"),
}

# 需要 cookies 的平台
PLATFORMS_NEED_COOKIES = {"douyin.com", "iesdouyin.com"}


def detect_platform(url: str) -> tuple[str, str]:
    """从 URL 自动识别平台，返回 (平台名, 状态)"""
    for domain, (name, status) in PLATFORM_MAP.items():
        if domain in url:
            return name, status
    return "其他", "unknown"


def needs_cookies(url: str) -> bool:
    """检查该 URL 对应的平台是否需要 cookies"""
    return any(d in url for d in PLATFORMS_NEED_COOKIES)


def _normalize_url(url: str) -> str:
    """
    标准化 URL，处理特殊格式：
    - 抖音任意页面 URL（含 modal_id）→ 直接视频 URL
    """
    if "douyin.com" in url:
        match = re.search(r'modal_id=(\d+)', url)
        if match:
            video_id = match.group(1)
            return f"https://www.douyin.com/video/{video_id}"
    return url


def _sanitize_filename(name: str) -> str:
    """移除文件名中的非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def _is_direct_url(url: str) -> bool:
    """判断是否是直接的视频文件链接"""
    direct_patterns = [
        r"\.mp4", r"\.webm", r"\.flv", r"\.mkv",
        r"bilivideo\.com", r"upos-.*\.bilivideo",
    ]
    return any(re.search(p, url) for p in direct_patterns)


def _download_direct_url(url: str, output_dir: Path, filename: str = "video.mp4") -> Path:
    """直接下载视频文件链接"""
    output_path = output_dir / filename
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response, open(output_path, "wb") as f:
        while chunk := response.read(8192):
            f.write(chunk)
    return output_path


def download_video(
    url: str,
    output_dir: Path,
    cookies_browser: str | None = None,
    verbose: bool = False,
) -> dict:
    """
    下载视频，返回 {"video_path": Path, "title": str}

    参数:
        url: 视频页面链接或直接视频文件链接
        output_dir: 视频保存目录
        cookies_browser: 从哪个浏览器提取 cookies（如 "chrome", "safari"）
        verbose: 是否输出详细信息
    """
    url = _normalize_url(url)

    # 抖音专用下载通道
    if any(d in url for d in ("douyin.com", "iesdouyin.com")):
        return download_douyin_video(url, output_dir)

    # 直接视频链接
    if _is_direct_url(url):
        path = _download_direct_url(url, output_dir)
        return {"video_path": path, "title": path.stem}

    # 使用 yt-dlp 下载
    ydl_opts = {
        "outtmpl": str(output_dir / "video.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": not verbose,
        "no_warnings": not verbose,
    }

    # 需要 cookies 的平台：从浏览器自动提取
    if cookies_browser and needs_cookies(url):
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "video")
        video_path = output_dir / "video.mp4"

        # yt-dlp 可能用不同扩展名保存，查找实际文件
        if not video_path.exists():
            files = sorted(output_dir.glob("video.*"), key=lambda f: f.stat().st_mtime, reverse=True)
            if files:
                video_path = files[0]

        return {"video_path": video_path, "title": title}
