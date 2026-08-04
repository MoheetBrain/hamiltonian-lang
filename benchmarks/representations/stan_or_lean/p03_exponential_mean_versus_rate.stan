// Helpdesk inter-arrival time.
// Stan's exponential() takes a RATE (inverse scale).
parameters {
  real<lower=0> wait;
}
model {
  wait ~ exponential(0.25);   // mean 4.0 minutes
}
