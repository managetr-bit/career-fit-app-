import streamlit as st
import json
from matcher import fit_score

st.set_page_config(page_title="Career Fit MVP", layout="centered")
st.title("Career Fit Results")

# --- User input (simplified MVP) ---
P_user = {
    "independence": st.slider("Independent work preference", 0.0, 1.0, 0.6),
    "ambiguity": st.slider("Comfort with ambiguity", 0.0, 1.0, 0.6),
    "cognitive": st.slider("Analytical thinking", 0.0, 1.0, 0.7),
    "pace": st.slider("Fast-paced work", 0.0, 1.0, 0.6),
    "structure": st.slider("Preference for structure", 0.0, 1.0, 0.6)
}

A_user = {
    "income": st.slider("Income priority", 0.0, 1.0, 0.7),
    "purpose": st.slider("Purpose / impact", 0.0, 1.0, 0.7),
    "leadership": st.slider("Leadership ambition", 0.0, 1.0, 0.4),
    "flexibility": st.slider("Flexibility", 0.0, 1.0, 0.7),
    "balance": st.slider("Work-life balance", 0.0, 1.0, 0.6)
}

C_user = {
    "education": st.slider("Education level", 0.0, 1.0, 0.6),
    "experience": st.slider("Experience level", 0.0, 1.0, 0.5),
    "learning": st.slider("Learning appetite", 0.0, 1.0, 0.7)
}

X_user = {
    "sales": st.checkbox("Avoid sales roles"),
    "political": st.checkbox("Avoid political environments"),
    "travel": st.checkbox("Avoid frequent travel")
}

user = {"P": P_user, "A": A_user, "C": C_user, "X": X_user}

# --- Load jobs ---
with open("jobs.json") as f:
    jobs = json.load(f)

# --- Score jobs ---
results = []
for job in jobs:
    score = fit_score(user, job)
    results.append({ "title": job["title"], "family": job["family"], "score": score })

results = sorted(results, key=lambda x: x["score"], reverse=True)

st.subheader("Top Career Matches")
for r in results[:5]:
    st.metric(r["title"], f"{r['score']}%")
