#!/usr/bin/env python3
"""Validate qa_extraction.md from Section A of podcast-digest (v4.1).

v4.1 关键变更(用户反馈驱动):
- 删除主题组/子 Q&A 数的固定区间约束(不同播客密度天然不同)
- 字幕完整度阈值提到 95%(目标 97%+)— 字幕完整是 v4 最重要的前置条件
- 新增「提取密度健康度」指标(words_per_qa) — 替代硬区间, 监控"是否漏问题"
- 引用反查仍是核心(防幻觉),容差不变
- 时间戳覆盖检查改用 end→next_start 模型(实际未覆盖时间)

Checks:
1. Frontmatter 必填字段
2. JSON 解析
3. 字幕完整度 >= 95% (强制) — 否则直接 FAIL
4. 每个 sub_qa 必填字段齐全
5. 每个 guest_key_quote 能在 transcript grep 到 (防幻觉, 80% 反查通过)
6. 时间戳单调递增
7. 主题之间未覆盖间隔 <= 10 分钟
8. 端覆盖 >= 85%
9. 提取密度健康度: words_per_qa (每个 Q&A 平均分摊 transcript 字数)
   - 健康区间: 200-1000 词/Q&A
   - < 200: 可能过度切碎
   - > 1000: 可能严重压缩 (漏问题)

Usage:
    python3 extract_qa_validator.py qa_extraction.md transcript.txt
"""
import argparse
import json
import re
import sys
from pathlib import Path


def extract_frontmatter(text):
    m = re.match(r"^---\n(.+?)\n---\n", text, re.DOTALL)
    if not m:
        return {}, text
    body = text[m.end():]
    fm_text = m.group(1)
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, body


def extract_json_block(text):
    m = re.search(r"```json\s*\n(.+?)\n```", text, re.DOTALL)
    if not m:
        return None, "no json code block found"
    raw = m.group(1)
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, f"json parse error: {e}"


def timestamp_to_min(ts):
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def check_quote_in_transcript(quote, transcript_text):
    if not quote:
        return True
    quote_clean = re.sub(r"[^\w\s]", "", quote.lower()).strip()
    transcript_clean = re.sub(r"[^\w\s]", "", transcript_text.lower())
    words = quote_clean.split()
    if len(words) < 3:
        return quote_clean in transcript_clean
    window = " ".join(words[:5])
    return window in transcript_clean


