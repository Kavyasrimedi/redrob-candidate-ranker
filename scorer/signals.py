# scorer/signals.py
#
# Stage 4: Behavioral signal multiplier from Redrob platform data.
#
# These 23 signals tell us about candidate AVAILABILITY and ENGAGEMENT,
# not just fit. A perfect-fit candidate who hasn't logged in for 8 months
# and has a 5% response rate is effectively unreachable — deprioritise them.
#
# Design: multiplier ranges from 0.5 (very poor signals) to 1.2 (exceptional).
# Applied as: final_score = raw_score * multiplier
# So it adjusts ranking but doesn't override fit — a weak candidate with
# great signals still won't beat a strong candidate with average signals.

from datetime import datetime


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None


def compute_signal_multiplier(candidate: dict) -> dict:
    """
    Compute behavioral multiplier from redrob_signals.

    Returns dict with individual signal scores + final multiplier.
    Keeping individual scores lets reasoning.py explain them.
    """
    sig = candidate.get("redrob_signals", {})
    today = datetime.now()

    scores = {}

    # ── AVAILABILITY SIGNALS (combined weight: 35%) ──────────────────────────

    # 1. Open to work — binary but important
    scores["open_to_work"] = 1.0 if sig.get("open_to_work_flag") else 0.3

    # 2. Notice period — shorter is better for recruiter urgency
    notice = sig.get("notice_period_days", 90)
    if notice <= 30:
        scores["notice_period"] = 1.0
    elif notice <= 60:
        scores["notice_period"] = 0.7
    elif notice <= 90:
        scores["notice_period"] = 0.5
    else:
        scores["notice_period"] = 0.2

    # 3. Willing to relocate (bonus if preferred locations don't match)
    scores["relocation"] = 1.0 if sig.get("willing_to_relocate") else 0.6

    # ── ENGAGEMENT SIGNALS (combined weight: 35%) ────────────────────────────

    # 4. Last active date — how recently were they on the platform
    last_active = _parse_date(sig.get("last_active_date"))
    if last_active:
        days_inactive = (today - last_active).days
        if days_inactive <= 7:
            scores["recency"] = 1.0
        elif days_inactive <= 30:
            scores["recency"] = 0.85
        elif days_inactive <= 90:
            scores["recency"] = 0.6
        elif days_inactive <= 180:
            scores["recency"] = 0.35
        else:
            scores["recency"] = 0.1   # inactive 6+ months — very unlikely to respond
    else:
        scores["recency"] = 0.5

    # 5. Recruiter response rate — how often they actually reply
    response_rate = sig.get("recruiter_response_rate", 0.5)
    scores["response_rate"] = response_rate   # already 0.0–1.0

    # 6. Avg response time — faster is better
    response_hours = sig.get("avg_response_time_hours", 48)
    if response_hours <= 4:
        scores["response_speed"] = 1.0
    elif response_hours <= 24:
        scores["response_speed"] = 0.8
    elif response_hours <= 72:
        scores["response_speed"] = 0.5
    else:
        scores["response_speed"] = 0.2

    # 7. Interview completion rate
    scores["interview_completion"] = sig.get("interview_completion_rate", 0.5)

    # ── CREDIBILITY SIGNALS (combined weight: 20%) ───────────────────────────

    # 8. Profile completeness
    completeness = sig.get("profile_completeness_score", 50) / 100.0
    scores["profile_completeness"] = completeness

    # 9. Verified contact info
    verified = (sig.get("verified_email", False) and sig.get("verified_phone", False))
    scores["verified"] = 1.0 if verified else 0.5

    # 10. Github activity — signals active coding practice
    github = sig.get("github_activity_score", 0) / 100.0
    scores["github_activity"] = github

    # 11. Skill assessment scores — average across all assessed skills
    assessments = sig.get("skill_assessment_scores", {})
    if assessments:
        avg_assessment = sum(assessments.values()) / len(assessments) / 100.0
        scores["skill_assessment"] = avg_assessment
    else:
        scores["skill_assessment"] = 0.5   # no assessments = neutral

    # ── SALARY FIT (weight: 10%) ──────────────────────────────────────────────
    # JD budget assumption: 25–60 LPA for Senior AI Engineer
    # Candidates expecting way above budget are a practical mismatch
    salary = sig.get("expected_salary_range_inr_lpa", {})
    sal_min = salary.get("min", 0)
    sal_max = salary.get("max", 0)
    if sal_max == 0:
        scores["salary_fit"] = 0.7   # unknown — neutral-ish
    elif sal_min <= 60 and sal_max >= 20:
        scores["salary_fit"] = 1.0   # within reasonable range
    elif sal_min > 80:
        scores["salary_fit"] = 0.3   # expecting far above likely budget
    else:
        scores["salary_fit"] = 0.6

    # ── COMBINE INTO MULTIPLIER ───────────────────────────────────────────────
    weights = {
        "open_to_work":          0.10,
        "notice_period":         0.08,
        "relocation":            0.05,
        "recency":               0.12,
        "response_rate":         0.12,
        "response_speed":        0.06,
        "interview_completion":  0.08,
        "profile_completeness":  0.08,
        "verified":              0.05,
        "github_activity":       0.08,
        "skill_assessment":      0.08,
        "salary_fit":            0.10,
    }

    weighted_sum = sum(scores[k] * weights[k] for k in weights)
    # Scale weighted_sum (0–1) to multiplier range 0.5–1.2
    multiplier = 0.5 + (weighted_sum * 0.7)
    multiplier = round(min(max(multiplier, 0.5), 1.2), 4)

    return {
        "signal_scores":  scores,
        "multiplier":     multiplier,
    }