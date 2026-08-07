"""Supported-subset round trips — HML-EVAL-001 §9.

Before this file, exactly one round trip existed: HML → HML, the trip that cannot lose
anything. These tests measure whether the one-object-many-views claim survives contact
with a real external representation.

Each route declares a **narrow supported subset**. A round trip passes only when the
reconstructed canonical object is *identical* — same content hash — to the original.
Anything outside the subset must be **rejected**, not approximated: an importer that
guessed would manufacture a passing round trip out of nothing.

No general Stan or Lean interoperability is claimed anywhere.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import render
from hamiltonian_lang.backends.canonical import canonical_json
from hamiltonian_lang.importers import (
    SUPPORTED_SUBSETS,
    UnsupportedConstruct,
    from_canonical_json,
    from_lean,
    from_stan,
    from_triples,
)

# ---------------------------------------------------------------------------
# Subset-conformant fixtures. Each is deliberately minimal.
# ---------------------------------------------------------------------------

CANONICAL_IN_SUBSET = [
    "module A\n\nparam mu : Real\nparam sigma : PositiveReal\n"
    "rv X : RandomVariable[Real]\n\nlaw X ~ Normal(location := mu, scale := sigma)\n",
    "module B\n\nparam theta : Probability\nprior theta ~ Beta(alpha := 1, beta := 1)\n"
    "obs n : Natural = 10\nobs k : Natural = 7\n"
    "likelihood k | theta ~ Binomial(trials := n, prob := theta)\n\ninfer posterior theta\n",
    "module C\n\nvar x : Real\nvar y : Real\n\nrequire x + y >= 10\nrequire x >= 0\n"
    "minimise x ^ 2 + y ^ 2\n\nsolve x y\n",
    "module D\n\nprove forall a : Real . exists b : Real . b > a\n",
    "module E\n\nprove exists b : Real . forall a : Real . b > a\n",
]

TRIPLES_IN_SUBSET = [
    "module A\n\nparam mu : Real\nparam sigma : PositiveReal\n"
    "rv X : RandomVariable[Real]\n\nlaw X ~ Normal(location := mu, scale := sigma)\n",
    "module B\n\nparam a : PositiveReal\nparam b : PositiveReal\nparam t : Probability\n"
    "prior t ~ Beta(alpha := a, beta := b)\n",
]

# Stan's `<lower=0>` means >= 0. HML's PositiveReal means > 0. Stan therefore CANNOT
# express strict positivity, so any module using PositiveReal is outside the
# round-trippable subset -- which is most probabilistic models, since scale parameters
# are strictly positive. That is a finding about the interoperability claim, not a
# workaround, and it is asserted explicitly below.
# Only families whose every role type is Stan-expressible can round-trip. Uniform
# (lower: Real, upper: Real), Binomial (trials: Natural, prob: Probability) and
# Bernoulli (prob: Probability) qualify. Normal, Cauchy, Beta, Gamma, Exponential,
# Poisson and the rest do not, because each has at least one PositiveReal role.
STAN_IN_SUBSET = [
    "module A\n\nparam lo : Real\nparam hi : Real\nparam u : Real\n\n"
    "law u ~ Uniform(lower := lo, upper := hi)\n",
    # Declarations must already be grouped data-then-parameters: Stan's block structure
    # reorders them, and HML declaration ordinals are positional, so an interleaved
    # module is outside the subset. Asserted directly below.
    # No observed VALUES: Stan takes data from a data file, not from the program text,
    # so `obs k : Natural = 7` loses the 7. Asserted directly below.
    "module B\n\nobs n : Natural\nobs k : Natural\nparam p : Probability\n\n"
    "law k ~ Binomial(trials := n, prob := p)\n",
]

LEAN_IN_SUBSET = [
    "module D\n\nprove forall a : Real . exists b : Real . b > a\n",
    "module E\n\nprove exists b : Real . forall a : Real . b > a\n",
]

OUT_OF_SUBSET = {
    "triples": [
        "module Q\n\nprove forall a : Real . exists b : Real . b > a\n",   # quantifiers
        "module R\n\nvar x : Real\nrequire x >= 0\n",                      # constraints
    ],
    "lean": [
        "module L\n\nparam m : Real\nparam s : PositiveReal\n"
        "rv X : RandomVariable[Real]\nlaw X ~ Normal(location := m, scale := s)\n",
    ],
}


def _compiled(src: str):
    r = compile_source(src)
    assert r.ok(), "\n" + r.diagnostics.render()
    return r


def _hash_up_to_module_name(result) -> str:
    """Content hash with the module name normalised away.

    The module *name* is metadata, not mathematics, and the graph and Lean views do not
    carry it. Declaring that explicitly is honest; silently comparing names would fail
    every round trip for a reason that has nothing to do with meaning.
    """
    import hashlib
    import json

    from hamiltonian_lang.backends.canonical import canonical_json

    doc = json.loads(canonical_json(result.module, include_names=False))
    doc["module"] = "<normalised>"
    blob = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _roundtrip(src: str, forward, backward) -> tuple[bool, str]:
    r = _compiled(src)
    intermediate = forward(r)
    back_src = backward(intermediate)
    b = compile_source(back_src, "<roundtrip>")
    if not b.ok():
        return False, "reconstruction does not compile:\n" + b.diagnostics.render()
    if _hash_up_to_module_name(b) != _hash_up_to_module_name(r):
        return False, (
            f"content hash changed\noriginal:\n{src}\nreconstructed:\n{back_src}"
        )
    return True, back_src


# ---------------------------------------------------------------------------
# HML -> canonical IR -> HML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("src", CANONICAL_IN_SUBSET, ids=range(len(CANONICAL_IN_SUBSET)))
def test_canonical_ir_roundtrip_preserves_the_content_hash(src):
    ok, detail = _roundtrip(
        src,
        lambda r: canonical_json(r.module),
        from_canonical_json,
    )
    assert ok, detail


def test_canonical_roundtrip_preserves_quantifier_order():
    """The two scopings must remain distinguishable through the IR."""
    a = _roundtrip(CANONICAL_IN_SUBSET[3], lambda r: canonical_json(r.module),
                   from_canonical_json)
    b = _roundtrip(CANONICAL_IN_SUBSET[4], lambda r: canonical_json(r.module),
                   from_canonical_json)
    assert a[0] and b[0]
    assert compile_source(a[1]).hash() != compile_source(b[1]).hash()


# ---------------------------------------------------------------------------
# HML -> graph -> HML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("src", TRIPLES_IN_SUBSET, ids=range(len(TRIPLES_IN_SUBSET)))
def test_graph_roundtrip_preserves_the_content_hash(src):
    ok, detail = _roundtrip(
        src,
        lambda r: render("triples", r.module, r.symbols).text,
        from_triples,
    )
    assert ok, detail


@pytest.mark.parametrize("src", OUT_OF_SUBSET["triples"], ids=["quantifiers", "constraints"])
def test_graph_importer_rejects_out_of_subset_input(src):
    """Rejection is the point. A silent approximation here would fabricate a result."""
    r = _compiled(src)
    triples = render("triples", r.module, r.symbols).text
    with pytest.raises(UnsupportedConstruct):
        from_triples(triples)


# ---------------------------------------------------------------------------
# HML -> Stan subset -> HML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("src", STAN_IN_SUBSET, ids=range(len(STAN_IN_SUBSET)))
def test_stan_subset_roundtrip_preserves_the_content_hash(src):
    ok, detail = _roundtrip(
        src,
        lambda r: render("stan", r.module, r.symbols).text,
        from_stan,
    )
    assert ok, detail


def test_stan_route_loses_observed_values():
    """Stan reads data from a data file, not from the program text.

    The backend records the values honestly in a comment header, but a comment is not
    code and nothing can reconstruct them. Observed values are therefore outside the
    round-trippable subset.
    """
    src = (
        "module V\n\nobs n : Natural = 20\nobs k : Natural = 7\n"
        "param p : Probability\n\nlaw k ~ Binomial(trials := n, prob := p)\n"
    )
    r = _compiled(src)
    stan = render("stan", r.module, r.symbols).text
    assert "n = 20" in stan, "the backend should at least record the values in a comment"
    back = from_stan(stan)
    assert "= 20" not in back, "the value cannot be recovered from Stan code"
    ok, detail = _roundtrip(src, lambda rr: render("stan", rr.module, rr.symbols).text,
                            from_stan)
    assert not ok and "content hash changed" in detail


def test_stan_block_structure_destroys_interleaved_declaration_order():
    """Another measured limit, tied to a known IR weakness.

    Stan groups declarations into `data` and `parameters` blocks. HML declaration
    ordinals are positional (see docs/design/IR_PROPOSAL.md section 7), so a module whose
    observations and parameters are interleaved comes back reordered and its content hash
    changes. The meaning is arguably unaltered; the identity is not. Both facts are worth
    recording, and neither is normalised away here.
    """
    interleaved = (
        "module I\n\nobs n : Natural\nparam p : Probability\n"
        "obs k : Natural\n\nlaw k ~ Binomial(trials := n, prob := p)\n"
    )
    ok, detail = _roundtrip(
        interleaved, lambda r: render("stan", r.module, r.symbols).text, from_stan
    )
    assert not ok, "expected the reordering to be detected"
    assert "content hash changed" in detail


def test_stan_cannot_express_strict_positivity():
    """A measured limit of the interoperability claim, not an incidental bug.

    Stan's `real<lower=0>` is a closed lower bound: it admits 0. HML's `PositiveReal`
    excludes 0. A scale parameter therefore cannot survive HML -> Stan -> HML, and since
    every scale parameter in every family is strictly positive, most probabilistic models
    fall outside the round-trippable Stan subset.
    """
    # The observed quantity and the location are distinct symbols. The original fixture
    # wrote `law m ~ Normal(location := m, ...)`, giving m's own law a dependency on m --
    # a self-referential law that specifies no distribution. It went unnoticed because
    # nothing checked for law cycles until HML-S607 (CT-022). The subject of this test is
    # Stan's closed lower bound, not m's law, so the fixture is corrected rather than the
    # check relaxed.
    src = (
        "module P\n\nparam mu : Real\nparam s : PositiveReal\nparam y : Real\n\n"
        "law y ~ Normal(location := mu, scale := s)\n"
    )
    r = _compiled(src)
    back = from_stan(render("stan", r.module, r.symbols).text)
    assert "NonNegativeReal" in back, "expected the widening to NonNegativeReal"
    b = compile_source(back)
    assert not b.ok(), "the widened program should fail: a scale must be strictly positive"
    assert "HML-T413" in [d.code for d in b.diagnostics.errors]


def test_stan_roundtrip_preserves_role_to_position_to_role():
    """The highest-value assertion in this file.

    A role→position error on the way out, or position→role on the way back, is silent
    and catastrophic. Round-tripping is the only check that catches an error in *either*
    table, because a matching pair of mistakes would cancel in a one-way test.
    """
    src = (
        "module S\n\nparam lo : Real\nparam hi : Real\nparam u : Real\n\n"
        "law u ~ Uniform(lower := lo, upper := hi)\n"
    )
    ok, back = _roundtrip(src, lambda r: render("stan", r.module, r.symbols).text,
                          from_stan)
    assert ok, back
    assert "lower := lo" in back and "upper := hi" in back

    swapped = (
        "module S\n\nparam lo : Real\nparam hi : Real\nparam u : Real\n\n"
        "law u ~ Uniform(lower := hi, upper := lo)\n"
    )
    r2 = compile_source(swapped)
    assert r2.ok(), r2.diagnostics.render()
    assert from_stan(render("stan", r2.module, r2.symbols).text) != back, (
        "a role swap survived the round trip undetected"
    )


def test_stan_subset_excludes_every_family_with_a_positive_real_role():
    """Quantifies how narrow the Stan round-trippable subset actually is."""
    from hamiltonian_lang.type_system.distributions import DISTRIBUTIONS

    expressible, blocked = [], []
    for name, spec in DISTRIBUTIONS.items():
        roles = {r: t.render() for r, t in spec.roles.items()}
        (blocked if any("PositiveReal" in t for t in roles.values()) else
         expressible).append(name)
    assert set(expressible) >= {"Uniform", "Binomial", "Bernoulli"}
    assert len(blocked) >= 10, blocked
    # Recorded as a measured fact: most of the registry cannot round-trip through Stan.
    assert len(blocked) > len(expressible)


@pytest.mark.parametrize(
    "bad,reason",
    [
        ("data {\n  real y;\n}\ntransformed data {\n  real z;\n}\n", "transformed data"),
        ("model {\n  for (i in 1:N) { y[i] ~ normal(0, 1); }\n}\n", "control flow"),
        ("model {\n  target += normal_lpdf(y | 0, 1);\n}\n", "target +="),
        ("parameters {\n  real y;\n}\nmodel {\n  y ~ wibble(1, 2);\n}\n", "unknown family"),
    ],
)
def test_stan_importer_rejects_out_of_subset_input(bad, reason):
    with pytest.raises(UnsupportedConstruct):
        from_stan(bad)


# ---------------------------------------------------------------------------
# HML -> Lean statement subset -> HML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("src", LEAN_IN_SUBSET, ids=range(len(LEAN_IN_SUBSET)))
def test_lean_subset_roundtrip_preserves_the_content_hash(src):
    ok, detail = _roundtrip(
        src,
        lambda r: render("lean", r.module, r.symbols).text,
        from_lean,
    )
    assert ok, detail


def test_lean_roundtrip_keeps_the_two_quantifier_scopings_distinct():
    a_ok, a_back = _roundtrip(LEAN_IN_SUBSET[0],
                              lambda r: render("lean", r.module, r.symbols).text, from_lean)
    b_ok, b_back = _roundtrip(LEAN_IN_SUBSET[1],
                              lambda r: render("lean", r.module, r.symbols).text, from_lean)
    assert a_ok and b_ok
    assert compile_source(a_back).hash() != compile_source(b_back).hash()


def test_lean_route_loses_probability_laws_and_only_the_roundtrip_detects_it():
    """The strongest argument in this file for round-tripping as a validation method.

    The Lean backend *declares* that it drops laws, and the importer cannot know a law
    was ever there -- there is nothing in the emitted Lean to notice. The reconstruction
    compiles perfectly happily. Only comparing the content hash against the original
    reveals that meaning went missing. A one-way test cannot detect this class of loss
    at all.
    """
    r = _compiled(OUT_OF_SUBSET["lean"][0])
    lean = render("lean", r.module, r.symbols).text
    # The backend does annotate the drop, honestly, in a comment. What matters is that
    # no Lean *code* carries the law, so nothing can reconstruct it.
    code = "\n".join(
        ln for ln in lean.splitlines() if not ln.strip().startswith(("--", "/-", "-}"))
    )
    assert "Normal" not in code, "the Lean code should not carry the family"
    back = from_lean(lean)
    b = compile_source(back)
    assert b.ok(), "the reconstruction compiles -- which is exactly the danger"
    assert _hash_up_to_module_name(b) != _hash_up_to_module_name(r), (
        "the lost law must be detectable by hash comparison"
    )


def test_every_subset_declares_what_it_rejects():
    for name, spec in SUPPORTED_SUBSETS.items():
        assert spec.supported, f"{name} declares no supported constructs"
        assert spec.rejected, f"{name} declares nothing rejected, which cannot be true"
