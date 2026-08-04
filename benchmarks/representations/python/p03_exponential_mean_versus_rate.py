import numpy as np

mean_wait_minutes = 4.0
# numpy parameterises by SCALE (= mean), not rate:
rng = np.random.default_rng(103)
wait = rng.exponential(scale=mean_wait_minutes)
# R's rexp() parameterises by RATE. The same number means different things.
rate = 1.0 / mean_wait_minutes  # 0.25 per minute
