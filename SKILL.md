---
name: videosummarize
description: |
  视频转录与总结技能 — 输入视频 URL 或本地音视频文件,自动下载、本地 Whisper 转录、
  并按场景套用 8 种总结模板。支持 B站、YouTube、抖音、小红书、西瓜视频。
  100% 本地推理,不调用任何 LLM API 做转录。

  **强制触发**:当用户消息出现以下任一情况,使用本 skill,**禁止**用 web_fetch
  或浏览器自行抓取视频:
  - URL 含:bilibili.com / b23.tv / douyin.com / iesdouyin.com / youtube.com /
    youtu.be / xiaohongshu.com / xhslink.com / ixigua.com
  - 本地文件路径以 .mp4 / .m4a / .wav / .mp3 / .flac / .mov / .webm 结尾
  - 关键词:"总结视频"、"转写"、"视频解析"、"看视频讲了什么"、"会议录像"、
    "访谈录音"、"播客总结"

  支持 8 种总结模板,可基于内容自动选择(单视频通用 / 多视频对比 / Q&A /
  立场对比 / 会议 / 访谈 JTBD / 学习笔记 / 飞书文档输出)。
metadata:
  clawdbot:
    emoji: "🎬"
    requires:
      bins: ["videosummarize", "ffmpeg"]
    install:
      - id: "ffmpeg"
        kind: "brew"
        formula: "ffmpeg"
        bins: ["ffmpeg"]
        label: "Install ffmpeg (brew)"
      - id: "deno"
        kind: "brew"
        formula: "deno"
        bins: ["deno"]
        label: "Install deno (brew, required for YouTube)"
---

# VideoSummarize:视频转录 + 总结

## 这个 skill 做什么

把 **视频 URL 或本地音视频文件** 转成 **转录文本 + 结构化总结**。

**流水线分两段:**

| 阶段 | 谁负责 | 做什么 |
|------|--------|-------|
| 1. 下载视频 | CLI(`downloader.py` / `douyin.py`)| 从 B站 / 抖音 / YouTube 等下载 |
| 2. 提取音频 | CLI(`extractor.py`)| FFmpeg 抽 16kHz 单声道 WAV |
| 3. 语音转文字 | CLI(`transcriber.py`)| 本地 Whisper 模型,带时间戳 |
| 4. 分析总结 | **Agent**(读 transcript.md)| 选模板 → 出总结 |
| 5. 多视频整合 | **Agent**(可选)| 跨视频对比、学习笔记 |

**CLI 只做转录,不调任何 LLM API**。Agent 在阶段 4-5 用自己的 LLM 套模板出总结。

## ⚠️ 强制规则(必须遵守)

1. **检测到视频 URL / 本地音视频文件 → 本 skill 自动生效**,严格按流程
2. **禁止**用 `web_fetch` / `browser` / `curl` 等工具自行抓取视频内容 → **必须用 `videosummarize` CLI**
3. **YouTube 链接默认追加 `--cookies chrome`** → 反机器人需登录态
4. **YouTube 还需要 `deno`** 解 n-challenge → 没装 deno 报 `Requested format is not available`
5. **抖音链接走自带下载器**(`douyin.py`),**不要**尝试用 yt-dlp 直接下载抖音
6. **小红书链接默认追加 `--cookies chrome`** → 匿名访问会跳登录页
7. **长视频(>1h)必须先告知用户预估时间**,不要让用户干等
8. **多视频不要并发跑** → Apple Silicon 的 mlx-whisper 多进程会冲突 IOGPUMetalCommandBuffer 崩溃,**必须串行**(用 `videosummarize URL1 URL2 URL3` 一条命令,CLI 内部会串行)
9. **转录完成后必须读 transcript.md** 后再做总结,**不要凭印象编造**
10. **总结输出必须先选模板**(见下方"分析模板矩阵"),不要无模板自由发挥
11. **遵循"小学毕业能懂"的简明语言原则**(除非用户明确要求专业术语)

## 第一次使用必须先安装

