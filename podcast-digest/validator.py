#!/usr/bin/env python3
"""Validate podcast-digest v6 final note.md (全中文 + 纯 Markdown).

v6 关键转变(相对 v5):
- 输出全中文(中文比例 ≥ 85%)
- 输出纯 Markdown(不允许飞书 XML 标签 <callout> <whiteboard> <blockquote> <title>)
- H2 主题段(用 `## ` 语法, 不再用 <h1> XML 标签)
- 新增 3 句开场金句校验
- 反向检查无飞书 XML 残留
"""
import argparse
import json
import re
import sys
from pathlib import Path


# v6: 不要翻译的保留词白名单 — 这些英文不计入"未翻译"统计
PRESERVED_TERMS = {
    # 人名片段
    "Lenny", "Cat", "Wu", "Sam", "Altman", "Brendan", "Foody", "Anthropic", "OpenAI",
    "Google", "Mercor", "Amol", "Sary", "Ezzat", "Dan", "Shipper", "Marc", "Andreessen",
    "Sid", "Boris", "Ben", "Mann", "Sarah", "Guo",
    # 产品/公司名
    "Claude", "Code", "Co-work", "ChatGPT", "Cursor", "Codex", "Slack", "Twitter",
    "Drive", "Gmail", "Calendar", "Desktop", "Mobile", "Web", "iPhone", "Mac",
    # 技术术语(无中文对应)
    "eval", "evals", "agent", "agentic", "harness", "prompt", "prompts",
    "RLHF", "RLAIF", "SFT", "fine-tuning", "trace", "vibe-coding", "vibe-check",
    "swe-bench", "GPQA", "context", "engineering",  # context engineering
    "MVP", "API", "SDK", "CLI", "GUI", "IDE", "URL", "JSON", "MD",
    "Opus", "Sonnet", "Haiku", "Cohere",
    # 单位 / 缩写 / 标准词
    "GPU", "CPU", "AI", "PM", "ARR", "MRR", "KR", "OKR", "PRD", "Q1", "Q2", "Q3", "Q4",
    "B2B", "B2C", "SaaS", "VC", "CEO", "CTO", "CPO", "CFO",
    "id", "URL", "x", "X",  # 数字单位
    # 节目名
    "Podcast", "Lennys",
}


def count_effective_chars(text):
    """中文字符 + 英文单词 × 2 (LaterCast 风格估算)."""
    # 去掉 YAML frontmatter
    text = re.sub(r"^---\n.+?\n---\n", "", text, count=1, flags=re.DOTALL)
    # 去掉代码块(包括 mermaid)
    text = re.sub(r"```.*?\n.*?```", " ", text, flags=re.DOTALL)
    # 去掉 URL
    text = re.sub(r"https?://\S+", " ", text)
    # 去掉 MD 语法符号
    text = re.sub(r"[#*\[\]`>!|_-]", "", text)
    chinese = len(re.findall(r"[一-鿿]", text))
    english_words = len(re.findall(r"\b[a-zA-Z]+\b", text))
    return chinese + english_words * 2


