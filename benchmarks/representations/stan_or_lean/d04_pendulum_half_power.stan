transformed data {
  real pendulum_length = 1.0;
  real gravity = 9.81;
  real period = 2 * pi() * sqrt(pendulum_length / gravity);
}
model { }
