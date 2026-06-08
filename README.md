# VideoSummarize

> 一个给 AI Agent 用的"视频解析 skill" — 看到 B 站 / YouTube / 抖音 / 小红书链接,自动下载、本地 Whisper 转录、按场景出结构化总结。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

```
B站/YouTube/抖音/小红书 链接   →   ┌─────────────┐
本地 .mp4/.m4a/.wav 文件     →   │  Agent 看到  │
                                  │ 自动调 CLI   │
                                  └──────┬──────┘
                                         ↓
   下载 ─→ 抽音频(ffmpeg) ─→ 本地 Whisper 转录 ─→ transcript.md
                                         ↓
                              Agent 套 7 种模板之一
                              出 summary.md(结构化总结)
```

**100% 本地推理**,转录不调用任何外部 LLM/STT API。Agent 只在最后一步用自己的 LLM 套模板出总结。

---

## ✨ 这是什么

一个**自带 CLI 源码的 skill 包**。把它放到你的 Agent skills 目录后,Agent 看到视频链接会自动:

1. 调用 `videosummarize` CLI 把视频转成 transcript
2. 读 transcript 后,根据视频类型(教程 / 访谈 / 会议 / Q&A …)自动选模板
3. 输出带时间戳引用的结构化总结

**支持平台**:Bilibili / YouTube / 抖音 / 小红书 / 西瓜视频 / 本地音视频文件

**适配 Agent**:Claude Code / OpenClaw / 任何能加载 skill 的 Agent

---

## 🚀 快速开始(给 Agent 装)

### Claude Code

```bash
# 把整个仓库 clone 下来,然后把 3 个 skill 软链/复制到 Claude Code 的 skills 目录
git clone https://github.com/EaseLearnAI/VideoSummarize.git /tmp/VideoSummarize
ln -s /tmp/VideoSummarize/videosummarize          ~/.claude/skills/videosummarize
ln -s /tmp/VideoSummarize/podcast-digest          ~/.claude/skills/podcast-digest
ln -s /tmp/VideoSummarize/youtube-podcast-digest  ~/.claude/skills/youtube-podcast-digest
```

只想要其中一个 skill?直接拷该子目录到 `~/.claude/skills/` 即可。下次跟 Claude Code 聊天时丢一个视频链接,它会自动按 [videosummarize/INSTALL.md](./videosummarize/INSTALL.md) 完成首次安装。

### OpenClaw

```bash
git clone https://github.com/EaseLearnAI/VideoSummarize.git /tmp/VideoSummarize
cp -R /tmp/VideoSummarize/{videosummarize,podcast-digest,youtube-podcast-digest} ~/.openclaw/skills/
```

### 其他 Agent / 手动

clone 到任何位置,把 `SKILL.md` 路径告诉 Agent 即可。

---

## 🔧 你自己想直接用 CLI?

不用 Agent,直接命令行用:

```bash
# 1. 装系统依赖(macOS,其他平台见 INSTALL.md)
brew install ffmpeg deno

# 2. 装 CLI(macOS Apple Silicon 用 [mlx],其他用 [cpu])
pipx install "$(pwd)/lib/cliskill[mlx]"

# 3. 跑
videosummarize "https://www.bilibili.com/video/BVxxx" --cookies chrome
```

跑完看 `~/.videosummarize/<视频标题>/transcript.md`。

---

## 📁 仓库结构

本仓库聚合了 **3 个并列的 skill**,各自独立,可单独 clone 一个目录使用:

```
VideoSummarize/
├── README.md
├── LICENSE
│
├── videosummarize/              ← Skill 1:本地转录(B站/YouTube/抖音/小红书 → transcript)
│   ├── SKILL.md                 ← Agent 入口,触发规则 + 决策矩阵
│   ├── INSTALL.md               ← 4 步安装指引
│   ├── EXAMPLES.md              ← 3 个真实场景的完整示例
│   ├── _meta.json
│   └── lib/cliskill/            ← CLI 源码(自带,不依赖 PyPI)
│
├── podcast-digest/              ← Skill 2:深度版(重要视频 → 全中文严肃笔记 + Q&A 中间产物)
│   ├── SKILL.md                 ← 9 步流程,含用户 review 暂停
│   ├── LATERCAST_PROMPT.md      ← 全中文输出模板
│   ├── USER_PROFILE.md          ← 沐阳视角延伸思考画像
│   ├── extract_qa_validator.py  ← Q&A 提取校验
│   ├── subtitle_integrity_check.py
│   ├── transcript_check.py
│   ├── validator.py             ← 最终笔记校验
│   ├── vtt_to_transcript.py
│   └── run.sh
│
└── youtube-podcast-digest/      ← Skill 3:轻量版(一次性消费 → LaterCast 风格 3500 字总结)
    ├── SKILL.md                 ← 一步到位,无 Q&A 中间产物
    ├── LATERCAST_PROMPT.md      ← 全中文输出模板
    ├── validator.py             ← 校验
    ├── vtt_to_transcript.py
    └── run.sh
```

