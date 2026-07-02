# scorer/reasoning.py
#
# Generates reasoning per candidate for the submission CSV.
#
# Spec requires at Stage 4:
# - Specific facts from the candidate's profile (title, years, named skills)
# - Connection to JD requirements
# - Honest concerns where gaps exist
# - No hallucination (only mention skills actually in their profile)
# - Variation across candidates (not templated)
# - Tone consistent with rank

from scorer.jd_parser import (
    MUST_HAVE_SKILLS, TITLE_TIER_1, TITLE_TIER_2,
    EXP_IDEAL_MIN, EXP_IDEAL_MAX, IT_SERVICES_COMPANIES
)


def _norm(t): return t.lower().strip() if t else ""


def generate_reasoning(candidate: dict, components: dict, signal_data: dict) -> str:
    profile  = candidate["profile"]
    title    = profile.get("current_title", "Unknown")
    exp      = profile.get("years_of_experience", 0) or 0
    location = profile.get("location", "")
    company  = profile.get("current_company", "")
    signals  = candidate.get("redrob_signals", {})

    skills      = candidate.get("skills", [])
    skill_names = [s["name"] for s in skills]
    skill_set   = {_norm(s) for s in skill_names}

    # ── Part 1: Title + experience fact ─────────────────────────────────────
    norm_title = _norm(title)
    if any(t in norm_title for t in TITLE_TIER_1):
        title_line = f"{title} with {exp:.1f} years experience"
    elif any(t in norm_title for t in TITLE_TIER_2):
        title_line = f"{title} ({exp:.1f} yrs) — adjacent to target role"
    else:
        title_line = f"{title} ({exp:.1f} yrs) — weak title match"

    # ── Part 2: Specific matched skills (only ones actually in profile) ──────
    core_skills = [
        "NLP", "Machine Learning", "Deep Learning", "Information Retrieval",
        "Ranking Systems", "Recommendation Systems", "Python",
        "Transformer", "BERT", "LLM", "Vector Search", "Embeddings", "RAG"
    ]
    matched = [s for s in core_skills if _norm(s) in skill_set]

    if matched:
        skill_line = f"matched core skills: {', '.join(matched[:4])}"
        if len(matched) > 4:
            skill_line += f" (+{len(matched)-4} more)"
    else:
        # Fall back to whatever skills they actually have
        actual = skill_names[:3]
        skill_line = f"skills on profile: {', '.join(actual) if actual else 'none relevant to JD'}"

    # ── Part 3: Experience band assessment ───────────────────────────────────
    if EXP_IDEAL_MIN <= exp <= EXP_IDEAL_MAX:
        exp_line = f"experience within ideal {EXP_IDEAL_MIN}–{EXP_IDEAL_MAX}yr band"
    elif exp < EXP_IDEAL_MIN:
        gap = EXP_IDEAL_MIN - exp
        exp_line = f"slightly under ideal band by {gap:.1f}yr"
    else:
        over = exp - EXP_IDEAL_MAX
        exp_line = f"above ideal band by {over:.1f}yr — may be overqualified"

    # ── Part 4: Honest concerns (spec requires this) ─────────────────────────
    concerns = []

    # IT services only?
    career = candidate.get("career_history", [])
    companies = [_norm(r.get("company","")) for r in career]
    it_count = sum(1 for c in companies if any(it in c for it in IT_SERVICES_COMPANIES))
    if it_count > 0 and it_count == len([c for c in companies if c]):
        concerns.append("IT services-only background")

    # Low response rate?
    resp_rate = signals.get("recruiter_response_rate", 1.0)
    if resp_rate < 0.3:
        concerns.append(f"low recruiter response rate ({resp_rate*100:.0f}%)")

    # Long notice period?
    notice = signals.get("notice_period_days", 0)
    if notice > 90:
        concerns.append(f"notice period {notice} days")

    # Not open to work?
    if not signals.get("open_to_work_flag", True):
        concerns.append("not marked open to work")

    # Inactive?
    multiplier = signal_data["multiplier"]
    if multiplier < 0.7:
        concerns.append("low platform engagement")

    # ── Part 5: Location ─────────────────────────────────────────────────────
    loc_note = f"{location}-based" if location else ""

    # ── Assemble final reasoning ──────────────────────────────────────────────
    parts = [f"{title_line}; {skill_line}; {exp_line}"]

    if loc_note:
        parts[0] += f"; {loc_note}"

    if concerns:
        parts.append(f"Concerns: {', '.join(concerns)}.")
    else:
        open_work = signals.get("open_to_work_flag", False)
        github    = signals.get("github_activity_score", 0)
        if open_work and github > 50:
            parts.append(f"Strong availability signals: open to work, GitHub activity score {github:.0f}.")
        elif open_work:
            parts.append("Open to work with good engagement signals.")

    return " ".join(parts)