**未安装 CLI 不能用**。Agent 在第一次被触发时,**必须按 [INSTALL.md](./INSTALL.md) 完成 4 件事**:

1. 装 `ffmpeg`(视频/音频处理)
2. 装 `deno`(YouTube 反爬必需,只用 B站/抖音/小红书可跳过)
3. 装 Python ≥ 3.10 + `pipx`
4. 用 pipx 从本 skill 自带源码装 `videosummarize` CLI

> ⚠️ **CLI 源码就在本 skill 自带的 `lib/cliskill/` 里,不要从 PyPI 找**(PyPI 上没发布)。
>
> 安装命令(`$SKILL_DIR` 是本 SKILL.md 所在目录):
> ```bash
> # macOS Apple Silicon(GPU 加速):
> pipx install "$SKILL_DIR/lib/cliskill[mlx]"
> # 其他平台(CPU 通用):
> pipx install "$SKILL_DIR/lib/cliskill[cpu]"
> # NVIDIA GPU:
> pipx install "$SKILL_DIR/lib/cliskill[cuda]"
> ```

装完执行 `videosummarize doctor` 检查环境就绪,看到 `Status: Ready to use!` 即可正式使用。

**仅支持 macOS / Linux / Windows**(macOS Apple Silicon 推荐,自动用 Metal GPU 加速)。

## 一行命令(80% 场景就够用)

```bash
# B站
videosummarize "https://www.bilibili.com/video/BVxxx" --cookies chrome

# YouTube(必须加 cookies)
videosummarize "https://www.youtube.com/watch?v=xxx" --cookies chrome

# 抖音(走自带下载器,不用 cookies)
videosummarize "https://www.douyin.com/video/xxx"

# 小红书
videosummarize "https://www.xiaohongshu.com/explore/xxx" --cookies chrome

# 本地音视频
videosummarize ~/recordings/meeting.m4a -l zh
```

## 产出物存放(File Management)

CLI 把所有产出物固定写到 `~/.videosummarize/`,**不污染当前目录**:

```
~/.videosummarize/
├── manifest.json                ← 所有项目的索引(给 Agent 查 transcript 路径用)
├── 视频标题_1/                   ← 每个视频一个目录
│   ├── video.mp4                ← 原视频(--no-keep-video 跳过)
│   ├── audio.wav                ← 提取的 16kHz 单声道音频
│   ├── transcript.md            ← 核心产物,带时间戳
│   ├── transcript.json          ← (可选)JSON 格式
│   └── chunks/                  ← (内部)分块缓存,断点续传用
└── 视频标题_2/
    └── ...
```

- 每个视频 = 一个项目目录
- 视频和音频默认保留(可用 `--no-keep-video` / `--no-keep-audio` 删)
- `manifest.json` 跟踪所有项目元数据(URL、平台、模型、时间戳、transcript 格式)
- 用 `-o` 覆盖默认 workspace 路径

## Working with Transcripts(Agent 必读)

**transcript.md 是核心产物**。CLI 跑完 → Agent 读这个文件 → 出总结。

### 找 transcript 路径的三种方式

**方式 1**:CLI 跑完会**直接打印**路径,Agent 抓这一行就够了:
```
Done! 1 video(s) transcribed:
  Video Title Here
    project:    ~/.videosummarize/Video_Title_Here
    transcript: ~/.videosummarize/Video_Title_Here/transcript.md
```

**方式 2**:从 `manifest.json` 找:
```bash
cat ~/.videosummarize/manifest.json
# 每个项目有 "id"(目录名)和 "transcript_format"(md/txt/json/srt)
# 路径就是 ~/.videosummarize/{id}/transcript.{transcript_format}
```

**方式 3**:用 `videosummarize list` 看所有项目和路径。

### transcript.md 长这样

`-f md` 格式自包含:
- YAML frontmatter:title / date / source URL
- 时间戳片段:每行 `[HH:MM:SS]` 前缀
- 末尾完整全文拼接

