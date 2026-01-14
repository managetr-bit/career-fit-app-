import streamlit as st
import json
from pathlib import Path
from matcher import fit_score

# -----------------------------
# Page setup (must be first)
# -----------------------------
st.set_page_config(page_title="Career Fit MVP", layout="centered")
st.title("Career Fit Results")
st.caption("MVP: profile → match → explainable recommendations")

# -----------------------------
# Load jobs (robust file search)
# -----------------------------
@st.cache_data
def load_jobs():
    candidates = [
        Path("jobs_onet_mvp.json"),
        Path("./jobs_onet_mvp.json"),
        Path("data/jobs_onet_mvp.json"),
        Path("./data/jobs_onet_mvp.json"),
    ]
    for p in candidates:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)

    st.error("Cannot find jobs_onet_mvp.json. Put it in the repo root (same folder as app.py) and redeploy.")
    st.stop()

jobs = load_jobs()

# -----------------------------
# Normalizers
# -----------------------------
def edu_to_01(level: str) -> float:
    mapping = {
        "High school": 0.25,
        "Associate / Diploma": 0.40,
        "Bachelor’s": 0.55,
        "Master’s": 0.70,
        "PhD / Doctorate": 0.90,
        "Other / Prefer not to say": 0.50,
    }
    return mapping.get(level, 0.50)

def exp_to_01(bucket: str) -> float:
    mapping = {"0–2": 0.20, "3–5": 0.40, "6–10": 0.60, "10+": 0.80}
    return mapping.get(bucket, 0.40)

def learning_to_01(choice: str) -> float:
    mapping = {
        "Prefer mastery of what I know": 0.30,
        "Comfortable learning gradually": 0.60,
        "Actively seek steep learning curves": 0.90,
    }
    return mapping.get(choice, 0.60)

def jobzone_required_edu(job_zone: int) -> float:
    return {1: 0.30, 2: 0.45, 3: 0.60, 4: 0.75, 5: 0.90}.get(int(job_zone), 0.60)

def edu_penalty(gap: float, mode: str) -> float:
    if gap <= 0:
        return 0.0
    if mode == "Strict":
        return 0.60
    if mode == "Flexible":
        return min(0.35, gap * 0.35)
    return min(0.15, gap * 0.15)

# -----------------------------
# UI: Assessment
# -----------------------------
st.subheader("Assessment (MVP)")
st.write("Adjust inputs, then click **Compute results**.")

with st.expander("A) Work style & personality", expanded=True):
    P_user = {
        "independence": st.slider("Prefer independent work", 0.0, 1.0, 0.6),
        "ambiguity": st.slider("Comfort with ambiguity", 0.0, 1.0, 0.6),
        "cognitive": st.slider("Analytical orientation", 0.0, 1.0, 0.7),
        "pace": st.slider("Prefer fast pace", 0.0, 1.0, 0.6),
        "structure": st.slider("Prefer structure", 0.0, 1.0, 0.6),
    }

with st.expander("B) Aspirations & preferences", expanded=True):
    leadership_track = st.selectbox("Career path preference", ["Expert / specialist", "Leadership / management", "Hybrid / undecided"])
    A_user = {
        "income": st.slider("Income priority", 0.0, 1.0, 0.7),
        "purpose": st.slider("Purpose / impact", 0.0, 1.0, 0.7),
        "leadership": {"Expert / specialist": 0.3, "Leadership / management": 0.8, "Hybrid / undecided": 0.5}[leadership_track],
        "flexibility": {"Fully remote": 0.9, "Hybrid": 0.7, "Mostly on-site": 0.3, "No preference": 0.6}[st.selectbox("Work location preference", ["Fully remote", "Hybrid", "Mostly on-site", "No preference"])],
        "balance": st.slider("Work–life balance importance", 0.0, 1.0, 0.6),
    }

with st.expander("C) Capabilities + Education/Training", expanded=True):
    edu_level = st.selectbox("Highest education completed", ["High school", "Associate / Diploma", "Bachelor’s", "Master’s", "PhD / Doctorate", "Other / Prefer not to say"])
    exp_bucket = st.selectbox("Years of experience", ["0–2", "3–5", "6–10", "10+"])
    learning_choice = st.selectbox("Learning appetite", ["Prefer mastery of what I know", "Comfortable learning gradually", "Actively seek steep learning curves"])

    st.markdown("### Education/Training (free text)")
    edu_free_text = st.text_input(
        "Add your education/training (if not listed)",
        placeholder="e.g., BSc Civil Engineering, PMP, CFA Level 1, HVAC apprenticeship..."
    )

    edu_mode = st.radio(
        "Education flexibility",
        ["Strict", "Flexible", "Transform"],
        index=1,
        help="Strict: only current education. Flexible: allow certifications/short training. Transform: allow new degree if match is excellent."
    )

    time_months = st.slider("Willing to invest time in learning (months)", 0, 24, 6)

    C_user = {
        "education": edu_to_01(edu_level),
        "experience": exp_to_01(exp_bucket),
        "learning": learning_to_01(learning_choice),
    }

with st.expander("D) Exclusions", expanded=True):
    X_user = {
        "sales": st.checkbox("Avoid sales-driven roles"),
        "political": st.checkbox("Avoid highly political environments"),
        "travel": st.checkbox("Avoid constant travel"),
    }

user = {"P": P_user, "A": A_user, "C": C_user, "X": X_user}

# Debug line so you SEE that changes are captured
st.caption(f"Debug (should change): income={A_user['income']:.2f} | purpose={A_user['purpose']:.2f} | edu={C_user['education']:.2f} | mode={edu_mode}")

st.divider()

# -----------------------------
# Compute results (button)
# -----------------------------
if st.button("Compute results"):
    results = []
    for job in jobs:
        base = fit_score(user, job)
        if base <= 1.0:
            base *= 100.0

        jz = int(job.get("job_zone", 3))
        required = jobzone_required_edu(jz)
        gap = max(0.0, required - C_user["education"])
        pen = edu_penalty(gap, edu_mode)
        final = round(base * (1 - pen), 1)

        results.append({
            "title": job.get("title", "Unknown"),
            "family": job.get("job_family", "Unknown"),
            "job_zone": jz,
            "score": final,
            "edu_gap": round(gap, 2)
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    st.subheader("✅ Ready Now")
    ready = [r for r in results if r["edu_gap"] <= 0.01]
    if ready:
        for r in ready[:5]:
            st.metric(f"{r['title']} · {r['family']}", f"{r['score']}%")
            st.caption(f"Job Zone: {r['job_zone']}")
    else:
        st.info("No strong Ready Now matches. Try Flexible/Transform or increase education level.")

    st.subheader("⭐ Best Potential")
    if edu_mode == "Strict":
        st.info("Strict mode hides roles requiring extra education.")
    else:
        potential = [r for r in results if r["edu_gap"] > 0.01]
        for r in potential[:5]:
            label = "Requires upskilling" if r["edu_gap"] <= 0.15 else "Requires new education"
            st.metric(f"{r['title']} · {r['family']}", f"{r['score']}%")
            st.caption(f"{label} | Job Zone: {r['job_zone']} | Gap: {r['edu_gap']}")

    st.divider()
    st.caption("Disclaimer: MVP decision-support tool. Not hiring advice.")
else:
    st.info("Adjust inputs, then click **Compute results**.")
