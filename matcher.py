import numpy as np

W_P, W_A, W_C = 0.40, 0.35, 0.25


def similarity(v1: dict, v2: dict) -> float:
    """Similarity in [0,1] via mean absolute difference across shared keys."""
    keys = [k for k in v1.keys() if k in v2]
    if not keys:
        return 0.5
    diffs = [abs(float(v1[k]) - float(v2[k])) for k in keys]
    return max(0.0, 1.0 - (sum(diffs) / len(diffs)))


def capability_score(user_c: dict, job_c: dict) -> float:
    """Threshold-aware readiness score in [0,1]."""
    if not job_c:
        return 0.5
    scores = []
    for k, req in job_c.items():
        req = float(req)
        have = float(user_c.get(k, 0.0))
        if req <= 0:
            scores.append(1.0)
        elif have >= req:
            scores.append(1.0)
        else:
            scores.append(max(0.0, have / req))
    return float(sum(scores) / len(scores))


def exclusion_penalty(user_x: dict, job_x: dict) -> float:
    """Penalty in [0,0.60]. Each conflict adds 0.15."""
    penalty = 0.0
    for k, v in user_x.items():
        if bool(v) and bool(job_x.get(k, False)):
            penalty += 0.15
    return float(min(penalty, 0.60))


def fit_score(user: dict, job: dict) -> float:
    """Return fit score as percentage [0,100]."""
    p = similarity(user.get("P", {}), job.get("P_job", {}))
    a = similarity(user.get("A", {}), job.get("A_job", {}))
    c = capability_score(user.get("C", {}), job.get("C_job", {}))

    base = (W_P * p) + (W_A * a) + (W_C * c)
    final = base * (1.0 - exclusion_penalty(user.get("X", {}), job.get("X_job", {})))
    return round(final * 100.0, 1)