**用户可能围绕同一视频问多个问题 → 每次都重新读 transcript**(它一直在项目目录里,可以反复读)。

## Quality Report(转录质量报告解读)

CLI 跑完会自动跑确定性质量检查并打印报告。Agent 看到下面这些警告时**主动告诉用户**:

| 警告 | 含义 | 建议动作 |
|------|------|---------|
| Coverage low | 转录没覆盖到音频结尾 | 可能要重下/重转 |
| Density low | 字符密度低 | 音乐/静音多的内容很正常 |
| Duplicate segments | 同样文字重复 | CLI 已自动去重,但建议 review 边界 |
| Large timestamp gaps | 时间戳间隔 > 30s | 检查是否有静音段 |
| Head/tail truncated | 开头/结尾缺失 | 可能要重下 |

如果质量检查通过 → 直接进入分析。出警告 → 告诉用户,让用户决定要不要重跑。

## 长视频参数推荐(>30min)

低内存机器(<4GB 可用)或长视频建议:
```bash
VS_BACKEND=faster videosummarize "URL" --cookies chrome -m small --chunk-size 600
```

- `VS_BACKEND=faster`:强制用 faster-whisper CPU 后端,**避免 mlx-whisper 在长视频/低内存时 GPU 崩溃**
- `--chunk-size 600`:把音频切 10min 一块并发转录(默认 5min)
- `-m tiny` / `-m base`:小模型,速度快,但中文长视频建议 `-m small` 或 `-m medium` 减少错字

### 长视频内部并行机制

CLI 对 ≥5min 的音频会**自动切片 + 并发转录**:
- 默认 chunk size:300s(5min),长音频自动适配
- 自适应:workers=1 + 长音频 → 30min chunk;多 workers → 默认大小
- 重叠保证句子不被切半,边界片段去重
- 并发 worker 数自动检测(CPU 核心数,min 2,max 4)
- **断点续传内置**:每个 chunk 立即保存,中断后再跑相同命令自动 resume

## 模型选择(速度 vs 准确度)

| 模型 | 大小 | 速度 | 中文准确度 | RAM | 推荐场景 |
|------|------|------|-----------|-----|---------|
| tiny | 75MB | 最快 | ⭐⭐(谐音错字多) | ~200MB | 临时验证、英文短视频 |
| base | 142MB | 快 | ⭐⭐⭐ | ~400MB | 日常使用(默认)|
| **small** | 488MB | 中 | ⭐⭐⭐⭐ | ~700MB | **中文推荐默认** |
| medium | 1.5GB | 慢 | ⭐⭐⭐⭐⭐ | ~1.8GB | 重要内容(技术访谈/会议)|
| large-v3 | 3GB | 最慢 | 最高 | ~3.5GB | 专业转写 |

- **中文内容**:`base` 通常够用,`small` 准确度更高
- **英文内容**:`base` 表现良好
- **混合语言**:`-l auto` + `small` 或更大模型

## Agent 决策矩阵(基于时长 + 内存推荐)

**处理视频前先评估资源,按下表选模型**:

| 视频时长 | 可用内存 | 推荐模型 | 预估时间(Apple Silicon)|
|---------|---------|---------|----------------------|
| < 10min | 任意 | small | < 1min |
| 10-30min | ≥ 4GB | small | 2-5min |
| 10-30min | < 4GB | base | 1-3min |
| 30min - 2h | ≥ 4GB | base | 10-30min |
| 30min - 2h | < 4GB | base | 10-20min |
| > 2h | 任意 | base | 30-60min+ |

**关键规则**:
1. **视频 > 1h**:开始转录前先告诉用户预估时间
2. **视频 > 2h**:除非用户明确要更高准确度,**只用 `base` 模型**
3. CLI 抽完音频会**打印 planning summary**(时长 / workers / 预估时间) — 用这个数据告诉用户,**不要自己猜时长**
4. 如果预估时间超过你的执行 timeout,告诉用户:"转录大约 X 分钟,如果超时,**重跑同样命令**会从中断处自动恢复"
5. **断点续传内置** — 重跑同样命令自动跳过已完成的 chunk

