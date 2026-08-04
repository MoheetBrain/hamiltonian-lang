import numpy as np

# drift: any real number
# jitter: a standard deviation, therefore strictly positive
drift = 0.0
jitter = 1.0

rng = np.random.default_rng(101)
E = rng.normal(loc=drift, scale=jitter)
# numpy's 'scale' is a standard deviation; scipy agrees; MATLAB's normrnd also.
# Nothing in this file enforces jitter > 0 before it is used.
