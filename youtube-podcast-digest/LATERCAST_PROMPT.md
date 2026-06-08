# LaterCast 风格 全中文深度总结模板 (v2)

> 这是 Claude 在 `youtube-podcast-digest` skill 流程里使用的总结指令模板。
> 当你读完一个 YouTube 播客的英文转录后, 严格按以下 8 段结构生成**全中文**深度总结。
>
> v2 关键变化:
> - 正文几乎**全中文**(中文比例 ≥ 85%)
> - 嘉宾引用保留英文原话, **下面单独一行加中文翻译**
> - 不再推飞书, 只归档到 Obsidian Vault

## 输入

- `transcript.txt` — 经过 vtt_to_transcript.py 清洗的英文转录(已去除 YouTube rolling display 重复, 带 `[HH:MM]` 时间戳)
- 元数据: `title` / `channel` / `duration_sec` / `upload_date`
- 视频 URL: 用于末尾来源标注

## ★ v2 必读: 中英文规则

### ✅ 保留英文原文的情况

- **人名**: Lenny Rachitsky / Cat Wu / Sam Altman / Brendan Foody / Dan Shipper
- **产品名**: Claude Code / Co-work / ChatGPT / Cursor / Codex / GPT-5
- **公司名**: Anthropic / OpenAI / Google / Mercor / Every
- **无中文对应的技术术语**:
  - eval / evals
  - agent / agentic
  - harness
  - context engineering / prompt engineering
  - RLHF / RLAIF / SFT
  - vibe-coding / vibe-check
  - trace
  - swe-bench / GPQA
  - high / extra high(模型推理档位)
- **嘉宾 key quote 的英文原话**(blockquote 里, 下面加一行中文翻译)

### ❌ 必须翻译成中文

- 描述词: anti-pattern → 反模式 / first-principles → 第一性原理 / overhead → 协调成本
- 形容词副词: ambitious → 野心勃勃 / hairy → 棘手 / amorphous → 没定形
- 动词短语: ship a product → 上线产品 / push the boundary → 推边界
- 概念词: dependency → 依赖 / partner team → 协作团队 / use case → 使用场景 / roadmap → 路线图

### ⚠️ 不要中英混排
- ❌ 「她是 head of product 在 Anthropic」
- ✅ 「她是 Anthropic 的产品负责人」
- ❌ 「PRD 在他们这里 evolve 了」
- ✅ 「PRD 在他们这里演变了」

### ✅ 引用嘉宾原话的双语格式

```markdown
> "The two most important things are one this unifying mission... and the second is focus."
>
> *(译: 最重要的两件事, 一是这个统一使命... 二是聚焦)*
```

## 输出: 严格遵循 8 段结构

### 1. 【标题】

格式: `# <反差或钩子句>?丨<节目名>`

示例:
- "为什么我从 Codex 又回到了 Claude?丨Every"
- "OpenAI 产品经理是如何工作的?丨Aakash Gupta"
- "Agent 从 Demo 到生产, 只差一个托管底座丨Claude"

要求:
- 反差感强 / 提问式 / 一线人视角
- 不超过 25 字
- 节目名前用全角 `丨` 分隔

### 2. 【导语】

固定句式开头(必须一模一样, 注意末尾"试试转成播客稍后再听"的语气):

> 我们每天为你更新硅谷最新的 AI 创业与科技播客总结, 让你与前沿保持同频。全文约 X 字, 如果你现在没有时间, 试试转成播客稍后再听。

其中 X 是你最终输出的等效字数(估到百位, 如 3700)。

### 3. 【三句金句开场】

从转录里挑 3 句最有冲击力的嘉宾原话, **每句独立段落, 英文 + 中文翻译并列**(★ v2 新增中文翻译):

```markdown
> "Anthropic is back."
>
> *(译: Anthropic 回来了)*

> "This is a paradigm shift model wrapped in a kind of pretty good okay-ish to pretty good harness."
>
> *(译: 这是一个范式跃迁级的模型, 但外包在一个还过得去的 harness 里)*

> "We're entering this world where the harness matters as much as the model does."
>
> *(译: 我们正在进入一个 harness 跟模型本身一样重要的世界)*
```

要求:
- 三句必须真实出自视频(在 transcript.txt 里能逐字找到, 可意译但语义不变)
- 三句要覆盖三个不同的核心观点, 不要重复
- 优先选反共识 / 戳痛点 / 有冲击力的话
- **保留英文原文 + 下面一行中文翻译**(用 `*(译: ...)*` 格式)

