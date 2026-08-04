rate: float = 1.0   # intended: strictly positive
rate: float = -1.0  # re-annotated; Python keeps the last binding, no error
# mypy accepts a repeated identical annotation and would only complain if the
# annotations disagreed syntactically, not if the intent disagreed.
