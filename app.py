import streamlit as st
import json
import re
from pathlib import Path
from matcher import fit_score

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(page_title="Career Fit MVP", layout="centered")
st.title("Career Fit")
st.caption("Profile → match → explainable recommendations")

# -----------------------------
# Load jobs (robust paths)
# -----------------------------
@st.cache_data
def load_jobs():
    candidates = [
        Path("jobs_onet_mvp.json"),
        Path("jobs_onet_mvp_v2.json"),
        Path("data/jobs_onet_mvp.json"),
        Path("data/jobs_onet_mvp_v2.json"),
    ]
    for p in candidates:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return json.load(f), p.name
    st.error("Jobs dataset not found. Put jobs_onet_mvp.json in the same folder as app.py.")
    st.stop()

jobs, jobs_filename = load_jobs()

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


def categorize(score_pct: float) -> str:
    if score_pct >= 80:
        return "Best Fit"
    if score_pct >= 65:
        return "Strong Fit"
    if score_pct >= 55:
        return "Safe Fit"
    return "Low Fit"

# -----------------------------
# Domain extraction (Education/Training → domain tags)
# -----------------------------
DOMAIN_PATTERNS = {
    "Construction / Infrastructure": [
        r"civil", r"construction", r"infrastructure", r"structural", r"geotechn", r"transport", r"highway", r"bridge", r"tunnel",
        r"architecture", r"real estate", r"facility", r"facilities", r"building", r"bim", r"project controls",
    ],
    "Engineering": [r"engineering", r"mechanical", r"electrical", r"industrial", r"chemical", r"manufact", r"systems"],
    "Business / Operations": [r"business", r"management", r"operations", r"strategy", r"mba", r"supply chain", r"logistics"],
    "Finance": [r"finance", r"accounting", r"cfa", r"audit", r"econom"],
    "Policy / Public": [r"policy", r"public", r"government", r"regulation", r"urban", r"planning"],
    "Sustainability / ESG": [r"sustain", r"esg", r"climate", r"circular"],
    "Technology / IT": [r"computer", r"software", r"data", r"ai", r"machine learning", r"it", r"cyber", r"cloud"],
    "Health": [r"nursing", r"medical", r"health", r"clinic", r"pharm"],
    "Education": [r"teacher", r"teaching", r"education", r"curriculum"],
    "Writing / Communication": [r"writing", r"writer", r"communication", r"proposal", r"report", r"editor", r"journal"],
}


def extract_domains_from_text(text: str) -> list[str]:
    if not text:
        return []
    t = text.lower()
    found = []
    for domain, pats in DOMAIN_PATTERNS.items():
        for pat in pats:
            if re.search(pat, t):
                found.append(domain)
                break
    # de-duplicate while preserving order
    seen = set()
    out = []
    for d in found:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def job_domains(job: dict) -> list[str]:
    """Derive rough domains from job family + title keywords (MVP)."""
    fam = (job.get("job_family") or "").lower()
    title = (job.get("title") or "").lower()
    d = []

    # family-based
    if any(k in fam for k in ["construction", "architecture", "maintenance", "facility", "real estate", "building", "engineering"]):
        d.append("Construction / Infrastructure")
    if any(k in fam for k in ["engineering", "production", "installation", "repair"]):
        d.append("Engineering")
    if any(k in fam for k in ["business", "finance", "management", "office", "administration"]):
        d.append("Business / Operations")
    if "finance" in fam:
        d.append("Finance")
    if any(k in fam for k in ["education", "training", "library"]):
        d.append("Education")
    if any(k in fam for k in ["health", "medical", "healthcare"]):
        d.append("Health")
    if any(k in fam for k in ["computer", "it", "technology"]):
        d.append("Technology / IT")
    if any(k in fam for k in ["legal", "protective", "public", "community", "social"]):
        d.append("Policy / Public")

    # title keywords
    if any(k in title for k in ["policy", "compliance", "planner", "planning", "regulatory"]):
        d.append("Policy / Public")
    if any(k in title for k in ["sustain", "esg", "environment", "climate", "circular"]):
        d.append("Sustainability / ESG")
    if any(k in title for k in ["writer", "writing", "editor", "proposal", "report", "communications"]):
        d.append("Writing / Communication")
    if any(k in title for k in ["software", "developer", "data", "analyst", "cyber", "network"]):
        d.append("Technology / IT")

    # de-duplicate
    seen = set()
    out = []
    for x in d:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

# -----------------------------
# Skills selection (chips + free text)
# -----------------------------
SKILL_CHIPS = [
    "Writing / Communication",
    "Research",
    "Project Management",
    "Stakeholder Management",
    "Analytical Thinking",
    "Finance / Budgeting",
    "Operations",
    "Leadership",
    "Technical Engineering",
    "Design / Creative",
    "Data / Coding",
]

