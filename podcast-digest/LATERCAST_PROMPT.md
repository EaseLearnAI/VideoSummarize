# PM 视角播客深度拆解 · Prompt 模板 (v6 · 全中文 · 纯 Markdown · Obsidian 原生)

> 这是 `podcast-digest` skill 的核心指令模板。v6 拆成两个阶段:
> - **Section A**: 先做 Q&A 提取(产出 `qa_extraction.md`, JSON + MD 包装)
> - **Section B**: 基于已提取的 Q&A 写最终深度笔记(产出 `note.md`, **纯 MD 全中文**)
>
> 关键转变(相对 v5):
> 1. 输出**全中文**(中文比例 ≥ 85%, 仅保留人名/产品名/必要技术术语)
> 2. 输出**纯 Markdown**(不再飞书 XML — 不允许 `<callout>` `<whiteboard>` `<blockquote>` 等)
> 3. 加入**3 句嘉宾原话开场**(从老版 LaterCast 吸收, 英文 + 中文翻译并列)
> 4. 删除飞书推送步骤(归档到 Obsidian Vault 后流程结束)

---

## 输入(两个阶段共用)

- `transcript.txt` — 已清洗的英文转录(带 `[HH:MM]` 时间戳)
- `transcript_check.json` — 转录预检结果(广告段位置 / 说话人识别 / gibberish 评分)
- `subtitle_integrity_check` 输出 — **字幕完整度 ≥ 95% 才能继续**
- 元数据: `video_id` / `title` / `channel` / `host` / `guests` / `duration_sec` / `upload_date`
- 视频 URL

---

## 中英文规则(v6 必读, 两阶段都遵守)

### ✅ 保留英文原文的情况

- **人名**: Lenny Rachitsky / Cat Wu / Sam Altman / Brendan Foody
- **产品名**: Claude Code / Co-work / ChatGPT / Cursor / Codex
- **公司名**: Anthropic / OpenAI / Google / Mercor
- **无中文对应的技术术语**:
  - eval / evals(不翻"评估")
  - agent / agentic
  - harness(模型外壳)
  - context engineering / prompt engineering
  - RLHF / RLAIF / SFT
  - vibe-coding / vibe-check
  - prompt
  - fine-tuning
  - trace
  - swe-bench / GPQA(特定 benchmark 名)
- **嘉宾 key quote 的英文原话**(blockquote 里, 下面加中文翻译标注)

### ❌ 必须翻译成中文的情况

- 描述性词汇: anti-pattern → 反模式 / first-principles → 第一性原理 / unifying mission → 统一使命 / overhead → 协调成本 / Day-zero → 零日
- 形容词副词: ambitious → 野心勃勃 / hairy → 棘手 / amorphous → 没定形 / extreme → 极端 / extremely happy → 非常开心
- 动词短语: ship a product → 上线产品 / build prototype → 做原型 / fix the hole → 补漏洞 / push the boundary → 推边界
- 概念词: dependency → 依赖 / partner team → 协作团队 / use case → 使用场景 / roadmap → 路线图 / feature → 功能(或保留, 但「ship feature」翻成「上线功能」)
- ⚠️ **不要混排**: 不要写「她是 head of product」, 写「她是产品负责人」; 不要写「PRD 在他们这里 evolve 了」, 写「PRD 在他们这里演变了」

### ✅ 引用嘉宾原话的双语格式(用 MD 引用块, 不是飞书 blockquote)

```markdown
> "The two most important things are one this unifying mission... and the second is focus."
>
> *(译: 最重要的两件事, 一是这个统一使命... 二是聚焦)*
```

### 自检
写完每段后, 数一下「英文短语 / 英文句子」(不含上述保留类)的数量 — 如果一个 H2 段超过 3 处, 说明翻译不彻底, 重写那段。

---

## 字幕完整度 — 整个流程的硬前置

`subtitle_integrity_check` 必须报告字幕覆盖 ≥ 95%(目标 97%+)才能开始 Section A。如果字幕不完整, Section A 就是在残缺信息上提取, 后续所有 Q&A 都不可信。

