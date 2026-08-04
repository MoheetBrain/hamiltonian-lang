# Security and confidentiality

This repository is **private, unpublished research and development**.

## Do not

- publish any part of this repository externally
- push to a public remote or change repository visibility
- open public issues or discussions referencing this work
- disclose design decisions, the optimisation methodology, the experimental strategy,
  or any commercial roadmap to outside parties
- reference anything under `docs/private/` from public-facing documentation

## Claims discipline

No statement asserting that Hamiltonian Lang outperforms English, LaTeX, Python, Stan,
Lean, or any other representation may appear anywhere in this repository until a
measurement supporting it exists and is reproducible. This is enforced mechanically by
`tests/golden/test_golden.py::test_no_superiority_claim_in_public_docs`.

Novelty claims require prior-art analysis. See `docs/research/PRIOR_ART.md`, in particular
its "Claims We Cannot Make" section.

## Dependencies

The core has no runtime dependencies beyond the Python standard library. Any addition
must be justified in `DECISIONS.md` and its licence checked for compatibility with private
commercial use. Licences verified during Wave 1 are recorded in
`docs/research/PRIOR_ART_MATRIX.csv`.

## Secrets

Never commit credentials, API keys, `.env` files, virtual environments, caches, or
generated dependency directories.
