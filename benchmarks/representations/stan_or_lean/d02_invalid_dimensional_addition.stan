// Stan will accept this without comment: it has no notion of dimension.
transformed data {
  real work = 10.0;
  real force = 4.0;
  real bad = work + force;   // accepted
}
model { }
