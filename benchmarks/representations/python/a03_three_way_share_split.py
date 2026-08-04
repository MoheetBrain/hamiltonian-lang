shares = {'share_a': 0.5, 'share_b': 0.3, 'share_c': 0.2}
assert abs(sum(shares.values()) - 1.0) < 1e-12
assert shares['share_a'] >= shares['share_b']
# The [0, 1] membership of each share is asserted nowhere.
