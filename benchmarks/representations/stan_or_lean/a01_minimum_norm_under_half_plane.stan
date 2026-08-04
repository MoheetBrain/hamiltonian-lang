// Stan is a sampler, not an optimiser over hard constraints; encoding this as a
// Stan model requires reformulating the constraints as bounds or as penalties,
// which changes the problem. This is a genuine limit of the arm-D encoding here.
parameters {
  real<lower=0> x;
  real<lower=0> y;
}
model {
  target += -(square(x) + square(y));      // minimise via negative log density
  target += (x + y >= 10.0) ? 0 : negative_infinity();   // hard constraint
}
