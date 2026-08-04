data {
  int<lower=1> N;
  int<lower=1> P;
  matrix[N, P] predictors;
  vector[N] response;
  vector[P] prior_location;
  real<lower=0> prior_scale;
}
parameters {
  vector[P] coefficients;
  real<lower=0> noise_scale;
}
model {
  coefficients ~ normal(prior_location, prior_scale);
  noise_scale  ~ normal(0, prior_scale);   // half-normal via the <lower=0> bound
  response     ~ normal(predictors * coefficients, noise_scale);
}
