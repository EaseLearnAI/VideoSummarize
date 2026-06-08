---
name: podcast-digest
description: |
  把任意一个 YouTube 播客视频转成「PM 视角」的全中文深度学习笔记(v6: 全中文 + Obsidian 归档)。

  **强制触发**: 当用户消息中出现以下任一情况, 使用本 skill, **禁止**用 web_fetch / browser 自行抓取视频:
  - URL 含 youtube.com/watch?v= 或 youtu.be/
  - 关键词: "总结这个 YouTube"、"播客总结"、"PM 视角拆解"、"深度学习笔记"

  **v6 关键升级(相对 v5)**:
  - 输出 **全中文**(只保留人名 / 产品名 / 公司名 / 无中文对应的技术术语 eg eval/agent/harness/RLHF)
  - 输出 **纯 Markdown**(替代飞书 XML), Obsidian 原生渲染
  - 归档到 **/2_学习/21_播客笔记/**(替代之前的 /youtube博客/ 不存在路径)
  - **删除飞书推送步骤**(用户不再需要)
  - 吸收老版 youtube-podcast-digest 的 LaterCast 「3 句金句开场」 优点(在 H2 主题段之前加 3 句嘉宾原话开场, 中英双语并列)
  - frontmatter 加强版 — 完整 tags / key_concepts / 嘉宾信息, 便于 Obsidian dataview 检索

  **核心流程(9 步, 已删飞书步骤)**:
  1. yt-dlp 拉英文字幕(零 GPU)→ vtt 清洗 → 字幕完整性检查
  2. 转录预检(广告段位置 / gibberish / 说话人)
  3. ★ Section A: Claude 读 transcript 输出 `qa_extraction.md`(JSON Q&A 列表)
  4. ★ extract_qa_validator.py 校验提取(主题数 / 子 Q&A 数 / quote 反查 / 时间戳 / 覆盖率)
  5. ★ 暂停让用户 review qa_extraction.md(可选, 首跑必做)
  6. Section B: Claude 读 qa_extraction.md 生成 `note.md`(纯 MD, 全中文)
  7. validator.py 校验 note(字数 / H2 数 / 沐阳延伸思考 / 全中文比例)
  8. 归档到 Obsidian Vault `/Users/mac/Documents/Obsidian Vault/2_学习/21_播客笔记/<date>_<channel>_<嘉宾>/`
  9. 任务完成通知(只在 IM 提示路径, 不再推飞书)

  与本地 videosummarize-skill 的区别:
  - 本 skill 只拿字幕, 零 GPU 占用, 不影响办公
  - 本 skill 输出的是 PM 视角主题组 + 沐阳延伸思考的深度笔记(LaterCast 风格)
  - videosummarize-skill 是 fallback: 视频无字幕 / 字幕质量差 时才走它
---

# YouTube Podcast Digest — PM 视角 · 全中文版(v6 · Obsidian 原生)

> 输入一个 YouTube URL, 输出符合「PM 视角主题段 + 沐阳延伸思考」的**全中文** Markdown 深度笔记。
> v6 升级核心: 输出全中文(仅保留人名/产品名/必要术语), 纯 MD 格式, Obsidian 原生渲染, 删除飞书推送。
> 零下载, 零 GPU, 完全在 Claude Code 内闭环。

## 这个 skill 做什么(9 步流程, v6 已删飞书)

### Step 1: 拉字幕
`run.sh <URL>` → `/tmp/ypd-<id>/<id>.en.vtt` + `title.txt / channel.txt / duration.txt / upload_date.txt`

### Step 2: vtt 清洗
`vtt_to_transcript.py` 去 rolling-display 重复 → `/tmp/ypd-<id>/transcript.txt`(带 [HH:MM] 时间戳)

### Step 3: 字幕完整性检查 ★ 硬阈值
`subtitle_integrity_check.py <URL> <transcript.txt>` → 报 yt 时长 vs 转录覆盖 + 时间戳跳跃 + 词密度异常

**强制规则**: 字幕完整度必须 ≥ 95%(目标 97%+)。< 95% 直接 FAIL — 必须重新拉字幕或确认 transcript 完整后才能进 Step 4。字幕不完整等于在残缺信息上提取, 后续所有 Q&A 都不可信。

### Step 4: 转录预检
`python3 transcript_check.py transcript.txt > transcript_check.json` → JSON 文件: 广告段位置 / gibberish / 说话人 / 命名实体

(脚本默认输出到 stdout, **必须 redirect 到 transcript_check.json**, 否则 Step 4.5 会找不到文件。)

### Step 4.5: Q&A 提取 (Section A)
Claude 读 `transcript.txt` + `transcript_check.json`, 按 `LATERCAST_PROMPT.md` 的 **Section A** 输出:

```
/tmp/ypd-<id>/qa_extraction.md
```

格式: frontmatter(video_id/url/total_topics/total_qa_count/status) + Markdown 包装的 JSON code block(topics → sub_qa)

★ v6 注意: Q&A 提取产物的 `host_question`/`guest_answer_thread` 等字段也用**中文**(只保留人名/产品名/必要技术术语原文)

### Step 4.6: Q&A 提取校验
`extract_qa_validator.py qa_extraction.md transcript.txt`

校验项:
1. frontmatter 必填字段
2. JSON 能解析
3. **字幕完整度 ≥ 95% (硬阈值, FAIL)** — 字幕不完整等于残缺信息上提取
4. **提取密度 words_per_qa ≤ 1000** — 每 Q&A 平均承载 transcript 词数, > 1000 说明严重漏问题
5. 每个 guest_key_quote 能在 transcript grep 到(防幻觉, 80% 通过)
6. 时间戳单调递增
7. 主题之间未覆盖间隔 ≤ 10 分钟(无大漏)
8. 最后主题覆盖到视频 85%+(无尾部丢失)
9. 每个 sub_qa 必填字段齐全

**已删除**: 主题组数/Q&A 数固定区间约束。不同播客密度天然不同 — 50min 精华访谈可能 30+ Q, 50min 散漫闲聊可能只 8 Q, 都合理。validator 不再卡这个数, 只卡完整度 + 真实性 + 密度健康度。

FAIL → Claude 重新提取(最多 2 次)

### Step 4.7: 暂停 review(首跑必做)
把 qa_extraction.md 路径告诉用户, 让用户:
1. 看「提取统计」是否符合期待
2. 抽 3 个 quote grep transcript 验证
3. 标记「这里漏了」或「这里凑数了」

用户给绿灯后才进 Step 5。**这个暂停是硬质量关。**

### Step 5: 生成最终深度笔记 (Section B v6) ★ 全中文 + 纯 MD
Claude **先读 `USER_PROFILE`(主在 Vault, 备份在 skill)**, 再读 `qa_extraction.md`(不再回去读 transcript), 按 `LATERCAST_PROMPT.md` 的 **Section B v6** 输出:

```
/tmp/ypd-<id>/note.md  (纯 Markdown, 全中文, 4000-8000 字)
```

v6 关键转变(相对 v5):
- **输出全中文**, 不再中英混排
- **纯 Markdown**, 不再飞书 XML
- 加入 **3 句嘉宾原话开场**(从老版 LaterCast 吸收, 英文原话 + 中文翻译并列)
- 6-8 个 H2 主题段, 每段 200-400 字: 嘉宾思路链白描 + 1-2 句原话引用(双语) + 1-2 句**沐阳延伸思考**
- 「写在最后」LaterCast 风格的思路浓缩段(不是行动清单)
- 底部 frontmatter 加强(tags / key_concepts / 嘉宾信息, 便于 dataview)

### Step 6: 校验 note (v6 validator)
`validator.py note.md --qa-extraction qa_extraction.md` → 检查 v6 规则:
- 字数 4000-8000
- H2 主题段数 [5, 10] 且每段 ≥ 200 字
- 「沐阳延伸思考」频次 ≥ H2 数的 80%
- **★ v6 新增: 全中文比例 ≥ 85%**(中文字符 / (中文字符 + 英文单词))
- 3 句开场金句存在(英文+中文双语)
- 反向检查无飞书 XML 标签残留(`<callout>` `<whiteboard>` `<blockquote>` 应改成 MD 引用块)

**FAIL 处理**: Claude 根据 validator issues 自动修复 note.md + 重跑 validator, 最多 2 次; 仍 FAIL 则把 issues 清单 + 当前 note 摘要发给用户 review 后决定(force pass / 手动 fix / 放弃)。

### Step 7: Vault 归档

**目录命名公式**:
```
/Users/mac/Documents/Obsidian Vault/2_学习/21_播客笔记/<YYYY-MM-DD>_<channel_short>_<嘉宾名_下划线>_<视频主题中文要点 5-15 字>/
```

子规则:
- `<YYYY-MM-DD>` = upload_date.txt 内容(YYYYMMDD 转 YYYY-MM-DD)
- `<channel_short>` = channel.txt 去标点空格取主体名(eg "Lenny's Podcast" → "Lennys" / "20VC with Harry Stebbings" → "20VC" / "The Tim Ferriss Show" → "TimFerriss")
- `<嘉宾名_下划线>` = 从 title.txt 抽嘉宾英文名, 空格用 `_` 替换(eg "Cat Wu" → "Cat_Wu" / "Sam Altman" → "Sam_Altman")
- `<视频主题中文要点>` = Claude 从 title 翻译/凝练成 5-15 字中文(eg "Anthropic产品团队为什么这么快" / "OpenAI内部如何做战略对齐")

示例: `2026-04-23_Lennys_Cat_Wu_Anthropic产品团队为什么这么快/`

**目录里 4 个文件**(从 /tmp/ypd-<id>/ 复制):
- `transcript.txt`(英文字幕原始, 供查证)
- `qa_extraction.md`(中间过程, 可被用户/dataview 检索)
- `note.md`(最终笔记, **纯 Markdown 全中文**, Obsidian 原生渲染)
- `meta.yaml`(frontmatter 元数据, **必须按下面模板**)

**meta.yaml 模板**(★ 必须按此 schema, 否则失去跨期 dataview 检索能力):
```yaml
---
source: youtube
video_id: {从 video_id.txt}
url: {YouTube URL}
channel: {channel.txt 原文}
host: {从 title/channel description 抽取主持人名}
guests: [{嘉宾名 1}, {嘉宾名 2}]
guest_role: {嘉宾职位描述, 中文}
duration_min: {duration.txt 转分钟数}
upload_date: {upload_date.txt YYYY-MM-DD}
ingested_at: {ISO timestamp}

# 字幕完整性(v6 硬阈值 >= 95%)
subtitle_coverage_pct: {从 subtitle_integrity_check.py stdout 抓数字}
yt_duration_min: {同上}
transcript_coverage_min: {同上}
subtitle_check_status: PASS

# Q&A 提取层
extraction_model: claude-opus-4-7
total_topics: {从 qa_extraction.md frontmatter}
total_qa_count: {同上}
extraction_status: PASS
extraction_validator: extract_qa_validator.py v6
quotes_total: {同 total_qa_count}
quotes_not_found: {validator stdout 抓}
words_per_qa: {transcript_words / total_qa_count}

# v6 全中文深度笔记
note_status: PASS
note_file: note.md
note_word_count: {validator stdout effective_chars 数字}
note_h2_topic_count: {validator stdout h2_topic_count 数字}
note_extension_thinking_pct: {validator stdout}
note_chinese_ratio: {validator stdout 全中文比例}
note_validator: validator.py v6
note_completed_at: {ISO timestamp}

# 标签和概念(便于 Obsidian dataview)
tags: [youtube, 播客, {channel-slug}, {嘉宾-slug}, ai-pm, ...]
key_concepts:
  - {从 note.md 主题段标题抽 8-12 个中文 slug}

# 流程版本
skill_version: podcast-digest-v6
---
```

### Step 8: 任务完成通知

**只在本地通知, 不推飞书**:

```bash
echo "✓ 完成: <视频中文主题>"
echo "  Vault 路径: /Users/mac/Documents/Obsidian Vault/2_学习/21_播客笔记/<dirname>/"
echo "  note.md (字数 X / H2 段数 Y / 全中文比例 Z%)"
echo "  qa_extraction.md (主题 A / Q&A 总数 B)"
```

如果用户启用了飞书通知机器人, 按 CLAUDE.md 规约发完整 markdown 通知 — 但 **不推送 note 本身到飞书**。

## 强制规则(★ v6)

1. **必须用 `--cookies-from-browser chrome`** — YouTube 反机器人
2. **必须先清洗 vtt** — 原始含 3 倍重复
3. **优先用英文字幕** — YouTube 中文翻译质量极差, 让 Claude 自己翻译
4. **★ 字幕完整度必须 ≥ 95%** — 这是整个流程的硬前置, < 95% 直接 STOP, 必须重拉字幕
   - **重拉操作清单**: (a) 先重跑一次 `run.sh <URL>`(网络抖动可能) (b) 检查 `--cookies-from-browser chrome` cookies 是否失效 → 重新登录 chrome (c) 尝试加 `--sub-langs en,zh,en.*` 多语言 fallback (d) 仍失败 → 自动转 videosummarize-skill (mlx-whisper 路线)
5. **嘉宾原话引用必须真实** — extract_qa_validator 反查 80%+
6. **Q&A 提取跟视频内容走, 不套硬区间** — 不同播客密度天然不同, 唯一指标是 words_per_qa ≤ 1000(不漏问题)
7. **首跑必须暂停让用户 review Q&A 提取** — 这是硬质量关
8. **★ v6 输出全中文** — 中文比例 ≥ 85%, 仅保留: 人名(eg Lenny / Cat Wu) / 产品名(eg Claude Code / Co-work / Slack) / 公司名(eg Anthropic / OpenAI) / 无中文对应的技术术语(eg eval / agent / harness / RLHF / context engineering / vibe-coding) / 嘉宾 key quote 的英文原话(放 blockquote, 下面加一行中文翻译)
9. **★ v6 输出纯 Markdown** — 不允许 `<callout>` `<whiteboard>` `<blockquote>` 等飞书 XML 标签, 用 MD 原生语法(# ## > ``` --- 表格)
10. **失败时返回 ERROR 并指向 fallback** — Step 1 run.sh exit 3/4/5 → 自动转 videosummarize-skill (mlx-whisper 路线); 不要让用户在卡住时缺路线图
11. **★ v6 已删飞书推送步骤** — 流程到 Step 7 (Vault 归档) 就结束, 不再有 lark-cli docs +create

## 中英文规则细则(v6 必读)

### ✅ 保留英文原文的情况
- **人名**: Lenny Rachitsky / Cat Wu / Sam Altman / Brendan Foody
- **产品名**: Claude Code / Co-work / ChatGPT / Cursor / Codex
- **公司名**: Anthropic / OpenAI / Google / Mercor
- **技术术语 — 没有公认中文对应**:
  - eval / evals(不翻"评估", 因这词在 AI 上下文有特定含义)
  - agent / agentic
  - harness(模型外壳)
  - context engineering(上下文工程, 但保留英文)
  - RLHF / RLAIF
  - vibe-coding / vibe-check
  - prompt / prompting
  - fine-tuning
  - trace(模型追踪)
  - swe-bench / GPQA(特定 benchmark 名)
- **嘉宾 key quote**: blockquote 里放英文原话, 下面单独一行加中文翻译并标 *(译: ...)*

### ❌ 必须翻译成中文的情况
- 描述性词汇: anti-pattern → 反模式 / first-principles → 第一性原理 / unifying mission → 统一使命 / overhead → 协调成本
- 形容词副词: ambitious / hairy / amorphous / extreme — 全部翻译
- 动词短语: ship a product → 上线产品 / build prototype → 做原型 / fix the hole → 补漏洞
- 概念词: dependency → 依赖 / partner team → 协作团队 / use case → 使用场景 / roadmap → 路线图

### ✅ 引用嘉宾原话的双语格式

```markdown
> "The two most important things are one this unifying mission... and the second is focus."
>
> *(译: 最重要的两件事, 一是这个统一使命... 二是聚焦)*
```

### 自检
写完 note.md 后, 数一下「英文短语 / 英文句子」(不含上述保留类)的数量 — 如果超过 5 处, 说明翻译不彻底, 重写。

## 与 videosummarize-skill 的边界

| 场景 | 用什么 |
|---|---|
| YouTube 视频 + 有字幕 + 想要 PM 视角全中文深度笔记 | **本 skill** (podcast-digest) |
| YouTube 视频 + 无字幕 / 字幕质量差 | videosummarize-skill (走 mlx-whisper) |
| B 站 / 抖音 / 小红书 | videosummarize-skill (走自带下载器) |
| 本地音视频文件 | videosummarize-skill |
| 要 7 种通用模板(Q&A / 会议 / JTBD 等) | videosummarize-skill |
| 想要更轻量、不走 Q&A 中间产物 | youtube-podcast-digest (老版, LaterCast 公众号体) |

## 关键文件

| 文件 | 用途 |
|---|---|
| `SKILL.md`(本文件) | 触发规则 + 9 步流程定义 |
| `LATERCAST_PROMPT.md` | Section A(Q&A 提取) + Section B(全中文笔记生成)两段 prompt |
| `vtt_to_transcript.py` | YouTube WEBVTT 字幕清洗脚本 |
| `transcript_check.py` | 转录预检(广告段 / gibberish / 说话人) |
| `subtitle_integrity_check.py` | 字幕完整度验证(yt 时长 vs 覆盖) |
| `extract_qa_validator.py` | Q&A 提取层校验 |
| `validator.py` | v6 最终 note.md 校验(MD 格式 / 全中文比例 / 主题段数 / 沐阳延伸思考) |
| `USER_PROFILE.md` | 沐阳个人偏好(skill 内副本, 主版本在 Obsidian Vault) |
| `run.sh` | 一键拉字幕(被流程调用) |
