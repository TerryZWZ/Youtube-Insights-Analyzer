from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from typing import Any
from sklearn.feature_extraction.text import TfidfVectorizer
from prompt import build_chat_prompt

def join_segments(segments: list[dict]) -> str:
    return " ".join((s.get("text") or "").strip() for s in segments if (s.get("text") or "").strip())

def chunk_segments(segments: list[dict], segs_per_chunk: int = 12) -> list[dict]:
    chunks = []
    buf = []
    start_t = None

    for seg in segments:
        txt = (seg.get("text") or "").strip()
        if not txt:
            continue

        if start_t is None:
            start_t = float(seg.get("start") or 0.0)

        buf.append(txt)
        if len(buf) >= segs_per_chunk:
            chunks.append({"start": start_t, "text": " ".join(buf)})
            buf = []
            start_t = None

    if buf:
        chunks.append({"start": start_t or 0.0, "text": " ".join(buf)})

    return chunks

def extract_salient_terms(full_text: str, top_k: int = 30) -> list[str]:
    if not full_text.strip():
        return []
    
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=8000)
    X = vec.fit_transform([full_text])
    feats = vec.get_feature_names_out()
    weights = X.toarray()[0]
    pairs = sorted(zip(feats, weights), key=lambda x: x[1], reverse=True)
    return [t for t, w in pairs[:top_k] if w > 0]

def compute_wpm(full_text: str, duration_seconds: int) -> float:
    words = len(full_text.split())
    mins = max(1e-6, duration_seconds / 60.0)
    return words / mins

def compute_target_chars(duration_seconds: int, wpm: float) -> int:
    mins = duration_seconds / 60.0 if duration_seconds else 0.0
    base = 260.0 + 35.0 * math.log1p(mins) # Duration Factor
    dens = 0.65 * max(0.0, wpm - 120.0) # Density Factor (120wpm baseline)
    tgt = base + dens
    return int(max(200, min(3000, tgt)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_jsonl", required=True, help="transcripts.jsonl")
    ap.add_argument("--out_jsonl", required=True, help="dataset.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()

    rows: list[dict[str, Any]] = []
    with open(args.in_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    out_path = Path(args.out_jsonl)

    n = 0
    with open(out_path, "w", encoding="utf-8") as w:
        for r in rows:
            segments = r.get("transcript_segments") or []
            full_text = join_segments(segments)
            evidence = full_text
            wpm = compute_wpm(full_text, int(r.get("duration_seconds") or 0))
            tgt_chars = compute_target_chars(int(r.get("duration_seconds") or 0), wpm)
            terms = extract_salient_terms(full_text, top_k=30)

            item = {
                "video_id": r.get("video_id", ""),
                "title": r.get("title", ""),
                "channel": r.get("channel", ""),
                "duration_seconds": int(r.get("duration_seconds") or 0),
                "url": r.get("url", ""),
                "evidence_text": evidence,
                "salient_terms": terms,
                "wpm": float(wpm),
                "target_chars": int(tgt_chars),
            }

            item["prompt"] = build_chat_prompt(item)
            w.write(json.dumps(item, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} rows to {out_path}")

if __name__ == "__main__":
    main()
