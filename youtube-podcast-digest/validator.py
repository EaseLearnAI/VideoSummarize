#!/usr/bin/env python3
"""Validate a LaterCast-style podcast summary against structural rules (v2 — 全中文 + 双语引用).

v2 关键变化:
- 新增中文比例 ≥ 85% 校验
- 新增引用块下面必须有 "*(译: ...)*" 翻译标注
- 反向检查无飞书 XML 标签残留 (<callout> <whiteboard> <blockquote> <title>)
- emoji 上限收紧到 ≤ 5

Usage:
    python3 validator.py PATH_TO_DRAFT.md
    python3 validator.py PATH_TO_DRAFT.md --json
    python3 validator.py PATH_TO_DRAFT.md --lenient  (放宽字数到 [3000, 4100])

Exit codes:
    0 - PASS
    1 - FAIL with issues printed
"""
import argparse
import json
import re
import sys
from pathlib import Path


CHINESE_RE = re.compile(r"[一-鿿]")
ENGLISH_WORD_RE = re.compile(r"\b[a-zA-Z][a-zA-Z-]*\b")
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)


# v2: 不要翻译的保留词白名单 — 这些英文不计入"未翻译"统计
PRESERVED_TERMS = {
    # 人名片段
    "Lenny", "Cat", "Wu", "Sam", "Altman", "Brendan", "Foody", "Anthropic", "OpenAI",
    "Google", "Mercor", "Amol", "Sary", "Ezzat", "Dan", "Shipper", "Marc", "Andreessen",
    "Sid", "Boris", "Ben", "Mann", "Sarah", "Guo", "Rachitsky", "Aakash", "Gupta",
    # 产品/公司名
    "Claude", "Code", "Co-work", "ChatGPT", "Cursor", "Codex", "Slack", "Twitter",
    "Drive", "Gmail", "Calendar", "Desktop", "Mobile", "Web", "iPhone", "Mac",
    "Every", "Opus", "Sonnet", "Haiku", "Cohere", "GPT",
    # 技术术语
    "eval", "evals", "agent", "agentic", "harness", "prompt", "prompts",
    "RLHF", "RLAIF", "SFT", "fine-tuning", "trace", "vibe-coding", "vibe-check",
    "swe-bench", "GPQA", "context", "engineering",
    "MVP", "API", "SDK", "CLI", "GUI", "IDE", "URL", "JSON", "MD",
    # 缩写
    "GPU", "CPU", "AI", "PM", "ARR", "MRR", "KR", "OKR", "PRD", "Q1", "Q2", "Q3", "Q4",
    "B2B", "B2C", "SaaS", "VC", "CEO", "CTO", "CPO", "CFO",
    "high", "extra",  # 模型推理档位 high / extra high
    # 节目名
    "Podcast", "Lennys",
}


def effective_char_count(text: str) -> int:
    """Count Chinese chars + English words * 2 (rough public-account style word count)."""
    text_no_url = re.sub(r"https?://\S+", "", text)
    text_no_md = re.sub(r"[#*\[\]\(\)`>!\-_|]", "", text_no_url)
    # 去掉 frontmatter
    text_no_md = re.sub(r"^---\n.+?\n---\n", "", text_no_md, count=1, flags=re.DOTALL)
    # 去掉代码块
    text_no_md = re.sub(r"```.*?\n.*?```", " ", text_no_md, flags=re.DOTALL)
    chinese = len(CHINESE_RE.findall(text_no_md))
    english = len(ENGLISH_WORD_RE.findall(text_no_md))
    return chinese + english * 2


