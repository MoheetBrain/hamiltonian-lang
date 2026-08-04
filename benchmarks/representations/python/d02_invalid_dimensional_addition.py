work = 10.0
force = 4.0
bad = work + force   # runs, returns 14.0, means nothing

# With the pint library this WOULD be caught:
#   import pint; u = pint.UnitRegistry()
#   (10 * u.joule) + (4 * u.newton)  ->  DimensionalityError
# Plain numeric Python has no such check.