**没有捷径**: 字幕缺一段 = 那段所有 Q&A 都漏 = 总结失真。验证字幕完整在前, 不在后。

---

## 提取密度 — 跟视频内容走, 不要套硬区间

不同播客密度天然不同:
- 一个 90min 的精华访谈可能有 50+ 真实问题(每分钟 0.5+ Q)
- 一个 90min 的散漫闲聊可能只有 15 个真实问题(每 6min 1 Q)
- 一个 90min 的单人独白可能只有 5-8 个真实问题

**规则**: 跟视频实际内容走, 不要为了凑数硬切, 也不要为了凑数硬合并。validator 只检查 2 件事:
1. **完整度**: words_per_qa ≤ 1000(否则说明严重压缩漏问题)
2. **真实性**: 每个 quote 能反查到 transcript

---

# Section A · Q&A 提取(产出 qa_extraction.md, ★ 中文化)

## 你的任务

读完整段 transcript, **穷举**主持人的每一个真实问题 + 嘉宾的每一次回答转折。**不要压缩, 不要总结, 不要跳过**。这一阶段的目标是「信息完整提取」, 不是「写好文章」。

★ v6 变化: `host_question`、`guest_answer_thread`、`host_intent_specific`、`pm_implication_hook` 这些字段用 **中文**(按上述中英文规则)。`guest_key_quote` 保留英文原话(下面加中文翻译可以可不加, 中间产物 OK)。

## 提取规则

**核心原则**: 你的任务是「穷举每个真实问题」, 不是「写一篇好读的文章」。后者是 Section B 的事。

1. **以主持人发问为切分单元** — 每次主持人重新问一个新方向就是一个新 Q
2. **追问归并到主问题下** — 同一个主题下 host 的 immediate 追问算 follow_ups, 但如果追问引出嘉宾完全不同的回答方向, 就拆成新 Q
3. **跳过广告段** — `transcript_check.json` 里 `ad_segment_ranges` 标的范围直接忽略
4. **跳过寒暄收尾** — "Thanks for being here" / "Where can people find you" 这种不算 Q
5. **绝对不要凑数**
6. **绝对不要漏** — 如果你输出后, words_per_qa > 700, **你几乎肯定漏了问题** — 回去再扫一遍 transcript
7. **每个 quote 都要可反查** — guest_key_quote 必须能在 transcript.txt 里 grep 到对应英文片段

## 自检步骤

输出 qa_extraction.md 前, 用以下伪代码自查:

```
total_words = transcript word count
total_qa = sum of all sub_qa across all topics
density = total_words / total_qa

if density > 700:
    "我漏问题了" → 回去重新扫 transcript
elif density < 150:
    "我切太碎了" → 合并相邻 Q&A
else:
    "密度健康, 继续"
```

## 主题组聚合

提取完所有 Q&A 后, 把相关的 3-5 个 Q&A 聚合成一个主题组(topic)。聚合标准:
- 相邻时间段
- 同一个核心矛盾或概念
- 嘉宾的思路有连贯递进

## 输出格式 (qa_extraction.md, v6 中文化)