### 4. 【嘉宾/节目介绍段】

1 段, 150-250 字, **全中文**, 包含:
- 节目背景(节目名 / 主持人 / 嘉宾是谁 / 来自哪个公司 / 做什么的)
- 录制场景(是访谈?演讲?workshop?一人 vibe check?)
- 本期主线 — 末句用 `**加粗**` 包裹的一句话, 点出本期最值得读者关注的角度

示例:

> Every 是一家把自己定义成「未来工作方式的 AI 应用实验室」的公司, 团队约 30 人, 长期用 AI 做编码、写作、设计、社区和内部产品。视频里出镜的是创始人 Dan Shipper, 他录的是 Opus 4.8 发布当天的零日 vibe check。开场他直接给了一个判断: Opus 4.7 不好用、不好爱, 过去一两个月他和团队里很多 Claude 老用户都转向了 Codex 和 GPT 5.5; Opus 4.8 让这个判断反转过来。**这期最值得关注的, 不是「Claude 又强了」, 而是模型能力、推理档位和产品外壳正在一起决定知识工作者每天伸手拿哪个工具。**

### 5. 【6-8 个 H2 小节】

每节 350-500 字, **三层结构(顺序不可换)**:

#### a) 铺垫段(中文)
- 讲清嘉宾在视频里做了什么 / 说了什么背景
- 引出本节要谈的核心问题
- 不能上来就引用, 要先给上下文

#### b) 嘉宾原话引用(双语)
- 独立段落, 1 句嘉宾原话
- MD 引用块 + 英文双引号 `""` 包裹
- **保留英文原文**(从 transcript.txt 里找原句, 可微调通顺度但不可改语义)
- **★ v2: 下面一行加中文翻译, 用 `*(译: ...)*` 格式**

#### c) 解读段(中文)
- 把嘉宾的话翻译成读者(中国知识工作者)能立刻用的工作启示
- **每节末尾至少 1 处 `**加粗**`**, 加粗的内容必须是「对读者的指令性建议」, 不是简单复述
- 解读要落地到具体动作, 不要空喊"很重要"

#### H2 段示范

```markdown
## Opus 4.8 让 Claude 重新回到桌面

过去一两个月, Dan Shipper 和 Every 团队里很多 Claude 老用户都转向了 Codex 和 GPT-5.5 — 不是 Claude 不强, 而是 Opus 4.7 那一代有种「不好用、不好爱」的体感, 任务跑久了容易出小错。Opus 4.8 发布零日他做了一组真实任务测试: 写一篇长文章、写一个完整的 deck、改一段棘手代码 — 结果是 Claude 终于又能进入他的默认工作流了。

> "Anthropic is back. Opus 4.8 is the model that brings me back to Claude as my daily driver."
>
> *(译: Anthropic 回来了。Opus 4.8 是让我重新把 Claude 当主力日常工具的模型)*

这一段对中国知识工作者真正的启发不是「该装哪个 app」, 而是模型迭代的窗口期非常短 — 上一波你以为放弃的工具, 下一个版本可能就重新值得用了。**重要任务用 Claude 的 high 或 extra high 档位再试一次, 拿真实代码、真实文章、真实 deck 去测, 不要凭上次的体感做决策。**
```

### 6. 【写在最后】

H2 标题就叫 `## 写在最后`。1 段, 2-3 句, **全中文**, 给读者一个**可立刻执行的小动作**。

示例:

> Opus 4.8 给人的启发很直接: 别只追榜单第一名, 也别只看自己习惯的 app。重要任务用 high 或 extra high 试一次, 拿真实代码、真实文章、真实 deck 去测。下一次工具切换, 可能不来自某张总榜, 而来自你在一个真实项目里突然发现: 它接住了原来接不住的那一段。

### 7. 【来源标注】

固定格式(用 MD 表格代替之前的纯文本两行):

```markdown
---

## 信息来源

| 项目 | 内容 |
|---|---|
| **原视频英文标题** | "<英文原标题>" |
| **节目** | <节目名> (主持人 <host>) |
| **原视频 URL** | <YouTube URL> |
| **发布日期** | <YYYY-MM-DD> |
| **视频长度** | <X> 分钟 |
| **本文生成方式** | youtube-podcast-digest v2 (LaterCast 风格 + 全中文) |
```

## 硬约束(必须遵守)

