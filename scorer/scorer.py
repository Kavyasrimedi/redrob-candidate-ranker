# scorer/scorer.py
#
# Stage 3: Weighted fit scoring.
# Produces a raw score 0–100 for each candidate that survives filters.
#
# Score components and their max contributions:
#   Title tier score      → up to 30 points
#   Skill match score     → up to 40 points
#   Experience fit score  → up to 15 points
#   Company type score    → up to 15 points
#   Total                 → 100 points max (before behavioral multiplier)

from scorer.jd_parser import (
    MUST_HAVE_SKILLS,
    NICE_TO_HAVE_SKILLS,
    TITLE_TIER_1,
    TITLE_TIER_2,
    TITLE_TIER_3,
    IT_SERVICES_COMPANIES,
    FICTIONAL_COMPANIES,
    EXP_IDEAL_MIN,
    EXP_IDEAL_MAX,
)


def _normalise(text: str) -> str:
    return text.lower().strip() if text else ""


# ── COMPONENT 1: TITLE TIER SCORE (max 30 pts) ──────────────────────────────

def score_title(candidate: dict) -> float:
    """
    Score based on current title's relevance to the role.

    Why title matters so much: the JD explicitly warns about candidates
    who list AI skills but whose actual career trajectory is unrelated.
    A 'Senior NLP Engineer' with 6 years is a fundamentally different
    signal than a 'Marketing Manager' who listed NLP in their skills.

    Tier 1 (exact match):  30 pts
    Tier 2 (adjacent):     18 pts
    Tier 3 (weak signal):   8 pts
    No tier (mismatch):     0 pts
    """
    title = _normalise(candidate["profile"].get("current_title", ""))

    if any(t in title for t in TITLE_TIER_1):
        return 30.0
    if any(t in title for t in TITLE_TIER_2):
        return 18.0
    if any(t in title for t in TITLE_TIER_3):
        return 8.0
    return 0.0


# ── COMPONENT 2: SKILL MATCH SCORE (max 40 pts) ─────────────────────────────

def score_skills(candidate: dict) -> float:
    """
    Score based on skill match against JD requirements.

    Key design decision: we don't just check IF a skill is present.
    We weight each matched skill by:
      - Its importance weight from jd_parser (must-have vs nice-to-have)
      - Proficiency level (expert > advanced > intermediate > beginner)
      - Endorsements (social proof that the skill is real)
      - Duration in months (used the skill for 2 months vs 36 months)

    This is how we catch 'Marketing Manager with 9 AI skills listed' —
    those skills will have 0 endorsements and 1-2 months duration,
    so their weighted contribution is near zero.
    """
    skills = candidate.get("skills", [])
    if not skills:
        return 0.0

    # Build a lookup: skill_name → skill data
    skill_lookup = {_normalise(s["name"]): s for s in skills}

    proficiency_multiplier = {
        "expert":       1.0,
        "advanced":     0.75,
        "intermediate": 0.5,
        "beginner":     0.25,
    }

    must_have_score    = 0.0
    must_have_max      = sum(MUST_HAVE_SKILLS.values())
    nice_to_have_score = 0.0
    nice_to_have_max   = sum(NICE_TO_HAVE_SKILLS.values())

    for skill_name, weight in MUST_HAVE_SKILLS.items():
        if skill_name in skill_lookup:
            s        = skill_lookup[skill_name]
            prof     = proficiency_multiplier.get(s.get("proficiency", ""), 0.25)
            # Endorsements: normalise to 0–1 using log scale (30+ endorsements → ~1.0)
            endorse  = min(s.get("endorsements", 0) / 30.0, 1.0)
            # Duration: normalise to 0–1 (36+ months → 1.0)
            duration = min((s.get("duration_months", 0) or 0) / 36.0, 1.0)
            # Combine: proficiency is primary, endorsements and duration add depth
            quality  = (prof * 0.5) + (endorse * 0.3) + (duration * 0.2)
            must_have_score += weight * quality

    for skill_name, weight in NICE_TO_HAVE_SKILLS.items():
        if skill_name in skill_lookup:
            s        = skill_lookup[skill_name]
            prof     = proficiency_multiplier.get(s.get("proficiency", ""), 0.25)
            endorse  = min(s.get("endorsements", 0) / 30.0, 1.0)
            quality  = (prof * 0.6) + (endorse * 0.4)
            nice_to_have_score += weight * quality

    # Must-haves contribute 32 pts max, nice-to-haves contribute 8 pts max
    must_norm      = (must_have_score / must_have_max) * 32 if must_have_max else 0
    nice_norm      = (nice_to_have_score / nice_to_have_max) * 8 if nice_to_have_max else 0

    return round(must_norm + nice_norm, 4)


