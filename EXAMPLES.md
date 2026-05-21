# 使用示例(EXAMPLES)

> 3 个真实场景:从用户提需求到 Agent 出总结的完整链路。
> Agent 看完这 3 个例子,应该能套用到 90% 的视频。

---

## 示例 1:5 分钟科普短视频(抖音)→ 学习笔记

### 用户输入

> "帮我看下这个抖音视频讲了啥:https://www.douyin.com/video/7521010686525230386"

### Agent 决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 用什么命令 | `videosummarize "URL"` | 一行搞定 |
| 模型 | `tiny` 或 `base` | 短视频,默认就够 |
| 后端 | 自动(mlx 或 faster) | 5 分钟视频 GPU 也不会崩 |
| cookies | 不加 | 抖音走自带下载器 |
| 模板 | **模板 7:学习笔记** | 单人讲科普,知识密度中等 |

### 命令

```bash
videosummarize "https://www.douyin.com/video/7521010686525230386" -m tiny -f md
```

### 输出(片段)

```
Done! 1 video(s) transcribed:
  赌你绝对听不出来的AI主播!#AI新星计划 ...
    project:    ~/.videosummarize/赌你绝对听不出来的AI主播.../
    transcript: ~/.videosummarize/赌你绝对听不出来的AI主播.../transcript.md
```

### Agent 读 transcript 后产出(模板 7 摘录)

```markdown
# 学习笔记:赌你绝对听不出来的 AI 主播

**视频时长**:5 分 10 秒
**主题**:用「豆包播客功能」生成 AI 播客

## 一句话总结
教你用豆包 App 一键把任意文本/链接/PDF 变成有逻辑、有方言、有口水音的 AI 播客。

## 知识图谱
豆包播客
  ├─ 端到端模型(直接生成完整播客,不是先文稿+再 TTS)
  ├─ 多模态训练数据(文本 + 播客音频)
  └─ 应用场景:学习总结 / 生活娱乐 / 创作

## 重点笔记
- **[00:01:12]** 豆包播客功能位置:打开豆包 → 播客功能,可上传 PDF 或网页链接
- **[00:02:35]** 端到端模型,不是「先生成文稿再 TTS」,所以会有方言和口水音
- **[00:03:25]** 用法 1:学习论文/小说,书太长发给豆包变播客
- **[00:04:30]** 用法 2:整合零碎信息(微博评论、新闻八卦)
- **[00:04:42]** 用法 3:整蛊家人 — 把朋友资料发给豆包让 AI 介绍

## 自测题
1. 豆包播客是端到端模型还是「先文稿+再 TTS」?为什么这个区别重要?
2. 哪三类内容最适合发给豆包播客?
```

---

## 示例 2:1 小时圆桌访谈(小红书)→ 访谈 JTBD

### 用户输入

> "总结一下这个小红书的视频:https://www.xiaohongshu.com/explore/6951f060000000001e0315cf?xsec_token=ABJHgocxBm0O9BnhGuqSIJr6cs9xgon4dPG9Wq8xyjwys=&xsec_source=pc_search&source=unknown
> 要详细一点"

### Agent 决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 模型 | `small`(用户要详细) | 长视频升级模型减少错字 |
| 后端 | `VS_BACKEND=faster` | 1h+ 视频,稳定优先 |
| cookies | `--cookies chrome` | 小红书反爬 |
| chunk-size | `600` | 切 10 分钟一块,4 worker 并发 |
| 模板 | **模板 6:访谈 JTBD** | 多人对话/访谈结构 |
| 长度 | `xl`(用户要详细) | 60+ min 默认 |

### 命令

```bash
VS_BACKEND=faster videosummarize \
  "https://www.xiaohongshu.com/explore/6951f06...&xsec_source=pc_search&source=unknown" \
  -m small -f md -l zh --cookies chrome --chunk-size 600
```

### 输出(片段)

```
Planning:
  audio:    1h 11m (4270s)
  backend:  faster-whisper (CPU)
  workers:  4
  chunks:   8 x 600s
  est time: ~15 min

** transcribe: chunk 8/8 done
verify: passed

Done! 1 video(s) transcribed:
  AI 与未来范式的深度漫谈|the prompt
    transcript: ~/.videosummarize/AI与未来范式的深度漫谈_the_prompt/transcript.md
```

