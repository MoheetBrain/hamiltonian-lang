data {
  int<lower=0> sample_size;
  int<lower=0> failures;
}
parameters {
  real<lower=0, upper=1> failure_probability;
}
model {
  failures ~ binomial(sample_size, failure_probability);
}
