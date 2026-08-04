alpha = 1.0
beta = 2.0

total = alpha + beta
weighted = total * beta
residual = weighted - alpha

# Recovering the dependency set requires parsing the source or tracing execution;
# the values themselves carry no provenance.
