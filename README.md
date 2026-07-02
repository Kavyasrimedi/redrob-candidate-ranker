# Redrob AI — India Runs Candidate Ranker

**Track 1: Data & AI Challenge**

## What This Does

Ranks **100,000 candidate profiles** against a **Senior AI Engineer** job description, surfacing the **Top 100** most suitable candidates based on structured reasoning rather than keyword matching.

---

## Why Rule-Based Instead of Embeddings?

The Job Description explicitly warns against ranking candidates based solely on AI-related keywords. Embedding-based approaches can incorrectly rank profiles such as a **Marketing Manager** with skills like _RAG_, _LLM_, and _Pinecone_ highly because of semantic similarity.

This system instead evaluates:

- Career trajectory
- Production ML experience
- Skill quality
- Product-company background
- Candidate engagement

using an explainable, rule-based scoring pipeline.

---

## Pipeline

```text
100,000 Candidates
        │
        ▼
Stage 1: Hard Filters
• Remove title mismatches
• Experience outside range
• IT-services-only careers
• Pure research profiles
≈ 61,252 candidates removed

        │
        ▼
Stage 2: Honeypot Detection
• Detect fabricated experience
• Penalize impossible timelines
≈ 10 honeypot profiles removed

        │
        ▼
Stage 3: Weighted Fit Scoring
• Title Tier (30 pts)
• Skill Quality (40 pts)
• Experience Fit (15 pts)
• Company Type (15 pts)

        │
        ▼
Stage 4: Behavioral Signal Multiplier
0.5× – 1.2× adjustment using:
• Availability
• Recruiter engagement
• Activity
• Credibility

        │
        ▼
Top 100 Ranked Candidates
(with explainable reasoning)
```

---

## Key Design Decisions

- **Skill Quality over Skill Presence**
  - Skills are weighted using:
    - Proficiency level
    - Endorsement count
    - Duration (months)
  - Skills with minimal experience contribute very little to the final score.

- **Honeypot Calibration**
  - Thresholds were derived from actual dataset distributions.
  - Profiles with **>7 years** of unsupported experience receive a full penalty.

- **Hard Override Architecture**
  - Impossible experience timelines immediately invalidate a profile instead of being averaged with other signals.

---

## How to Run

```bash
pip install -r requirements.txt

python rank.py \
  --candidates data/candidates.jsonl \
  --out submission.csv

python validate_submission.py submission.csv
```

---

## Demo

🔗 **Live Streamlit App**

```
https://kavyasrimedi-resume-ranker.streamlit.app/
```

---

## Tech Stack

- Python 3.11
- pandas
- NumPy
- Streamlit
