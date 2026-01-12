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
    r"^S:\s*\S[^\n\r]*\r?\nV:\s*\S[^\n\r]*\s*$"
)

NUM_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")

TOKEN_EST_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)

def _text(completion) -> str:
    return (completion[0].get("content") or "").strip()

def _split_sv(text: str) -> tuple[str, str]:
    """
    Returns (S, V) or ("","") if parse fails
    """
    lines = (text or "").strip().splitlines()
    if len(lines) != 2:
        return "", ""
    
    s_line, v_line = lines
    if not s_line.startswith("S:") or not v_line.startswith("V:"):
        return "", ""
    
    return s_line[2:].strip(), v_line[2:].strip()

def _tokens(s: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", (s or "").lower())

def _tok_count_est(s: str) -> int:
    return len(TOKEN_EST_RE.findall(s or ""))

def _content_words(s: str) -> list[str]:
    toks = _tokens(s)
    return [t for t in toks if t not in STOPWORDS and len(t) > 2]

def _repeat_penalty(words: list[str]) -> float:
    """
    Penalize heavy repetition of a single content word.
    """
    if not words:
        return 0.0
    
    c = Counter(words)
    top = c.most_common(1)[0][1]
    frac = top / max(1, len(words))
    return max(0.0, frac - 0.12)  # Allow a little repetition

def _clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)

def _norm_nums(text: str) -> set[str]:
    """
    Normalize numeric strings to reduce false penalties:
    - Remove commas (1,000 -> 1000)
    - Normalize ' percent' -> '%'
    """
    t = (text or "").lower().replace(",", "")
    t = t.replace(" percent", "%")
    return set(NUM_RE.findall(t))

def _approx_tokens_from_target_chars(target_chars: float) -> float:
    """
    ~4 chars/token for text, within a reasonable band to avoid extreme targets.
    """
    return _clip(target_chars / 4.0, 160.0, 900.0)

def reward_format(completions, **kwargs):
    """
    Must be EXACTLY 2 lines with S: and V:.
    """
    scores = []

    for comp in completions:
        t = _text(comp)
        scores.append(1.0 if FORMAT_RE.match(t) else -3.0)

    return scores


def reward_length(completions, target_chars, duration_seconds=None, **kwargs):
    """
    Length reward in *token-estimate space* to directly push mean tokens higher:
      - Strong ramp-up until min_tokens (prevents short outputs)
      - Peak near tgt_tokens
      - Soft penalty above soft_max, harsh penalty above hard_max
    """
    scores = []

    soft_max_disable_after_seconds = float(kwargs.get("soft_max_disable_after_seconds", 1500.0))
    soft_max_disable_after_seconds = max(0.0, soft_max_disable_after_seconds)

    n_items = min(len(completions), len(target_chars))

    # Normalize durations
    if duration_seconds is None:
        durations = [0.0] * n_items
    elif isinstance(duration_seconds, (list, tuple)):
        durations = list(duration_seconds[:n_items])
        if len(durations) < n_items:
            durations.extend([0.0] * (n_items - len(durations)))
    else:
        durations = [duration_seconds] * n_items

    min_floor_tokens = float(kwargs.get("min_floor_tokens", 220.0))  # Absolute floor
    min_frac_of_target = float(kwargs.get("min_frac_of_target", 0.70))  # Floor relative to target

    for i in range(n_items):
        comp = completions[i]
        tgt_chars = float(target_chars[i] or 0.0)
        tgt_chars = _clip(tgt_chars, 200.0, 3000.0)

        dur = float(durations[i] or 0.0)
        t = _text(comp)
        n = float(_tok_count_est(t))  # Token-estimate length

        tgt_tokens = _approx_tokens_from_target_chars(tgt_chars)

        # Floor target to push mean tokens up
        min_tokens = max(min_floor_tokens, min_frac_of_target * tgt_tokens)

        # Soft/hard maxima around target
        soft_max = max(min_tokens + 40.0, 1.20 * tgt_tokens + 40.0)
        hard_max = max(soft_max + 80.0, 1.55 * tgt_tokens + 120.0)

        if soft_max_disable_after_seconds and dur >= soft_max_disable_after_seconds:
            soft_max = hard_max

        # If hard over-length, strong penalty
        if n > hard_max:
            scores.append(-6.0 - 0.03 * (n - hard_max))
            continue

        # If too short, ramp up from negative to ~0 as it approaches min_tokens
        if n < min_tokens:
            scores.append(-1.8 + 1.8 * (n / max(1.0, min_tokens))) # At 0 tokens => -1.8, at min_tokens => ~0.0
            continue

        # If too long (above soft max), mild slope
        if n > soft_max:
            scores.append(0.6 - 0.02 * (n - soft_max))
            continue

        # When in-range, peak near target, but don't punish slightly longer too hard
        diff = abs(n - tgt_tokens)
        scores.append(1.6 - (diff / max(1.0, tgt_tokens))) # 1.6 at target, decays with relative error

    return scores


def reward_no_artifacts(completions, **kwargs):
    """
    Penalize LLM artifacts / banned phrases.
    Clipped so it doesn't dominate.
    """
    scores = []
    per_hit = float(kwargs.get("artifact_per_hit_penalty", 0.8))
    min_score = float(kwargs.get("artifact_min_score", -1.5))

    for comp in completions:
        t = _text(comp).lower()
        penalty = 0.0

        for pat in BANNED_PATTERNS:
            if re.search(pat, t, flags=re.DOTALL):
                penalty += per_hit

        scores.append(max(min_score, 1.0 - penalty))

    return scores


