#!/usr/bin/env python3
"""Transcript quality pre-check for podcast-digest skill."""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


AD_MARKERS = [
    "this episode is brought to you by",
    "sponsored by",
    "thanks to our sponsor",
    "today's episode is brought",
    "head on over to",
    ".com/lenny",
    ".com/listeners",
    "use code",
    "promo code",
    "get a discount",
    "first month free",
    "free trial",
    "subscribe to my newsletter",
    "lenniesnewsletter.com",
    "lennysnewsletter.com",
    "lenny's product pass",
    "leave a review",
    "rating or leaving a review",
    "subscribe to the show",
    "favorite podcast app",
]

HOST_PATTERNS = [
    r"\bI want to (?:start|ask|dig|go|come back)\b",
    r"\bWhat's your sense\b",
    r"\bTalk about\b",
    r"\bMy guest (?:today |is)\b",
    r"\bWelcome to the podcast\b",
    r"\bone (?:final|last) question\b",
    r"\bgo to (?:our|the) lightning round\b",
]


def detect_ad_segments(text):
    lines = text.split("\n")
    ad_ranges = []
    in_ad = False
    ad_start = 0
    for i, line in enumerate(lines):
        line_lower = line.lower()
        marker_hits = sum(1 for m in AD_MARKERS if m in line_lower)
        if marker_hits >= 2 and not in_ad:
            in_ad = True
            ad_start = i
        elif in_ad and marker_hits == 0 and len(line.strip()) > 100:
            ad_ranges.append((ad_start, i - 1))
            in_ad = False
    if in_ad:
        ad_ranges.append((ad_start, len(lines) - 1))
    return ad_ranges


def detect_speakers(text):
    arrow_count = text.count(">>") + text.count(">> ")
    word_count = len(re.findall(r"\b[a-zA-Z]+\b", text))
    host_hint_count = sum(1 for p in HOST_PATTERNS if re.search(p, text, re.IGNORECASE))
    has_interview_structure = arrow_count > 20 or (host_hint_count >= 3 and word_count >= 5000)
    return {
        "structure": "interview" if has_interview_structure else "monologue_or_unclear",
        "arrow_marker_count": arrow_count,
        "host_pattern_matches": host_hint_count,
        "confidence": "high" if has_interview_structure and host_hint_count >= 2 else "medium",
    }


def extract_named_entities(text):
    candidates = re.findall(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\b", text)
    excluded = {
        "I", "I'm", "I've", "I'll", "I'd", "The", "This", "That", "These", "Those",
        "And", "But", "Or", "So", "For", "Not", "Yes", "No", "Okay", "OK", "Well",
        "AI", "PM", "CEO", "CTO", "CPO", "GM", "VC", "API", "URL",
    }
    counter = Counter(c for c in candidates if c not in excluded and len(c) > 2)
    return {
        "top_named": [{"name": k, "count": v} for k, v in counter.most_common(30)],
        "uppercase_phrases_total": sum(counter.values()),
    }


def gibberish_score(text):
    if not text.strip():
        return 1.0
    words = re.findall(r"\b[a-zA-Z]+\b", text)
    if not words:
        return 1.0
    long_words = [w for w in words if len(w) > 25]
    repeat_chars = sum(1 for w in words if re.search(r"(.)\1{3,}", w))
    return min(1.0, (len(long_words) + repeat_chars) / max(len(words), 1) * 10)


def time_coverage(text):
    markers = re.findall(r"\[(\d{2}):(\d{2})\]", text)
    if not markers:
        return {"markers_found": 0, "first": None, "last": None, "even_distribution": False}
    minutes = [int(h) * 60 + int(m) for h, m in markers]
    gaps = [minutes[i + 1] - minutes[i] for i in range(len(minutes) - 1)]
    return {
        "markers_found": len(markers),
        "first": f"{markers[0][0]}:{markers[0][1]}",
        "last": f"{markers[-1][0]}:{markers[-1][1]}",
        "avg_gap_min": round(sum(gaps) / len(gaps), 1) if gaps else None,
        "even_distribution": all(1 <= g <= 5 for g in gaps) if gaps else False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript_path", type=Path)
    args = ap.parse_args()

    text = args.transcript_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    words = re.findall(r"\b[a-zA-Z]+\b", text)

    speakers = detect_speakers(text)
    entities = extract_named_entities(text)
    gscore = gibberish_score(text)
    ads = detect_ad_segments(text)
    tcov = time_coverage(text)

    issues = []
    if len(words) < 800:
        issues.append("word_count=" + str(len(words)) + " too low (<800)")
    if gscore > 0.05:
        issues.append("gibberish_score=" + format(gscore, ".3f") + " too high (>0.05)")
    if tcov["markers_found"] == 0:
        issues.append("no [HH:MM] time markers found")
    if speakers["structure"] == "monologue_or_unclear":
        issues.append("speaker structure unclear")

    verdict = "PASS" if not issues else ("WARN" if len(issues) <= 2 else "FAIL")

    result = {
        "path": str(args.transcript_path),
        "verdict": verdict,
        "issues": issues,
        "metrics": {
            "word_count": len(words),
            "line_count": len(lines),
            "ad_segments": len(ads),
            "ad_segment_ranges": ads,
            "gibberish_score": round(gscore, 4),
        },
        "speakers": speakers,
        "time_coverage": tcov,
        "named_entities": entities,
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    if verdict == "FAIL":
        sys.stderr.write("\n[FAIL] " + str(issues) + "\n")
        return 2
    elif verdict == "WARN":
        sys.stderr.write("\n[WARN] " + str(issues) + "\n")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
