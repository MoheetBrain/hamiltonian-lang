from scipy import stats

sample_size = 30
failure_probability = 0.05   # unknown in general; a value is needed to instantiate
failures = stats.binom(n=sample_size, p=failure_probability)
# scipy names the roles; a positional call binom(30, 0.05) does not.