def reward_density(completions, **kwargs):
    """
    Reward informative, non-repetitive content across both S and V.
    """
    scores = []

    w_s = float(kwargs.get("density_weight_s", 0.55))
    w_v = float(kwargs.get("density_weight_v", 0.45))

    for comp in completions:
        t = _text(comp)
        s, v = _split_sv(t)

        if not s and not v:
            scores.append(-1.0)
            continue

        words_s = _content_words(s)
        words_v = _content_words(v)

        words = (words_s * int(round(w_s * 10))) + (words_v * int(round(w_v * 10)))

        # If both are empty, treat as low density
        if not words:
            scores.append(-1.0)
            continue

        unique_ratio = len(set(words)) / max(1, len(words))
        rep = _repeat_penalty(words)
        scores.append(1.3 * unique_ratio - 2.1 * rep) # Favor unique informative content; punish heavy repetition.

    return scores


def reward_coverage(completions, salient_terms, **kwargs):
    """
    Encourage covering more salient terms, without saturating too early.
    """
    scores = []

    max_terms = int(kwargs.get("coverage_max_terms", 60))
    tanh_den = float(kwargs.get("coverage_tanh_den", 10.0))
    linear_w = float(kwargs.get("coverage_linear_w", 0.02))
    base_w = float(kwargs.get("coverage_base_w", 1.1))

    for comp, terms in zip(completions, salient_terms):
        t = _text(comp)
        s, _ = _split_sv(t)
        s_low = (s or "").lower()

        if not s:
            scores.append(-1.0)
            continue

        hits = 0
        for term in (terms or [])[:max_terms]:
            term_l = (term or "").strip().lower()
            if not term_l:
                continue

            # If it's a single "word", enforce word boundaries to avoid substring gaming.
            if re.fullmatch(r"[a-z0-9']+", term_l):
                if re.search(rf"\b{re.escape(term_l)}\b", s_low):
                    hits += 1
            else:
                # For phrases, substring is acceptable (but still exact phrase)
                if term_l in s_low:
                    hits += 1

        # Bounded growth + Small continued incentive
        score = base_w * math.tanh(hits / max(1e-6, tanh_den)) + linear_w * hits
        scores.append(score)

    return scores


def reward_incremental_value(completions, salient_terms, evidence_text, **kwargs):
    """
    Encourage V to add transcript-backed info beyond S.
    """
    scores = []

    novel_w = float(kwargs.get("inc_novel_w", 0.18))
    backed_w = float(kwargs.get("inc_backed_w", 0.42))
    unbacked_pen = float(kwargs.get("inc_unbacked_pen", 0.16))
    overlap_pen = float(kwargs.get("inc_overlap_pen", 1.0))
    clip_hi = float(kwargs.get("inc_clip_hi", 3.0))

    for comp, terms, ev in zip(completions, salient_terms, evidence_text):
        t = _text(comp)
        s, v = _split_sv(t)

        if not s or not v:
            scores.append(-1.5)
            continue

        s_low, v_low = s.lower(), v.lower()
        ev_low = (ev or "").lower()

        s_words = set(_content_words(s))
        v_words = set(_content_words(v))

        overlap = (len(s_words & v_words) / max(1, len(v_words))) if v_words else 1.0 # Overlap ratio (how much V just repeats S)

        novel_hits = 0
        backed_hits = 0

        for term in (terms or [])[:35]:
            term_l = (term or "").strip().lower()
            if not term_l:
                continue

            in_s = term_l in s_low
            in_v = term_l in v_low
            in_ev = term_l in ev_low

            if in_v and not in_s:
                novel_hits += 1
                if in_ev:
                    backed_hits += 1

        unbacked = max(0, novel_hits - backed_hits)

        score = novel_w * novel_hits + backed_w * backed_hits - unbacked_pen * unbacked

        # Bonus when transcript suggests visuals and V mentions them
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

        score -= overlap_pen * max(0.0, overlap - 0.35) # Penalize high overlap (V restating S)

        scores.append(_clip(score, -2.0, clip_hi))

    return scores


def reward_grounding_numbers(completions, evidence_text, **kwargs):
    """
    Penalize numbers in output that do not appear (normalized) in evidence.
    Clipped so a few numbers don't completely dominate.
    """
    scores = []

    avoid_bonus = float(kwargs.get("num_avoid_bonus", 0.2))
    base = float(kwargs.get("num_base", 0.6))
    per_bad = float(kwargs.get("num_per_bad", 0.6))
    min_score = float(kwargs.get("num_min_score", -2.0))

    for comp, ev in zip(completions, evidence_text):
        t = _text(comp)
        ev_nums = _norm_nums(ev or "")
        out_nums = _norm_nums(t)

        if not out_nums:
            scores.append(avoid_bonus)
            continue

        bad = 0
        for n in out_nums:
            if n not in ev_nums:
                bad += 1

        score = base - per_bad * bad
        scores.append(max(min_score, score))

    return scores


def reward_keyword_stuffing(completions, **kwargs):
    """
    Penalty-only.
    """
    scores = []
    max_separators = int(kwargs.get("stuffing_max_separators", 18))
    penalty = float(kwargs.get("stuffing_penalty", -2.0))

    for comp in completions:
        t = _text(comp)
        commas = t.count(",")
        semis = t.count(";")

        if commas + semis > max_separators:
            scores.append(penalty)
        else:
            scores.append(0.0)

    return scores
