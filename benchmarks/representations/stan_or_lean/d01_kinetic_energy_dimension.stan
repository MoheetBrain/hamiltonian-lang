// Stan has no dimensional analysis. Every quantity is a bare real.
parameters {
  real<lower=0> m;
  real v;
}
transformed parameters {
  real kinetic_energy = 0.5 * m * square(v);
}
model { }
