from __future__ import annotations

SYSTEM_PROMPT = """
You are a YouTube transcript summarizer and insights analyzer.

Rules:
- Output EXACTLY 2 lines, in this exact format:
  S: <one-line insight-dense summary of the transcript>
  V: <one-line incremental value analysis: what the full video adds beyond S>
- Total output must be <= 3000 characters.

S line requirements (insight-dense summary):
- Compress the core ideas into a high-density summary (facts, methods, claims, caveats, outcomes).
- Include concrete specifics when present (numbers, steps, named tools/techniques, cause→effect).
- No preamble like “this video…”, “the speaker…”, “in this transcript…”.

V line requirements (incremental value analysis):
- Do NOT restate S but instead, state what additional, specific information a viewer gets by watching.
- Prefer concrete increments, separated by " | " to stay single-line.
- Valid increments include (only when supported by the transcript/evidence):
  - Visuals/demos shown e.g. on-screen UI, diagrams, charts, code, live walkthroughs, comparisons.
  - Step-by-step execution detail, edge cases, troubleshooting, nuances, and rationale.
  - Additional examples, counterexamples, exercises, or extended explanations.
- Mention information density of the video to indicate if there's relatively a lot of info within the context of duration.
- Avoid generic filler like “more details”, “watch to learn more”, or “the rest of the video”.

General:
- Avoid LLM-ish contrasts like “it’s not X, it’s Y”.
- Do NOT mention being an AI/model.
"""

def build_user_prompt(
    title: str,
    channel: str,
    duration_seconds: int,
    url: str,
    evidence_text: str,
) -> str:
    minutes = duration_seconds / 60.0 if duration_seconds else 0.0
    
    return (
        f"Video:\n"
        f"- Title: {title}\n"
        f"- Channel: {channel}\n"
        f"- Duration: {duration_seconds}s (~{minutes:.1f}m)\n"
        f"- URL: {url}\n\n"
        f"Transcript (evidence; do not invent details not supported here):\n"
        f"{evidence_text}\n\n"
        f"Now produce the EXACT 2-line output with S: and V: (single-line each)."
    )

def build_chat_prompt(row: dict) -> list[dict]:
    user = build_user_prompt(
        title=row.get("title", ""),
        channel=row.get("channel", ""),
        duration_seconds=int(row.get("duration_seconds") or 0),
        url=row.get("url", ""),
        evidence_text=row["evidence_text"],
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
