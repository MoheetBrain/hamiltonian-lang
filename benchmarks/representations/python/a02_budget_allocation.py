from scipy.optimize import linprog

budget = 25000.0
# linprog MINIMISES, so the objective is negated. Forgetting the sign is the
# classic silent error here.
result = linprog(c=[-3.1, -1.4], A_ub=[[1.0, 1.0]], b_ub=[budget],
                 bounds=[(0, None), (0, None)])
