"""
音频提取模块

使用 FFmpeg 从视频文件中提取音频，输出 16kHz 单声道 WAV（Whisper 兼容格式）。
支持长音频分块切割（用于并行转录）。
"""

import subprocess
from pathlib import Path


def extract_audio(video_path: Path, output_dir: Path) -> Path:
    """
    从视频文件中提取音频

    参数:
        video_path: 视频文件路径
        output_dir: 音频输出目录

    返回:
        音频文件路径
    """
    audio_path = output_dir / "audio.wav"

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vn",                  # 不要视频
        "-acodec", "pcm_s16le", # 16-bit PCM
        "-ar", "16000",         # 16kHz 采样率
        "-ac", "1",             # 单声道
        "-y",                   # 覆盖已存在的文件
        str(audio_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 音频提取失败:\n{result.stderr}")

    return audio_path


def get_audio_duration(audio_path: Path) -> float:
    """获取音频时长（秒）"""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {result.stderr}")
    return float(result.stdout.strip())


def split_audio(
    audio_path: Path,
    output_dir: Path,
    chunk_seconds: int = 300,
    overlap_seconds: int = 30,
) -> list[dict]:
    """
    将长音频切割为带重叠的分块，用于并行转录。

    重叠策略：相邻分块之间有 overlap_seconds 秒的重叠区域，
    保证跨边界的句子至少在某个分块中被完整包含。

    参数:
        audio_path: 音频文件路径
        output_dir: 分块输出目录
        chunk_seconds: 每块时长（秒），默认 300（5 分钟）
        overlap_seconds: 重叠时长（秒），默认 30

    返回:
        list[{"path": Path, "offset": float, "duration": float}]
    """
    total_duration = get_audio_duration(audio_path)

    # 短音频不需要切割
    if total_duration <= chunk_seconds + overlap_seconds:
        return [{"path": audio_path, "offset": 0.0, "duration": total_duration}]

    step = chunk_seconds - overlap_seconds
    chunks = []
    start = 0.0
    idx = 0

    while start < total_duration:
        chunk_dur = min(chunk_seconds, total_duration - start)

        # 尾部太短（<10s）就不单独成块，并入前一块
        if chunk_dur < 10 and idx > 0:
            break

        chunk_path = output_dir / f"_chunk_{idx:03d}.wav"

        # WAV 是无压缩 PCM，-c copy 可以精确切割，无需重新编码
        cmd = [
            "ffmpeg",
            "-ss", str(start),
            "-t", str(chunk_dur),
            "-i", str(audio_path),
            "-c", "copy",
            "-y",
            str(chunk_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"音频分块失败: {result.stderr}")

        chunks.append({
            "path": chunk_path,
            "offset": start,
            "duration": chunk_dur,
        })

        start += step
        idx += 1

    return chunks
