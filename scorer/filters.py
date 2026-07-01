# scorer/filters.py
#
# Stage 1: Hard disqualification filters.
# Each function returns True if the candidate PASSES (should survive),
# False if they should be eliminated.
#
# Design principle: only eliminate when we're CERTAIN they don't fit.
# When in doubt, let the candidate through to the scorer — false negatives
# (missing a good candidate) are worse than false positives here.

from scorer.jd_parser import (
    DISQUALIFYING_TITLES,
    IT_SERVICES_COMPANIES,
    FICTIONAL_COMPANIES,
    EXP_HARD_MIN,
    EXP_HARD_MAX,
)


def _normalise(text: str) -> str:
    """Lowercase and strip whitespace — used before every string comparison."""
    return text.lower().strip() if text else ""


def passes_title_filter(candidate: dict) -> bool:
    """
    Eliminate candidates whose current title is a clear mismatch AND
    whose career history shows no ML/AI trajectory at all.

    Why both conditions? A 'Software Engineer' who spent 5 years building
    ML systems is valid even though the title looks generic. We only hard-
    eliminate when BOTH the title AND history point away from ML/AI.
    """
    title = _normalise(candidate["profile"].get("current_title", ""))

    is_bad_title = any(bad in title for bad in DISQUALIFYING_TITLES)
    if not is_bad_title:
        return True  # title looks fine, pass through

    # Title is bad — check if career history redeems them
    career = candidate.get("career_history", [])
    ml_keywords = {
        "machine learning", "ml", "ai", "nlp", "deep learning",
        "data science", "neural", "ranking", "search", "recommendation"
    }

    for role in career:
        role_title = _normalise(role.get("title", ""))
        role_desc  = _normalise(role.get("description", ""))
        if any(kw in role_title or kw in role_desc for kw in ml_keywords):
            return True

    return False  # bad title + no ML history = eliminate


def passes_experience_filter(candidate: dict) -> bool:
    """
    Eliminate candidates outside the hard experience bounds.

    NOTE: years_of_experience lives inside candidate["profile"],
    not at the top level — this is the actual schema.
    """
    exp = candidate["profile"].get("years_of_experience", 0)
    if exp is None:
        exp = 0
    return EXP_HARD_MIN <= exp <= EXP_HARD_MAX


def passes_company_type_filter(candidate: dict) -> bool:
    """
    Eliminate candidates whose ENTIRE career is at IT services companies.

    One stint at Infosys + product company experience = fine.
    Only Infosys → Wipro → TCS → Cognizant with nothing else = eliminated.
    """
    career = candidate.get("career_history", [])
    if not career:
        return True  # no history — don't eliminate, let scorer handle

    companies_worked = set()
    for role in career:
        company = _normalise(role.get("company", ""))
        companies_worked.add(company)

    # Remove fictional companies (neutral filler in dataset)
    real_companies = companies_worked - FICTIONAL_COMPANIES

    if not real_companies:
        return True  # only fictional companies — neutral, pass through

    all_it_services = all(
        any(it in company for it in IT_SERVICES_COMPANIES)
        for company in real_companies
    )

    return not all_it_services  # pass if NOT entirely IT services


def passes_research_only_filter(candidate: dict) -> bool:
    """
    Eliminate pure researchers with zero production deployment.

    Signal: every role title contains research/intern/phd terms
    AND no description mentions shipping/production/deployed.
    """
    career = candidate.get("career_history", [])
    if not career:
        return True

    research_signals   = {"research", "phd", "intern", "student", "scholar"}
    production_signals = {
        "production", "deployed", "launched", "shipped", "serving",
        "real-time", "live", "scaled", "millions", "users"
    }

    all_research = all(
        any(rs in _normalise(r.get("title", "")) for rs in research_signals)
        for r in career
    )

    if not all_research:
        return True  # mixed career — not pure research, pass through

    has_production = any(
        any(ps in _normalise(r.get("description", "")) for ps in production_signals)
        for r in career
    )

    return has_production  # eliminate only if pure research AND no production signals


def apply_all_filters(candidate: dict) -> bool:
    """
    Master filter — runs all checks in order.
    Returns True if candidate survives ALL filters (should be scored).
    Order: cheapest/most-eliminating first for performance.
    """
    return (
        passes_title_filter(candidate)
        and passes_experience_filter(candidate)
        and passes_company_type_filter(candidate)
        and passes_research_only_filter(candidate)
    )