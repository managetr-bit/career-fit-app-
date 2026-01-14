import streamlit as st
import json
from matcher import fit_score

# -----------------------------
# Page setup (must be first)
# -----------------------------
st.set_page_config(page_title="Career Fit MVP", layout="centered")
st.title("Career Fit Results")
st.caption("MVP: profile → match → explainable recommendations")

# -----------------------------
# Load jobs (JSON embedded)
# -----------------------------
@st.cache_data
def load_jobs():
    with open("jobs_onet_mvp.json", "r", encoding="utf-8") as f:
        return json.load(f)

jobs = load_jobs()

# -----------------------------
# Helpers
# -----------------------------
def normalize_education_level(level: str) -> float:
    # maps to 0–1 scale
    mapping = {
        "High school": 0.25,
        "Associate / Diploma": 0.40,
        "Bachelor’s": 0.55,
        "Master’s": 0.70,
        "PhD / Doctorate": 0.90,
        "Other / Prefer not to say": 0.50,
    }
    return mapping.get(level, 0.50)

def normalize_experience_years(bucket: str) -> float:
    mapping = {
        "0–2": 0.20,
        "3–5": 0.40,
        "6–10": 0.60,
        "10+": 0.80,
    }
    return mapping.get(bucket, 0.40)

def normalize_learning_appetite(choice: str) -> float:
    mapping = {
        "Prefer mastery of what I know": 0.30,
        "Comfortable learning gradually": 0.60,
        "Actively seek steep learning curves": 0.90,
    }
    return mapping.get(choice, 0.60)

def education_gap(user_edu: float, job_required_edu: float) -> float:
    # positive gap means job needs higher education level than user currently has
    return max(0.0, job_required_edu - user_edu)

def education_penalty(gap: float, mode: str) -> float:
    # returns penalty factor in [0, 0.60]
    if gap <= 0:
        return 0.0
    if mode == "Strict":
        return 0.60  # effectively removes it from top ranks
    if mode == "Flexible":
        return min(0.35, gap * 0.35)
    # Transform
    return min(0.15, gap * 0.15)

def categorize_fit(score_pct: float) -> str:
    if score_pct >= 80:
        return "Best Fit"
    if score_pct >= 65:
        return "Strong Fit"
    if score_pct >= 55:
        return "Safe Fit"
    return "Low Fit"

def simple_skill_tags(selected):
    # lightweight encoding only (MVP)
    # used to mildly lift jobs in those families later if you want
    return selected

# -----------------------------
# UI: Assessment (MVP)
# -----------------------------
with st.expander("Assessment (MVP) — Answer to get your results", expanded=True):

    st.subheader("A) Work style & personality")
    p_independence = st.slider("I prefer working independently (vs collaborating constantly)", 0.0, 1.0, 0.6)
    p_ambiguity = st.slider("I am comfortable with uncertainty and ambiguity", 0.0, 1.0, 0.6)
    p_structure = st.slider("I prefer structured work with clear processes", 0.0, 1.0, 0.6)
    p_cognitive = st.slider("I prefer analytical/data-driven work (vs intuitive/creative)", 0.0, 1.0, 0.7)
    p_pace = st.slider("I prefer fast-paced environments", 0.0, 1.0, 0.6)

    # Mapping to MVP P vector
    P_user = {
        "independence": p_independence,
        "ambiguity": p_ambiguity,
        "structure": p_structure,
        "cognitive": p_cognitive,
        "pace": p_pace,
    }

    st.divider()
    st.subheader("B) Aspirations & preferences")
    a_income = st.slider("Income priority", 0.0, 1.0, 0.7)
    a_purpose = st.slider("Purpose / impact importance", 0.0, 1.0, 0.7)
    leadership_track = st.selectbox("Career path preference", ["Expert / specialist", "Leadership / management", "Hybrid / undecided"])
    a_leadership = {"Expert / specialist": 0.3, "Leadership / management": 0.8, "Hybrid / undecided": 0.5}[leadership_track]
    modality = st.selectbox("Work location preference", ["Fully remote", "Hybrid", "Mostly on-site", "No preference"])
    a_flexibility = {"Fully remote": 0.9, "Hybrid": 0.7, "Mostly on-site": 0.3, "No preference": 0.6}[modality]
    a_balance = st.slider("Work–life balance importance", 0.0, 1.0, 0.6)

    A_user = {
        "income": a_income,
        "purpose": a_purpose,
        "leadership": a_leadership,
        "flexibility": a_flexibility,
        "balance": a_balance,
    }

    st.divider()
    st.subheader("C) Capabilities & readiness")

    edu_level = st.selectbox(
        "Highest education level completed",
        ["High school", "Associate / Diploma", "Bachelor’s", "Master’s", "PhD / Doctorate", "Other / Prefer not to say"]
    )
    exp_bucket = st.selectbox("Years of professional experience", ["0–2", "3–5", "6–10", "10+"])
    skill_clusters = st.multiselect(
        "Primary skill areas (select up to 3)",
        ["Analysis / Data", "Strategy / Planning", "Technology / Digital", "Design / Creative",
         "Operations / Delivery", "Finance / Economics", "Policy / Research", "People / Facilitation"],
        default=["Analysis / Data"]
    )
    learning_appetite = st.selectbox(
        "Learning appetite",
        ["Prefer mastery of what I know", "Comfortable learning gradually", "Actively seek steep learning curves"]
    )

    # Education/Training (new requested UI)
    st.markdown("### Education/Training")
    st.caption("If your education/training is not in the list, type it below. We will use it to interpret your background (MVP: stored as text).")
    edu_free_text = st.text_input(
        "Add your education/training (free text)",
        placeholder="e.g., BSc Civil Engineering, PMP, Lean Six Sigma Green Belt, CFA Level 1, HVAC apprenticeship..."
    )

    edu_mode = st.radio(
        "Education flexibility",
        ["Strict", "Flexible", "Transform"],
        index=1,
        help="Strict: recommend only roles aligned with current education. Flexible: allow certifications/short training. Transform: allow new degree if match is excellent."
    )
    time_invest_months = st.slider("Willing to invest time in learning (months)", 0, 24, 6)

    C_user = {
        "education": normalize_education_level(edu_level),
        "experience": normalize_experience_years(exp_bucket),
        "learning": normalize_learning_appetite(learning_appetite),
        # MVP: skills are not numeric; kept for future scoring refinements
    }
    user_skill_tags = simple_skill_tags(skill_clusters)

    st.divider()
    st.subheader("D) Exclusions & constraints")
    avoid_sales = st.checkbox("Avoid sales-driven roles")
    avoid_political = st.checkbox("Avoid highly political environments")
    avoid_travel = st.checkbox("Avoid constant travel")

    X_user = {
        "sales": avoid_sales,
        "political": avoid_political,
        "travel": avoid_travel,
    }

