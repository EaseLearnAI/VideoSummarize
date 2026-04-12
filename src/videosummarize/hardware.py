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
    根据系统配置自动计算转录的最大并行数

    考虑因素：
    1. 可用内存 / 每个模型实例所需内存
    2. CPU 物理核数的一半（留资源给系统）
    3. 上限 4（GPU 竞争收益递减）
    """
    available_mb = psutil.virtual_memory().available / (1024 * 1024)
    mem_per_instance = MODEL_MEMORY_MB.get(model_size, 400)

    # 留 2GB 给系统和其他进程
    usable_mb = available_mb - 2048
    by_memory = max(1, int(usable_mb / mem_per_instance))

    # 不超过 CPU 物理核数的一半
    cpu_cores = psutil.cpu_count(logical=False) or 1
    by_cpu = max(1, cpu_cores // 2)

    # 可用内存不足 4GB 时强制单线程
    if available_mb < 4096:
        return 1

    return min(by_memory, by_cpu, 4)