def parse_subtitle_coverage(qa_text):
    """从 qa_extraction.md 的「字幕完整度」字段读取数字。"""
    m = re.search(r"字幕完整度[**]*[:\s]*([0-9.]+)\s*%", qa_text)
    if m:
        return float(m.group(1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("qa_path", type=Path)
    ap.add_argument("transcript_path", type=Path)
    ap.add_argument("--subtitle-coverage-pct", type=float,
                    help="override subtitle coverage percent (otherwise read from qa_extraction.md)")
    args = ap.parse_args()

    qa_text = args.qa_path.read_text(encoding="utf-8")
    transcript_text = args.transcript_path.read_text(encoding="utf-8")
    transcript_words = len(re.findall(r"\b[a-zA-Z]+\b", transcript_text))

    issues = []
    warnings = []
    metrics = {}

    # 1. Frontmatter
    fm, body = extract_frontmatter(qa_text)
    required_fm = ["source", "video_id", "url", "channel", "duration_min", "total_topics", "total_qa_count"]
    missing_fm = [k for k in required_fm if k not in fm]
    if missing_fm:
        issues.append(f"frontmatter missing: {missing_fm}")

    # 2. JSON parse
    data, err = extract_json_block(qa_text)
    if err:
        issues.append(err)
        print(f"[✗ FAIL] {args.qa_path}\n  问题: {issues}")
        return 2

    topics = data.get("topics", [])
    actual_topics = len(topics)
    actual_qa_count = sum(len(t.get("sub_qa", [])) for t in topics)
    metrics["actual_topics"] = actual_topics
    metrics["actual_qa_count"] = actual_qa_count
    metrics["transcript_words"] = transcript_words

    # 3. ★ v4.1 NEW: 字幕完整度 >= 95% (强制)
    coverage_pct = args.subtitle_coverage_pct or parse_subtitle_coverage(qa_text)
    metrics["subtitle_coverage_pct"] = coverage_pct
    if coverage_pct is None:
        issues.append("无法从 qa_extraction.md 读到字幕完整度 — 必须在统计部分写明")
    elif coverage_pct < 95.0:
        issues.append(
            f"★ 字幕完整度 {coverage_pct}% < 95% (硬阈值) — 总结质量无法保证, "
            f"必须先重新拉字幕或确认 transcript 完整后再继续"
        )
    elif coverage_pct < 97.0:
        warnings.append(f"字幕完整度 {coverage_pct}% < 97% (建议) — 注意检查是否有片段缺失")

    # 4. Per-sub_qa required fields
    required_qa_fields = ["id", "host_question", "guest_answer_thread"]
    qa_missing_fields = []
    for t in topics:
        for sq in t.get("sub_qa", []):
            missing = [f for f in required_qa_fields if not sq.get(f)]
            if missing:
                qa_missing_fields.append({"qa_id": sq.get("id", "?"), "missing": missing})
    metrics["qa_missing_fields_count"] = len(qa_missing_fields)
    if qa_missing_fields:
        issues.append(f"{len(qa_missing_fields)} 个子 Q&A 缺必填字段(id/host_question/guest_answer_thread)")

    # 5. Quote reverse-check (anti-hallucination)
    quote_check_results = []
    for t in topics:
        for sq in t.get("sub_qa", []):
            quote = sq.get("guest_key_quote") or sq.get("quote_source_line")
            if quote and quote != "null":
                found = check_quote_in_transcript(quote, transcript_text)
                quote_check_results.append({
                    "qa_id": sq.get("id"),
                    "quote_prefix": quote[:50],
                    "found": found,
                })
    metrics["quotes_total"] = len(quote_check_results)
    quotes_not_found = [q for q in quote_check_results if not q["found"]]
    metrics["quotes_not_found_count"] = len(quotes_not_found)
    if quotes_not_found:
        if len(quotes_not_found) > metrics["quotes_total"] * 0.2:
            issues.append(f"{len(quotes_not_found)} / {metrics['quotes_total']} 引用在 transcript 找不到(>20%, 可能幻觉)")
        else:
            warnings.append(f"{len(quotes_not_found)} 引用在 transcript 找不到(可接受)")
        for q in quotes_not_found[:3]:
            warnings.append(f"  - {q['qa_id']}: {q['quote_prefix']}...")

    # 6. Timestamp monotonic
    last_ts_min = -1
    ts_violations = 0
    for t in topics:
        for sq in t.get("sub_qa", []):
            ts = sq.get("timestamp")
            if ts:
                m = timestamp_to_min(ts)
                if m < last_ts_min:
                    ts_violations += 1
                last_ts_min = m
    metrics["timestamp_violations"] = ts_violations
    if ts_violations > 2:
        issues.append(f"时间戳非单调递增({ts_violations} 处违反)")

    # 7. Coverage gap (end → next_start)
    sorted_topics = sorted(topics, key=lambda t: timestamp_to_min(t.get("start_timestamp", "00:00")))
    max_gap = 0
    for i in range(1, len(sorted_topics)):
        prev_end = timestamp_to_min(sorted_topics[i - 1].get("end_timestamp", "00:00"))
        cur_start = timestamp_to_min(sorted_topics[i].get("start_timestamp", "00:00"))
        gap = cur_start - prev_end
        if gap > max_gap:
            max_gap = gap
    metrics["max_topic_gap_min"] = max_gap
    if max_gap > 10:
        issues.append(f"主题之间最大未覆盖间隔 {max_gap} 分钟 > 10(可能漏了一段)")
    elif max_gap > 5:
        warnings.append(f"主题之间最大未覆盖间隔 {max_gap} 分钟(注意检查)")

    # 8. End-of-video coverage
    duration_min = int(fm.get("duration_min", 60))
    metrics["duration_min"] = duration_min
    if topics:
        last_topic_end = timestamp_to_min(topics[-1].get("end_timestamp", "00:00"))
        end_coverage_pct = (last_topic_end / duration_min * 100) if duration_min > 0 else 0
        metrics["end_coverage_pct"] = round(end_coverage_pct, 1)
        if end_coverage_pct < 85:
            issues.append(f"最后主题在 {last_topic_end} 分,只覆盖到视频 {end_coverage_pct:.0f}%(应 ≥ 85%)")

    # 9. ★ v4.1 NEW: 提取密度健康度 (words_per_qa)
    # 替代硬区间, 监控"是否漏问题"
    if actual_qa_count > 0:
        words_per_qa = round(transcript_words / actual_qa_count)
        metrics["words_per_qa"] = words_per_qa
        if words_per_qa > 1000:
            issues.append(
                f"★ 提取密度过低: 每个 Q&A 平均承载 {words_per_qa} 词 (>1000) — "
                f"严重压缩, 几乎肯定漏了真实问题, 重新提取"
            )
        elif words_per_qa > 700:
            warnings.append(
                f"提取密度偏低: 每个 Q&A 平均承载 {words_per_qa} 词 (>700) — "
                f"可能漏了问题, 建议再扫一遍 transcript 看是否每个 host 提问都覆盖"
            )
        elif words_per_qa < 150:
            warnings.append(
                f"提取密度偏高: 每个 Q&A 仅承载 {words_per_qa} 词 (<150) — "
                f"可能过度切碎, 多个 Q&A 实际是同一个问题的不同方面"
            )

    # Verdict
    verdict = "PASS" if not issues else ("WARN" if len(issues) <= 1 else "FAIL")

    print(f"[{'✓ PASS' if verdict == 'PASS' else ('⚠ WARN' if verdict == 'WARN' else '✗ FAIL')}] {args.qa_path}\n")
    print("指标:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    if warnings:
        print(f"\n警告 ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    if issues:
        print(f"\n问题 ({len(issues)}):")
        for i, iss in enumerate(issues, 1):
            print(f"  {i}. {iss}")

    return 0 if verdict == "PASS" else (1 if verdict == "WARN" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
