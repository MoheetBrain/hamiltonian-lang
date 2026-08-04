from scipy import stats
first, second = 1.0, 2.0
Z = stats.norm(scale=second, loc=first)   # keyword order is irrelevant in Python too