## 总结模板矩阵(读完 transcript 后选)

| 视频类型识别信号 | 模板 | 关键产出 |
|---------------|------|---------|
| 短科普/教程/演讲(单人讲) | **模板 1:单视频通用** | Summary + Key Points + Action Items |
| 同主题多个视频(课程/系列)| **模板 2:多视频学习笔记** | 主题整合 + 知识盲区 |
| 答疑/Q&A 形式 | **模板 3:Q&A 提取** | 问答对 + 时间戳 |
| 立场/观点对比 | **模板 4:对比分析** | 观点对比表 |
| **议程 + 决策 + 行动项**等关键词 | **模板 5:会议总结** | 决策 + Action Items 表 + 开放问题 |
| **1对N 问答**结构(主持人+嘉宾)| **模板 6:访谈 JTBD** | Jobs To Be Done + 痛点 + 金句 |
| **章节明确 + 知识密度高** | **模板 7:学习笔记** | 知识图谱 + 自测题 + 易错点 |
| 用户要发飞书 / 知识库归档 | **模板 8:飞书文档输出** | Lark-flavored Markdown |

完整 3 个真实场景示例见 [EXAMPLES.md](./EXAMPLES.md)。

## 默认长度规则

| 视频时长 | 默认总结长度 |
|---------|------------|
| < 10 分钟 | medium(800-1500 字) |
| 10-60 分钟 | long(1500-3500 字) |
| > 60 分钟 | xl(3500-8000 字)+ 分章节 |

用户可以说"短一点"、"详细一点"覆盖默认。

## 简明语言原则(强制)

- **目标读者**:小学毕业能看懂
- **专业术语**:首次出现必须括号解释,如 `JTBD(Jobs To Be Done,待完成的任务)`
- **句子长度**:平均一句不超过 35 字
- **避免**:"赋能"、"抓手"、"打通"、"闭环"、"颗粒度"等八股词,除非引用原文
- **保留**:数字、时间戳、人名、术语英文原文(便于查证)

---

## 8 个总结模板的详细格式

### 模板 1:单视频通用总结

适用:单个科普/教程/演讲视频。

```markdown
## Summary
[2-3 句概览]

## Key Points
- [核心要点 1]
- [核心要点 2]
- ...

## Detailed Notes
[按主题/时间戳组织]

## Action Items
- [ ] [若适用]
```

---

### 模板 2:多视频学习笔记

适用:课程/系列里多个 transcript 的整合。

```markdown
## Topic Overview
[这些视频整体覆盖什么主题]

## Consolidated Notes
### [主题 A]
- 来自视频 1:[关键点]
- 来自视频 3:[相关点]

### [主题 B]
...

## Knowledge Gaps
[视频提到但没讲透的部分]

## Study Questions
1. [基于内容的问题]
2. ...
```

---

### 模板 3:Q&A 提取

适用:答疑/Q&A 形式视频。

```markdown
## Questions & Answers

### Q: [视频里的问题]
**A:** [带时间戳引用的答案]
**Source:** [HH:MM:SS]

### Q: [下一个问题]
...
```

---

### 模板 4:对比分析

适用:跨视频立场/观点对比。

```markdown
## Comparison: [主题]

| Aspect | Video A | Video B |
|--------|---------|---------|
| [点] | [观点] | [观点] |

## Agreements
- ...

## Disagreements
- ...

## Synthesis
[你的整合理解]
```

---

### 模板 5:会议总结(Meeting Summary)

适用:会议录像 / Zoom 录制 / 腾讯会议 / 飞书会议等。

