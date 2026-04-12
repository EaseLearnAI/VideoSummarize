"""
断点续传模块

保存和恢复分块转录的中间结果。
每个 chunk 转录完成后立即保存到 _ckpt_NNN.json，
被中断后重新运行可以跳过已完成的 chunk。
"""

import json
from pathlib import Path


def checkpoint_path(project_dir: Path, chunk_idx: int) -> Path:
    return project_dir / f"_ckpt_{chunk_idx:03d}.json"


def checkpoint_meta_path(project_dir: Path) -> Path:
    return project_dir / "_ckpt_meta.json"


def save_checkpoint_meta(
    project_dir: Path,
    model_size: str,
    language: str,
    chunk_size: int,
    total_chunks: int,
) -> None:
    """保存分块参数，用于续传时校验兼容性"""
    meta = {
        "model_size": model_size,
        "language": language,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "version": 1,
    }
    path = checkpoint_meta_path(project_dir)
    _atomic_write_json(path, meta)


def save_chunk_result(
    project_dir: Path,
    chunk_idx: int,
    chunk_info: dict,
    result: dict,
) -> None:
    """保存单个 chunk 的转录结果（原子写入）"""
    data = {
        "chunk_idx": chunk_idx,
        "offset": chunk_info["offset"],
        "duration": chunk_info["duration"],
        "result": result,
    }
    path = checkpoint_path(project_dir, chunk_idx)
    _atomic_write_json(path, data)


def load_chunk_result(project_dir: Path, chunk_idx: int) -> dict | None:
    """加载已保存的 chunk 结果，不存在则返回 None"""
    path = checkpoint_path(project_dir, chunk_idx)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("result")
    except (json.JSONDecodeError, OSError):
        return None


def get_completed_chunks(project_dir: Path, total_chunks: int) -> set[int]:
    """返回已完成的 chunk 索引集合"""
    completed = set()
    for i in range(total_chunks):
        if checkpoint_path(project_dir, i).exists():
            completed.add(i)
    return completed


def is_compatible_resume(
    project_dir: Path,
    model_size: str,
    language: str,
    chunk_size: int,
) -> bool:
    """检查已有的 checkpoint 是否与当前参数兼容"""
    path = checkpoint_meta_path(project_dir)
    if not path.exists():
        return False
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    return (
        meta.get("model_size") == model_size
        and meta.get("language") == language
        and meta.get("chunk_size") == chunk_size
    )


def cleanup_checkpoints(project_dir: Path) -> None:
    """转录全部完成后清理 checkpoint 文件"""
    for f in project_dir.glob("_ckpt_*.json"):
        f.unlink(missing_ok=True)
    for f in project_dir.glob("_ckpt_*.tmp"):
        f.unlink(missing_ok=True)


def _atomic_write_json(path: Path, data: dict) -> None:
    """原子写入 JSON 文件（写临时文件再 rename）"""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.rename(path)
