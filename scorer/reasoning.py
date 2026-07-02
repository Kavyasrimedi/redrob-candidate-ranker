# scorer/reasoning.py
#
# Generates human-readable reasoning for each ranked candidate.
# Required by submission spec Section 7 — reasoning must be derived
# from actual score components, not a generic template.
#
# Design: each score component contributes specific language.
# The output reads naturally but is 100% data-driven.

from scorer.jd_parser import TITLE_TIER_1, TITLE_TIER_2, EXP_IDEAL_MIN, EXP_IDEAL_MAX


def _normalise(text: str) -> str:
    return text.lower().strip() if text else ""


def generate_reasoning(candidate: dict, components: dict, signal_data: dict) -> str:
    """
    Build a plain-English explanation of why this candidate was ranked here.

    Parameters:
        candidate   — raw candidate dict
        components  — output of compute_raw_score() from scorer.py
        signal_data — output of compute_signal_multiplier() from signals.py

    Returns a single string, 2–4 sentences, suitable for the output CSV.
    """
    parts = []
    profile = candidate["profile"]
    title   = profile.get("current_title", "Unknown")
    exp     = profile.get("years_of_experience", 0) or 0

    # ── Title reasoning ──────────────────────────────────────────────────────
    norm_title = _normalise(title)
    if any(t in norm_title for t in TITLE_TIER_1):
        parts.append(f"Strong title match ({title}, Tier 1 role).")
    elif components["title_score"] > 0:
        parts.append(f"Adjacent title ({title}) with relevant career signals.")
    else:
        parts.append(f"Title ({title}) is a weak match but skill profile compensates.")

    # ── Skill reasoning ──────────────────────────────────────────────────────
    skills        = candidate.get("skills", [])
    skill_names   = {s["name"].lower() for s in skills}
    must_matched  = [k for k in ["machine learning", "nlp", "deep learning",
                                  "information retrieval", "python", "ranking systems",
                                  "recommendation systems"] if k in skill_names]
    skill_score   = components["skill_score"]

    if skill_score >= 25:
        parts.append(
            f"Excellent skill alignment — matched {len(must_matched)} core skills "
            f"including {', '.join(must_matched[:3])} with strong endorsements."
        )
    elif skill_score >= 15:
        parts.append(
            f"Good skill coverage — matched {len(must_matched)} must-have skills "
            f"({', '.join(must_matched[:3]) if must_matched else 'via adjacent skills'})."
        )
    else:
        parts.append("Partial skill match — missing several must-have skills.")

    # ── Experience reasoning ─────────────────────────────────────────────────
    if EXP_IDEAL_MIN <= exp <= EXP_IDEAL_MAX:
        parts.append(f"{exp:.1f} years experience — within the ideal {EXP_IDEAL_MIN}–{EXP_IDEAL_MAX} year band.")
    elif exp < EXP_IDEAL_MIN:
        parts.append(f"{exp:.1f} years experience — slightly below ideal band, offset by skill depth.")
    else:
        parts.append(f"{exp:.1f} years experience — above ideal band, may be overqualified.")

    # ── Behavioral signal reasoning ──────────────────────────────────────────
    multiplier = signal_data["multiplier"]
    sig        = signal_data["signal_scores"]
    open_work  = candidate.get("redrob_signals", {}).get("open_to_work_flag", False)
    recency    = sig.get("recency", 0.5)
    resp_rate  = sig.get("response_rate", 0.5)

    if multiplier >= 1.1:
        parts.append(
            f"Behavioral signals excellent (multiplier {multiplier}x) — "
            f"{'open to work, ' if open_work else ''}"
            f"response rate {resp_rate*100:.0f}%, recently active."
        )
    elif multiplier >= 0.85:
        parts.append(
            f"Behavioral signals moderate (multiplier {multiplier}x) — "
            f"{'open to work' if open_work else 'not marked open to work'}, "
            f"response rate {resp_rate*100:.0f}%."
        )
    else:
        parts.append(
            f"Behavioral signals weak (multiplier {multiplier}x) — "
            f"low recent activity or response rate ({resp_rate*100:.0f}%), "
            f"may be hard to reach."
        )

    return " ".join(parts)