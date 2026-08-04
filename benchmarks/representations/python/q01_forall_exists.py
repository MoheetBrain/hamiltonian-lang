# There is no faithful Python encoding: the reals are not enumerable.
# The usual rendering is a bounded approximation, which changes the statement.
def forall_exists(xs, ys):
    return all(any(y > x for y in ys) for x in xs)

# forall_exists(range(10), range(10)) is False, though the mathematical
# statement is True. The encoding is not the statement.
