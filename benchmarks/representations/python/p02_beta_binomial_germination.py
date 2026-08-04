import numpy as np
from scipy import stats

planted = 48
# prior over the germination rate
prior = stats.beta(a=2.0, b=5.0)
# likelihood, given the rate
def likelihood(sprouted, rate):
    return stats.binom.pmf(sprouted, n=planted, p=rate)

# Nothing here records that 'rate' must lie in [0, 1]; stats.binom will
# silently return nan for p outside the unit interval.
