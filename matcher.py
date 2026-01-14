import numpy as np

W_P, W_A, W_C = 0.40, 0.35, 0.25

def similarity(v1, v2):
    diffs = [abs(v1[k] - v2[k]) for k in v1]
    return 1 - np.mean(diffs)

def capability_score(user, job):
    scores = []
    for k in job:
        if user[k] >= job[k]:
            scores.append(1)
        else:
            scores.append(user[k] / job[k])
    return sum(scores) / len(scores)

def exclusion_penalty(user_x, job_x):
    penalty = 0
    for k in user_x:
        if user_x[k] and job_x.get(k, False):
            penalty += 0.15
    return min(penalty, 0.60)

def fit_score(user, job):
    base = (
        W_P * similarity(user["P"], job["P_job"]) +
        W_A * similarity(user["A"], job["A_job"]) +
        W_C * capability_score(user["C"], job["C_job"])
    )
    final = base * (1 - exclusion_penalty(user["X"], job["X_job"]))
    return round(final * 100, 1)
