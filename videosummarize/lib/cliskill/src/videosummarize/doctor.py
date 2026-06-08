"""
依赖诊断模块

videosummarize doctor — 检查所有依赖状态，输出诊断报告和安装指引。
"""

import platform
import shutil
import subprocess

from .hardware import MODEL_MEMORY_MB, get_max_transcribe_workers, get_system_info
from .transcriber import MLX_MODEL_MAP, _detect_backend


def _check_binary(name: str) -> tuple[str, str]:
    """检查系统二进制是否存在，返回 (路径或空, 版本或空)"""
    path = shutil.which(name)
    if not path:
        return "", ""

    try:
        result = subprocess.run(
            [path, "-version"] if name == "ffmpeg" else [path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout + result.stderr
        # 取第一行作为版本信息
        version = output.strip().split("\n")[0] if output.strip() else "unknown"
    except Exception:
        version = "installed"

    return path, version


def _check_python_package(name: str) -> tuple[bool, str]:
    """检查 Python 包是否可导入，返回 (是否存在, 版本)"""
    try:
        mod = __import__(name)
        version = getattr(mod, "__version__", "unknown")
        return True, version
    except ImportError:
        return False, ""


def _check_whisper_models() -> list[dict]:
    """检查已缓存的 Whisper 模型"""
    from pathlib import Path

    results = []
    backend = _detect_backend()

    if backend == "mlx":
        # mlx-whisper 模型缓存在 HuggingFace 目录
        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"

        for size, repo in MLX_MODEL_MAP.items():
            cache_name = "models--" + repo.replace("/", "--")
            cached = (hf_cache / cache_name).exists() if hf_cache.exists() else False
            results.append({
                "size": size,
                "repo": repo,
                "cached": cached,
            })

    elif backend == "faster":
        # faster-whisper 模型缓存在 HuggingFace 目录
        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"

        for size in MODEL_MEMORY_MB:
            # faster-whisper 使用 CTranslate2 格式模型
            cache_name = f"models--Systran--faster-whisper-{size}"
            cached = (hf_cache / cache_name).exists() if hf_cache.exists() else False
            results.append({
                "size": size,
                "repo": f"Systran/faster-whisper-{size}",
                "cached": cached,
            })

    elif backend == "openai":
        # openai-whisper 模型缓存在 ~/.cache/whisper
        whisper_cache = Path.home() / ".cache" / "whisper"

        for size in MODEL_MEMORY_MB:
            model_file = f"{size}.pt"
            cached = (whisper_cache / model_file).exists() if whisper_cache.exists() else False
            results.append({
                "size": size,
                "repo": f"openai/whisper-{size}",
                "cached": cached,
            })

    return results


def _get_cuda_info() -> str:
    """获取 CUDA 设备信息"""
    try:
        import ctranslate2
        count = ctranslate2.get_cuda_device_count()
        if count > 0:
            return f"{count} GPU(s)"
        return "not available"
    except Exception:
        return "not available"


def run_doctor() -> bool:
    """
    运行完整的诊断检查，输出报告。

    返回:
        True 如果所有必需依赖就绪
    """
    import click

    info = get_system_info()
    all_ok = True

    # === 系统信息 ===
    click.echo()
    click.secho("VideoSummarize Environment Check", bold=True)
    click.secho("=" * 40)
    click.echo()

    click.secho("System:", bold=True)
    click.echo(f"  Platform:     {info['platform']}")
    click.echo(f"  Python:       {info['python_version']}")
    click.echo(f"  RAM:          {info['total_memory_gb']} GB (available: {info['available_memory_gb']} GB)")
    click.echo(f"  CPU cores:    {info['cpu_cores']} (physical), {info['cpu_threads']} (logical)")
    if info["is_apple_silicon"]:
        click.echo(f"  Apple Silicon: Yes")
    if info["has_nvidia_gpu"]:
        cuda_info = _get_cuda_info()
        click.echo(f"  NVIDIA GPU:   Yes ({cuda_info})")
    click.echo()

    # === 依赖检查 ===
    click.secho("Dependencies:", bold=True)
    errors = []

    # ffmpeg
    ffmpeg_path, ffmpeg_ver = _check_binary("ffmpeg")
    if ffmpeg_path:
        click.echo(f"  ffmpeg:         {click.style('OK', fg='green')} {ffmpeg_path}")
    else:
        click.echo(f"  ffmpeg:         {click.style('NOT FOUND', fg='red')}")
        if platform.system() == "Darwin":
            click.echo(f"                  → Fix: brew install ffmpeg")
        elif platform.system() == "Linux":
            click.echo(f"                  → Fix: sudo apt install ffmpeg")
        else:
            click.echo(f"                  → Fix: choco install ffmpeg  OR  scoop install ffmpeg")
        errors.append("ffmpeg")
        all_ok = False

    # yt-dlp
    ytdlp_ok, ytdlp_ver = _check_python_package("yt_dlp")
    if ytdlp_ok:
        click.echo(f"  yt-dlp:         {click.style('OK', fg='green')} {ytdlp_ver} (bundled)")
    else:
        click.echo(f"  yt-dlp:         {click.style('NOT FOUND', fg='red')}")
        click.echo(f"                  → Fix: pip install videosummarize")
        errors.append("yt-dlp")
        all_ok = False

    # whisper 后端（显示所有已安装的后端）
    backend = _detect_backend()

    # 检查每个后端的安装状态
    mlx_ok, mlx_ver = _check_python_package("mlx_whisper")
    faster_ok, faster_ver = _check_python_package("faster_whisper")
    openai_ok, openai_ver = _check_python_package("whisper")

    if mlx_ok:
        active = " (active)" if backend == "mlx" else ""
        click.echo(f"  mlx-whisper:    {click.style('OK', fg='green')} {mlx_ver} Apple Silicon{active}")
    if faster_ok:
        active = " (active)" if backend == "faster" else ""
        device = "CUDA" if info["has_nvidia_gpu"] else "CPU"
        click.echo(f"  faster-whisper: {click.style('OK', fg='green')} {faster_ver} {device}{active}")
    if openai_ok:
        active = " (active)" if backend == "openai" else ""
        click.echo(f"  openai-whisper: {click.style('OK', fg='green')} {openai_ver}{active}")

    if not any([mlx_ok, faster_ok, openai_ok]):
        click.echo(f"  whisper:        {click.style('NOT FOUND', fg='red')}")
        if info["is_apple_silicon"]:
            click.echo(f"                  → Fix: pip install videosummarize[mlx]")
        elif info["has_nvidia_gpu"]:
            click.echo(f"                  → Fix: pip install videosummarize[cuda]")
        else:
            click.echo(f"                  → Fix: pip install videosummarize[cpu]")
        errors.append("whisper")
        all_ok = False

    click.echo()

    # === Whisper 模型缓存 ===
    if backend in ("mlx", "faster", "openai"):
        click.secho(f"Whisper Models (cached, backend={backend}):", bold=True)
        models = _check_whisper_models()
        for m in models:
            status = click.style("OK", fg="green") if m["cached"] else click.style("not downloaded", fg="yellow")
            note = "" if m["cached"] else " (will auto-download on first use)"
            click.echo(f"  {m['size']:12s}  {status}{note}")
        click.echo()

    # === 推荐并行度 ===
    if all_ok:
        workers = get_max_transcribe_workers("base")
        click.echo(f"Recommended workers:  {workers} (base model)")
        click.echo()

    # === 状态总结 ===
    if all_ok:
        click.secho("Status: Ready to use!", fg="green", bold=True)
    else:
        click.secho(
            f"Status: Missing dependencies: {', '.join(errors)}",
            fg="red", bold=True,
        )
        click.echo("Fix the issues above and run 'videosummarize doctor' again.")

    click.echo()
    return all_ok
