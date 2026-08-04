// Stan has a first-class simplex type, which captures the sum-to-one and the
// [0,1] range in ONE declaration. This is a case where Stan is more concise
// and no less explicit than the Hamiltonian encoding.
parameters {
  simplex[3] shares;
}
model {
  // shares[1] >= shares[2] still has to be imposed by hand
  target += (shares[1] >= shares[2]) ? 0 : negative_infinity();
}
