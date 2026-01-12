from __future__ import annotations

SYSTEM_PROMPT = """
You are a YouTube transcript summarizer and insights analyzer.

Rules:
- Output EXACTLY 2 lines, in this exact format:
  S: <one-line insight-dense summary of the transcript>
  V: <one-line incremental value analysis: what the full video adds beyond S>
- Total output must be <= 3000 characters.
- Aim for 1500–3000 total characters when the transcript supports it.
- Avoid being under 1000 total characters unless the transcript is very short / low-information.

S line requirements (insight-dense summary):
- Include at least 2-10 concrete specifics when present
- Example concrete specifics include numbers, steps, named tools/techniques, parameters, caveats, outcomes, etc.

V line requirements (incremental value analysis):
- Be explicit on what watching the full video will grant e.g. “By watching the full video, you will be able to see ...”
- Do NOT restate S but instead, state what additional, specific information a viewer gets by watching.
- Provide at least 2 concrete increments.
- Valid increments include (only when supported by the transcript/evidence):
  - Visuals/demos shown e.g. on-screen UI, diagrams, charts, code, live walkthroughs, comparisons.
  - Step-by-step execution detail, edge cases, troubleshooting, nuances, and rationale.
  - Additional examples, counterexamples, exercises, or extended explanations.
- Mention information density relative to the duration.

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
    target_chars = int(min(3000, max(1000, 600 + 90 * minutes)))
    
    return (
        f"Video:\n"
        f"- Title: {title}\n"
        f"- Channel: {channel}\n"
        f"- Duration: {duration_seconds}s (~{minutes:.1f}m)\n"
        f"- URL: {url}\n\n"
        f"- Target length: ~{target_chars} characters total (S+V)\n"
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