def chinese_ratio(text: str):
    """v2 新增: 中文比例 — 中文字符 / (中文字符 + 非保留词英文单词 × 0.8)."""
    text = re.sub(r"^---\n.+?\n---\n", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"```.*?\n.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"https?://\S+", " ", text)
    # 去掉嘉宾原话引用块(不计入)
    text = re.sub(r"^>.+?$", "", text, flags=re.MULTILINE)
    text_clean = re.sub(r"[#*\[\]`>!|_-]", "", text)
    chinese = len(CHINESE_RE.findall(text_clean))
    all_english = ENGLISH_WORD_RE.findall(text_clean)
    non_preserved = [w for w in all_english if w not in PRESERVED_TERMS]
    if chinese + len(non_preserved) * 0.8 == 0:
        return 1.0, 0, 0
    ratio = chinese / (chinese + len(non_preserved) * 0.8)
    return ratio, chinese, len(non_preserved)


def check_quote_translations(text: str):
    """v2 新增: 检查嘉宾原话引用块下面必须有 *(译: ...)* 翻译标注 (开场 3 句 + H2 段引用)."""
    # 找所有引用块(以 > " 开头, MD 引用 + 英文双引号)
    quote_blocks = re.findall(r"^>\s*\".+?\".*?$", text, re.MULTILINE)
    # 找所有翻译标注
    translations = re.findall(r"\*\(译:.+?\)\*", text)
    return len(quote_blocks), len(translations)


def check_xml_tag_residue(text: str):
    """v2 新增: 反向检查无飞书 XML 标签."""
    residue = []
    xml_tags = ["<callout", "<whiteboard", "<blockquote", "<title>", "<h1", "<h2", "<checkbox"]
    for tag in xml_tags:
        if tag in text:
            count = text.count(tag)
            residue.append(f"{tag} × {count}")
    return residue


def validate(markdown: str, strict_word_count: bool = True) -> dict:
    issues: list[str] = []
    metrics: dict = {}

    main = markdown
    if "## 写在最后" in main:
        body_before_final = main.split("## 写在最后")[0]
    else:
        body_before_final = main

    # 1. 字数
    word_count = effective_char_count(main)
    metrics["word_count"] = word_count
    if strict_word_count:
        if not (3500 <= word_count <= 3900):
            issues.append(f"等效字数 {word_count} 不在 [3500, 3900] 区间")
    else:
        if not (3000 <= word_count <= 4100):
            issues.append(f"等效字数 {word_count} 不在放宽区间 [3000, 4100]")

    # 2. ★ v2 新增: 中文比例 ≥ 85%
    cn_ratio, cn_count, en_count = chinese_ratio(main)
    metrics["chinese_chars"] = cn_count
    metrics["english_words_non_preserved"] = en_count
    metrics["chinese_ratio"] = f"{cn_ratio*100:.1f}%"
    if cn_ratio < 0.85:
        issues.append(
            f"★ 中文比例 {cn_ratio*100:.1f}% < 85% — "
            f"非保留词英文单词 {en_count} 个过多, 必须翻译成中文"
        )

    # 3. H2 数(不含写在最后 / 信息来源)
    h2_titles = re.findall(r"^## (.+)$", main, re.MULTILINE)
    h2_content = [t.strip() for t in h2_titles if t.strip() not in ("写在最后", "信息来源")]
    metrics["h2_count"] = len(h2_content)
    metrics["h2_titles"] = h2_content
    if not (6 <= len(h2_content) <= 8):
        issues.append(f"H2 小标题数 {len(h2_content)} 不在 [6, 8]")

    # 4. 「写在最后」存在
    if "## 写在最后" not in main:
        issues.append("缺少「写在最后」H2 段")

    # 5. 嘉宾原话引用数 ≥ 8 (3 句开场 + 每节 ≥ 1 句)
    quote_blocks = re.findall(r"^>\s*\".+?\".*?$", main, re.MULTILINE)
    metrics["quote_count"] = len(quote_blocks)
    if len(quote_blocks) < 8:
        issues.append(f"嘉宾原话引用 {len(quote_blocks)} 句, 应 ≥ 8 (3 句开场 + 每节 ≥ 1 句)")

    # 6. ★ v2 新增: 每个引用块下面必须有翻译标注
    quote_count, trans_count = check_quote_translations(main)
    metrics["quote_translation_count"] = trans_count
    if quote_count > 0 and trans_count < quote_count * 0.8:
        issues.append(
            f"★ {trans_count}/{quote_count} 引用块有 *(译: ...)* 翻译标注 < 80% — "
            f"v2 要求每个英文引用下面单独一行加中文翻译"
        )

    # 7. 每个 H2 小节末尾至少 1 处加粗
    sections = re.split(r"^## ", main, flags=re.MULTILINE)[1:]
    sections_no_bold = []
    for sec in sections:
        title = sec.split("\n")[0].strip()
        if title in ("写在最后", "信息来源"):
            continue
        if "**" not in sec:
            sections_no_bold.append(title)
    if sections_no_bold:
        issues.append(f"以下 H2 小节没有加粗解读: {sections_no_bold}")
    metrics["sections_missing_bold"] = sections_no_bold

    # 8. YouTube URL 在末尾
    url_match = re.search(r"https://www\.youtube\.com/watch\?v=[\w-]+", main)
    metrics["youtube_url_present"] = bool(url_match)
    if not url_match:
        issues.append("末尾缺少 YouTube 原视频 URL")

    # 9. 来源标注
    if "信息来源" not in main and "内容来源:" not in main:
        issues.append("缺少「信息来源」段或「内容来源:」标注")

    # 10. emoji ≤ 5 (v2 收紧)
    emoji_matches = EMOJI_RE.findall(main)
    metrics["emoji_count"] = len(emoji_matches)
    if len(emoji_matches) > 5:
        issues.append(f"发现 emoji ({len(emoji_matches)} 个) > 5, v2 收紧上限")

    # 11. ★ v2 新增: 反向检查无飞书 XML 残留
    xml_residue = check_xml_tag_residue(main)
    metrics["xml_residue_count"] = len(xml_residue)
    if xml_residue:
        issues.append(f"★ 飞书 XML 标签残留 (v2 应改为 MD): {', '.join(xml_residue)}")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "metrics": metrics,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("draft", type=Path)
    ap.add_argument("--json", action="store_true", help="Output JSON only")
    ap.add_argument("--lenient", action="store_true", help="Relax word count to [3000, 4100]")
    args = ap.parse_args()

    md = args.draft.read_text(encoding="utf-8")
    result = validate(md, strict_word_count=not args.lenient)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"[{status}] {args.draft}")
        print(f"\n指标:")
        for k, v in result["metrics"].items():
            print(f"  {k}: {v}")
        if result["issues"]:
            print(f"\n问题 ({len(result['issues'])}):")
            for i, issue in enumerate(result["issues"], 1):
                print(f"  {i}. {issue}")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
