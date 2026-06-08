---
name: youtube-podcast-digest
description: |
  把任意一个 YouTube 播客视频转成「晚点再听 LaterCast」风格的 3500-3900 字**全中文**深度总结(v2 轻量版)。

  **强制触发**: 当用户消息中出现以下任一情况, 使用本 skill, **禁止**用 web_fetch / browser 自行抓取视频:
  - URL 含 youtube.com/watch?v= 或 youtu.be/
  - 关键词: "总结这个 YouTube"、"播客总结"、"LaterCast 风格"、"晚点再听风格"、"快速总结"

  **本 skill 的定位 — 轻量版**:
  - 一步到位(transcript → note), 不走 Q&A 中间产物, 不做用户 review 暂停
  - 适合用户明说「不用这么认真, 快速出一个能看的」的场景
  - 适合不那么重要的视频, 或第一次 sample 一个新节目
  - 想要深度版(8-9 步流程 + Q&A 中间产物 + 用户 review)用 `podcast-digest` 替代

  **v2 关键变化(相对老版)**:
  - **输出全中文**(中文比例 ≥ 85%, 仅保留人名 / 产品名 / 必要技术术语)
  - **删除飞书推送**, 只归档到 Obsidian Vault
  - 归档路径改为 **/2_学习/21_播客笔记/**(跟 podcast-digest 一致, 便于统一检索)
  - 引用嘉宾原话时, 英文原话下面加一行中文翻译

  核心流程: yt-dlp 拿英文字幕 → vtt 清洗 → Claude 按 LATERCAST_PROMPT.md 生成全中文总结 → validator.py 校验 → 落地到 Obsidian Vault。
---

# YouTube Podcast Digest — LaterCast 风格 · 全中文 · 轻量版 (v2)

> 输入一个 YouTube URL, 输出一篇符合「晚点再听 LaterCast」公众号风格的**全中文**深度总结。
> 零下载, 零 GPU, 完全在 Claude Code 内闭环。归档到 Obsidian Vault, 不推飞书。

## 这个 skill 做什么

1. **拉字幕**: 用 `yt-dlp --skip-download --write-auto-subs` 拿 YouTube 自动生成的英文字幕(WEBVTT 格式), 不下载视频本体, 不占 GPU
2. **清洗字幕**: 用 `vtt_to_transcript.py` 把 YouTube rolling-display 格式的重复字幕去重, 合并成纯文本转录
3. **生成总结**: Claude(当前的你)读完转录后, 按 `LATERCAST_PROMPT.md` 的模板生成 **3500-3900 字全中文**深度总结
4. **质量校验**: 用 `validator.py` 检查结构是否符合 LaterCast 标准(H2 数 / 引用数 / 加粗位置 / 字数 / 中文比例)
5. **入库**: 写到 `/Users/mac/Documents/Obsidian Vault/2_学习/21_播客笔记/<date>_<channel>_<title>/note.md`, 带 frontmatter

## 强制规则

1. **必须用 `--cookies-from-browser chrome`** — YouTube 反机器人, 否则字幕拉不下来
2. **必须先清洗 vtt** — 原始 vtt 含 3 倍重复行, 不清洗直接喂模型会浪费 token 且影响理解
3. **优先用英文字幕** — YouTube 中文自动翻译质量差(把 "Opus 4.8" 翻成 "新车 / 八滴"), 必须用英文字幕让 Claude 自己翻译
4. **★ v2: 输出全中文** — 中文比例 ≥ 85%, 仅保留: 人名 / 产品名 / 公司名 / 无中文对应的技术术语(eval / agent / harness / RLHF / context engineering / vibe-coding 等)
5. **嘉宾原话引用必须真实** — 从转录里挑, 不可编造或意译失真; **引用保留原始英文, 但下面单独一行加中文翻译**(LaterCast 风格基础上的双语并列)
6. **字数 3500-3900 是硬指标** — 短视频(< 15 分钟)可放宽到 3000-3500; 长视频(> 1 小时)必须落在标准区间
7. **失败时返回 ERROR** — 如果视频私密 / 无字幕 / 字幕过短(< 500 词), 直接返回 `ERROR: <原因>` 给用户, 让用户决定是否走 videosummarize-skill fallback
8. **★ v2 已删飞书推送** — 流程到 Step 5 入库就结束, 不再调用 lark-cli

## 流程详解(给 Claude 自己执行)

### 步骤 1: 拉字幕

```bash
mkdir -p /tmp/ypd-<video_id> && cd /tmp/ypd-<video_id>
yt-dlp \
  --skip-download \
  --write-auto-subs \
  --write-subs \
  --sub-langs "en" \
  --sub-format "vtt" \
  --cookies-from-browser chrome \
  --sleep-interval 3 --max-sleep-interval 8 \
  -o "%(id)s.%(ext)s" \
  --print-to-file "%(title)s" title.txt \
  --print-to-file "%(channel)s" channel.txt \
  --print-to-file "%(duration)s" duration.txt \
  --print-to-file "%(upload_date)s" upload_date.txt \
  "<YouTube URL>"
```

如果 `<video_id>.en.vtt` 不存在或 < 5KB → 返回 `ERROR: 无英文字幕可用`

### 步骤 2: 清洗 vtt

```bash
python3 ~/.claude/skills/youtube-podcast-digest/vtt_to_transcript.py \
  /tmp/ypd-<video_id>/<video_id>.en.vtt \
  --with-timestamps \
  > /tmp/ypd-<video_id>/transcript.txt
```

读 `transcript.txt`, 统计字数。如果 < 500 词 → `ERROR: 字幕过短`。

### 步骤 3: 生成总结

读取以下文件:
- `~/.claude/skills/youtube-podcast-digest/LATERCAST_PROMPT.md` — 总结模板
- `/tmp/ypd-<video_id>/transcript.txt` — 清洗后的英文转录
- `/tmp/ypd-<video_id>/title.txt` `channel.txt` `duration.txt` `upload_date.txt` — 元数据

按 LATERCAST_PROMPT 的 8 段结构生成**全中文**总结。**注意**:
- 你就是 Claude, 直接在自己上下文里读完转录后生成总结, 不需要调外部 API
- 输出长度严格控制在 3500-3900 等效字数(中文字符 + 英文单词 × 2)
- 短视频(原转录 < 1500 词)可放宽到 3000-3500
- 嘉宾引用必须从转录里找到原句, 保留英文, **下面加一行中文翻译**
- **★ v2: 正文几乎全中文** — 人名/产品名/必要技术术语保留, 其他全部翻译成中文

写入: `/tmp/ypd-<video_id>/draft.md`

### 步骤 4: 校验

```bash
python3 ~/.claude/skills/youtube-podcast-digest/validator.py \
  /tmp/ypd-<video_id>/draft.md
```

如果 FAIL, 根据 issues 重写一次。2 次仍 FAIL → 标记 `validation: NEEDS_REVIEW` 入库, 通知用户。

### 步骤 5: 入库(Obsidian Vault, 不推飞书)

```bash
# 准备元数据变量
DATE_RAW=$(cat /tmp/ypd-<video_id>/upload_date.txt)  # YYYYMMDD
DATE="${DATE_RAW:0:4}-${DATE_RAW:4:2}-${DATE_RAW:6:2}"  # YYYY-MM-DD
CHANNEL=$(cat /tmp/ypd-<video_id>/channel.txt)
CHANNEL_SAFE=$(echo "$CHANNEL" | tr -d "'." | sed -e 's/ /_/g' | cut -c1-30)
# 嘉宾名 + 中文主题由 Claude 在 thinking 阶段从 title 抽出, 作为变量 GUEST_KEY 和 TOPIC_CN

# 目录命名: <date>_<channel_short>_<guest_key>_<topic_cn>
TARGET="/Users/mac/Documents/Obsidian Vault/2_学习/21_播客笔记/${DATE}_${CHANNEL_SAFE}_${GUEST_KEY}_${TOPIC_CN}"
mkdir -p "$TARGET"

# 写入 note.md(带 frontmatter)
cat > "$TARGET/note.md" <<EOF
---
source: youtube
video_id: <video_id>
url: <youtube_url>
channel: $CHANNEL
host: <主持人名>
guests: [<嘉宾名 1>]
guest_role: <嘉宾职位描述, 中文>
duration_min: $(($(cat /tmp/ypd-<video_id>/duration.txt) / 60))
upload_date: $DATE
ingested_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
word_count: <实际等效字数>
chinese_ratio: <validator stdout 中文比例>
summary_model: claude-opus-4-7
summary_path: yt-dlp+claude
validation: PASS
skill_version: youtube-podcast-digest-v2
tags: [youtube, 播客, $CHANNEL_SAFE, <嘉宾-slug>]
key_concepts:
  - <从 note 主题中抽 5-8 个中文 slug>
---

<总结正文>
EOF

# 保留 transcript 供日后审核
cp /tmp/ypd-<video_id>/transcript.txt "$TARGET/transcript.txt"

# 清理临时
rm -rf /tmp/ypd-<video_id>
```

### 步骤 6: 任务完成通知(★ v2: 不推飞书, 只本地提示)

```bash
echo "✓ 完成: <视频中文主题>"
echo "  Vault 路径: $TARGET"
echo "  note.md (字数 X / H2 段数 Y / 中文比例 Z%)"
```

## 已知坑与解决

| 坑 | 表现 | 解决 |
|---|---|---|
| YouTube 报 `Sign in to confirm you're not a bot` | 没加 cookies | `--cookies-from-browser chrome`, **已写进流程** |
| YouTube 报 `Requested format is not available` | n-challenge 解算需要 JS | `brew install deno`, **已装** |
| 中文字幕翻译离谱(Opus 4.8 → 新车) | YouTube 自动翻译质量差 | 只拉英文字幕, 让 Claude 自己翻译, **已写进规则** |
| 字幕重复 3 倍 | YouTube rolling display 格式 | 用 `vtt_to_transcript.py` 清洗, **已写脚本** |
| 字数控制不住 | 模型对字数约束不敏感 | validator 检测后让 Claude 重写, **已写校验** |
| 中文字符 + 英文单词混算 | 直接 len() 会高估 | validator.py 用 中文字符 + 英文单词×2 等效统计, **已写正确逻辑** |
| **★ v2: 中英混排太多** | 模型保留太多英文短句 | validator 加中文比例 ≥ 85% 校验, FAIL 重写 |
| 长视频(> 1h)单次塞不下 | Claude 上下文限制 | 当前实现先全塞(20w token 上下文够, 8 小时也只 30k 字), 后续超长再加 chapter map-reduce |

## 与 podcast-digest 的边界

| 场景 | 用什么 |
|---|---|
| 重要视频 / 要做严肃学习笔记 / 想要 Q&A 中间产物 / 想介入 review | **podcast-digest**(深度版, 9 步流程) |
| 快速看一个新节目 / sample / 不那么重要 / 一次性消费 | **本 skill**(youtube-podcast-digest, 轻量版) |
| YouTube 视频 + 无字幕 / 字幕质量差 | videosummarize-skill(走 mlx-whisper) |
| B 站 / 抖音 / 小红书 | videosummarize-skill(走自带下载器) |
| 本地音视频文件 | videosummarize-skill |

## 关键文件

| 文件 | 用途 |
|---|---|
| `SKILL.md`(本文件) | 触发规则 + 流程定义 |
| `LATERCAST_PROMPT.md` | LaterCast 风格全中文总结模板(给 Claude 自己读) |
| `vtt_to_transcript.py` | YouTube WEBVTT 字幕清洗脚本 |
| `validator.py` | 输出质量校验(v2: 加中文比例 ≥ 85% 检查) |
| `run.sh` | 一键脚本(给定 URL 跑完前 2 步, 留 Claude 生成总结) |
