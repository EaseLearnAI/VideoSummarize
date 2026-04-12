"""
语音转文字模块

支持三种后端（按优先级自动选择）：
- mlx-whisper（Apple Silicon 加速，macOS 首选）
- faster-whisper（CTranslate2 加速，CUDA/CPU 跨平台，推荐 Windows/Linux）
- openai-whisper（CPU/CUDA 回退，最后兜底）
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 延迟检测后端
_BACKEND = None


def _detect_backend() -> str:
    """
    检测可用的 Whisper 后端

    优先级：
    1. mlx-whisper — Apple Silicon 专属加速
    2. faster-whisper — CTranslate2，CUDA 或 CPU，跨平台首选
    3. openai-whisper — 最后兜底
    """
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    # 1. Apple Silicon: mlx-whisper
    try:
        import mlx_whisper  # noqa: F401
        _BACKEND = "mlx"
        return _BACKEND
    except ImportError:
        pass

    # 2. 跨平台: faster-whisper (CTranslate2)
    try:
        import faster_whisper  # noqa: F401
        _BACKEND = "faster"
        return _BACKEND
    except ImportError:
        pass

    # 3. 兜底: openai-whisper
    try:
        import whisper  # noqa: F401
        _BACKEND = "openai"
        return _BACKEND
    except ImportError:
        pass

    _BACKEND = "none"
    return _BACKEND


# mlx-whisper 模型名映射（HuggingFace mlx-community 仓库）
MLX_MODEL_MAP = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


def _transcribe_mlx(audio_path: Path, model_size: str, language: str) -> dict:
    """使用 mlx-whisper 转录"""
    import mlx_whisper

    model_name = MLX_MODEL_MAP.get(model_size, MLX_MODEL_MAP["base"])
    kwargs = {
        "path_or_hf_repo": model_name,
        "verbose": False,
    }
    if language != "auto":
        kwargs["language"] = language

    result = mlx_whisper.transcribe(str(audio_path), **kwargs)

    full_text = result.get("text", "").strip()
    raw_segments = result.get("segments", [])

    segments = [
        {
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        }
        for seg in raw_segments
    ]

    return {"text": full_text, "segments": segments}


def _transcribe_faster(audio_path: Path, model_size: str, language: str) -> dict:
    """
    使用 faster-whisper 转录（CTranslate2 后端）

    自动检测 CUDA GPU，有则用 GPU + float16，否则 CPU + int8。
    """
    import logging as _logging

    from faster_whisper import WhisperModel

    # 抑制 ctranslate2 在 CPU 上的 float16→float32 降级警告（功能正常，只是噪音）
    _logging.getLogger("ctranslate2").setLevel(_logging.ERROR)

    # 明确选择设备和精度，避免 auto 模式产生警告
    try:
        import ctranslate2
        has_cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        has_cuda = False

    if has_cuda:
        device, compute_type = "cuda", "float16"
    else:
        device, compute_type = "cpu", "int8"

    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    kwargs = {}
    if language != "auto":
        kwargs["language"] = language

    segments_gen, info = model.transcribe(str(audio_path), **kwargs)

    # segments_gen 是生成器，需要消费
    segments_list = list(segments_gen)

    full_text = " ".join(seg.text.strip() for seg in segments_list)
    segments = [
        {
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        }
        for seg in segments_list
    ]

    return {"text": full_text, "segments": segments}


def _transcribe_openai(audio_path: Path, model_size: str, language: str) -> dict:
    """使用 openai-whisper 转录"""
    import whisper

    model = whisper.load_model(model_size)
    kwargs = {"verbose": False}
    if language != "auto":
        kwargs["language"] = language

    result = model.transcribe(str(audio_path), **kwargs)

    full_text = result.get("text", "").strip()
    raw_segments = result.get("segments", [])

    segments = [
        {
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        }
        for seg in raw_segments
    ]

    return {"text": full_text, "segments": segments}


def get_backend_name() -> str:
    """返回当前使用的后端名称（含硬件信息）"""
    backend = _detect_backend()
    if backend == "mlx":
        return "mlx-whisper (Apple Silicon)"
    elif backend == "faster":
        device = "CPU"
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                device = "CUDA"
        except Exception:
            pass
        return f"faster-whisper ({device})"
    elif backend == "openai":
        return "openai-whisper (CPU)"
    return "none"


def transcribe_audio(
    audio_path: Path,
    model_size: str = "base",
    language: str = "zh",
) -> dict:
    """
    将音频转为文字

    参数:
        audio_path: 音频文件路径
        model_size: 模型大小 (tiny/base/small/medium/large-v3)
        language: 语言提示 (zh/en/ja/auto)

    返回:
        {"text": str, "segments": list[dict]}
    """
    backend = _detect_backend()

    if backend == "mlx":
        return _transcribe_mlx(audio_path, model_size, language)
    elif backend == "faster":
        return _transcribe_faster(audio_path, model_size, language)
    elif backend == "openai":
        return _transcribe_openai(audio_path, model_size, language)
    else:
        raise RuntimeError(
            "No whisper backend found.\n"
            "  Apple Silicon:       pip install videosummarize[mlx]\n"
            "  NVIDIA GPU (CUDA):   pip install videosummarize[cuda]\n"
            "  CPU (cross-platform): pip install videosummarize[cpu]\n\n"
            "Run 'videosummarize doctor' for full diagnostics."
        )


# ── 长音频分块并行转录 ──


def transcribe_audio_chunked(
    chunks: list[dict],
    model_size: str = "base",
    language: str = "zh",
    max_workers: int | None = None,
    on_chunk_done: callable = None,
) -> dict:
    """
    分块并行转录长音频，然后合并结果。

    参数:
        chunks: split_audio() 返回的分块列表
                [{"path": Path, "offset": float, "duration": float}, ...]
        model_size: Whisper 模型大小
        language: 语言提示
        max_workers: 最大并行数（None=自动检测）
        on_chunk_done: 每块完成时的回调 fn(done_count, total_count)

    返回:
        {"text": str, "segments": list[dict]}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .hardware import get_max_transcribe_workers

    if max_workers is None:
        max_workers = get_max_transcribe_workers(model_size)
    max_workers = max(1, min(max_workers, len(chunks)))

    # 单块：直接转录，不需要并行
    if len(chunks) == 1:
        result = transcribe_audio(chunks[0]["path"], model_size, language)
        offset = chunks[0]["offset"]
        segments = [
            {"start": s["start"] + offset, "end": s["end"] + offset, "text": s["text"]}
            for s in result["segments"]
        ]
        return {"text": result["text"], "segments": segments}

    # 多块并行转录
    results_by_idx = {}
    done_count = 0

    def do_transcribe(idx, chunk):
        return idx, transcribe_audio(chunk["path"], model_size, language)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(do_transcribe, i, chunk): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            idx, result = future.result()
            results_by_idx[idx] = result
            done_count += 1
            if on_chunk_done:
                on_chunk_done(done_count, len(chunks))

    # 按原始顺序组装
    chunks_with_results = [
        {**chunks[i], "result": results_by_idx[i]}
        for i in range(len(chunks))
    ]

    return _merge_chunk_results(chunks_with_results)