SKILL_PATTERNS = {
    "Writing / Communication": [r"writing", r"writer", r"proposal", r"report", r"communication", r"editing", r"editor"],
    "Research": [r"research", r"academic", r"publication", r"journal", r"study"],
    "Project Management": [r"project", r"pmp", r"schedule", r"controls", r"planning"],
    "Stakeholder Management": [r"stakeholder", r"client", r"negotiat", r"facilitat"],
    "Analytical Thinking": [r"analysis", r"analytical", r"data", r"model"],
    "Finance / Budgeting": [r"budget", r"finance", r"cost", r"capex", r"opex"],
    "Operations": [r"operations", r"process", r"delivery", r"lean"],
    "Leadership": [r"leader", r"manage", r"director"],
    "Technical Engineering": [r"engineering", r"civil", r"mechanical", r"electrical", r"structural"],
    "Design / Creative": [r"design", r"creative", r"ux", r"graphic"],
    "Data / Coding": [r"python", r"sql", r"coding", r"software", r"developer"],
}


def extract_skills_from_text(text: str) -> list[str]:
    if not text:
        return []
    t = text.lower()
    found = []
    for skill, pats in SKILL_PATTERNS.items():
        for pat in pats:
            if re.search(pat, t):
                found.append(skill)
                break
    seen = set()
    out = []
    for s in found:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

# -----------------------------
# UI — Assessment
# -----------------------------
st.subheader("Assessment")
st.caption(f"Dataset: {jobs_filename} · Occupations loaded: {len(jobs)}")

with st.expander("1) Work style & personality", expanded=True):
    P_user = {
        "independence": st.slider("Prefer independent work", 0.0, 1.0, 0.6),
        "ambiguity": st.slider("Comfort with ambiguity", 0.0, 1.0, 0.6),
        "structure": st.slider("Prefer structure", 0.0, 1.0, 0.6),
        "cognitive": st.slider("Analytical orientation", 0.0, 1.0, 0.7),
        "pace": st.slider("Prefer fast pace", 0.0, 1.0, 0.6),
    }

with st.expander("2) Aspirations & preferences", expanded=True):
    leadership_track = st.selectbox("Career path preference", ["Expert / specialist", "Leadership / management", "Hybrid / undecided"])
    modality = st.selectbox("Work location preference", ["Fully remote", "Hybrid", "Mostly on-site", "No preference"])
    A_user = {
        "income": st.slider("Income priority", 0.0, 1.0, 0.7),
        "purpose": st.slider("Purpose / impact", 0.0, 1.0, 0.7),
        "leadership": {"Expert / specialist": 0.3, "Leadership / management": 0.8, "Hybrid / undecided": 0.5}[leadership_track],
        "flexibility": {"Fully remote": 0.9, "Hybrid": 0.7, "Mostly on-site": 0.3, "No preference": 0.6}[modality],
        "balance": st.slider("Work–life balance importance", 0.0, 1.0, 0.6),
    }