```markdown
## 会议总结

**会议时间**:[YYYY-MM-DD HH:MM-HH:MM,从转录第一行/最后一行时间戳推算]
**参会人**:[从转录抽取,标注角色]
**主题**:[一句话,会议讲的什么]

## 核心结论
- **结论 1**:[重大决策]
- **结论 2**:[重大决策]
- **结论 N**:...

## 讨论摘要
- **议题 A**:讨论了什么 → 形成什么观点 → [HH:MM:SS]
- **议题 B**:...

## 行动项

| 截止日 | 负责人 | 行动 | 来源时间戳 |
|-------|--------|------|----------|
| YYYY-MM-DD | 张三 | 跟进 X 数据 | [00:23:15] |
| YYYY-MM-DD | 李四 | 完成 Y 方案 | [01:05:42] |

## 已决策项
- [决策 1,带依据]
- [决策 2,带依据]

## 开放问题
- [尚未拍板的问题 1]
- [尚未拍板的问题 2]
```

**会议总结铁律**:
- ✅ 用"我们"语气,不带个人评价
- ✅ 行动项必须有"谁 + 做什么 + 啥时候"三要素,缺哪个就标"-"
- ✅ 决策和讨论分开,**不要把"讨论中"当成"已决策"**

---

### 模板 6:访谈总结(Interview / Podcast - JTBD 框架)

适用:用户访谈、产品调研、播客对话、人物专访。

```markdown
## 访谈总结

**访谈时间**:[YYYY-MM-DD]
**受访人**:[姓名,职位,行业背景]
**采访人**:[姓名,角色]
**访谈主题**:[一句话,主要聊什么]

## 受访人背景
[2-3 句:他是谁、做什么、为什么这次访谈值得听]

## 当前现状(Current State)
[他/他的团队现在怎么做这件事?用什么工具/方法?]

## JTBD(待完成的任务,Jobs To Be Done)

| 用户想完成的任务(JTBD) | 期望的结果 | 重要性 1-5 | 满意度 1-5 |
|---------------------|----------|-----------|----------|
| [Job 1] | [Outcome] | 5 | 2 |
| [Job 2] | [Outcome] | 4 | 4 |

## 当前方案的优点
- [优点 1,带原文金句和时间戳]
- [优点 2]

## 当前方案的痛点
- [痛点 1,带原文金句和时间戳]
- [痛点 2]

## 关键洞察(Key Insights)
- [让你"啊哈"的瞬间或反共识观点]
- [可能改变产品策略的发现]

## 金句摘录
> [原文金句 1] —— [HH:MM:SS]
> [原文金句 2] —— [HH:MM:SS]

## 后续动作
- [ ] [基于洞察该做什么]
```

---

### 模板 7:科普/教学视频学习笔记

适用:技术教程、知识科普、纪录片、课程录像。

````markdown
## 学习笔记

**视频标题**:[原标题]
**视频时长**:[X 分钟]
**主讲人**:[从转录抽取]
**主题领域**:[领域标签]

## 一句话总结
[这个视频教会你什么]

## 知识图谱

```
[核心概念]
  ├─ [子概念 A] ──[关系]── [子概念 B]
  ├─ [子概念 C]
  └─ [应用场景]
```

## 重点笔记(按章节)

### 1. [章节 1 标题]([HH:MM:SS]–[HH:MM:SS])
- [要点 1]
- [要点 2]
- **关键术语**:`术语` = 解释

### 2. [章节 2 标题]
...

## 易错点 / 反直觉的地方
- [常见误解 1] vs 正解
- [常见误解 2] vs 正解

## 自测题(检验是否真懂)
1. [问题 1] —— 参考答案见 [HH:MM:SS]
2. [问题 2]
3. [问题 3]

## 进一步学习建议
- [相关概念/资料/工具]
````

---

### 模板 8:飞书文档输出(可选)

适用:用户要把总结发到飞书 / Lark / 知识库归档。

在上面任一模板基础上,按 **Lark-flavored Markdown** 重组:

```markdown
<callout emoji="🎬" background-color="light-blue">
**视频来源**:[标题](原始 URL)
**时长**:HH:MM:SS  |  **平台**:B站/抖音/YouTube/小红书
**总结时间**:YYYY-MM-DD HH:mm
**模板**:[模板 X 名称]
</callout>

[此处嵌入对应模板的内容,合理使用 h2/h3、加粗、列表、callout、表格]

---

*由 videosummarize CLI 转录 + AI Agent 总结*
```

