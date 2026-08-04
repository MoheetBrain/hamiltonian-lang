import numpy as np

N, P = 120, 4
predictors = np.zeros((N, P))
prior_location = np.zeros(P)
prior_scale = 1.0

rng = np.random.default_rng(203)
coefficients = rng.normal(prior_location, prior_scale)
noise_scale = abs(rng.normal(0.0, prior_scale))
response = rng.normal(predictors @ coefficients, noise_scale)
# The conditioning set is implicit in which names appear on the right-hand side.