with st.expander("3) Education/Training", expanded=True):
    edu_level = st.selectbox(
        "Highest education completed",
        ["High school", "Associate / Diploma", "Bachelor’s", "Master’s", "PhD / Doctorate", "Other / Prefer not to say"],
    )
    exp_bucket = st.selectbox("Years of professional experience", ["0–2", "3–5", "6–10", "10+"])
    learning_choice = st.selectbox(
        "Learning appetite",
        ["Prefer mastery of what I know", "Comfortable learning gradually", "Actively seek steep learning curves"],
    )

    st.markdown("### Education/Training (free text)")
    edu_free_text = st.text_input(
        "Add education/training (if not listed)",
        placeholder="e.g., BSc Civil Engineering, PMP, Lean Six Sigma, PhD Business Engineering...",
    )

    # Interpret tags (MVP: deterministic keyword extraction)
    inferred_domains = extract_domains_from_text(edu_free_text)
    inferred_other = []
    # show degree/cert info as 'other' (not used for strict alignment)
    if re.search(r"\bphd\b|doctor", (edu_free_text or "").lower()):
        inferred_other.append("PhD-level")
    if re.search(r"\bmsc\b|master", (edu_free_text or "").lower()):
        inferred_other.append("Master’s")
    if re.search(r"\bbsc\b|bachelor", (edu_free_text or "").lower()):
        inferred_other.append("Bachelor’s")
    if re.search(r"\bpmp\b", (edu_free_text or "").lower()):
        inferred_other.append("PMP")

    st.markdown("**Interpreted tags (preview)**")
    if inferred_domains:
        st.write("Domains (used for alignment):", ", ".join(inferred_domains))
    else:
        st.write("Domains (used for alignment): (none detected yet)")
    if inferred_other:
        st.write("Other tags (used for ranking):", ", ".join(inferred_other))

    # Modal editor (Option A) — domains only matter for strict alignment
    if "domains" not in st.session_state:
        st.session_state.domains = inferred_domains.copy()
    if "other_tags" not in st.session_state:
        st.session_state.other_tags = inferred_other.copy()

    if st.button("Edit tags"):
        st.session_state.show_modal = True

    if st.session_state.get("show_modal", False):
        with st.modal("Edit tags"):
            st.caption("Domains are used for Strict alignment. Other tags influence ranking but do not restrict recommendations.")
            st.write("### Domains (used for alignment)")
            domains_text = st.text_input("Edit domains (comma-separated)", value=", ".join(st.session_state.domains))

            st.write("### Other tags (used for ranking)")
            other_text = st.text_input("Edit other tags (comma-separated)", value=", ".join(st.session_state.other_tags))

            c1, c2 = st.columns(2)
            if c1.button("Save tags"):
                st.session_state.domains = [x.strip() for x in domains_text.split(",") if x.strip()]
                st.session_state.other_tags = [x.strip() for x in other_text.split(",") if x.strip()]
                st.session_state.show_modal = False
                st.rerun()
            if c2.button("Cancel"):
                st.session_state.show_modal = False
                st.rerun()

    strict_alignment = st.toggle("Strict alignment to my education/training", value=True)
    st.caption("Strict alignment uses DOMAIN tags only (e.g., Civil Engineering, Infrastructure). Degree and credentials do not restrict.")

    edu_mode = st.radio(
        "Education flexibility",
        ["Strict", "Flexible", "Transform"],
        index=0,
        help="Strict: only current education. Flexible: allow certifications/short training. Transform: allow new degree if match is excellent.",
    )
    time_months = st.slider("Willing to invest time in learning (months)", 0, 24, 6)

with st.expander("4) Skills to Consider", expanded=True):
    skills_selected = st.multiselect("Select strengths to prioritize (up to 5)", SKILL_CHIPS, default=[], max_selections=5)
    skills_free_text = st.text_input("Add another skill (free text)", placeholder="e.g., technical writing, proposal writing, academic publishing")

    inferred_skills = extract_skills_from_text(skills_free_text)
    all_skills = []
    for s in skills_selected + inferred_skills:
        if s not in all_skills:
            all_skills.append(s)

    st.markdown("**Skills considered in matching:**")
    st.write(", ".join(all_skills) if all_skills else "(none)")

with st.expander("5) Exclusions", expanded=False):
    X_user = {
        "sales": st.checkbox("Avoid sales-driven roles"),
        "political": st.checkbox("Avoid highly political environments"),
        "travel": st.checkbox("Avoid constant travel"),
    }

# Build user vector
C_user = {
    "education": edu_to_01(edu_level),
    "experience": exp_to_01(exp_bucket),
    "learning": learning_to_01(learning_choice),
}

user = {"P": P_user, "A": A_user, "C": C_user, "X": X_user}

# Debug line so you can confirm UI is live
st.caption(
    f"Debug: income={A_user['income']:.2f} | purpose={A_user['purpose']:.2f} | learning={C_user['learning']:.2f} | strict_alignment={strict_alignment}"
)

st.divider()

# -----------------------------
# Scoring helpers: strict alignment + skills boosts
# -----------------------------
def alignment_penalty(job_dom: list[str], user_dom: list[str], enabled: bool) -> float:
    if not enabled:
        return 0.0
    if not user_dom:
        # If user gave no domains, do not suppress.
        return 0.0
    if any(d in job_dom for d in user_dom):
        return 0.0
    # strong suppression (not absolute zero so list isn't empty)
    return 0.85


def skill_boost(job: dict, user_skills: list[str]) -> float:
    """Return multiplicative boost factor, e.g., 1.00–1.12."""
    if not user_skills:
        return 1.0
    title = (job.get("title") or "").lower()
    fam = (job.get("job_family") or "").lower()
    boost = 1.0

    # Writing/communication boost
    if "Writing / Communication" in user_skills:
        if any(k in title for k in ["writer", "writing", "proposal", "editor", "communications", "report"]):
            boost *= 1.10
        elif any(k in fam for k in ["legal", "education", "community", "social", "business"]):
            boost *= 1.04

    # Project management boost
    if "Project Management" in user_skills:
        if any(k in title for k in ["project", "manager", "planner", "controls", "coordinator"]):
            boost *= 1.08

    # Technical engineering boost
    if "Technical Engineering" in user_skills:
        if any(k in title for k in ["engineer", "engineering", "architect", "surveyor"]):
            boost *= 1.06

    # Research boost
    if "Research" in user_skills:
        if any(k in title for k in ["research", "scientist", "economist", "analyst"]):
            boost *= 1.05

    # Cap boost to avoid distortion
    return min(boost, 1.15)


