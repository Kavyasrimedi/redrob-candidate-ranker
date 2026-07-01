# scorer/jd_parser.py
#
# This file encodes the Job Description into structured data.
# Nothing here is automatic — every decision below is a deliberate
# interpretation of what the JD actually says.
# If you're asked "why did you weight NLP higher than cloud skills?"
# the answer lives in this file.

# ── EXPERIENCE ──────────────────────────────────────────────────────────────
# JD says "5–9 years", but explicitly says "we're flexible on the edges
# for exceptional candidates". So we set a soft ideal band and a hard
# disqualify band (e.g. 0–1 year is clearly junior, 20+ is mismatch).

EXP_IDEAL_MIN = 4        # anything below this gets penalised
EXP_IDEAL_MAX = 10       # anything above this gets penalised
EXP_HARD_MIN  = 2        # below this = hard disqualify (too junior)
EXP_HARD_MAX  = 22       # above this = hard disqualify (too senior/mismatch)

# ── MUST-HAVE SKILLS ─────────────────────────────────────────────────────────
# These are skills the JD treats as core to the role.
# Weight = how central this skill is to "Senior AI Engineer doing ranking/search"
# Higher weight → bigger score impact when matched, bigger penalty when missing.
# Weights don't need to add to 1 — the scorer will normalise later.

MUST_HAVE_SKILLS = {
    "machine learning":          10,
    "nlp":                       10,
    "natural language processing": 10,
    "information retrieval":     9,
    "ranking systems":           9,
    "recommendation systems":    8,
    "deep learning":             8,
    "python":                    7,
    "search":                    7,
    "neural networks":           6,
    "transformer":               6,
    "bert":                      6,
    "llm":                       5,
    "large language models":     5,
    "vector search":             5,
    "embeddings":                5,
    "rag":                       4,
    "retrieval augmented generation": 4,
}

# ── NICE-TO-HAVE SKILLS ──────────────────────────────────────────────────────
# Mentioned in JD as "good to have" or implied by the product context.
# These add to score but their absence is not penalised.

NICE_TO_HAVE_SKILLS = {
    "faiss":              3,
    "elasticsearch":      3,
    "pytorch":            4,
    "tensorflow":         3,
    "mlops":              3,
    "feature engineering": 3,
    "a/b testing":        3,
    "redis":              2,
    "kafka":              2,
    "docker":             2,
    "kubernetes":         2,
    "sql":                2,
    "spark":              2,
    "fastapi":            2,
    "flask":              2,
    "airflow":            2,
    "aws":                2,
    "gcp":                2,
    "azure":              2,
}

# ── TITLE SIGNALS ────────────────────────────────────────────────────────────
# Titles that suggest genuine ML/AI career trajectory.
# Split into tiers — a "Senior ML Engineer" with 6 years is a stronger
# signal than a "Software Engineer" even if both have the same skill list.
# This is how we catch the "Marketing Manager with 9 AI skills" trap.

TITLE_TIER_1 = [          # near-exact role match
    "senior ai engineer",
    "senior machine learning engineer",
    "senior ml engineer",
    "senior nlp engineer",
    "senior data scientist",
    "senior software engineer (ml)",
    "ai research engineer",
    "machine learning engineer",
    "nlp engineer",
    "ml engineer",
    "computer vision engineer",    # adjacent — not ideal but real ML
]

TITLE_TIER_2 = [          # adjacent — relevant but not ideal
    "data scientist",
    "analytics engineer",
    "search engineer",
    "software engineer",           # only valid if ML skills are strong
    "full stack developer",        # only valid if ML skills are strong
    "junior ml engineer",          # valid, penalised for seniority mismatch
]

TITLE_TIER_3 = [          # weak signal — needs exceptional skill compensation
    "cloud engineer",
    "devops engineer",
    "data engineer",
    "data analyst",
]

# Anything not in the above three tiers = Tier 0 (clear mismatch)
# e.g. "HR Manager", "Accountant", "Civil Engineer", "Content Writer"
# These should be caught by filters.py before they even reach the scorer.

# ── DISQUALIFYING TITLE PATTERNS ─────────────────────────────────────────────
# If current_title is any of these AND they have no actual ML career history,
# they are removed in Stage 1 (filters.py) regardless of skills listed.

DISQUALIFYING_TITLES = [
    "hr manager", "human resources", "accountant", "sales executive",
    "content writer", "graphic designer", "civil engineer",
    "mechanical engineer", "customer support", "operations manager",
    "marketing manager", "business analyst", "project manager",
    "mobile developer", ".net developer", "java developer",
]

# ── COMPANY TYPE SIGNALS ─────────────────────────────────────────────────────
# JD explicitly says: "IT services-only background is a red flag".
# Someone whose entire career is Infosys → Wipro → TCS with no product
# company is penalised. A product company is one that ships its own software
# to end users — not body-shopping or outsourcing.
# 
# Note: working at one of these is fine; working ONLY at these is a red flag.

IT_SERVICES_COMPANIES = {
    "infosys", "wipro", "tcs", "tata consultancy services",
    "accenture", "capgemini", "cognizant", "hcl", "mphasis",
    "tech mahindra", "hexaware", "l&t infotech", "ltimindtree",
}

# Fictional companies in the dataset (used as fillers — treat as neutral,
# not as "product companies" but not penalised either)
FICTIONAL_COMPANIES = {
    "wayne enterprises", "initech", "pied piper", "globex inc",
    "acme corp", "dunder mifflin", "hooli", "stark industries",
}

# ── LOCATION SIGNALS ─────────────────────────────────────────────────────────
# JD mentions these locations explicitly as acceptable.
# Candidates outside this list are not disqualified — just scored lower.

PREFERRED_LOCATIONS = {
    "bangalore", "bengaluru", "hyderabad", "chennai",
    "pune", "mumbai", "remote", "delhi", "noida", "gurgaon",
}

# ── BEHAVIORAL SIGNAL WEIGHTS ─────────────────────────────────────────────────
# These come from redrob_signals_doc — applied as a multiplier in signals.py.
# Values here define how much each signal nudges the final score.
# Range of final multiplier: 0.5 (very poor signals) to 1.2 (exceptional).

SIGNAL_WEIGHTS = {
    "profile_completeness_score":   0.20,
    "response_rate_score":          0.20,
    "active_last_30_days":          0.15,
    "open_to_work":                 0.15,
    "skill_endorsement_count":      0.10,
    "application_quality_score":    0.10,
    "cultural_fit_indicators":      0.10,
}