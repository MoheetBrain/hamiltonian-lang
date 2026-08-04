# Uniform continuity is not decidable and not enumerable in Python.
# A test harness can only sample, which tests neither direction of the claim.
def sampled_uniform_continuity(f, eps, delta, samples):
    return all(abs(f(u) - f(v)) < eps
               for u in samples for v in samples if abs(u - v) < delta)
# Note the delta is passed IN, so the existential has already been discharged
# by the caller. The quantifier structure is lost.
