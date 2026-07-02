# app.py — Streamlit demo for the Redrob sandbox requirement
import streamlit as st
import json
import pandas as pd
import os

from scorer.filters   import apply_all_filters
from scorer.honeypot  import compute_honeypot_penalty
from scorer.scorer    import compute_raw_score
from scorer.signals   import compute_signal_multiplier
from scorer.reasoning import generate_reasoning

st.set_page_config(page_title="Redrob Candidate Ranker", layout="wide")

st.title("🏆 Redrob AI — Candidate Ranker")
st.caption("India Runs Hackathon · Track 1 · Data & AI Challenge")

st.markdown("""
**Pipeline:** Hard filters → Honeypot detection → Weighted fit scoring → Behavioral signal multiplier → Top N ranked candidates

> **Note:** This demo accepts up to 100 candidates as a reproducibility check.
> The full 100,000-candidate run is executed via `python rank.py --candidates candidates.jsonl --out submission.csv`.
""")

# ── Input: upload or use pre-loaded sample ───────────────────────────────────
st.subheader("Input")
input_mode = st.radio(
    "Candidate source",
    ["Use pre-loaded sample (sample_candidates.json)", "Upload your own file (.json or .jsonl)"],
    horizontal=True
)

candidates = []

if input_mode.startswith("Use pre-loaded"):
    sample_path = "data/sample_candidates.json"
    if os.path.exists(sample_path):
        with open(sample_path) as f:
            candidates = json.load(f)
        st.success(f"Loaded {len(candidates)} pre-loaded sample candidates")
    else:
        st.error("sample_candidates.json not found in data/. Please upload a file instead.")

else:
    uploaded = st.file_uploader("Upload candidates (.json array or .jsonl)", type=["json","jsonl"])
    if uploaded:
        raw = uploaded.read().decode("utf-8").strip()
        if raw.startswith("["):
            candidates = json.loads(raw)
        else:
            for line in raw.splitlines():
                line = line.strip()
                if line:
                    candidates.append(json.loads(line))
        if len(candidates) > 100:
            st.warning(f"Demo accepts ≤100 candidates. Truncating to first 100.")
            candidates = candidates[:100]
        st.success(f"Loaded {len(candidates)} candidates")

# ── Run pipeline ─────────────────────────────────────────────────────────────
if candidates:
    top_n = st.slider("Candidates to show in output", 5, min(50, len(candidates)), 10)

    if st.button("▶ Run Ranker", type="primary"):
        with st.spinner("Running pipeline..."):
            results      = []
            filtered_out = 0
            honeypots    = 0

            for c in candidates:
                if not apply_all_filters(c):
                    filtered_out += 1
                    continue
                penalty = compute_honeypot_penalty(c)
                if penalty >= 1.0:
                    honeypots += 1
                    continue
                components  = compute_raw_score(c)
                signal_data = compute_signal_multiplier(c)
                final_score = round(
                    components["raw_score"] * (1 - penalty) * signal_data["multiplier"], 4
                )
                reasoning = generate_reasoning(c, components, signal_data)
                results.append({
                    "Rank":        0,
                    "ID":          c["candidate_id"],
                    "Score":       final_score,
                    "Title":       c["profile"].get("current_title", ""),
                    "Exp (yrs)":   round(c["profile"].get("years_of_experience", 0), 1),
                    "Location":    c["profile"].get("location", ""),
                    "Multiplier":  signal_data["multiplier"],
                    "Skill Score": round(components["skill_score"], 2),
                    "Title Score": components["title_score"],
                    "Reasoning":   reasoning,
                })

            results.sort(reverse=True, key=lambda x: x["Score"])
            for i, r in enumerate(results, 1):
                r["Rank"] = i

        # ── Pipeline summary ──────────────────────────────────────────────
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Input",       len(candidates))
        col2.metric("After Filters",     len(candidates) - filtered_out,
                    delta=f"-{filtered_out} eliminated")
        col3.metric("Honeypots Removed", honeypots)
        col4.metric("Final Ranked Pool", len(results))

        if len(results) == 0:
            st.warning("""
            No candidates survived the filters in this sample.
            This is expected for a small/mixed sample — the full 100k dataset
            contains ~38,700 candidates that pass filters.
            Try uploading a file with ML/AI-titled candidates.
            """)
        else:
            st.divider()

            # ── Score distribution ────────────────────────────────────────
            scores = [r["Score"] for r in results]
            st.caption(
                f"Score range: {min(scores):.2f} – {max(scores):.2f}  |  "
                f"Mean: {sum(scores)/len(scores):.2f}"
            )

            # ── Ranked table ──────────────────────────────────────────────
            st.subheader(f"Top {min(top_n, len(results))} Candidates")
            df = pd.DataFrame(results[:top_n])
            st.dataframe(
                df[["Rank","ID","Score","Title","Exp (yrs)","Location","Multiplier","Skill Score","Title Score"]],
                use_container_width=True,
                hide_index=True,
            )

            # ── Per-candidate reasoning ───────────────────────────────────
            st.subheader("Reasoning (per candidate)")
            for row in results[:top_n]:
                with st.expander(
                    f"#{row['Rank']} {row['ID']} · {row['Title']} · Score {row['Score']}"
                ):
                    st.write(row["Reasoning"])
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Final Score",   row["Score"])
                    c2.metric("Skill Score",   row["Skill Score"])
                    c3.metric("Title Score",   row["Title Score"])
                    c4.metric("Signal ×",      row["Multiplier"])

            # ── Download ──────────────────────────────────────────────────
            st.divider()
            csv_out = pd.DataFrame(results).to_csv(index=False)
            st.download_button(
                "⬇️ Download ranked CSV",
                data=csv_out,
                file_name="ranked_output.csv",
                mime="text/csv"
            )