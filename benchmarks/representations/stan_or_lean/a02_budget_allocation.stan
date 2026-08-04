// A linear program is not a natural Stan model; encoded as a bounded parameter
// space with a linear log-density, which is a reformulation, not a translation.
data {
  real<lower=0> budget;
}
parameters {
  real<lower=0> digital;
  real<lower=0> print_spend;
}
model {
  target += (digital + print_spend <= budget) ? (3.1 * digital + 1.4 * print_spend)
                                              : negative_infinity();
}
