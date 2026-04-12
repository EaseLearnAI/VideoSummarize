"""
Pipeline 编排模块

编排 download → extract audio → transcribe 三阶段流水线。
所有文件直接在 ~/.videosummarize/{project}/ 下操作，不使用临时目录。
"""

import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from .downloader import download_video, detect_platform
from .extractor import extract_audio, get_audio_duration, split_audio
from .formats import save_transcript
from .hardware import get_max_transcribe_workers
from .transcriber import transcribe_audio, transcribe_audio_chunked, get_backend_name
from .workspace import (
    create_temp_project_dir,
    rename_project_dir,
    add_to_manifest,
    get_workspace_dir,
)

logger = logging.getLogger(__name__)


def check_dependencies():
    """检查必需的外部依赖，缺失时给出明确的安装指引。"""
    errors = []

    if not shutil.which("ffmpeg"):
        errors.append("ffmpeg not found. Install: brew install ffmpeg")

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        errors.append("yt-dlp not found. Reinstall: pip install videosummarize")

    try:
        import mlx_whisper  # noqa: F401
    except ImportError:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            try:
                import whisper  # noqa: F401
            except ImportError:
                errors.append(
                    "No whisper backend. Install one of:\n"
                    "  pip install videosummarize[mlx]   # Apple Silicon\n"
                    "  pip install videosummarize[cuda]  # NVIDIA GPU\n"
                    "  pip install videosummarize[cpu]   # CPU (cross-platform)"
                )

    if errors:
        raise SystemExit(
            "Missing dependencies:\n\n"
            + "\n\n".join(f"  ✗ {e}" for e in errors)
            + "\n\nRun 'videosummarize doctor' for full diagnostics."
        )