def chinese_ratio(text):
    """计算中文比例 — 中文字符 / (中文字符 + 非保留词英文单词 × 0.8)."""
    text = re.sub(r"^---\n.+?\n---\n", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"```.*?\n.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"https?://\S+", " ", text)
    # 去掉 MD 语法但保留文字
    text_clean = re.sub(r"[#*\[\]`>!|_-]", "", text)
    chinese = len(re.findall(r"[一-鿿]", text_clean))
    # 计算英文单词, 但排除保留词
    all_english = re.findall(r"\b[a-zA-Z][a-zA-Z-]*\b", text_clean)
    non_preserved = [w for w in all_english if w not in PRESERVED_TERMS]
    # 简单复合词去保留: 像 "Lenny's" -> 拆 -> "Lenny" 在白名单
    # 英文权重 × 0.8 — 一个英文单词等价 0.8 个中文字 (因为英文密度更高)
    if chinese + len(non_preserved) * 0.8 == 0:
        return 1.0, 0, 0
    ratio = chinese / (chinese + len(non_preserved) * 0.8)
    return ratio, chinese, len(non_preserved)


def split_into_h2_blocks(text):
    """v6: 按 `## ` 切 H2 块, 排除脚手架标题(三句开场 / 关于嘉宾 / 本期主题地图 / 写在最后 / 信息来源)."""
    parts = re.split(r"(^## .+?$)", text, flags=re.MULTILINE)
    blocks = []
    current_title = None
    current_body = ""
    scaffolding = ["本期主题地图", "三句开场", "关于嘉宾", "写在最后", "信息来源", "主题地图"]
    for part in parts:
        m = re.match(r"^## (.+?)$", part)
        if m:
            if current_title is not None:
                if not any(s in current_title for s in scaffolding):
                    blocks.append((current_title, current_body))
            current_title = m.group(1).strip()
            current_body = ""
        else:
            current_body += part
    if current_title is not None:
        if not any(s in current_title for s in scaffolding):
            blocks.append((current_title, current_body))
    return blocks


def count_h2_topic_blocks(text):
    """v6: H2 主题段数."""
    blocks = split_into_h2_blocks(text)
    return len(blocks), [t[:60] for t, _ in blocks]


def check_each_h2_min_chars(text, min_chars=200):
    """每个主题段 H2 内文有效字数 >= min_chars."""
    blocks = split_into_h2_blocks(text)
    too_short = []
    for title, body in blocks:
        ec = count_effective_chars(body)
        if ec < min_chars:
            too_short.append({"title": title[:60], "chars": ec, "min": min_chars})
    return too_short


def check_extension_thinking_freq(text):
    """v6: 「沐阳延伸思考」或同义句式应出现于 ≥ 80% 的主题段."""
    blocks = split_into_h2_blocks(text)
    if not blocks:
        return 0, 0, 0.0
    extension_markers = [
        "沐阳的延伸思考",
        "沐阳延伸思考",
        "我们产品",
        "我之前遇到",
        "这让我想到",
        "我之前在做",
        "我现在做",
        "我自己产品",
        "这跟我之前",
    ]
    hit = 0
    for _, body in blocks:
        if any(m in body for m in extension_markers):
            hit += 1
    pct = hit / len(blocks) if blocks else 0
    return hit, len(blocks), pct


def check_negative_residue_v6(text):
    """v6 反向检查: 飞书 XML 标签 / PM 启示三件套 / checkbox 行动清单 残留."""
    residue = []
    # 1. ★ v6: 飞书 XML 标签
    xml_tags = ["<callout", "<whiteboard", "<blockquote", "<title>", "<h1", "<callout>", "<h2"]
    for tag in xml_tags:
        if tag in text:
            count = text.count(tag)
            residue.append(f"飞书 XML 标签残留: {tag} × {count} (v6 应改为 MD 原生语法)")
    # 2. PM 启示三件套字串
    triple_kits = ["决策规则", "可执行动作", "反面陷阱", "PM 启示", "PM启示"]
    found_kits = [k for k in triple_kits if k in text]
    if found_kits:
        residue.append(f"PM 启示三件套残留字串: {', '.join(found_kits)}")
    # 3. checkbox 行动清单
    checkbox_count = len(re.findall(r"<checkbox", text, re.IGNORECASE))
    if checkbox_count > 0:
        residue.append(f"checkbox 行动清单残留: {checkbox_count} 个 (v6 删除)")
    # 4. 「行动清单」H1/H2
    if re.search(r"^#{1,3}\s*.*?行动清单.*?$", text, re.MULTILINE):
        residue.append("「行动清单」标题残留 (v6 应改成「写在最后」)")
    # 5. 🎯/🧠/💡 强制切割
    target_count = text.count("🎯")
    brain_count = text.count("🧠")
    bulb_count = text.count("💡")
    if target_count >= 3 and brain_count >= 3 and bulb_count >= 3:
        residue.append(
            f"v4.1 三段式 emoji 残留: 🎯×{target_count} 🧠×{brain_count} 💡×{bulb_count}"
        )
    return residue


def check_opening_quotes(text):
    """v6: 检查三句开场金句 — 必须有「三句开场」标题, 且至少 3 个引用块带中文翻译。"""
    has_opening_h2 = bool(re.search(r"^##\s*三句开场", text, re.MULTILINE))
    if not has_opening_h2:
        return False, 0, "缺少「三句开场」H2 标题"
    # 找到「三句开场」段落内容
    m = re.search(r"^##\s*三句开场(.+?)(?=^##\s)", text, re.MULTILINE | re.DOTALL)
    if not m:
        # 是末段
        m = re.search(r"^##\s*三句开场(.+)$", text, re.MULTILINE | re.DOTALL)
    if not m:
        return False, 0, "「三句开场」段抓取失败"
    section = m.group(1)
    # 数引用块数量(以 > " 开头)
    quote_count = len(re.findall(r"^>\s*\"", section, re.MULTILINE))
    # 数翻译标注 "*(译: ...)*" 数量
    trans_count = len(re.findall(r"\*\(译:.+?\)\*", section))
    if quote_count < 3:
        return False, quote_count, f"三句开场只有 {quote_count} 个引用块, 应 ≥ 3"
    if trans_count < 3:
        return False, quote_count, f"三句开场只有 {trans_count} 个中文翻译, 应 ≥ 3"
    return True, quote_count, None


def load_qa_stats(qa_path):
    """Return (total_topics, total_qa_count, coverage_pct) from qa_extraction.md."""
    if not qa_path or not qa_path.exists():
        return None, None, None
    qa_text = qa_path.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.+?)\n---\n", qa_text, re.DOTALL)
    total_topics, total_qa, coverage = None, None, None
    if fm_match:
        fm_text = fm_match.group(1)
        for line in fm_text.split("\n"):
            if line.startswith("total_topics:"):
                try:
                    total_topics = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("total_qa_count:"):
                try:
                    total_qa = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("subtitle_coverage_pct:") or line.startswith("coverage_pct:"):
                try:
                    coverage = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
    if total_topics is None or total_qa is None:
        json_match = re.search(r"```json\s*\n(.+?)\n```", qa_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                topics = data.get("topics", [])
                total_topics = total_topics or len(topics)
                total_qa = total_qa or sum(len(t.get("sub_qa", [])) for t in topics)
            except json.JSONDecodeError:
                pass
    return total_topics, total_qa, coverage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path, help="note.md path")
    ap.add_argument("--qa-extraction", type=Path, help="qa_extraction.md path for stats")
    args = ap.parse_args()

    text = args.path.read_text(encoding="utf-8")

    metrics = {}
    issues = []

    # 1. 字数 4000-8000
    eff_chars = count_effective_chars(text)
    metrics["effective_chars"] = eff_chars
    if eff_chars < 3000:
        issues.append(f"字数 {eff_chars} < 3000 (严重压缩, 可能漏了主题)")
    elif eff_chars > 12000:
        issues.append(f"字数 {eff_chars} > 12000 (note 太长, v6 应控制 4000-8000)")

    # 2. ★ v6 新增: 全中文比例 ≥ 85%
    cn_ratio, cn_count, en_count = chinese_ratio(text)
    metrics["chinese_chars"] = cn_count
    metrics["english_words_non_preserved"] = en_count
    metrics["chinese_ratio"] = f"{cn_ratio*100:.1f}%"
    if cn_ratio < 0.85:
        issues.append(
            f"★ 中文比例 {cn_ratio*100:.1f}% < 85% — "
            f"非保留词英文单词 {en_count} 个过多, 必须翻译成中文"
            f"(只保留人名/产品名/无中文对应技术术语)"
        )

    # 3. H2 主题段数 [5, 10]
    h2_count, h2_titles = count_h2_topic_blocks(text)
    metrics["h2_topic_count"] = h2_count
    metrics["h2_topic_titles"] = h2_titles
    if h2_count < 5:
        issues.append(f"H2 主题段数 {h2_count} < 5 (太少, 建议 6-8)")
    elif h2_count > 10:
        issues.append(f"H2 主题段数 {h2_count} > 10 (太多, 建议 6-8)")

    # 4. 每个主题段 ≥ 200 字
    too_short = check_each_h2_min_chars(text, min_chars=200)
    metrics["short_blocks_count"] = len(too_short)
    if too_short:
        details = "; ".join(f"{b['title']} ({b['chars']}字)" for b in too_short[:3])
        issues.append(f"{len(too_short)} 个主题段 < 200 字: {details}")

    # 5. 沐阳延伸思考频次 ≥ 80%
    ext_hit, ext_total, ext_pct = check_extension_thinking_freq(text)
    metrics["extension_thinking_hit"] = ext_hit
    metrics["extension_thinking_total"] = ext_total
    metrics["extension_thinking_pct"] = f"{ext_pct*100:.0f}%"
    if ext_total > 0 and ext_pct < 0.8:
        issues.append(
            f"沐阳延伸思考命中 {ext_hit}/{ext_total} = {ext_pct*100:.0f}% < 80% "
            f"(每段必须有「沐阳的延伸思考」或「我们产品」「我之前遇到」句式)"
        )

    # 6. Mermaid 脑图 (★ v6: 用代码块, 不是 <whiteboard>)
    has_mermaid = bool(re.search(r"```mermaid", text))
    metrics["has_mermaid"] = has_mermaid
    if not has_mermaid:
        issues.append("缺少顶部 mermaid 脑图 (用 ```mermaid 代码块)")

    # 7. ★ v6 新增: 三句开场金句
    has_opening, opening_count, opening_err = check_opening_quotes(text)
    metrics["has_opening_quotes"] = has_opening
    metrics["opening_quote_count"] = opening_count
    if not has_opening:
        issues.append(f"三句开场金句: {opening_err}")

    # 8. ★ v6: 反向检查无飞书 XML 残留 + 三件套 + checkbox
    residue = check_negative_residue_v6(text)
    metrics["residue_count"] = len(residue)
    if residue:
        for r in residue:
            issues.append(f"残留: {r}")

    # 9. 「写在最后」H2 存在
    has_ending = bool(re.search(r"^##\s*(写在最后|最后)", text, re.MULTILINE))
    metrics["has_ending_h2"] = has_ending
    if not has_ending:
        issues.append("缺少「写在最后」H2 段")

    # 10. 信息来源段完整
    has_source = bool(
        re.search(r"信息来源", text)
        and re.search(r"youtube\.com/watch\?v=", text)
    )
    metrics["has_source_section"] = has_source
    if not has_source:
        issues.append("缺少底部「信息来源」段或缺 YouTube URL")

    # 11. emoji 总数 <= 10 (v6 收紧)
    emoji_chars = re.findall(
        r"[\U0001F300-\U0001FAFF\U0001F000-\U0001F02F\U0001F900-\U0001F9FF✀-➿☀-⛿]",
        text,
    )
    metrics["emoji_count"] = len(emoji_chars)
    if len(emoji_chars) > 10:
        issues.append(f"emoji 数 {len(emoji_chars)} > 10 (v6 进一步收紧)")

    # 12. (可选) qa_extraction 字幕完整度透传
    if args.qa_extraction:
        qa_topics, qa_count, coverage = load_qa_stats(args.qa_extraction)
        metrics["qa_topics_ref"] = qa_topics
        metrics["qa_count_ref"] = qa_count
        metrics["coverage_pct_ref"] = coverage
        if coverage is not None and coverage < 95.0:
            issues.append(f"qa_extraction 字幕完整度 {coverage:.1f}% < 95% (硬阈值)")

    verdict = "PASS" if not issues else "FAIL"
    print(f"[{'✓ PASS' if verdict == 'PASS' else '✗ FAIL'}] {args.path}")
    print(f"\n指标:")
    for k, v in metrics.items():
        if isinstance(v, list) and len(v) > 5:
            print(f"  {k}: [{len(v)} 项, 前 3: {v[:3]}]")
        else:
            print(f"  {k}: {v}")
    if issues:
        print(f"\n问题 ({len(issues)}):")
        for i, iss in enumerate(issues, 1):
            print(f"  {i}. {iss}")

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
