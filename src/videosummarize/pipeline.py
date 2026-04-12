"""
Pipeline 编排模块

编排 download → extract audio → transcribe 三阶段流水线。
所有文件直接在 ~/.videosummarize/{project}/ 下操作，不使用临时目录。

特性：
- 自适应分块：根据并行数和时长选择最优 chunk 大小
- 断点续传：每个 chunk 转录完立即保存，中断后可恢复
- 进度报告：打印 planning 摘要供 Agent 使用
- 质量验证：转录后自动运行确定性质量检查
"""

import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import psutil

from .checkpoint import (
    cleanup_checkpoints,
    get_completed_chunks,
    is_compatible_resume,
    save_checkpoint_meta,
)
from .downloader import download_video, detect_platform
from .extractor import extract_audio, get_audio_duration, split_audio
from .formats import save_transcript
from .hardware import (
    get_max_transcribe_workers,
    estimate_transcription_time,
)
from .transcriber import transcribe_audio, transcribe_audio_chunked, get_backend_name
from .verify import verify_transcript
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


def _compute_chunk_strategy(
    duration: float,
    chunk_size: int,
    workers: int,
) -> tuple[int, int]:
    """
    根据并行数和音频时长，计算自适应的 chunk 大小和 overlap。

    返回: (effective_chunk_size, overlap_seconds)
    """
    if chunk_size <= 0:
        return 0, 0

    if duration <= chunk_size + 30:
        return chunk_size, 30

    if workers <= 1 and duration > 1800:
        return 1800, 60
    elif workers <= 2 and duration > 3600:
        return 900, 45
    else:
        return chunk_size, 30


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
    处理单个视频的完整流水线：下载 → 提取音频 → 转录 → 验证 → 保存

    返回:
        {"project_dir": Path, "transcript_path": Path, "title": str}
    """
    ws = get_workspace_dir(workspace_dir)
    temp_dir = create_temp_project_dir(ws)

    try:
        # ── Stage 1: 下载视频 ──
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

        project_dir = rename_project_dir(temp_dir, title, ws)
        video_path = project_dir / video_path.name

        # ── Stage 2: 提取音频（幂等：已存在则跳过）──
        audio_path = project_dir / "audio.wav"
        if audio_path.exists() and audio_path.stat().st_size > 0:
            if on_stage:
                on_stage("resume", "audio.wav 已存在，跳过提取")
        else:
            if on_stage:
                on_stage("extract", str(video_path.name))
            audio_path = extract_audio(video_path, project_dir)

        # ── 计算转录策略 ──
        duration = get_audio_duration(audio_path)
        workers = get_max_transcribe_workers(model_size)
        effective_chunk_size, overlap = _compute_chunk_strategy(
            duration, chunk_size, workers,
        )

        # 计算预期 chunk 数
        if effective_chunk_size > 0 and duration > effective_chunk_size + overlap:
            step = effective_chunk_size - overlap
            num_chunks = max(1, int((duration - overlap) / step) + 1)
        else:
            num_chunks = 1

        # ── 进度报告：Planning 摘要 ──
        est_time = estimate_transcription_time(duration, model_size, workers)
        if on_stage:
            on_stage("plan", {
                "duration": duration,
                "workers": workers,
                "available_memory_gb": round(
                    psutil.virtual_memory().available / (1024 ** 3), 1
                ),
                "num_chunks": num_chunks,
                "estimated_minutes": max(1, round(est_time / 60)),
                "model": model_size,
                "backend": get_backend_name(),
                "chunk_size": effective_chunk_size,
            })

        # ── Stage 3: 转录 ──
        if effective_chunk_size > 0 and duration > effective_chunk_size + overlap:
            # 长音频：分块转录 + 断点续传
            completed = set()
            if is_compatible_resume(
                project_dir, model_size, language, effective_chunk_size,
            ):
                completed = get_completed_chunks(project_dir, num_chunks)
                if completed and on_stage:
                    on_stage(
                        "resume",
                        f"恢复 {len(completed)}/{num_chunks} 个已完成的块",
                    )
            else:
                save_checkpoint_meta(
                    project_dir, model_size, language,
                    effective_chunk_size, num_chunks,
                )

            if on_stage and not completed:
                on_stage(
                    "transcribe",
                    f"分块 {num_chunks} 块, {workers} 并行, model={model_size}",
                )

            chunks = split_audio(
                audio_path, project_dir,
                chunk_seconds=effective_chunk_size,
                overlap_seconds=overlap,
            )

            def on_chunk_done(done, total):
                if on_stage:
                    on_stage("transcribe", f"chunk {done}/{total} done")

            result = transcribe_audio_chunked(
                chunks,
                model_size=model_size,
                language=language,
                max_workers=workers,
                on_chunk_done=on_chunk_done,
                project_dir=project_dir,
                completed_chunks=completed,
            )

            # 清理 chunk WAV 文件（全部成功才清理）
            for chunk in chunks:
                if chunk["path"] != audio_path and chunk["path"].exists():
                    chunk["path"].unlink()
        else:
            # 短音频：直接转录
            if on_stage:
                on_stage("transcribe", f"{model_size} model, lang={language}")

            result = transcribe_audio(
                audio_path, model_size=model_size, language=language,
            )

        # ── Stage 4: 质量验证 ──
        report = verify_transcript(result["segments"], duration)
        if on_stage:
            on_stage("verify", report)

        # ── Stage 5: 保存 ──
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

        # 清理 checkpoint 文件
        cleanup_checkpoints(project_dir)

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
    """批量处理多个视频"""
    if parallel is None:
        parallel = get_max_transcribe_workers(model_size)

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
