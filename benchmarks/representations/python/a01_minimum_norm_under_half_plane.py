from scipy.optimize import minimize

constraints = [
    {'type': 'ineq', 'fun': lambda z: z[0] + z[1] - 10.0},
    {'type': 'ineq', 'fun': lambda z: z[0]},
    {'type': 'ineq', 'fun': lambda z: z[1]},
]
result = minimize(lambda z: z[0] ** 2 + z[1] ** 2, x0=[0.0, 0.0],
                  constraints=constraints)
# The sign convention ('ineq' means >= 0) is a library detail, not a statement
# of the mathematics, and reversing it silently solves a different problem.