user = {"P": P_user, "A": A_user, "C": C_user, "X": X_user}

# -----------------------------
# Score all jobs
# -----------------------------
results = []
for job in jobs:
    # base score from your matcher (uses vectors in the job record)
    base_score = fit_score(user, job)  # expected to return 0–100 or 0–1? your matcher returns percent in earlier examples

    # Ensure base_score is 0–100
    if base_score <= 1.0:
        base_score = base_score * 100.0

    # Education gap logic using Job Zone proxy (if present)
    # Our embedded dataset includes job_zone 1..5; map to required education 0–1
    job_zone = job.get("job_zone", 3)
    job_required_edu = {1: 0.30, 2: 0.45, 3: 0.60, 4: 0.75, 5: 0.90}.get(int(job_zone), 0.60)

    gap = education_gap(C_user["education"], job_required_edu)
    pen = education_penalty(gap, edu_mode)
    final_score = round(base_score * (1 - pen), 1)

    results.append({
        "job_id": job.get("job_id"),
        "title": job.get("title"),
        "family": job.get("job_family"),
        "job_zone": job_zone,
        "score": final_score,
        "base_score": round(base_score, 1),
        "edu_gap": round(gap, 2),
        "category": categorize_fit(final_score),
    })

results = sorted(results, key=lambda x: x["score"], reverse=True)

# -----------------------------
# Results UI (Approved structure)
# -----------------------------
st.divider()
st.subheader("Your Results")

# Confidence proxy (simple for MVP): top score
top_score = results[0]["score"] if results else 0
st.metric("Overall Fit Confidence (proxy)", f"{top_score:.0f}%")

with st.expander("What we understood about you", expanded=True):
    st.write("**Work style**")
    st.write(f"- Independence preference: **{P_user['independence']:.2f}**")
    st.write(f"- Ambiguity tolerance: **{P_user['ambiguity']:.2f}**")
    st.write(f"- Analytical orientation: **{P_user['cognitive']:.2f}**")
    st.write("")
    st.write("**Preferences**")
    st.write(f"- Income priority: **{A_user['income']:.2f}**")
    st.write(f"- Purpose / impact: **{A_user['purpose']:.2f}**")
    st.write(f"- Flexibility: **{A_user['flexibility']:.2f}**")
    st.write("")
    st.write("**Education/Training**")
    st.write(f"- Current education level: **{edu_level}**")
    st.write(f"- Flexibility mode: **{edu_mode}** | Time investment: **{time_invest_months} months**")
    if edu_free_text.strip():
        st.write(f"- Free-text entry: *{edu_free_text}*")
    st.write("")
    st.write("**Exclusions**")
    exclusions = [k for k, v in X_user.items() if v]
    st.write("- " + (", ".join(exclusions) if exclusions else "None"))

# Split: Ready Now vs Best Potential
ready_now = [r for r in results if r["edu_gap"] <= 0.01]
best_potential = [r for r in results if r["edu_gap"] > 0.01]

st.markdown("## ✅ Ready Now")
if ready_now:
    for r in ready_now[:5]:
        st.metric(f"{r['title']}  ·  {r['family']}", f"{r['score']}%")
        st.caption(f"Job Zone: {r['job_zone']} | Fit: {r['category']}")
else:
    st.info("No strong 'Ready Now' matches found under your current education constraint. Consider switching to Flexible/Transform.")

st.markdown("## ⭐ Best Potential (if you are open to learning)")
if edu_mode == "Strict":
    st.info("You selected **Strict** mode, so potential roles requiring additional education are suppressed.")
else:
    if best_potential:
        for r in best_potential[:5]:
            label = "Requires upskilling" if r["edu_gap"] <= 0.15 else "Requires new education"
            st.metric(f"{r['title']}  ·  {r['family']}", f"{r['score']}%")
            st.caption(f"{label} | Job Zone: {r['job_zone']} | Education gap: {r['edu_gap']}")
    else:
        st.info("No additional 'Best Potential' roles identified beyond Ready Now.")

st.divider()
st.caption("Disclaimer: MVP decision-support tool. Not hiring advice or certification.")
