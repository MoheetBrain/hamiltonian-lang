import math

pendulum_length = 1.0
gravity = 9.81
period = 2 * math.pi * math.sqrt(pendulum_length / gravity)
# math.sqrt of a negative argument raises; math.sqrt of a wrong-dimension
# argument does not, because there are no dimensions.