```markdown
---
source: youtube
video_id: <VIDEO_ID>
url: https://www.youtube.com/watch?v=<VIDEO_ID>
channel: <CHANNEL>
host: <HOST>
guests: [<GUEST>]
duration_min: <INT>
upload_date: <YYYY-MM-DD>
extracted_at: <ISO8601>
extraction_model: claude-opus-4-7
total_topics: <INT>
total_qa_count: <INT>
status: PASS_OR_NEEDS_REVIEW
---

# Q&A 提取 · <视频中文标题>

## 提取统计

- **视频总长**: <X> 分钟
- **字幕词数**: <X>
- **字幕完整度**: <X>%
- **主题组数**: <X>
- **子 Q&A 总数**: <X>
- **跳过广告段**: <X> 段(位置 <line ranges>)

## 主题与子 Q&A 列表

\`\`\`json
{
  "topics": [
    {
      "id": "T1",
      "title": "本话题的核心矛盾(host 视角, 1 句中文)",
      "start_timestamp": "00:02",
      "end_timestamp": "00:14",
      "host_intent": "主持人在这一段挖什么?(1-2 句中文)",
      "guest_overall_thread": "嘉宾在这一段的整体思路(2-3 句中文)",
      "sub_qa": [
        {
          "id": "Q1.1",
          "timestamp": "00:02",
          "host_question": "主持人具体问什么?(完整问题, 中文)",
          "host_intent_specific": "这个具体问题想挖到什么细节(1 句中文)",
          "follow_ups": [
            "host 在嘉宾答完后的追问 1(中文)",
            "追问 2(中文)"
          ],
          "guest_answer_thread": "嘉宾的隐含推理路径(80-150 字中文, 不堆原话, 把框架显化)",
          "guest_key_quote": "1 句最有冲击力的英文原话(可选, 如果没特别冲击的就 null)",
          "quote_source_line": "字幕原文里能找到的对应英文片段(用于反查)",
          "pm_implication_hook": "这个 Q&A 对 AI PM 的核心启示(1 句中文钩子, Section B 会展开)"
        },
        { "id": "Q1.2", "timestamp": "00:05", ... }
      ]
    },
    { "id": "T2", ... }
  ]
}
\`\`\`

## 提取自检 checklist

- [ ] 每个 guest_key_quote 都能在 transcript.txt 里 grep 到 quote_source_line?
- [ ] 时间戳单调递增?
- [ ] 没有跨度 > 10 分钟的空白主题区?
- [ ] 跳过了所有广告段?
- [ ] **所有中文字段都是中文(host_question / guest_answer_thread / host_intent_specific / pm_implication_hook)?**

## 用户审核要点

请打开本文件后:
1. 看「提取统计」是否符合视频长度对应的密度
2. 抽查 3 个 sub_qa 的 guest_key_quote 是否真在 transcript 里
3. 看主题分布是否覆盖了视频从 [00:00] 到末段
4. 标记问题:「这个主题被漏了」/「这个 Q&A 是凑的」
```

## Section A 失败情况

- 字幕完整度 < 95% → 返回 `ERROR: 字幕覆盖不足 (< 95% 硬阈值), 不能可靠提取`
- 转录词数 < 800 → 返回 `ERROR: 转录过短`
- 视频是广告 / 短宣传 → 返回 `ERROR: 视频内容空洞`

---

# Section B · 基于 Q&A 提取写最终深度笔记 (产出 note.md, v6 全中文 + 纯 MD)

## ★ v6 关键转变(必读)

相对 v5, v6 做了 3 件事:
1. **输出全中文**(只保留人名 / 产品名 / 公司名 / 无中文对应技术术语)
2. **输出纯 Markdown**(不允许 `<callout>` `<whiteboard>` `<blockquote>` 等飞书 XML 标签)
3. **加入 3 句嘉宾原话开场**(从老版 LaterCast 吸收, 在主题地图之后、嘉宾介绍之前)

note.md 是「沐阳看完这期后的精华笔记 + 自己的延伸思考」 — 像「晚点再听 LaterCast」公众号那种, 但用 Obsidian 原生 MD 渲染。qa_extraction.md(全部 Q&A)继续作为「事实底层」, 用户感兴趣了下钻看。

---

## 必读前置文件(★ 必做, 不读直接 FAIL)

写 note.md 之前, **必须先读这两个文件**:

1. **`/Users/mac/Documents/Obsidian Vault/_PROFILE_沐阳.md`** (主, 沐阳可自己编辑)
2. **`/Users/mac/.claude/skills/podcast-digest/USER_PROFILE.md`** (备份, 跟主文件同步)

它们定义了:
- 沐阳的风格偏好(❌ 不要的 / ✅ 必须做的)
- 沐阳的关注主线(10 条 AI PM 思考方向)
- 嘉宾思路展开标准(白描 ≠ 抽象总结)
- 沐阳延伸思考的句式(「我们产品...」/「我之前遇到...」)

如果两个文件都读不到, **立即报错**: `ERROR: USER_PROFILE 缺失, 无法保证个人偏好对齐`

---

## 输入

- `qa_extraction.md`(Section A 输出, **必须先验证通过**)
- `_PROFILE_沐阳.md` + skill 内副本(刚读过)
- 元数据(同 Section A)

