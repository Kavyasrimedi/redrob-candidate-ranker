# scorer/honeypot.py
#
# Stage 2: Honeypot / contradictory profile detection.
#
# Design: some signals are hard overrides (one strike = penalty 1.0),
# others are soft and get combined. This reflects the nature of the data:
# a fabricated experience claim of 8+ years is mathematically impossible
# and cannot be explained by data quality issues — it's a hard signal.
# Skill inflation or minor date overlaps are softer and get weighted.

from datetime import datetime


def _parse_date(date_str: str):
    """Parse date string to datetime. Returns None if unparseable."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def check_experience_vs_dates(candidate: dict) -> float:
    """
    Hard signal: claimed years_of_experience far exceeds career date math.

    Calibrated to this dataset — 10 candidates with ML titles claim
    8–11 more years than their earliest job start date supports.
    This is mathematically impossible, not a data quality issue.

    Returns 1.0 (hard override) if discrepancy > 7 years.
    """
    claimed = candidate["profile"].get("years_of_experience", 0) or 0
    career  = candidate.get("career_history", [])

    starts = [_parse_date(r.get("start_date")) for r in career]
    starts = [s for s in starts if s]

    if not starts or claimed == 0:
        return 0.0

    actual_years = (datetime.now() - min(starts)).days / 365.25
    discrepancy  = claimed - actual_years

    if discrepancy > 7:
        return 1.0   # hard override — fabricated experience claim
    if discrepancy > 4:
        return 0.6
    if discrepancy > 2:
        return 0.2
    return 0.0


def check_tenure_vs_company_age(candidate: dict) -> float:
    """Soft signal: single role tenure exceeding realistic company age."""
    for role in candidate.get("career_history", []):
        duration = role.get("duration_months", 0) or 0
        if duration > 240:
            return 1.0
        if duration > 180:
            return 0.5
    return 0.0


def check_date_overlaps(candidate: dict) -> float:
    """Soft signal: heavily overlapping full-time role dates."""
    career = candidate.get("career_history", [])
    if len(career) < 2:
        return 0.0

    periods = []
    for role in career:
        start = _parse_date(role.get("start_date"))
        end   = _parse_date(role.get("end_date")) if role.get("end_date") else datetime.now()
        if start and end and end > start:
            periods.append((start, end))

    periods.sort(key=lambda x: x[0])
    max_overlap = 0
    for i in range(len(periods) - 1):
        if periods[i][1] > periods[i + 1][0]:
            overlap = (periods[i][1] - periods[i + 1][0]).days / 30
            max_overlap = max(max_overlap, overlap)

    if max_overlap > 12:
        return 0.8
    if max_overlap > 6:
        return 0.4
    return 0.0


def check_skill_inflation(candidate: dict) -> float:
    """Soft signal: unnaturally inflated skill profile."""
    skills = candidate.get("skills", [])
    if not skills:
        return 0.0

    total         = len(skills)
    expert_count  = sum(1 for s in skills if s.get("proficiency") == "expert")
    avg_endorse   = sum(s.get("endorsements", 0) for s in skills) / total

    penalty = 0.0
    if total > 20:
        penalty += 0.3
    if expert_count > 10:
        penalty += 0.4
    if avg_endorse > 30:
        penalty += 0.3
    return min(penalty, 1.0)


def compute_honeypot_penalty(candidate: dict) -> float:
    """
    Master honeypot scorer — returns penalty 0.0 to 1.0.

    Architecture: hard overrides first, then soft signals combined.
    If ANY hard signal fires, we return 1.0 immediately.
    Soft signals are weighted and combined only if no hard signal fires.

    Final score in scorer.py = raw_score * (1 - honeypot_penalty)
    So penalty 1.0 → score becomes 0, never reaches top 100.
    """
    # ── Hard overrides (one strike = penalty 1.0) ──────────────────────────
    if check_experience_vs_dates(candidate) == 1.0:
        return 1.0

    if check_tenure_vs_company_age(candidate) == 1.0:
        return 1.0

    # ── Soft signals (weighted combination) ────────────────────────────────
    soft_penalties = {
        "tenure":          check_tenure_vs_company_age(candidate),
        "date_overlap":    check_date_overlaps(candidate),
        "skill_inflation": check_skill_inflation(candidate),
        "exp_vs_dates":    check_experience_vs_dates(candidate),
    }
    soft_weights = {
        "tenure":          0.30,
        "date_overlap":    0.35,
        "skill_inflation": 0.15,
        "exp_vs_dates":    0.20,
    }
    weighted = sum(soft_penalties[k] * soft_weights[k] for k in soft_penalties)
    return min(weighted, 1.0)