# ── COMPONENT 3: EXPERIENCE FIT SCORE (max 15 pts) ──────────────────────────

def score_experience(candidate: dict) -> float:
    """
    Score based on how well total experience matches the ideal band.

    Ideal band: EXP_IDEAL_MIN to EXP_IDEAL_MAX (4–10 years).
    Perfect score for being inside the band.
    Partial score for being close but outside.
    Zero for being far outside (already caught by hard filter).
    """
    exp = candidate["profile"].get("years_of_experience", 0) or 0

    if EXP_IDEAL_MIN <= exp <= EXP_IDEAL_MAX:
        return 15.0   # perfect band fit

    if exp < EXP_IDEAL_MIN:
        # Below ideal — scale down proportionally
        shortfall = EXP_IDEAL_MIN - exp
        return max(0.0, 15.0 - (shortfall * 3.0))

    # Above ideal — mild penalty (overqualified but not disqualified)
    excess = exp - EXP_IDEAL_MAX
    return max(0.0, 15.0 - (excess * 2.0))


# ── COMPONENT 4: COMPANY TYPE SCORE (max 15 pts) ────────────────────────────

def score_company_type(candidate: dict) -> float:
    """
    Score based on career company trajectory.

    Product company experience = strong signal (built real systems for users).
    Mix of IT services + product = neutral.
    Only fictional companies = neutral (dataset filler, can't penalise).

    We look at ALL companies in career history, not just current.
    """
    career = candidate.get("career_history", [])
    if not career:
        return 7.5   # no data — give neutral score

    companies = [_normalise(r.get("company", "")) for r in career]

    it_count      = sum(1 for c in companies if any(it in c for it in IT_SERVICES_COMPANIES))
    fictional_count = sum(1 for c in companies if c in FICTIONAL_COMPANIES)
    product_count  = len(companies) - it_count - fictional_count

    total_real = it_count + product_count
    if total_real == 0:
        return 7.5   # only fictional — neutral

    product_ratio = product_count / total_real

    if product_ratio >= 0.8:
        return 15.0   # mostly product companies
    if product_ratio >= 0.5:
        return 10.0   # healthy mix
    if product_ratio >= 0.2:
        return 5.0    # mostly IT services
    return 2.0        # almost entirely IT services (didn't get caught by filter
                      # because filter only removes 100% IT services careers)


# ── MASTER SCORER ────────────────────────────────────────────────────────────

def compute_raw_score(candidate: dict) -> dict:
    """
    Compute all score components and return them individually + combined.

    Returning components separately (not just a total) is intentional —
    reasoning.py uses these to generate human-readable explanations,
    and it lets us audit why any candidate scored the way they did.
    """
    title_score   = score_title(candidate)
    skill_score   = score_skills(candidate)
    exp_score     = score_experience(candidate)
    company_score = score_company_type(candidate)

    total = title_score + skill_score + exp_score + company_score

    return {
        "title_score":   round(title_score, 2),
        "skill_score":   round(skill_score, 2),
        "exp_score":     round(exp_score, 2),
        "company_score": round(company_score, 2),
        "raw_score":     round(total, 2),
    }