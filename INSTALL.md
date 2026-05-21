# 安装指引(INSTALL)

> Agent 第一次使用本 skill 时,**必须按本文档完成 4 个步骤**,跳过任何一步都会导致 CLI 不可用或转录失败。
>
> **预计耗时**:5-10 分钟(首次模型下载额外 1-3 分钟)。
> **磁盘占用**:CLI 源码 ~120 KB + 依赖 ~600 MB + 模型 ~150 MB(base)/ ~1.5 GB(medium)。

---

## 系统要求

| 项 | 要求 |
|----|------|
| 操作系统 | **macOS 12+**(推荐 Apple Silicon)/ Ubuntu 20+ / Windows 10+ |
| Python | **≥ 3.10** |
| RAM | ≥ 8 GB(短视频可 4GB,长视频建议 16GB)|
| 磁盘 | ≥ 2 GB 空闲 |
| 网络 | 能访问 huggingface.co、github.com、PyPI |

**已知不支持**:Python 3.9 及以下、ARM Linux(无 mlx)、不带 AVX 指令的旧 CPU。

---

## 关于 `$SKILL_DIR`

下文命令中的 `$SKILL_DIR` 指**本 SKILL.md 所在目录**(也就是这个 skill 的根目录)。

不同 Agent 加载 skill 的位置不同:
- Claude Code:通常 `~/.claude/skills/videosummarize/`
- OpenClaw:通常 `~/.openclaw/skills/videosummarize/`
- 其他 / 手动:任意你 clone 仓库后的路径

Agent 通常能从 SKILL.md 的路径自动推断出这个值。如果不能,让用户提供绝对路径。

---

## Step 1:装 ffmpeg(必装,所有平台)

ffmpeg 用于从视频中提取音频。**没有 ffmpeg,CLI 无法工作**。

### macOS

```bash
brew install ffmpeg
```

(如果没有 Homebrew:`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`)

### Linux(Ubuntu/Debian)

```bash
sudo apt update && sudo apt install -y ffmpeg
```

### Windows(PowerShell)

```powershell
# 选一个:
choco install ffmpeg          # 如果有 Chocolatey
scoop install ffmpeg          # 如果有 Scoop
winget install ffmpeg         # Windows 11 自带 winget
```

### 验证

```bash
ffmpeg -version
# 应输出:ffmpeg version X.X.X ...
```

---

## Step 2:装 deno(YouTube 必装)

YouTube 现在用 JavaScript challenge 反爬,yt-dlp 需要一个 JS runtime 来解算。**deno 是最轻最快的选择**。

> 如果**只用 B 站 / 抖音 / 小红书**,可以跳过这一步。但**任何 YouTube URL 不装 deno 必失败**。

### macOS

```bash
brew install deno
```

### Linux

```bash
curl -fsSL https://deno.land/install.sh | sh
# 安装后会提示加 PATH,跟着提示走
```

### Windows

```powershell
irm https://deno.land/install.ps1 | iex
```

### 验证

```bash
deno --version
# 应输出:deno X.X.X (...)
```

---

## Step 3:装 videosummarize CLI(从本 skill 自带源码)

**本 skill 自带 CLI 源码**,在 `$SKILL_DIR/lib/cliskill/` 目录里。**不需要从 PyPI / GitHub 下载**。

### 通用流程(所有平台)

#### 推荐:用 pipx 隔离安装(不污染系统 Python)

```bash
# 一次性装 pipx(如果没装过)
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# 装 videosummarize(指定平台对应的可选依赖)
# macOS Apple Silicon → mlx 后端(GPU 加速):
pipx install "$SKILL_DIR/lib/cliskill[mlx]"

# 其他平台 → faster 后端(CPU 通用):
pipx install "$SKILL_DIR/lib/cliskill[cpu]"

# NVIDIA GPU 机器 → CUDA 后端:
pipx install "$SKILL_DIR/lib/cliskill[cuda]"
```

#### 备选:用 pip 装到当前 Python(简单但可能依赖冲突)

```bash
# macOS Apple Silicon:
pip install "$SKILL_DIR/lib/cliskill[mlx]"

# 其他平台:
pip install "$SKILL_DIR/lib/cliskill[cpu]"
```

### 验证

```bash
videosummarize --version
# 应输出:videosummarize, version 0.1.0

videosummarize doctor
# 应看到一份环境检查报告,末尾是:
#   Status: Ready to use!
```