然后用 `feishu_create_doc`(若可用)或 `lark-doc` skill 创建文档:
- **title**:`🎬 {视频标题}`
- **markdown**:上面的内容
- **wiki_space**:`my_library`(默认)或用户指定

返回飞书文档链接给用户。**注意**:在飞书/微信内回复时,**URL 用纯文本**,不要包在 markdown `[]()` 里,避免被吞。

---

## 已知坑(Agent 必读)

| 现象 | 原因 | 解决方案 |
|------|------|---------|
| YouTube `Sign in to confirm not a bot` | 反机器人 | **必加** `--cookies chrome` |
| YouTube `Requested format is not available` | n-challenge 解算缺 JS runtime | 装 `deno`(`brew install deno`),CLI 自带 `remote_components: ["ejs:github"]` |
| 抖音 yt-dlp 报 `expat module` 错 | yt-dlp 抖音提取器 bug | 抖音走 CLI **自带下载器**(`douyin.py`),无需额外操作 |
| 长视频(>30min)mlx-whisper segfault `IOGPUMetalCommandBuffer` | mlx + Metal GPU 多 worker 冲突 | 加 `VS_BACKEND=faster` 切 CPU 后端 |
| 多个 CLI 进程并发跑 GPU 崩溃 | Apple Silicon Metal/MLX 不支持多进程并发 GPU | **必须串行**(单 CLI 多 URL 或一条一条跑) |
| 小红书页面跳登录看不了 | 反爬 | CLI 用 `--cookies chrome` 还能从浏览器 cookies 下载 |
| CDN 下载超时(`Read timed out`) | 大文件 + 弱网 | CLI 已内置 `retries: 10, fragment_retries: 10, socket_timeout: 30`,**重跑同样命令会自动 resume** |
| transcript 中文谐音错字多 | 用了 tiny 模型 | 升级到 `-m small` 或 `-m medium` |
| `videosummarize: command not found` | pipx 的 PATH 没加 | 重新跑 `pipx ensurepath`,**新开终端** |

## 🚀 高速场景:用 mavis-team 并行(可选)

