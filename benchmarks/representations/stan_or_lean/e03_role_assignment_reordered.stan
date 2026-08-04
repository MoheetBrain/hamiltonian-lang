// Stan's normal() is POSITIONAL, so this reordering cannot be expressed:
// there is no way to write the scale before the location.
parameters {
  real<lower=0> first;
  real<lower=0> second;
  real Z;
}
model {
  Z ~ normal(first, second);
}
