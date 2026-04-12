"""
工作目录管理模块

管理 ~/.videosummarize/ 下的项目文件夹和 manifest.json 索引。
每个视频 = 一个项目文件夹，包含 video.mp4、audio.wav、transcript.{fmt}。
"""

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = Path.home() / ".videosummarize"


def get_workspace_dir(custom_root: Path | None = None) -> Path:
    """
    返回工作目录根路径，不存在则自动创建。

    参数:
        custom_root: 自定义根路径（覆盖默认的 ~/.videosummarize/）
    """
    workspace = custom_root if custom_root else DEFAULT_WORKSPACE
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _safe_dirname(title: str) -> str:
    """将视频标题转换为安全的目录名"""
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    safe = "_".join(safe.split())  # 空格替换为下划线
    safe = safe.strip("_")  # 去掉首尾多余的下划线
    if len(safe) > 80:
        safe = safe[:80].rstrip("_")
    return safe or "untitled"


def create_project_dir(title: str, workspace_dir: Path | None = None) -> Path:
    """
    在工作目录下创建项目文件夹。

    标题重复时自动加序号（_2, _3, ...）。

    参数:
        title: 视频标题
        workspace_dir: 工作目录根路径

    返回:
        项目文件夹路径
    """
    ws = get_workspace_dir(workspace_dir)
    base_name = _safe_dirname(title)

    project_dir = ws / base_name
    if not project_dir.exists():
        project_dir.mkdir(parents=True)
        return project_dir

    # 重名：加序号
    counter = 2
    while True:
        project_dir = ws / f"{base_name}_{counter}"
        if not project_dir.exists():
            project_dir.mkdir(parents=True)
            return project_dir
        counter += 1


def create_temp_project_dir(workspace_dir: Path | None = None) -> Path:
    """
    创建临时项目目录（下载完成前还不知道标题时使用）。

    返回:
        临时项目文件夹路径（在 workspace 下，前缀 _pending_）
    """
    ws = get_workspace_dir(workspace_dir)
    tmp = Path(tempfile.mkdtemp(prefix="_pending_", dir=ws))
    return tmp


def rename_project_dir(temp_dir: Path, title: str, workspace_dir: Path | None = None) -> Path:
    """
    将临时项目目录重命名为正式名称。

    参数:
        temp_dir: 临时项目目录路径
        title: 视频标题
        workspace_dir: 工作目录根路径

    返回:
        重命名后的项目目录路径
    """
    ws = get_workspace_dir(workspace_dir)
    base_name = _safe_dirname(title)

    target = ws / base_name
    if not target.exists():
        temp_dir.rename(target)
        return target

    # 重名：加序号
    counter = 2
    while True:
        target = ws / f"{base_name}_{counter}"
        if not target.exists():
            temp_dir.rename(target)
            return target
        counter += 1


# ── manifest.json ──


def _manifest_path(workspace_dir: Path) -> Path:
    return workspace_dir / "manifest.json"


def load_manifest(workspace_dir: Path | None = None) -> dict:
    """读取 manifest.json，不存在则返回空结构"""
    ws = get_workspace_dir(workspace_dir)
    path = _manifest_path(ws)

    if not path.exists():
        return {"projects": []}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("manifest.json 损坏，重新创建")
        return {"projects": []}


def save_manifest(data: dict, workspace_dir: Path | None = None) -> None:
    """写入 manifest.json（原子写入，防止并发损坏）"""
    ws = get_workspace_dir(workspace_dir)
    path = _manifest_path(ws)

    # 写到临时文件再 rename，保证原子性
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.rename(path)


def add_to_manifest(
    project_info: dict,
    workspace_dir: Path | None = None,
) -> None:
    """
    添加一条项目记录到 manifest。

    project_info 应包含：
        id, title, url, platform, created_at, model, language,
        backend, has_video, has_audio, has_transcript, transcript_format
    """
    ws = get_workspace_dir(workspace_dir)
    manifest = load_manifest(ws)

    # 去重：同 id 的记录替换
    manifest["projects"] = [
        p for p in manifest["projects"] if p.get("id") != project_info.get("id")
    ]
    manifest["projects"].append(project_info)

    save_manifest(manifest, ws)


def list_projects(workspace_dir: Path | None = None) -> list[dict]:
    """返回所有项目记录列表"""
    manifest = load_manifest(workspace_dir)
    return manifest.get("projects", [])