| # | 约束 | 校验方式 |
|---|---|---|
| 1 | 等效字数 [3500, 3900](等效=中文字符+英文单词×2) | validator.py 检查 |
| 2 | 短视频(转录 < 1500 词)放宽到 [3000, 3500] | 同上 |
| 3 | 6-8 个 H2 小节(不含"写在最后") | validator.py 检查 |
| 4 | ≥ 8 句嘉宾原话引用(3 句开场 + 每节 ≥ 1 句) | validator.py 检查 |
| 5 | 每个 H2 小节末尾至少 1 处加粗 | validator.py 检查 |
| 6 | 来源标注 + YouTube URL 在末尾 | validator.py 检查 |
| 7 | 不使用 emoji(全篇 ≤ 5 个) | validator.py 检查 |
| 8 | 嘉宾引用必须能在 transcript.txt 里找到 | 人工抽查 / LLM judge |
| 9 | 中文流畅, 避免直译腔、长定语堆叠 | 人工 |
| 10 | 关键英文术语保留(eval / agent / harness / trace / context engineering) | 人工 |
| 11 | 不编造视频里没出现的数字、人名、产品名 | 人工 / LLM judge |
| 12 | **★ v2: 每个英文嘉宾引用下面一行加中文翻译** | validator.py 检查 |
| 13 | **★ v2: 中文比例 ≥ 85%** | validator.py 检查 |
| 14 | **★ v2: 不允许飞书 XML 标签**(`<callout>` `<whiteboard>` `<blockquote>` `<title>`) | validator.py 检查 |

## 失败情况

如果你判断**无法生成符合标准的总结**(转录太短 / 转录质量差 / 视频内容空洞), 直接返回:

```
ERROR: <具体原因>
```

例如:
- `ERROR: 转录只有 320 词, 不足以生成 3500 字深度总结, 建议走 videosummarize-skill 做更精细转录`
- `ERROR: 转录看起来是会议录像, 没有清晰嘉宾观点, 不适合 LaterCast 风格`

不要试图根据标题瞎编。

## 风格细节

- **不要写"总结"、"概述"、"本期要点"** 这种元描述, 直接进入内容
- **不要用 emoji**(全篇 ≤ 5 个)
- **不要把英文术语全翻译**: harness 不翻译成"机壳", trace 不翻译成"踪迹", agent 不翻译成"代理"
- **★ v2 不要中英混排**: 不要写「PM 应该 wear hats」, 写「PM 应该多戴几顶帽子」(如果保留 hats 这种比喻意味)或者更直接「PM 应该多扛活」
- **不要用职场黑话**: 避免"赋能"、"打通"、"链路"、"抓手"、"底层逻辑"这种 LinkedIn 体
- **不要在小节末尾问问题**: 用陈述句给建议, 不用"你做到了吗?"这种修辞
- **段落长度**: 每段控制在 200-350 字, 不要超过 400 字一段
- **加粗用 `**`**: 不要用其他符号

## 风格的反例(来自 LaterCast 公众号原文的对照)

✗ 错误风格: "AI 时代的产品经理需要构建多维度的认知能力, 以适应快速变化的技术生态"
✓ 正确风格: "如果 PM 不能读 trace、不能理解 eval、不能把反馈变成 agent 可执行任务, 就会被卡在流程外"

✗ 错误: "模型能力是核心壁垒"
✓ 正确: "模型强, 不保证用户每天会伸手去拿"

✗ 错误: "建议大家都试一试, 会有惊喜"
✓ 正确: "重要任务用 high 和 extra high 试一次, 拿真实代码、真实文章、真实 deck 去测"

✗ 错误(★ v2 新增): "PM 需要 reconcile engineer 跑太快的 anti-pattern"
✓ 正确: "PM 要协调好 engineer 跑太快导致 PM/designer 被挤压的反模式"

## 长视频(> 1 小时)的处理

如果转录 > 1.5 万词(对应约 1.5-2 小时视频):
- 不要简单地按时间顺序写, 要先在 thinking 阶段提炼 6-8 个跨段落主题
- 每个 H2 对应一个主题, 引用可以跨时间段
- 避免按 [HH:MM] 顺序流水账

如果转录 > 4 万词(对应 4 小时以上):
- 当前 skill 一次性处理可能字数控制困难
- **建议改用 podcast-digest(深度版)** — 它的 Q&A 中间产物 + 用户 review 阶段更适合长视频
- 或考虑分章节:先生成 8-12 个章节大纲, 再针对每章独立总结, 最后合稿

---

End of LATERCAST_PROMPT.md (v2)
