# rank.py
# Usage: python rank.py --candidates data/candidates.jsonl --out submission.csv

import argparse
import json
import csv
import time

from scorer.filters   import apply_all_filters
from scorer.honeypot  import compute_honeypot_penalty
from scorer.scorer    import compute_raw_score
from scorer.signals   import compute_signal_multiplier
from scorer.reasoning import generate_reasoning


def main():
    parser = argparse.ArgumentParser(description="Redrob Candidate Ranker")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out",        required=True, help="Output CSV path")
    parser.add_argument("--top",        type=int, default=100)
    args = parser.parse_args()

    print("=" * 55)
    print("  Redrob AI — India Runs Candidate Ranker")
    print("=" * 55)

    # ── Stage 1 + 2: Load, filter, honeypot ─────────────────────────────────
    print("\n[1/4] Loading and filtering candidates...")
    t0 = time.time()

    total       = 0
    survived    = 0
    honeypotted = 0
    results     = []

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

    # ── Stage 3 + 4: Score and signals ──────────────────────────────────────
    print("\n[2/4] Scoring candidates...")
    t1 = time.time()

    scored = []
    for candidate, penalty in results:
        components  = compute_raw_score(candidate)
        signal_data = compute_signal_multiplier(candidate)
        raw_final   = components["raw_score"] * (1 - penalty) * signal_data["multiplier"]
        scored.append((raw_final, components, signal_data, candidate))

    scored.sort(reverse=True, key=lambda x: x[0])

    # Normalise scores to 0–1 range (required by spec)
    max_score = scored[0][0] if scored else 1.0
    min_score = scored[-1][0] if scored else 0.0
    score_range = max_score - min_score if max_score != min_score else 1.0

    print(f"    Done in {time.time()-t1:.1f}s")
    print(f"    Raw score range: {min_score:.2f} – {max_score:.2f}")

    # ── Stage 5: Reasoning + write output ───────────────────────────────────
    print("\n[3/4] Generating reasoning and writing output...")
    top = scored[:args.top]

    # Spec requires exactly: candidate_id, rank, score, reasoning
    rows = []
    for rank, (raw_score, components, signal_data, candidate) in enumerate(top, 1):
        # Normalise to 0–1, preserve ordering
        normalised_score = round(
            (raw_score - min_score) / score_range, 4
        )
        reasoning = generate_reasoning(candidate, components, signal_data)
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "rank":         rank,
            "score":        normalised_score,
            "reasoning":    reasoning,
        })

    # ── Write CSV ────────────────────────────────────────────────────────────
    print(f"\n[4/4] Writing {args.top} candidates to {args.out}...")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id","rank","score","reasoning"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'='*55}")
    print(f"  Done in {time.time()-t0:.1f}s total")
    print(f"  Output: {args.out}")
    print(f"{'='*55}\n")

    # ── Preview top 5 ────────────────────────────────────────────────────────
    print("Top 5 candidates:")
    print(f"{'Rank':<5} {'ID':<15} {'Score':<8} {'Title':<35} {'Exp':>5}")
    print("-" * 68)
    for rank, (raw, comp, sig, c) in enumerate(top[:5], 1):
        norm = round((raw - min_score) / score_range, 4)
        print(
            f"{rank:<5} {c['candidate_id']:<15} {norm:<8} "
            f"{c['profile'].get('current_title','')[:33]:<35} "
            f"{c['profile'].get('years_of_experience',0):>5.1f}"
        )


if __name__ == "__main__":
    main()