// Calibration reading error.
data {
}
parameters {
  real drift;
  real<lower=0> jitter;   // Stan's <lower=0> is the positivity constraint
  real E;
}
model {
  E ~ normal(drift, jitter);  // Stan's second normal argument is sigma, not sigma^2
}
