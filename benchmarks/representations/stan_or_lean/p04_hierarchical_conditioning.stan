// Two-level clinic model.
data {
  int<lower=1> G;
  vector[G] prior_location;
  vector[G] outcome;
}
parameters {
  vector[G] clinic_mean;
  real<lower=0> population_scale;
  real<lower=0> measurement_scale;
}
model {
  clinic_mean ~ normal(prior_location, population_scale);
  outcome     ~ normal(clinic_mean, measurement_scale);
}