---

## 你的任务

把 qa_extraction.md 里的 N 个 Q&A(可能 30-50 个), **再做一次编辑性提炼**成 6-8 个 H2 主题段。每个主题段:
- **嘉宾思路链白描**(150-300 字, 含 host 设问 + 嘉宾论证 + 反常识判断 + 关键例子)
- 1-2 句嘉宾原话引用(英文保留, 用 MD `>` 引用块, 下面加中文翻译)
- 1-2 句**沐阳延伸思考**(把嘉宾观点拉到沐阳具体产品场景, 不是泛泛 takeaway)

整篇目标字数: **4000-8000 字**

---

## H2 主题选择标准(怎么从 N 个 Q&A 里挑出 6-8 个)

不要按 qa_extraction 的 topic 1:1 映射。从 N 个 sub_qa 里挑出最值得深写的:

1. **嘉宾论证过程特别清楚的** — 有具体例子 + 多步推理(不是一句话结论)
2. **跟沐阳关心主线强相关的** — 看 USER_PROFILE 第二节 10 条, 命中其中任意一条优先
3. **有戏剧性矛盾的对话** — host 设套 + 嘉宾给反直觉答案
4. **反常识观点** — 可以用「很反常识」「很少见」标记的
5. **故事性强的** — 有具体场景

可以合并相邻 Q&A。也可以跳过不重要的(寒暄 / 转场 / 重复 / 用户不会关心的)。

---

## 输出格式(note.md, ★ v6 纯 MD)

### 段落 1 · 标题

```markdown
# 「钩子句」 · 嘉宾 + 节目(v6 深度笔记)
```

钩子句要求(从老版 LaterCast 吸收):
- 反差感强 / 提问式 / 一线人视角
- 不超过 25 字
- 节目名前用全角 `丨` 分隔

示例:
- `# 把 PRD 砍掉、把 harness 删了, 最值钱的是给 6 个月后才会成立的产品做原型丨Lenny's Podcast`
- `# 给 AI 写 evals 的专家, 是历史上增长最快公司的核心丨Lenny's Podcast`

### 段落 2 · 元信息表格(替代飞书 callout)

```markdown
| 项目 | 内容 |
|---|---|
| **嘉宾** | Cat Wu, Anthropic Claude Code 产品负责人 |
| **节目** | Lenny's Podcast (86 分钟, 2026-04-23 发布) |
| **原视频** | https://www.youtube.com/watch?v=PplmzlgE0kg |
| **本文定位** | 沐阳的编辑式深度笔记 — 7 个主题段 + 个人延伸思考 |
| **完整 Q&A** | 见同目录 `qa_extraction.md` |
```

### 段落 3 · 本期脑图(顶部 mermaid 代码块, Obsidian 原生支持)

```markdown
## 本期主题地图

\`\`\`mermaid
flowchart TD
    CORE["核心矛盾(1 句话中文)"]
    CORE --> T1["主题 1 简化标题(中文)"]
    CORE --> T2["主题 2 简化标题(中文)"]
    CORE --> T3["主题 3 简化标题(中文)"]
    ...
    classDef core fill:#ff7f50,stroke:#d2691e,color:#fff
    classDef t fill:#4a90e2,stroke:#1f5fa3,color:#fff
    class CORE core
    class T1,T2,T3,T4,T5,T6 t
\`\`\`
```

### 段落 4 · 三句嘉宾原话开场(★ v6 新增, 从老版 LaterCast 吸收)

```markdown
## 三句开场

> "The timelines for a lot of our product features have gone down from 6 months to 1 month and sometimes to even 1 day."
>
> *(译: 我们很多产品功能的交付周期已经从 6 个月压到了 1 个月, 有时候甚至 1 天)*

> "As code becomes much cheaper to write, the thing that becomes more valuable is deciding what to write."
>
> *(译: 代码写起来越来越便宜, 真正变贵的是决定该写什么)*

> "It's pretty important to build products that don't necessarily work yet so that you know what is missing for this product to work."
>
> *(译: 给那些还做不成的产品先 build 出原型很重要, 这样你才知道它差什么才能跑起来)*
```

