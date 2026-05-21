"""
抖音视频独立下载模块

通过 iesdouyin.com 分享页解析视频信息并下载，不依赖 yt-dlp。
零新依赖，仅使用 Python 内置库。
"""

import json
import re
import urllib.request
from pathlib import Path

# 移动端 UA，用于访问 iesdouyin.com 分享页
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.0 Mobile/15E148 Safari/604.1"
)

_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.douyin.com/",
}


def extract_aweme_id(url: str) -> str | None:
    """
    从任意抖音 URL 中提取视频 ID (aweme_id)

    支持格式:
      - https://www.douyin.com/video/7601792901659495720
      - https://www.douyin.com/user/self/search/xxx?modal_id=7601792901659495720
      - https://www.douyin.com/search/xxx?modal_id=7601792901659495720
    """
    match = re.search(r'modal_id=(\d+)', url)
    if match:
        return match.group(1)

    match = re.search(r'douyin\.com/video/(\d+)', url)
    if match:
        return match.group(1)

    return None


def _find_video_info(data, depth: int = 0):
    """递归搜索 JSON 中的视频信息"""
    if depth > 10:
        return None
    if isinstance(data, dict):
        if "aweme_id" in data and "video" in data:
            return data
        for value in data.values():
            result = _find_video_info(value, depth + 1)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_video_info(item, depth + 1)
            if result:
                return result
    return None


def fetch_video_info(aweme_id: str) -> dict:
    """
    通过 iesdouyin.com 分享页获取视频元数据

    返回:
        dict: 包含 title, author, download_url 等信息
    """
    share_url = f"https://www.iesdouyin.com/share/video/{aweme_id}/"

    req = urllib.request.Request(share_url, headers={"User-Agent": _MOBILE_UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"访问抖音分享页失败: {e}")

    match = re.search(r'window\._ROUTER_DATA\s*=\s*({.*?})\s*</script>', html, re.DOTALL)
    if not match:
        raise RuntimeError("无法从分享页提取视频数据（_ROUTER_DATA 未找到）")

    try:
        router_data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"解析 _ROUTER_DATA 失败: {e}")

    aweme_data = _find_video_info(router_data)
    if not aweme_data:
        raise RuntimeError("无法从页面数据中定位视频信息")

    title = aweme_data.get("desc", "抖音视频")
    author = aweme_data.get("author", {}).get("nickname", "未知")

    video = aweme_data.get("video", {})
    play_addr = video.get("play_addr", {})
    url_list = play_addr.get("url_list", [])
    uri = play_addr.get("uri", "")

    download_url = None
    if url_list:
        download_url = url_list[0].replace("playwm", "play")
    elif uri:
        download_url = (
            f"https://aweme.snssdk.com/aweme/v1/play/"
            f"?video_id={uri}&ratio=1080p&line=0"
        )

    if not download_url:
        raise RuntimeError("无法获取视频下载地址")

    return {
        "title": title,
        "author": author,
        "download_url": download_url,
        "aweme_id": aweme_id,
    }


def _sanitize_filename(name: str) -> str:
    """移除文件名中的非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def download_douyin_video(url: str, output_dir: Path) -> dict:
    """
    下载抖音视频的完整流程

    参数:
        url: 抖音视频链接（支持多种格式）
        output_dir: 视频保存目录

    返回:
        {"video_path": Path, "title": str}
    """
    aweme_id = extract_aweme_id(url)
    if not aweme_id:
        raise ValueError(f"无法从 URL 中提取抖音视频 ID: {url}")

    info = fetch_video_info(aweme_id)
    title = info["title"]
    download_url = info["download_url"]

    video_path = output_dir / "video.mp4"

    req = urllib.request.Request(download_url, headers=_DOWNLOAD_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            with open(video_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
    except Exception as e:
        raise RuntimeError(f"抖音视频下载失败: {e}")

    if video_path.stat().st_size < 1024:
        video_path.unlink(missing_ok=True)
        raise RuntimeError("下载的文件异常小，可能不是有效视频")

    return {"video_path": video_path, "title": title}