def education_penalty(gap: float, mode: str) -> float:
    if gap <= 0:
        return 0.0
    if mode == "Strict":
        return 0.60
    if mode == "Flexible":
        return min(0.35, gap * 0.35)
    return min(0.15, gap * 0.15)

# -----------------------------
# Compute results
# -----------------------------
if st.button("Compute results"):
    # Use edited domains if present
    user_domains = st.session_state.get("domains", inferred_domains)

    results = []
    for job in jobs:
        base = fit_score(user, job)  # 0–100

        jz = int(job.get("job_zone", 3))
        required = jobzone_required_edu(jz)
        gap = max(0.0, required - C_user["education"])
        epen = education_penalty(gap, edu_mode)

        jdom = job_domains(job)
        apen = alignment_penalty(jdom, user_domains, strict_alignment)

        boosted = base * (1.0 - epen) * (1.0 - apen)
        boosted = boosted * skill_boost(job, all_skills)

        final = round(min(100.0, boosted), 1)

        results.append({
            "title": job.get("title", "Unknown"),
            "family": job.get("job_family", "Unknown"),
            "job_zone": jz,
            "score": final,
            "edu_gap": round(gap, 2),
            "domains": jdom,
            "category": categorize(final),
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    st.subheader("Your Results")

    # Summary chips
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Education/Training domains (alignment):**")
        st.write(", ".join(user_domains) if user_domains else "(none)")
    with col2:
        st.markdown("**Skills prioritized:**")
        st.write(", ".join(all_skills) if all_skills else "(none)")

    # Ready Now vs Best Potential
    ready_now = [r for r in results if r["edu_gap"] <= 0.01]
    best_potential = [r for r in results if r["edu_gap"] > 0.01]

    st.markdown("## ✅ Best Fit (Aligned)")
    shown = 0
    for r in results:
        if strict_alignment and user_domains and not any(d in r["domains"] for d in user_domains):
            continue
        st.metric(f"{r['title']} · {r['family']}", f"{r['score']}%")
        st.caption(f"Fit: {r['category']} | Job Zone: {r['job_zone']} | Domains: {', '.join(r['domains']) if r['domains'] else '—'}")
        shown += 1
        if shown >= 5:
            break
    if shown == 0:
        st.info("No aligned matches found with the current domain tags. Edit domains or turn off Strict alignment.")

    st.markdown("## ✍️ Best Fit using your strengths (Aligned + Skills)")
    # prioritize roles likely to use writing if selected
    def strength_rank(r):
        t = r["title"].lower()
        score = r["score"]
        if "Writing / Communication" in all_skills and any(k in t for k in ["writer", "proposal", "editor", "communications", "report"]):
            score += 5
        return score

    strength_sorted = sorted(results, key=strength_rank, reverse=True)
    shown = 0
    for r in strength_sorted:
        if strict_alignment and user_domains and not any(d in r["domains"] for d in user_domains):
            continue
        st.metric(f"{r['title']} · {r['family']}", f"{r['score']}%")
        st.caption("Aligned to your background · Uses selected strengths")
        shown += 1
        if shown >= 5:
            break

    st.markdown("## ⭐ Best Potential (Aligned, requires upskilling)")
    if edu_mode == "Strict":
        st.info("Education flexibility is set to Strict. Switch to Flexible/Transform to see upskilling pathways.")
    else:
        shown = 0
        for r in best_potential:
            if strict_alignment and user_domains and not any(d in r["domains"] for d in user_domains):
                continue
            label = "Requires upskilling" if r["edu_gap"] <= 0.15 else "Requires new education"
            st.metric(f"{r['title']} · {r['family']}", f"{r['score']}%")
            st.caption(f"{label} | Education gap: {r['edu_gap']} | Time willing: {time_months} months")
            shown += 1
            if shown >= 5:
                break
        if shown == 0:
            st.info("No aligned best-potential roles identified beyond Ready Now.")

    if strict_alignment:
        st.divider()
        with st.expander("Show unrelated roles (suppressed)", expanded=False):
            shown = 0
            for r in results:
                if user_domains and any(d in r["domains"] for d in user_domains):
                    continue
                st.metric(f"{r['title']} · {r['family']}", f"{r['score']}%")
                shown += 1
                if shown >= 10:
                    break

    st.caption("Disclaimer: MVP decision-support tool. Not hiring advice.")
else:
    st.info("Adjust inputs and click **Compute results**.")