如果 `doctor` 报告缺东西,**按它的指引补**(它会精确告诉你哪个组件缺、怎么装)。

---

## Step 4:首次跑触发模型下载(自动)

**模型不需要手动装**。第一次跑 `videosummarize` 时,所选模型会自动从 HuggingFace 下载到你的家目录。

### 下载到哪里(规定)

| 后端 | 模型存放位置 |
|------|------------|
| **mlx-whisper**(macOS Apple Silicon) | `~/.cache/huggingface/hub/models--mlx-community--whisper-*` |
| **faster-whisper**(Win/Linux/Intel Mac) | `~/.cache/huggingface/hub/models--Systran--faster-whisper-*` |
| **openai-whisper**(兜底) | `~/.cache/whisper/` |

### 模型大小(下载一次,长期复用)

| 模型 | 体积 | 下载时间(50 Mbps)|
|------|------|---------------|
| tiny | 75 MB | < 30s |
| base | 142 MB | ~ 30s |
| small | 488 MB | ~ 1.5 min |
| medium | 1.5 GB | ~ 5 min |
| large-v3 | 3 GB | ~ 10 min |

### 触发下载

```bash
# 跑任意短视频,会自动下默认模型(base)
videosummarize "https://www.bilibili.com/video/BV1GJ411x7h7" -m base
```

### 离线场景

机器没法访问 huggingface.co?提前在能联网的机器上跑一遍触发下载,然后把整个 `~/.cache/huggingface/hub/` 目录拷到目标机器同位置即可。

### 国内加速(可选)

```bash
export HF_ENDPOINT=https://hf-mirror.com    # bash/zsh
$env:HF_ENDPOINT = "https://hf-mirror.com"  # PowerShell
```

设置后再跑 `videosummarize`,模型会从镜像站下,大陆速度通常 5-10 倍。

---

## 产出物存放位置(规定)

CLI **永远把输出放在固定的 workspace 里**,不会污染当前目录。

```
~/.videosummarize/                        ← workspace 根目录
├── manifest.json                         ← 所有项目的索引
├── <视频标题_1>/                          ← 每个视频一个目录
│   ├── video.mp4                         ← 原视频(可 --no-keep-video 跳过)
│   ├── audio.wav                         ← 提取的 16kHz 单声道音频
│   ├── transcript.md                     ← 核心产物,带时间戳
│   ├── transcript.json                   ← (可选)JSON 格式
│   └── chunks/                           ← (内部)分块缓存,断点续传用
└── <视频标题_2>/
    └── ...
```

**自定义 workspace**:
```bash
videosummarize "URL" -o ~/my-video-notes
```

**总结产物的存放(由 Agent 决定)**:
- 推荐:写到与 transcript 同目录,文件名 `summary.md`
- 或:写到用户当前工作目录
- **不要**写到 skill 自身目录,会污染 skill

---

## 卸载

```bash
# 卸载 CLI
pipx uninstall videosummarize

# 删 workspace(所有转录历史一起删,谨慎)
rm -rf ~/.videosummarize

# 删模型缓存(下次再用要重新下)
rm -rf ~/.cache/huggingface/hub/models--mlx-community--whisper-*
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-*
rm -rf ~/.cache/whisper

# 卸载 ffmpeg/deno(可选,其他工具可能还在用)
brew uninstall ffmpeg deno    # macOS
```

---

## 安装失败排查

| 报错 | 原因 | 解决 |
|------|------|------|
| `ERROR: No matching distribution found for mlx-whisper` | 你不是 macOS Apple Silicon | 改用 `[cpu]` 而不是 `[mlx]` |
| `ffmpeg: command not found` | 跳过了 Step 1 | 回去装 ffmpeg |
| `videosummarize: command not found` | pipx 的 PATH 没加 | 重新跑 `pipx ensurepath`,然后 **新开终端** |
| `Connection error` 下模型 | 国内访问 huggingface 慢 | 设 `HF_ENDPOINT=https://hf-mirror.com` |
| `Could not solve [n-challenge]` | YouTube 反爬,缺 deno | 回去装 deno |
| `Permission denied` 装 pip | 用了系统 Python | 改用 pipx 或加 `--user` 参数 |

如果 `videosummarize doctor` 显示 `Status: Ready to use!`,就可以正式开始用了。
