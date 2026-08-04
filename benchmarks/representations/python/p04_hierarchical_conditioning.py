import numpy as np

G = 8
prior_location = np.zeros(G)
population_scale = 1.0    # tau > 0
measurement_scale = 1.0   # sigma > 0

rng = np.random.default_rng(104)
clinic_mean = rng.normal(loc=prior_location, scale=population_scale)
outcome = rng.normal(loc=clinic_mean, scale=measurement_scale)
# The conditional dependence structure exists only in the call order.
