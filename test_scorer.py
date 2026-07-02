# test_scorer.py
import json
from scorer.filters import apply_all_filters
from scorer.honeypot import compute_honeypot_penalty
from scorer.scorer import compute_raw_score

scores = []

with open("data/candidates.jsonl") as f:
    for line in f:
        candidate = json.loads(line)
        if not apply_all_filters(candidate):
            continue
        penalty    = compute_honeypot_penalty(candidate)
        components = compute_raw_score(candidate)
        final      = round(components["raw_score"] * (1 - penalty), 2)
        scores.append((final, components, candidate))

scores.sort(reverse=True, key=lambda x: x[0])

print(f"Scored: {len(scores):,} candidates")
print(f"Score range: {scores[-1][0]:.2f} – {scores[0][0]:.2f}")
print(f"Mean score:  {sum(s[0] for s in scores)/len(scores):.1f}")
print()
print("Top 10 candidates:")
print(f"{'Rank':<6}{'ID':<20}{'Title':<40}{'Score':<8}{'Title_S':<9}{'Skill_S':<9}{'Exp_S':<7}{'Co_S'}")
print("-" * 105)
for i, (score, comp, cand) in enumerate(scores[:10], 1):
    title = cand["profile"]["current_title"][:38]
    print(f"{i:<6}{cand['candidate_id']:<20}{title:<40}{score:<8}{comp['title_score']:<9}{comp['skill_score']:<9}{comp['exp_score']:<7}{comp['company_score']}")