def _merge_chunk_results(chunks_with_results: list[dict]) -> dict:
    """
    合并带重叠的分块转录结果。

    策略：重叠区域的段落，保留"离分块中心更近"的版本。
    因为分块中心的上下文最完整，转录质量最高。

    边界段落的选择逻辑：
    - 分块 A 和 B 有 30 秒重叠
    - 重叠区域的中点 = (A 结束 + B 开始) / 2
    - 段落在中点之前 → 用 A 的版本
    - 段落在中点之后 → 用 B 的版本
    """
    all_segments = []

    for i, chunk in enumerate(chunks_with_results):
        offset = chunk["offset"]
        segments = chunk["result"]["segments"]

        for seg in segments:
            # 跳过空段落（Whisper 有时在边界处产生空文本）
            if not seg["text"].strip():
                continue

            abs_start = seg["start"] + offset
            abs_end = seg["end"] + offset
            seg_mid = (abs_start + abs_end) / 2

            # 检查与前一块的重叠
            if i > 0:
                prev = chunks_with_results[i - 1]
                prev_end = prev["offset"] + prev["duration"]
                # 如果段落起始在前一块的范围内 → 属于重叠区域
                if abs_start < prev_end:
                    overlap_mid = (chunk["offset"] + prev_end) / 2
                    # 段落中点在重叠中点之前 → 前一块的版本更好，跳过
                    if seg_mid < overlap_mid:
                        continue

            all_segments.append({
                "start": round(abs_start, 2),
                "end": round(abs_end, 2),
                "text": seg["text"],
            })

    all_segments.sort(key=lambda s: s["start"])
    full_text = " ".join(seg["text"] for seg in all_segments if seg["text"])

    return {"text": full_text, "segments": all_segments}