### 3 个 skill 如何选用

| 场景 | 用哪个 |
|------|-------|
| 想拿到任意视频的本地转录 transcript(B站 / YouTube / 抖音 / 小红书 / 本地文件) | `videosummarize` |
| 重要 YouTube 播客 + 想做严肃笔记 + 想要 Q&A 中间产物 + 想在 review 阶段介入 | `podcast-digest`(深度版) |
| 不重要 / 快速 sample 一个新节目 / 一次性消费 | `youtube-podcast-digest`(轻量版) |

---

## 🎯 7 种总结模板

Agent 读完 transcript 后,根据内容自动选:

| 视频类型 | 模板 | 关键产出 |
|---------|------|---------|
| 教程 / 演讲 / 单人讲 | 模板 1:单视频通用 | Summary + Key Points + Action Items |
| 同主题多视频 | 模板 2:多视频对比 | 主题整合 + 知识盲区 |
| 答疑 / Q&A | 模板 3:Q&A 提取 | 问答对 + 时间戳 |
| 立场 / 观点对比 | 模板 4:对比分析 | 观点对比表 |
| 会议(议程 + 决策 + 行动项) | 模板 5:会议总结 | 决策 + Action 表 + 开放问题 |
| 1对N 问答(主持+嘉宾) | 模板 6:访谈 JTBD | Jobs To Be Done + 痛点 + 金句 |
| 章节明确 + 知识密度高 | 模板 7:学习笔记 | 知识图谱 + 自测题 + 易错点 |

详细模板见 [videosummarize/EXAMPLES.md](./videosummarize/EXAMPLES.md)。

---

## ⚙️ Whisper 模型选择

| 模型 | 大小 | 速度 | 中文准确度 | 推荐场景 |
|------|------|------|-----------|---------|
| tiny | 75MB | 最快 | ⭐⭐ | 临时验证、英文短视频 |
| base | 142MB | 快 | ⭐⭐⭐ | 日常使用(默认)|
| **small** | 488MB | 中 | ⭐⭐⭐⭐ | **中文推荐默认** |
| medium | 1.5GB | 慢 | ⭐⭐⭐⭐⭐ | 重要内容 |
| large-v3 | 3GB | 最慢 | 最高 | 专业转写 |

模型首次运行时**自动从 HuggingFace 下载**到 `~/.cache/huggingface/`,长期复用。
国内加速:`export HF_ENDPOINT=https://hf-mirror.com`。

---

## 🔬 后端自动选择

| 后端 | 平台 | 加速 |
|------|------|------|
| **mlx-whisper** | macOS Apple Silicon | Metal GPU(最快) |
| **faster-whisper** | 全平台 | CUDA(NVIDIA)或 CPU |
| **openai-whisper** | 兜底 | CPU |

CLI 自动按机器选,你不用管。
长视频(>30min)在 mlx 后端可能 GPU 崩,加 `VS_BACKEND=faster` 切 CPU 后端最稳。

---

## 📝 一些设计决策

- **为什么 100% 本地转录?** 隐私 + 不花 API 钱 + 不依赖网络。Agent 只在最后一步用自己的 LLM 套模板。
- **为什么自带 CLI 源码?** PyPI 上没发布,而且嵌入源码让 skill 完全自包含 — 用户 clone 一次就能用。
- **为什么不直接调 yt-dlp?** 抖音的 yt-dlp 提取器有 bug,所以抖音走 CLI 的自带下载器;其他平台才走 yt-dlp。
- **为什么需要 deno?** YouTube 的 n-challenge 反爬要 JS runtime 解算。只用 B 站/抖音/小红书可以不装。

---

## 🐛 已知坑

| 现象 | 解决 |
|------|------|
| YouTube `Sign in to confirm not a bot` | 加 `--cookies chrome` |
| YouTube `Requested format not available` | 装 `deno` |
| 长视频 mlx-whisper segfault | 加 `VS_BACKEND=faster` |
| 中文谐音错字多 | 升级到 `-m small` 或 `-m medium` |
| `videosummarize: command not found` | `pipx ensurepath` 然后**新开终端** |

完整问题表见 [videosummarize/SKILL.md](./videosummarize/SKILL.md#已知坑agent-必读) 和 [videosummarize/INSTALL.md](./videosummarize/INSTALL.md#安装失败排查)。

---

## 📜 License

[MIT](./LICENSE)

---

## 🤝 贡献

欢迎 issue / PR。`videosummarize` CLI 源码在 [videosummarize/lib/cliskill/](./videosummarize/lib/cliskill/),3 个 skill 的文档在各自子目录的 `SKILL.md`。
