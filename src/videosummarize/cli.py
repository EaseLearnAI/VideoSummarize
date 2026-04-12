"""
CLI 入口

videosummarize [OPTIONS] URL [URL...]
videosummarize doctor
videosummarize list
"""

from pathlib import Path

import click

from . import __version__


@click.command()
@click.argument("urls", nargs=-1)
@click.option("-m", "--model", default="base", show_default=True,
              type=click.Choice(["tiny", "base", "small", "medium", "large-v3"]),
              help="Whisper model size")
@click.option("-o", "--output-dir", default=None,
              type=click.Path(),
              help="Workspace root (default: ~/.videosummarize)")
@click.option("-f", "--format", "fmt", default="txt", show_default=True,
              type=click.Choice(["txt", "md", "json", "srt"]),
              help="Output format")
@click.option("-l", "--language", default="zh", show_default=True,
              help="Language hint (zh/en/ja/auto)")
@click.option("-p", "--parallel", default=None, type=int,
              help="Parallel workers (default: auto)")
@click.option("--cookies", default=None,
              help="Browser cookies: chrome/safari/edge/firefox")
@click.option("--no-keep-video", is_flag=True,
              help="Delete video after transcription")
@click.option("--no-keep-audio", is_flag=True,
              help="Delete audio after transcription")
@click.option("--chunk-size", default=300, show_default=True, type=int,
              help="Chunk size (seconds) for parallel transcription of long audio. 0=disable")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.version_option(version=__version__, prog_name="videosummarize")
def main(urls, model, output_dir, fmt, language, parallel,
         cookies, no_keep_video, no_keep_audio, chunk_size, verbose):
    """Video URL -> Transcript. Download, extract audio, transcribe with Whisper.

    \b
    Usage:
      videosummarize URL [URL...]     Transcribe video(s)
      videosummarize doctor           Check dependencies
      videosummarize list             List all projects
    """
    # 特殊子命令：doctor
    if urls and urls[0] == "doctor":
        from .doctor import run_doctor
        run_doctor()
        return

    # 特殊子命令：list
    if urls and urls[0] == "list":
        _run_list(output_dir)
        return

    if not urls:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        return

    from .pipeline import check_dependencies, process_batch

    # 运行时依赖检查
    check_dependencies()

    workspace_dir = Path(output_dir) if output_dir else None

    def on_stage(stage, detail):
        if stage == "plan":
            d = detail
            dur = d["duration"]
            h, m = int(dur // 3600), int((dur % 3600) // 60)
            click.echo()
            click.echo(f"  Planning:")
            click.echo(f"    audio:    {h}h {m}m ({int(dur)}s)")
            click.echo(f"    backend:  {d['backend']}")
            click.echo(f"    model:    {d['model']}")
            click.echo(f"    workers:  {d['workers']} (avail mem: {d['available_memory_gb']}GB)")
            click.echo(f"    chunks:   {d['num_chunks']} x {d.get('chunk_size', '?')}s")
            click.echo(f"    est time: ~{d['estimated_minutes']} min")
            click.echo()
            return
        if stage == "resume":
            click.secho(f"  resume: {detail}", fg="cyan")
            return
        if stage == "verify":
            report = detail
            if report["passed"]:
                click.secho("  verify: passed", fg="green")
            else:
                click.secho("  verify: warnings:", fg="yellow")
                for w in report["warnings"]:
                    click.echo(f"    - {w}")
            return
        if stage == "warning":
            click.secho(f"  warning: {detail}", fg="yellow")
            return
        icons = {
            "download": "->",
            "extract": ">>",
            "transcribe": "**",
            "save": "=>",
        }
        icon = icons.get(stage, "  ")
        click.echo(f"  {icon} {stage}: {detail}")

    click.echo(f"VideoSummarize v{__version__}")
    click.echo(f"Processing {len(urls)} video(s), model={model}, format={fmt}")
    click.echo()

    results = process_batch(
        urls=list(urls),
        workspace_dir=workspace_dir,
        model_size=model,
        language=language,
        fmt=fmt,
        parallel=parallel,
        cookies_browser=cookies,
        keep_video=not no_keep_video,
        keep_audio=not no_keep_audio,
        chunk_size=chunk_size,
        verbose=verbose,
        on_stage=on_stage if len(urls) == 1 else None,
    )

    # 输出结果摘要
    click.echo()
    success = [r for r in results if r["error"] is None]
    failed = [r for r in results if r["error"] is not None]

    if success:
        click.secho(f"Done! {len(success)} video(s) transcribed:", fg="green")
        for r in success:
            res = r["result"]
            click.echo(f"  {res['title']}")
            click.echo(f"    project:    {res['project_dir']}")
            click.echo(f"    transcript: {res['transcript_path']}")

    if failed:
        click.secho(f"Failed: {len(failed)} video(s):", fg="red")
        for r in failed:
            click.echo(f"  {r['url']}: {r['error']}")

    click.echo()


def _run_list(output_dir: str | None):
    """列出所有已处理的项目"""
    from .workspace import get_workspace_dir, list_projects

    workspace_dir = Path(output_dir) if output_dir else None
    ws = get_workspace_dir(workspace_dir)

    projects = list_projects(ws)

    if not projects:
        click.echo(f"No projects found in {ws}")
        return

    click.secho(f"Projects in {ws}:", bold=True)
    click.echo()

    for p in projects:
        status_parts = []
        if p.get("has_video"):
            status_parts.append("video")
        if p.get("has_audio"):
            status_parts.append("audio")
        if p.get("has_transcript"):
            status_parts.append(f"transcript.{p.get('transcript_format', 'txt')}")

        files = ", ".join(status_parts) if status_parts else "empty"
        date = p.get("created_at", "")[:10]

        click.echo(f"  {p.get('title', p.get('id', '?'))}")
        click.echo(f"    [{date}] {p.get('platform', '?')} | {p.get('model', '?')} | {files}")
        click.echo(f"    {ws / p.get('id', '')}")
        click.echo()

    click.echo(f"Total: {len(projects)} project(s)")
