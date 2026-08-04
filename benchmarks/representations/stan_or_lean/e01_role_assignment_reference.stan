parameters {
  real<lower=0> first;
  real<lower=0> second;
  real Z;
}
model {
  Z ~ normal(first, second);
}
