parameters {
  real alpha;
  real beta;
}
transformed parameters {
  real total    = alpha + beta;
  real weighted = total * beta;
  real residual = weighted - alpha;
}
model { }
