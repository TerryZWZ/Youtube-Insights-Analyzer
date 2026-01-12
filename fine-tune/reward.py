from __future__ import annotations
import math
import re
from collections import Counter
from typing import Iterable

STOPWORDS = {
    "the","a","an","and","or","but","if","then","else","when","while","to","of","in","on","for","with",
    "is","are","was","were","be","been","being","as","at","by","from","it","this","that","these","those",
    "you","your","we","they","their","i","me","my","our","us","he","she","him","her","them",
    "not","do","does","did","so","just","very","can","could","should","would","may","might","will"
}

BANNED_PATTERNS = [
    r"\bit’s not\b.*\bit’s\b",
    r"\bit's not\b.*\bit's\b",
    r"\bas an ai\b",
    r"\bi(?:'| a)m an ai\b",
    r"\bthis video (dives|delves)\b",
    r"\bin (today'?s|this) video\b",
    r"\blet'?s dive\b",
    r"\bin summary\b",
    r"\bwatch (the )?(full )?video\b",
    r"\bto learn more\b",
    r"\bfor more details\b",
    r"\bthe rest of the video\b",
]

FORMAT_RE = re.compile(
    r"^S:\s*\S[^\n\r]*\r?\nV:\s*\S[^\n\r]*(?:\r?\n)?$"
)

NUM_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")

def _text(completion) -> str:
    return (completion[0].get("content") or "").strip()

def _split_sv(text: str) -> tuple[str, str]:
    # Returns (S, V) or ("","") if parse fails
    lines = (text or "").strip().splitlines()
    if len(lines) != 2:
        return "", ""

    s_line, v_line = lines
    if not s_line.startswith("S:") or not v_line.startswith("V:"):
        return "", ""

    return s_line[2:].strip(), v_line[2:].strip()