要求:
- 三句必须真实出自视频(在 transcript.txt 里能逐字找到)
- 三句要覆盖三个不同的核心观点, 不要重复
- 优先选反共识 / 戳痛点 / 有冲击力的话
- **每句下面一行加中文翻译, 用 `*(译: ...)*` 格式**

### 段落 5 · 嘉宾 + 本期主线介绍(1 段, 100-200 字)

```markdown
## 关于嘉宾 · 为什么这期值得读

{1 段, 100-200 字。讲清: 嘉宾是谁 / 做什么 / 为什么这期对沐阳重要 / 本期最值得关注的整体角度。末句加粗点出主线。}
```

### 段落 6 · 6-8 个 H2 主题段(★ 核心)

每个 H2 的内部结构(★ 严格遵守, 不要用 emoji 强制切割):

```markdown
## 1. {主题标题 — 用陈述句或反问}

{嘉宾思路链白描, 150-300 字。

这一段必须包含:
- host 怎么 frame 这个问题(为什么问, 引用了什么矛盾)
- 嘉宾的论证过程(分了哪几层 / 举了什么例子 / 用了什么类比 / 反常识在哪)
- 嘉宾的核心判断 + 关键 caveat(如果有)

写法风格: 平铺直叙 + 第三人称转述 + 适度使用「{host} 拉了...」「{guest} 没站任何一边...」「她/他举了具体例子...」「她/他真正强调的是...」这种引导词。
**禁止**: 「这给我们启示」「关键是...」「核心要点」这类编辑评论。
**禁止**: 大段英文短句, 一定要翻译。}

> "{嘉宾原话, 英文保留, 1-2 句最有冲击力的}"
>
> *(译: {中文翻译})*

> **沐阳的延伸思考**: {1-2 句, 不超过 100 字, 把嘉宾观点拉到沐阳具体产品场景。用「我们产品...」「我之前遇到...」「这让我想到...」「这跟我之前在做的 X 思路一致」这类句式。}
```

**注意**:
- H2 标题不强制问号形式(LaterCast 用陈述句更多)
- 每段不强制三段式, 嘉宾思路一段 + 引用一段 + 沐阳延伸一段 即可
- 嘉宾原话引用最多 2 句, 没冲击力的就 0 句
- 沐阳延伸思考**必须有**(每个 H2 都要)
- **沐阳延伸思考用 MD 引用块 + 加粗标记**, 让它在 Obsidian 里视觉上明确分离

### 段落 7 · 视觉元素(可选)

- A vs B 对比 → 用 MD 表格
- 嘉宾说了一组「3 个原则」/「5 个步骤」→ 用 MD 有序列表或表格
- 特别值得记的判断 → MD 引用块加粗

**整篇至少**: 1 个表格 / 列表(强化对比或步骤)

### 段落 8 · 写在最后(LaterCast 风格的思路浓缩, ★ 不是行动清单)

```markdown
## 写在最后

{150-250 字, 一段或两段, 对整期对话核心思路的浓缩 + 沐阳自己的整体感受。
不是行动清单, 不是 takeaway 罗列。
风格参考 LaterCast 的「写在最后」段: 把核心矛盾再点一次, 给读者一个 lingering 的思考。
末句可以给沐阳一个**可立刻执行的小动作**(吸收老版 LaterCast 优点)。}
```

### 段落 9 · 信息来源(底部, 用 MD 表格)

```markdown
---

## 信息来源

| 项目 | 内容 |
|---|---|
| **原视频英文标题** | "{english_title}" |
| **节目** | {channel} (主持人 {host}) |
| **原视频 URL** | {youtube_url} |
| **发布日期** | {upload_date} |
| **视频长度** | {duration_min} 分钟 |
| **字幕完整度** | {coverage_pct}% |
| **本文生成方式** | podcast-digest skill v6 (全中文 + Obsidian 原生 MD) |
| **完整 Q&A 提取** | 同目录 `qa_extraction.md` ({total_qa} 个 Q&A 全部反查通过) |
```

---

