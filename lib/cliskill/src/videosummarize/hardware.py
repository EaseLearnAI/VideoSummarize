"""
系统硬件信息与自动并行度计算
"""

import platform

import psutil

# 每个 Whisper 模型实例的估算内存占用（模型权重 + 推理工作内存），单位 MB
MODEL_MEMORY_MB = {
    "tiny": 200,
    "base": 400,
    "small": 700,
    "medium": 1800,
    "large-v3": 3500,
}

# Apple Silicon mlx-whisper 的大约实时速度倍率
# 10.0 表示 60s 音频约需 6s 处理
MODEL_SPEED_FACTOR = {
    "tiny": 20.0,
    "base": 10.0,
    "small": 4.0,
    "medium": 2.0,
    "large-v3": 1.0,
}


def has_nvidia_gpu() -> bool:
    """检测是否有可用的 NVIDIA GPU (CUDA)"""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def get_system_info() -> dict:
    """获取系统硬件信息"""
    mem = psutil.virtual_memory()
    return {
        "total_memory_gb": round(mem.total / (1024 ** 3), 1),
        "available_memory_gb": round(mem.available / (1024 ** 3), 1),
        "cpu_cores": psutil.cpu_count(logical=False) or 1,
        "cpu_threads": psutil.cpu_count(logical=True) or 1,
        "is_apple_silicon": platform.machine() == "arm64" and platform.system() == "Darwin",
        "has_nvidia_gpu": has_nvidia_gpu(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }


def get_max_transcribe_workers(model_size: str) -> int:
    """
    计算转录的最大并行数。

    关键发现：mlx-whisper 使用 ModelHolder 全局单例缓存模型，
    多线程共享同一个模型实例，内存不会随 worker 数翻倍。
    因此主要限制因素是 CPU 核数，不是内存。

    策略：
    - 并行数 = CPU 物理核数 // 2，最少 2，最多 4
    - 唯一的内存硬限制：可用内存不够加载 1 个模型实例时降为 1
    """
    cpu_cores = psutil.cpu_count(logical=False) or 1
    workers = max(2, min(cpu_cores // 2, 4))

    # 内存硬限制：连一个模型都装不下就只能单线程
    available_mb = psutil.virtual_memory().available / (1024 * 1024)
    mem_per_model = MODEL_MEMORY_MB.get(model_size, 400)
    if available_mb < mem_per_model + 1024:
        return 1

    return workers


def estimate_transcription_time(
    duration_seconds: float,
    model_size: str,
    workers: int,
) -> float:
    """
    预估转录时间（秒）

    基于模型速度因子和并行数粗略估算。
    实际时间受硬件、音频内容等影响，结果仅供参考。
    """
    speed = MODEL_SPEED_FACTOR.get(model_size, 5.0)
    return duration_seconds / speed / max(workers, 1)