def _tokens(s: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", s.lower())

def _content_words(s: str) -> list[str]:
    toks = _tokens(s)
    return [t for t in toks if t not in STOPWORDS and len(t) > 2]

def _repeat_penalty(words: list[str]) -> float:
    # Penalize heavy repetition
    if not words:
        return 0.0
    
    c = Counter(words)
    top = c.most_common(1)[0][1]
    frac = top / max(1, len(words))

    return max(0.0, frac - 0.12)  # Allow a little repetition

def reward_format(completions, **kwargs):
    scores = []

    for comp in completions:
        t = _text(comp)
        scores.append(1.0 if FORMAT_RE.match(t) else -3.0)

    return scores

def reward_length(completions, target_chars, duration_seconds=None, **kwargs): # target_chars is a list aligned with completions
    scores = []

    soft_max_disable_after_seconds = float(kwargs.get("soft_max_disable_after_seconds", 1500.0))
    soft_max_disable_after_seconds = max(0.0, soft_max_disable_after_seconds)

    n_items = min(len(completions), len(target_chars))
    if duration_seconds is None:
        durations = [0.0] * n_items
    elif isinstance(duration_seconds, (list, tuple)):
        durations = list(duration_seconds[:n_items])
        if len(durations) < n_items:
            durations.extend([0.0] * (n_items - len(durations)))
    else:
        durations = [duration_seconds] * n_items

    for i in range(n_items):
        comp = completions[i]
        tgt = target_chars[i]
        dur = float(durations[i] or 0.0)
        t = _text(comp)
        n = len(t)

        tgt = float(tgt)
        tgt = max(200.0, min(3000.0, tgt))

        soft_max = max(1600.0, 1.15 * tgt + 250.0)
        hard_max = max(3000.0, 1.50 * tgt + 700.0)
        if soft_max_disable_after_seconds and dur >= soft_max_disable_after_seconds:
            soft_max = hard_max

        if n > hard_max:
            scores.append(-6.0 - 0.01 * (n - hard_max))
            continue

        # Strongly discourage extremely short or extremely long outputs.
        if n < 120:
            scores.append(-1.0 + (n / 120.0))
            continue
        if n > soft_max:
            scores.append(-2.5 - 0.004 * (n - soft_max))
            continue

        diff = abs(n - tgt)  # Peak near target, still ok to be shorter/longer
        scores.append(1.4 - (diff / max(1.0, tgt)))

    return scores

def reward_no_artifacts(completions, **kwargs):
    scores = []

    for comp in completions:
        t = _text(comp).lower()
        penalty = 0.0

        for pat in BANNED_PATTERNS:
            if re.search(pat, t, flags=re.DOTALL):
                penalty += 1.0

        scores.append(1.0 - penalty)

    return scores

def reward_density(completions, **kwargs):
    scores = []

    for comp in completions:
        t = _text(comp)
        s, v = _split_sv(t)
        words = _content_words(s)

        if not words:
            scores.append(-1.0)
            continue

        unique_ratio = len(set(words)) / max(1, len(words))
        rep = _repeat_penalty(words)
        scores.append(1.2 * unique_ratio - 2.0 * rep) # Favor unique content words, penalize repetition

    return scores

def reward_coverage(completions, salient_terms, **kwargs): # salient_terms is list[list[str]]
    scores = []

    for comp, terms in zip(completions, salient_terms):
        t = _text(comp)
        s, _ = _split_sv(t)
        s_low = s.lower()

        if not s:
            scores.append(-1.0)
            continue

        hits = 0
        for term in terms[:20]:
            if term.lower() in s_low:
                hits += 1

        scores.append(math.tanh(hits / 6.0) * 1.5) # Diminishing returns: 0..~1.5

    return scores

def reward_incremental_value(completions, salient_terms, evidence_text, **kwargs):
    scores = []

    # Encourage V to mention *additional* transcript-backed terms not in S
    for comp, terms, ev in zip(completions, salient_terms, evidence_text):
        t = _text(comp)
        s, v = _split_sv(t)

        if not s or not v:
            scores.append(-1.5)
            continue

        s_low, v_low = s.lower(), v.lower()
        ev_low = (ev or "").lower()
        novel_hits = 0
        backed_hits = 0

        s_words = set(_content_words(s))
        v_words = set(_content_words(v))
        # Penalize V that is essentially a restatement of S.
        overlap = (len(s_words & v_words) / max(1, len(v_words))) if v_words else 1.0

        for term in terms[:25]:
            term_l = term.lower()
            in_s = term_l in s_low
            in_v = term_l in v_low
            in_ev = term_l in ev_low

            if in_v and not in_s:
                novel_hits += 1

                if in_ev:
                    backed_hits += 1

        # Reward novelty and grounding
        score = 0.25 * novel_hits + 0.35 * backed_hits

        # Light boost when the transcript suggests on-screen visuals/demos and V mentions them.
        visuals_in_ev = bool(
            re.search(
                r"\b(on (the )?screen|as you can see|here'?s (a|the)|let'?s (look|open)|"
                r"diagram|chart|graph|demo|walkthrough|code|terminal|ui)\b",
                ev_low,
            )
        )
        visuals_in_v = bool(re.search(r"\b(visual|screen|diagram|chart|graph|demo|walkthrough|code|ui)\b", v_low))
        if visuals_in_ev and visuals_in_v:
            score += 0.4

        # Penalize high overlap (V restating S).
        score -= 1.0 * max(0.0, overlap - 0.35)

        scores.append(min(3.0, score))

    return scores

def reward_grounding_numbers(completions, evidence_text, **kwargs):
    scores = []

    # Penalize numbers not appearing in evidence (approx. verifiable)
    for comp, ev in zip(completions, evidence_text):
        t = _text(comp)
        ev = (ev or "")
        nums = set(NUM_RE.findall(t))

        if not nums:
            scores.append(0.2)  # Slight reward for avoiding random numbers
            continue

        bad = 0

        for n in nums:
            if n not in ev:
                bad += 1

        scores.append(0.5 - 0.8 * bad)

    return scores

def reward_keyword_stuffing(completions, **kwargs):
    scores = []

    # Penalize suspicious comma-separated keyword lists / spam.
    for comp in completions:
        t = _text(comp)
        commas = t.count(",")
        semis = t.count(";")

        # If tons of separators, likely stuffing.
        if commas + semis > 18:
            scores.append(-2.0)
        else:
            scores.append(0.3)
            
    return scores
