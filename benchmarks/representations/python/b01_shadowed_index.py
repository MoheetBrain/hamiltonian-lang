i = 0  # module-level index

def constraint():
    return all(i > 0 for i in range(1, 10))   # the comprehension rebinds i

# Python permits this silently. In Python 2 the comprehension even leaked the
# rebinding back out. The shadowing is legal and invisible.
