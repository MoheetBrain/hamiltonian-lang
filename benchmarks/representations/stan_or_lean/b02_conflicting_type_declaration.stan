// Stan rejects duplicate declarations in the same block.
parameters {
  real<lower=0> rate;
  real rate;            // error: duplicate declaration of variable 'rate'
}
model { }
