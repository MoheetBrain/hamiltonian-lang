def exists_forall(xs, ys):
    return any(all(y > x for x in xs) for y in ys)

# Over any finite list this is True whenever ys contains max(xs) + 1,
# so the finite encoding gets the truth value backwards.