### Agent 读 transcript 后产出(模板 6 摘录)

```markdown
# 访谈总结:AI 与未来范式的深度漫谈

**访谈时长**:1h 11min
**形式**:4 人圆桌
**主题**:2025 AI 复盘 + 2026 展望

## JTBD(待完成的任务)

| 用户想完成的任务 | 期望结果 | 重要性 | 满意度 |
|---------------|---------|-------|-------|
| 把内容(论文/网页)变成易消化的播客 | 听完就懂,不用读 | 5 | 4 |
| 让 AI 助理主动预判我下一步想做什么 | 不用每次重复说同样的话 | 5 | 3 |
| 多 Agent 协作创造新内容 | 1+1>2,涌现新创意 | 4 | 1 |

## 关键洞察
- **DeepSeek 是 2025 转折点**,中国模型节奏明显加速 [00:00:46]
- **GPT-5.1 Memory 让 AI 像有助理**,会主动追问 [00:32:50]
- **多 Agent 协作还没真正涌现创意**,目前 Agent 还是被动牛马 [01:09:30]

## 金句摘录
> "我反而比今天的更重要" —— [00:00:42]
> "更大模型可以更稀疏,但小了模型你太稀疏,效果就会下降得非常严重" —— [01:39:15]
```

---

## 示例 3:本地会议录音(.m4a)→ 会议总结

### 用户输入

> "整理一下这个录音:/Users/mac/recordings/产品评审会_2026-05-08.m4a"

### Agent 决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 模型 | `medium` | 会议录音重要,要尽量准 |
| 后端 | `VS_BACKEND=faster` | 时长不确定,稳定优先 |
| cookies | 不加 | 本地文件,不下载 |
| 模板 | **模板 5:会议总结** | "评审会"关键词 → 会议 |
| 输出位置 | 转录文件夹同目录的 `summary.md` | 用户能直接看到 |

### 命令

```bash
VS_BACKEND=faster videosummarize \
  "/Users/mac/recordings/产品评审会_2026-05-08.m4a" \
  -m medium -f md -l zh --chunk-size 600
```

### Agent 读 transcript 后产出(模板 5 摘录)

```markdown
# 会议总结:产品评审会(2026-05-08)

**会议时长**:1h 25min
**主题**:V3.2 版本功能评审 + 上线节奏决策

## 核心结论
- **决策 1**:V3.2 推迟一周上线(原 5/15 → 5/22),给压力测试留时间
- **决策 2**:支付模块由小张接手,原负责人小李转去做数据看板
- **决策 3**:本周五前所有 P0 bug 必须 close

## 行动项

| 截止日 | 负责人 | 行动 | 来源 |
|-------|--------|------|------|
| 2026-05-10 | 小张 | 接手支付模块,review 现有代码 | [00:23:15] |
| 2026-05-15 | 小李 | 数据看板 PRD 初稿 | [00:45:20] |
| 2026-05-12 | 测试组 | 完成 V3.2 全量回归 | [01:05:42] |

## 已决策
- V3.2 上线时间:2026-05-22(基于压力测试覆盖率)
- 支付模块 owner 调整(小李 → 小张)

## 开放问题
- 数据看板的取数口径还没拍板,需要小李 PRD 出来后再讨论
- 海外版上线时间未定,等海外组反馈
```

---

## Agent 工作流总结(三步)

```
1. 收到视频 URL / 本地路径
   ↓
2. 决策:模型(默认 base/小视频用 tiny)、后端(长视频用 faster)、cookies、模板
   ↓
3. 跑 videosummarize → 读 transcript.md → 套对应模板 → 输出 summary.md
```

**核心原则**:
- ✅ 一切基于真实 transcript,不编造
- ✅ 模板 5 个"我们语气",模板 6 抓 JTBD,模板 7 重知识图谱
- ✅ 简明语言:小学水平 + 术语括号解释
- ✅ 不省略时间戳,方便用户回看原片
