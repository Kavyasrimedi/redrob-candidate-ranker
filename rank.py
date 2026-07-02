# rank.py
#
# Main CLI entry point. Wires the full pipeline together:
#   Load → Filter → Honeypot → Score → Signals → Reason → Output
#
# Usage:
#   python rank.py --candidates data/candidates.jsonl --out submission.csv

import argparse
import json
import csv
import time

from scorer.filters  import apply_all_filters
from scorer.honeypot import compute_honeypot_penalty
from scorer.scorer   import compute_raw_score
from scorer.signals  import compute_signal_multiplier
from scorer.reasoning import generate_reasoning


def main():
    parser = argparse.ArgumentParser(description="Redrob Candidate Ranker")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out",        required=True, help="Output CSV path")
    parser.add_argument("--top",        type=int, default=100, help="Number of candidates to output")
    args = parser.parse_args()

    print("=" * 55)
    print("  Redrob AI — India Runs Candidate Ranker")
    print("=" * 55)

    # ── Stage 1 + 2: Load, filter, honeypot ─────────────────────────────────
    print("\n[1/4] Loading and filtering candidates...")
    t0 = time.time()

    total      = 0
    survived   = 0
    honeypotted = 0
    results    = []

    with open(args.candidates, encoding="utf-8") as f:
        for line in f:
            candidate = json.loads(line)
            total += 1

            if not apply_all_filters(candidate):
                continue
            survived += 1

            penalty = compute_honeypot_penalty(candidate)
            if penalty >= 1.0:
                honeypotted += 1
                continue

            results.append((candidate, penalty))

    print(f"    Total loaded:        {total:,}")
    print(f"    After filters:       {survived:,}  ({survived/total*100:.1f}%)")
    print(f"    Honeypots removed:   {honeypotted}")
    print(f"    Candidates to score: {len(results):,}")

    # ── Stage 3 + 4: Score and apply signals ────────────────────────────────
    print("\n[2/4] Scoring candidates...")
    t1 = time.time()

    scored = []
    for candidate, penalty in results:
        components   = compute_raw_score(candidate)
        signal_data  = compute_signal_multiplier(candidate)
        final_score  = round(
            components["raw_score"] * (1 - penalty) * signal_data["multiplier"], 4
        )
        scored.append((final_score, components, signal_data, candidate))

    scored.sort(reverse=True, key=lambda x: x[0])
    print(f"    Done in {time.time()-t1:.1f}s")
    print(f"    Score range: {scored[-1][0]:.2f} – {scored[0][0]:.2f}")

    # ── Stage 5: Generate reasoning + write output ───────────────────────────
    print("\n[3/4] Generating reasoning for top candidates...")
    top = scored[:args.top]

    rows = []
    for rank, (score, components, signal_data, candidate) in enumerate(top, 1):
        reasoning = generate_reasoning(candidate, components, signal_data)
        rows.append({
            "rank":                rank,
            "candidate_id":        candidate["candidate_id"],
            "final_score":         score,
            "title_score":         components["title_score"],
            "skill_score":         components["skill_score"],
            "exp_score":           components["exp_score"],
            "company_score":       components["company_score"],
            "signal_multiplier":   signal_data["multiplier"],
            "current_title":       candidate["profile"].get("current_title", ""),
            "years_of_experience": candidate["profile"].get("years_of_experience", 0),
            "location":            candidate["profile"].get("location", ""),
            "reasoning":           reasoning,
        })

    # ── Write CSV ─────────────────────────────────────────────────────────────
    print(f"\n[4/4] Writing {args.top} candidates to {args.out}...")
    fieldnames = list(rows[0].keys())
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'='*55}")
    print(f"  Done in {time.time()-t0:.1f}s total")
    print(f"  Output: {args.out}")
    print(f"{'='*55}\n")

    # ── Preview top 5 ─────────────────────────────────────────────────────────
    print("Top 5 candidates:")
    print(f"{'Rank':<5} {'ID':<15} {'Score':<8} {'Title':<35} {'Exp':>5}")
    print("-" * 72)
    for row in rows[:5]:
        print(
            f"{row['rank']:<5} {row['candidate_id']:<15} "
            f"{row['final_score']:<8} {row['current_title'][:33]:<35} "
            f"{row['years_of_experience']:>5.1f}"
        )


if __name__ == "__main__":
    main()