def inner_negation(xs):
    return all(not (x > 0) for x in xs)
