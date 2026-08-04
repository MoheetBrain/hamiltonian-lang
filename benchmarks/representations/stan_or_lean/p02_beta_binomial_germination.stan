// Seed germination.
data {
  int<lower=0> planted;
  int<lower=0> sprouted;
}
parameters {
  real<lower=0, upper=1> germination_rate;
}
model {
  germination_rate ~ beta(2.0, 5.0);
  sprouted ~ binomial(planted, germination_rate);
}
