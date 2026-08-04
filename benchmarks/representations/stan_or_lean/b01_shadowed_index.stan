// Stan DOES reject this one: a loop index may not shadow a declared variable
// in the same scope chain.
data {
  int i;
}
model {
  for (i in 1:10) {        // error: variable 'i' already declared
    target += 0;
  }
}