如果机器装了 [mavis-team](file:///Users/mac/.mavis/agents/main/.builtin-skills/mavis-team/SKILL.md) skill,可以用 **agent 层并行** 进一步提速。

### 何时**应该**用 mavis-team

| 场景 | 原因 |
|------|------|
| **批量处理 ≥3 个视频** | 每个视频是独立 track,worker 各处理一个,owner 合并对比 |
| **同主题多源对比研究** | B站 + YouTube + 小红书 同一关键词,多 worker 并行采集+总结 |
| **长视频多视角分析** | 同一 transcript 出"会议总结 + 决策要点 + 行动项"3 个独立视角 |
| **质量重要,要独立验证** | 一个 worker 出总结,另一个 worker 回原文校对(防幻觉) |

### 何时**不该**用 mavis-team

| 场景 | 原因 |
|------|------|
| 单个短视频(<10min) | 单 agent 直接跑 CLI 就够了,team 反而慢 |
| 用户只要一份总结 | 没有"独立 track",team 没价值 |
| 切单个 transcript 给多 worker 分段总结 | ❌ **禁止** — 每段缺上下文质量差,且 CLI 内部已有 chunk 并行转录 |

### 关于"切片并行"的真相

> **CLI 内部已经做了音频切片 + 并发转录**(ThreadPoolExecutor + chunked,4 worker 默认)
> 这是 **CPU/GPU 层并行**,1h 视频转录从 1h 缩到 ~15min。
>
> mavis-team 的"并行"是 **Agent 层并行**,适合**多个独立任务**,不是切单视频。
> 一个视频已经被 CLI 内部并行了,再用 team 切只会增加协调成本。

### Plan YAML 模板:批量处理多视频

```yaml
version: 1
plan:
  name: '批量总结 5 个 AI 访谈视频'
  max_concurrency: 5
  max_consecutive_failures: 2
  max_cycles: 8
tasks:
  - id: video-1-bilibili
    title: '处理 B站访谈视频 1'
    prompt: |
      使用 videosummarize skill 处理这个 B站视频:https://www.bilibili.com/video/BVxxx
      命令:VS_BACKEND=faster videosummarize "URL" -m small -f md -l zh --cookies chrome --chunk-size 600
      读 transcript.md 后,套模板 6(访谈 JTBD)出总结,写到 deliverable.md
    assigned_to: general
    verified_by: verifier
    verify_prompt: '回到 transcript.md 抽样 5 个时间戳,验证总结里的引用确实来自原文,没有幻觉'
    timeout_ms: 1800000

  - id: synthesis
    title: '跨视频对比 + 整合总结'
    prompt: |
      读所有 deliverable.md,套模板 4(对比分析):
      - 列出各视频对同一主题的不同观点
      - 标出共识和分歧
      - 每个观点带原视频时间戳引用
    assigned_to: general
    depends_on: [video-1-bilibili]
    verified_by: verifier
    verify_prompt: '抽查每个对比观点的原视频时间戳,确认引用准确'
    timeout_ms: 1800000
```

### 给 worker 的提示模板(避坑)

每个 worker 的 prompt 末尾**必须**加这几句:

```
注意事项:
- 不要轮询 CI / 不要 sleep — worker 30 分钟硬上限,生产 deliverable.md 后立即退出
- 必须读 transcript.md 后再写总结,不要凭印象编造
- 总结要带时间戳引用,方便用户回看原片
- 用 small 模型(中文准确度 OK + 速度合理)
- 长视频用 VS_BACKEND=faster + chunk-size 600 避免 GPU 崩溃
```

## 完整 CLI 参考

```
videosummarize [OPTIONS] URL [URL...]
videosummarize doctor
videosummarize list

常用选项:
  -m, --model [tiny|base|small|medium|large-v3]    模型 [默认 base]
  -f, --format [txt|md|json|srt]                   转录输出格式 [默认 txt]
  -l, --language TEXT                              语言 zh/en/ja/auto [默认 zh]
  -o, --output-dir PATH                            workspace 路径 [默认 ~/.videosummarize]
  --cookies TEXT                                   浏览器 cookies chrome/safari/edge/firefox
  --chunk-size INT                                 音频分块大小(秒)[默认 300],0 = 禁用
  -p, --parallel INT                               并发 worker 数 [默认 自动]
  --no-keep-video                                  转录后删视频
  --no-keep-audio                                  转录后删音频
  -v, --verbose                                    详细输出

子命令:
  doctor       检查环境(ffmpeg/deno/whisper 后端/模型缓存)
  list         列出所有已转录的项目

环境变量:
  VS_BACKEND=faster   强制用 faster-whisper CPU 后端(长视频/低内存场景必须)
  VS_BACKEND=mlx      强制用 mlx-whisper Apple Silicon GPU(仅 macOS ARM)
  VS_BACKEND=openai   强制用 openai-whisper(兜底)
```

## Tips(实战小贴士)

- 用 `-f md` 做分析 — YAML frontmatter + Markdown 结构最好解析
- 需要剪视频字幕用 `-f srt`,要程序化处理用 `-f json`
- 视频和音频默认保留在项目目录,方便回看
- 想省盘:`--no-keep-video --no-keep-audio` 只留 transcript
- 长视频(> 1h)考虑 `small` 或 `medium` 模型,中文错字会少很多
- 不确定环境状态:`videosummarize doctor` 一键诊断
- 看所有处理过的视频:`videosummarize list`
- 国内下模型慢:`export HF_ENDPOINT=https://hf-mirror.com` 提速 5-10 倍
- 中断后重跑同样命令 → CLI 自动从断点恢复(checkpoint 内置)