## Section B 硬约束(v6 validator.py 检查)

| # | 约束 | 说明 |
|---|---|---|
| 1 | 字数 4000-8000 等效字 | |
| 2 | H2 主题段数 在 [5, 10] | LaterCast 是 6-8, 放宽 5-10 |
| 3 | 顶部 mermaid 脑图存在 | 用 ` ```mermaid ` 代码块 |
| 4 | 每个 H2 段字数 ≥ 200 | 防止压缩饼干 |
| 5 | 「沐阳延伸思考」出现 ≥ H2 数的 80% | 确保每段都有个人化思考 |
| 6 | **★ v6: 全中文比例 ≥ 85%** | 中文字符 / (中文字符 + 英文单词 × 0.8) |
| 7 | **★ v6: 3 句开场金句存在**(英 + 中翻译并列) | |
| 8 | **★ v6: 不允许飞书 XML 标签**(`<callout>` `<whiteboard>` `<blockquote>` `<title>` `<callout`) | 用 MD 原生语法 |
| 9 | **★ v6: 不允许 PM 启示三件套字串**(决策规则 / 可执行动作 / 反面陷阱) | |
| 10 | **★ v6: 不允许 checkbox 行动清单** | 用「写在最后」浓缩段替代 |
| 11 | 「写在最后」段存在 | |
| 12 | 信息来源段完整(含 YouTube URL) | |
| 13 | emoji 总数 ≤ 10 | v6 进一步收紧 (Obsidian 主要看正文, emoji 干扰) |

---

## 风格(★ 必读 USER_PROFILE 后再写)

### ❌ 完全不要做
- 不要 PM 启示三件套(决策规则 / 可执行动作 / 反面陷阱)
- 不要 🎯/🧠/💡 emoji 强制切割
- 不要把嘉宾思路压成 1-2 行抽象总结
- 不要写「这给我们启示」「这告诉我们」「关键是...」
- 不要 checkbox 行动清单
- 不要按 Q&A 顺序逐个展开
- **★ v6 不要中英混排**: 「她是 head of product 在 Anthropic」(不行), 写成「她是 Anthropic 的产品负责人」
- **★ v6 不要飞书 XML 标签**: `<callout>` `<whiteboard>` `<blockquote>` 都禁止

### ✅ 必须做
- H2 6-8 个主题段, 每段 200-400 字
- 嘉宾思路白描(host 设问 + 嘉宾论证 + 反常识判断 + 关键例子)
- 引文英文保留, 用 MD `>` 引用块, **下面加中文翻译**
- **每个 H2 末必有沐阳延伸思考** — 1-2 句, 不超过 100 字, 用 MD 加粗的引用块格式
- 「写在最后」是 LaterCast 风格的思路浓缩, 末句可以是可执行的小动作
- **★ v6 全中文**: 描述/形容/动作词全部翻译; 只保留人名/产品名/公司名/必要技术术语
- **★ v6 纯 MD**: # ## > ``` --- 表格 列表 — 都是 MD 原生语法
- **★ v6 三句开场**: 在主题地图之后、嘉宾介绍之前, 三句嘉宾原话 + 中文翻译

### 自检
输出前问自己 4 个问题:
1. 这篇 note 沐阳看完会不会觉得「这就是我看完播客后想到的事」?
2. 每个 H2 段最后有没有「沐阳延伸思考」?(用「我们产品」「我之前遇到」这类句式)
3. **正文里除了人名/产品名/必要术语, 还有没有其他英文短句没翻译?**(超过 5 处就重写)
4. **有没有用飞书 XML 标签**(`<callout>` `<whiteboard>` `<blockquote>` `<title>`)? 有就改成 MD 原生语法

---

## 失败情况

- USER_PROFILE 读不到 → `ERROR: USER_PROFILE 缺失, 无法保证个人偏好对齐`
- qa_extraction.md 没通过 extract_qa_validator → `ERROR: 中间产物未通过校验, 不能生成 note`
- 字数严重不足(< 3000) → `ERROR: 严重压缩, 可能漏了主题`
- 中文比例 < 85% → 让 validator 报错后自动重写, 重点查英文短句