def process_single(
    url: str,
    workspace_dir: Path | None = None,
    model_size: str = "base",
    language: str = "zh",
    fmt: str = "txt",
    cookies_browser: str | None = None,
    keep_video: bool = True,
    keep_audio: bool = True,
    chunk_size: int = 300,
    verbose: bool = False,
    on_stage: callable = None,
) -> dict:
    """
    处理单个视频的完整流水线：下载 → 提取音频 → 转录 → 保存

    所有文件直接在项目目录下操作：
      project_dir/video.mp4
      project_dir/audio.wav
      project_dir/transcript.{fmt}

    参数:
        url: 视频 URL
        workspace_dir: 工作目录根路径（默认 ~/.videosummarize/）
        model_size: Whisper 模型大小
        language: 语言提示
        fmt: 输出格式 (txt/md/json/srt)
        cookies_browser: 浏览器 cookies
        keep_video: 是否保留视频文件（默认 True）
        keep_audio: 是否保留音频文件（默认 True）
        chunk_size: 分块大小（秒），0=禁用分块。长音频自动分块并行转录
        verbose: 详细输出
        on_stage: 阶段回调 fn(stage_name, detail)

    返回:
        {"project_dir": Path, "transcript_path": Path, "title": str}
    """
    ws = get_workspace_dir(workspace_dir)

    # 创建临时项目目录（下载前不知道标题）
    temp_dir = create_temp_project_dir(ws)

    try:
        # Stage 1: 下载视频
        if on_stage:
            on_stage("download", url)

        dl_result = download_video(
            url=url,
            output_dir=temp_dir,
            cookies_browser=cookies_browser,
            verbose=verbose,
        )
        title = dl_result["title"]
        video_path = dl_result["video_path"]

        # 重命名项目目录为正式名称
        project_dir = rename_project_dir(temp_dir, title, ws)

        # 更新 video_path 到新目录
        video_path = project_dir / video_path.name

        # Stage 2: 提取音频
        if on_stage:
            on_stage("extract", str(video_path.name))

        audio_path = extract_audio(video_path, project_dir)

        # Stage 3: 转录（长音频自动分块并行处理）
        duration = get_audio_duration(audio_path)

        if chunk_size > 0 and duration > chunk_size + 30:
            # 长音频：分块并行转录
            num_chunks = int(duration / (chunk_size - 30)) + 1
            if on_stage:
                on_stage("transcribe", f"splitting {int(duration)}s audio into {num_chunks} chunks")

            chunks = split_audio(audio_path, project_dir, chunk_seconds=chunk_size)

            def on_chunk_done(done, total):
                if on_stage:
                    on_stage("transcribe", f"chunk {done}/{total} done")

            result = transcribe_audio_chunked(
                chunks, model_size=model_size, language=language,
                on_chunk_done=on_chunk_done,
            )

            # 清理分块临时文件
            for chunk in chunks:
                if chunk["path"] != audio_path and chunk["path"].exists():
                    chunk["path"].unlink()
        else:
            # 短音频：直接转录
            if on_stage:
                on_stage("transcribe", f"{model_size} model, lang={language}")

            result = transcribe_audio(audio_path, model_size=model_size, language=language)

        # 保存转录结果
        if on_stage:
            on_stage("save", fmt)

        transcript_path = save_transcript(
            title=title,
            text=result["text"],
            segments=result["segments"],
            output_dir=project_dir,
            fmt=fmt,
            url=url,
            filename="transcript",
        )

        # 可选：删除中间文件
        if not keep_video and video_path.exists():
            video_path.unlink()

        if not keep_audio and audio_path.exists():
            audio_path.unlink()

        # 写入 manifest
        platform_name, _ = detect_platform(url)
        add_to_manifest(
            project_info={
                "id": project_dir.name,
                "title": title,
                "url": url,
                "platform": platform_name,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "model": model_size,
                "language": language,
                "backend": get_backend_name(),
                "has_video": keep_video and video_path.exists(),
                "has_audio": keep_audio and audio_path.exists(),
                "has_transcript": True,
                "transcript_format": fmt,
            },
            workspace_dir=ws,
        )

        return {
            "project_dir": project_dir,
            "transcript_path": transcript_path,
            "title": title,
        }

    except Exception:
        # 失败时清理临时目录（如果还没被 rename）
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def process_batch(
    urls: list[str],
    workspace_dir: Path | None = None,
    model_size: str = "base",
    language: str = "zh",
    fmt: str = "txt",
    parallel: int | None = None,
    cookies_browser: str | None = None,
    keep_video: bool = True,
    keep_audio: bool = True,
    chunk_size: int = 300,
    verbose: bool = False,
    on_stage: callable = None,
) -> list[dict]:
    """
    批量处理多个视频

    参数:
        urls: 视频 URL 列表
        workspace_dir: 工作目录根路径
        parallel: 并行数（None 表示自动计算）
        其他参数同 process_single

    返回:
        list[{"url": str, "result": dict | None, "error": str | None}]
    """
    if parallel is None:
        parallel = get_max_transcribe_workers(model_size)

    # 单个视频直接处理，不用线程池
    if len(urls) == 1:
        try:
            result = process_single(
                url=urls[0],
                workspace_dir=workspace_dir,
                model_size=model_size,
                language=language,
                fmt=fmt,
                cookies_browser=cookies_browser,
                keep_video=keep_video,
                keep_audio=keep_audio,
                chunk_size=chunk_size,
                verbose=verbose,
                on_stage=on_stage,
            )
            return [{"url": urls[0], "result": result, "error": None}]
        except Exception as e:
            return [{"url": urls[0], "result": None, "error": str(e)}]

    # 多个视频并行处理
    results = []
    with ThreadPoolExecutor(max_workers=min(parallel, len(urls))) as executor:
        future_to_url = {}
        for url in urls:
            future = executor.submit(
                process_single,
                url=url,
                workspace_dir=workspace_dir,
                model_size=model_size,
                language=language,
                fmt=fmt,
                cookies_browser=cookies_browser,
                keep_video=keep_video,
                keep_audio=keep_audio,
                chunk_size=chunk_size,
                verbose=verbose,
            )
            future_to_url[future] = url

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append({"url": url, "result": result, "error": None})
            except Exception as e:
                results.append({"url": url, "result": None, "error": str(e)})

    return results
