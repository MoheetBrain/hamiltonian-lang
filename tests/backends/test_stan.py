"""Stan backend tests.

**No Stan toolchain validated any of this output.** ``stanc`` is not installed in this
environment and is not invoked anywhere in this file. Every "valid Stan" claim below is
a *structural* claim only: block presence, brace balance, and consistency between what
the emitted program declares and what it uses. A program that passes these tests could
still be rejected by a real ``stanc``.

The highest-value assertions in this file are in
:class:`TestArgumentOrder`. Hamiltonian Lang labels distribution arguments by role and
Stan takes them positionally; a role-to-position error would produce a Stan program that
compiles, runs, and is silently wrong. That is precisely the class of bug the language
exists to prevent, so the ordering is asserted family by family with distinguishable
arguments, rather than inferred from the fact that "it renders".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import render
from hamiltonian_lang.backends.stan import (
    STAN_DISTRIBUTIONS,
    audit_distribution_table,
    to_stan,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def example_files() -> list[Path]:
    return sorted(
        p for p in EXAMPLES.rglob("*.hml") if "candidate_syntaxes" not in p.parts
    )


def compile_ok(source: str):
    result = compile_source(source)
    assert result.ok(), "\n" + result.diagnostics.render()
    return result

# Stan built-ins and keywords that may legitimately appear in the model block without
# being declared by the program.
_STAN_BUILTINS = {
    "normal", "lognormal", "student_t", "cauchy", "uniform", "beta", "bernoulli",
    "binomial", "poisson", "exponential", "gamma", "inv_gamma", "dirichlet",
    "categorical", "exp", "log", "sqrt", "sin", "cos", "tan", "abs", "target",
    "for", "in", "if", "else", "while", "print", "reject",
}


def stan_of(path):
    result = compile_ok(path.read_text())
    return render("stan", result.module, result.symbols)


# ---------------------------------------------------------------------------
# 1. Every example survives the backend
# ---------------------------------------------------------------------------


def test_every_example_renders_without_crashing(example):
    out = stan_of(example)
    assert out.target == "stan"
    assert isinstance(out.text, str)
    assert out.text.strip(), f"{example} produced empty Stan output"


def test_to_stan_entry_point_matches_registry(example):
    result = compile_ok(example.read_text())
    direct = to_stan(result.module, result.symbols)
    viaregistry = render("stan", result.module, result.symbols)
    assert direct.text == viaregistry.text


# ---------------------------------------------------------------------------
# 2. Argument ORDER. The point of the backend.
# ---------------------------------------------------------------------------


class TestArgumentOrder:
    """Role -> position. A wrong entry here is a silent correctness bug."""

    def _model_lines(self, source: str) -> list[str]:
        out = compile_ok(source).render("stan")
        body = out.text.split("model {", 1)[1]
        return [ln.strip() for ln in body.splitlines() if ln.strip().startswith(("_", *"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"))]

    def test_normal_takes_location_then_scale(self):
        # Stan's normal(mu, sigma) takes the STANDARD DEVIATION second, not the
        # variance. HML's `scale` role is the standard deviation (see the registry
        # note), so scale must land in slot 2.
        lines = self._model_lines(
            "module M\n"
            "param mu : Real\n"
            "param sigma : PositiveReal\n"
            "var X : RandomVariable[Real]\n"
            "law X ~ Normal(location := mu, scale := sigma)\n"
        )
        assert "X ~ normal(mu, sigma);" in lines

    def test_normal_order_is_determined_by_role_not_by_source_order(self):
        """Writing the roles in the other order must not move them in Stan."""
        forward = compile_ok(
            "module M\n"
            "param mu : Real\n"
            "param sigma : PositiveReal\n"
            "var X : RandomVariable[Real]\n"
            "law X ~ Normal(location := mu, scale := sigma)\n"
        ).render("stan")
        reversed_ = compile_ok(
            "module M\n"
            "param mu : Real\n"
            "param sigma : PositiveReal\n"
            "var X : RandomVariable[Real]\n"
            "law X ~ Normal(scale := sigma, location := mu)\n"
        ).render("stan")
        assert "X ~ normal(mu, sigma);" in forward.text
        assert forward.text == reversed_.text

    def test_beta_takes_alpha_then_beta(self):
        lines = self._model_lines(
            "module M\n"
            "const a : PositiveReal\n"
            "const b : PositiveReal\n"
            "param theta : Probability\n"
            "prior theta ~ Beta(alpha := a, beta := b)\n"
        )
        assert "theta ~ beta(a, b);" in lines

    def test_binomial_takes_trials_then_prob(self):
        # binomial(N, theta): the COUNT first, the probability second.
        lines = self._model_lines(
            "module M\n"
            "obs n : Natural\n"
            "obs k : Natural\n"
            "param p : Probability\n"
            "likelihood k | p ~ Binomial(trials := n, prob := p)\n"
        )
        assert "k ~ binomial(n, p);" in lines

    def test_half_normal_puts_scale_second_after_a_literal_zero(self):
        # Stan has no half_normal. The idiom is normal(0, scale) on a <lower=0>
        # declaration: the scale must be the SECOND argument, never the first.
        out = compile_ok(
            "module M\n"
            "const s0 : PositiveReal\n"
            "param s : PositiveReal\n"
            "prior s ~ HalfNormal(scale := s0)\n"
        ).render("stan")
        assert "s ~ normal(0, s0);" in out.text
        # and the truncation must be present in the declaration, not the statement
        assert "real<lower=0> s;" in out.text
        assert any(
            u.severity == "approximated" and "half_normal" in u.reason
            for u in out.unsupported
        ), "the HalfNormal -> normal(0, .) rewrite must be reported as approximated"

    def test_half_normal_on_an_unbounded_variable_is_reported_as_dropped(self):
        """The rewrite is only a half-normal if the declaration bounds the variable.

        When it does not, the emitted Stan is a *full* normal. That is a genuine
        semantic difference and must not be reported as a mere approximation.
        """
        out = compile_ok(
            "module M\n"
            "const s0 : PositiveReal\n"
            "var u : RandomVariable[Real]\n"
            "law u ~ HalfNormal(scale := s0)\n"
        ).render("stan")
        assert "u ~ normal(0, s0);" in out.text
        assert "real u;" in out.text  # no lower bound
        assert any(
            u.severity == "dropped" and "half-normal" in u.reason
            for u in out.unsupported
        ), "losing the support restriction must be reported as dropped, not approximated"

    def test_student_t_order(self):
        lines = self._model_lines(
            "module M\n"
            "const nu : PositiveReal\n"
            "param mu : Real\n"
            "param sigma : PositiveReal\n"
            "var X : RandomVariable[Real]\n"
            "law X ~ StudentT(degrees_of_freedom := nu, location := mu, scale := sigma)\n"
        )
        assert "X ~ student_t(nu, mu, sigma);" in lines

    def test_gamma_is_shape_then_rate(self):
        lines = self._model_lines(
            "module M\n"
            "const k : PositiveReal\n"
            "const r : PositiveReal\n"
            "param g : PositiveReal\n"
            "prior g ~ Gamma(shape := k, rate := r)\n"
        )
        assert "g ~ gamma(k, r);" in lines

    def test_uniform_is_lower_then_upper(self):
        lines = self._model_lines(
            "module M\n"
            "const lo : Real\n"
            "const hi : Real\n"
            "var X : RandomVariable[Real]\n"
            "law X ~ Uniform(lower := lo, upper := hi)\n"
        )
        assert "X ~ uniform(lo, hi);" in lines


class TestDistributionTable:
    def test_table_agrees_with_the_hml_registry(self):
        """Every registered family must have a Stan mapping over exactly its roles."""
        problems = audit_distribution_table()
        assert problems == [], "\n".join(problems)

    @pytest.mark.parametrize(
        ("family", "fn", "slots"),
        [
            ("Normal", "normal", ("location", "scale")),
            ("Beta", "beta", ("alpha", "beta")),
            ("Binomial", "binomial", ("trials", "prob")),
            ("HalfNormal", "normal", ("#0", "scale")),
            ("LogNormal", "lognormal", ("location", "scale")),
            ("Cauchy", "cauchy", ("location", "scale")),
            ("Uniform", "uniform", ("lower", "upper")),
            ("StudentT", "student_t", ("degrees_of_freedom", "location", "scale")),
            ("Gamma", "gamma", ("shape", "rate")),
            ("InverseGamma", "inv_gamma", ("shape", "scale")),
            ("Exponential", "exponential", ("rate",)),
            ("Poisson", "poisson", ("rate",)),
            ("Bernoulli", "bernoulli", ("prob",)),
            ("Dirichlet", "dirichlet", ("concentration",)),
            ("Categorical", "categorical", ("probs",)),
            ("NormalVector", "normal", ("location", "scale")),
        ],
    )
    def test_slot_order_is_pinned(self, family, fn, slots):
        """Pin every ordering explicitly so a reordering edit fails loudly."""
        mapped = STAN_DISTRIBUTIONS[family]
        assert mapped.fn == fn
        assert mapped.slots == slots


# ---------------------------------------------------------------------------
# 3. Loss reporting
# ---------------------------------------------------------------------------


def test_no_example_is_losslessly_expressible_in_stan(example):
    """Not one of the eight examples survives translation intact.

    That is a finding, not a defect: it is what the backend contract predicts, and if
    an example ever did become faithful this test should be revisited deliberately
    rather than silently.
    """
    out = stan_of(example)
    assert out.unsupported, f"{example}: no loss reported"
    assert out.faithful is False
    for u in out.unsupported:
        assert u.severity in ("dropped", "approximated", "weakened")
        assert u.reason.strip(), f"{u.construct}: empty reason"


def test_limitations_are_declared_on_the_class():
    from hamiltonian_lang.backends.stan import StanBackend

    assert StanBackend.limitations
    assert all(isinstance(s, str) and s.strip() for s in StanBackend.limitations)


def test_report_is_carried_into_the_result_notes(example):
    from hamiltonian_lang.backends.stan import StanBackend

    out = stan_of(example)
    for lim in StanBackend.limitations:
        assert lim in out.notes


def test_role_labels_are_reported_as_weakened_wherever_a_law_appears():
    out = stan_of(next(p for p in example_files() if p.name == "bayesian_coin.hml"))
    weakened = [u for u in out.unsupported if u.severity == "weakened"]
    assert any("argument roles" in u.construct for u in weakened), (
        "the loss of role labels to positional arguments is the central Stan "
        "translation loss and must be reported"
    )


def test_dimensions_are_reported_as_lost():
    out = stan_of(next(p for p in example_files() if p.name == "kinetic_energy.hml"))
    assert any("dimensionless" in u.reason for u in out.unsupported)
    assert any(
        u.construct == "check dimension" and u.severity == "dropped"
        for u in out.unsupported
    )


def test_quantifiers_are_reported_as_dropped():
    out = stan_of(next(p for p in example_files() if p.name == "quantifier_scope.hml"))
    assert any("quantifier" in u.construct and u.severity == "dropped" for u in out.unsupported)


def test_concepts_are_reported_as_dropped():
    out = stan_of(
        next(p for p in example_files() if p.name == "location_scale_family.hml")
    )
    assert any(u.construct.startswith("concept") and u.severity == "dropped" for u in out.unsupported)


# ---------------------------------------------------------------------------
# 4. Structural validity (NOT compiler validation -- see the module docstring)
# ---------------------------------------------------------------------------


def _strip_comments(text: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def test_braces_are_balanced(example):
    body = _strip_comments(stan_of(example).text)
    depth = 0
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            assert depth >= 0, f"{example}: closing brace before opening"
    assert depth == 0, f"{example}: {depth} unclosed brace(s)"


def test_a_model_block_is_always_present(example):
    assert re.search(r"^model \{", stan_of(example).text, re.M), (
        f"{example}: no model block"
    )


def test_blocks_appear_in_stans_required_order(example):
    """Stan fixes the block order; an out-of-order program is rejected by stanc."""
    order = [
        "functions", "data", "transformed data", "parameters",
        "transformed parameters", "model", "generated quantities",
    ]
    text = stan_of(example).text
    seen = [
        (m.start(), m.group(1))
        for m in re.finditer(r"^(functions|data|transformed data|parameters|transformed parameters|model|generated quantities) \{", text, re.M)
    ]
    indices = [order.index(name) for _, name in seen]
    assert indices == sorted(indices), f"{example}: blocks out of order: {seen}"


def test_every_statement_line_is_terminated(example):
    """Inside a block, a non-comment, non-brace line must end in `;` or `{`/`}`."""
    text = stan_of(example).text
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line or line in ("{", "}") or line.endswith(("{", "}")):
            continue
        assert line.endswith(";"), f"{example}: unterminated line {raw!r}"


def test_model_block_uses_only_declared_names(example):
    """Declaration/usage consistency: every symbol used is declared somewhere above."""
    text = stan_of(example).text
    declared: set[str] = set()
    for m in re.finditer(
        r"^\s*(?:real|int|vector|matrix|row_vector|simplex|complex)"
        r"(?:<[^>]*>)?(?:\[[^\]]*\])?\s+([A-Za-z_]\w*)\s*[;=(]",
        _strip_comments(text),
        re.M,
    ):
        declared.add(m.group(1))
    # extents used inside vector[N] / matrix[N, P] are declared names too
    model_src = _strip_comments(text).split("model {", 1)[1]
    used = {
        name
        for name in re.findall(r"[A-Za-z_]\w*", model_src)
        if name not in _STAN_BUILTINS
    }
    undeclared = used - declared
    assert not undeclared, f"{example}: model block uses undeclared {sorted(undeclared)}"


def test_declared_array_extents_are_themselves_declared(example):
    """`vector[N]` is only valid if `N` is a declared int."""
    text = _strip_comments(stan_of(example).text)
    declared_ints = set(re.findall(r"^\s*int(?:<[^>]*>)?\s+([A-Za-z_]\w*)\s*;", text, re.M))
    for extent in re.findall(r"(?:vector|matrix)(?:<[^>]*>)?\[([^\]]*)\]", text):
        for part in extent.split(","):
            part = part.strip()
            if part and not part.isdigit():
                assert part in declared_ints, (
                    f"{example}: extent {part!r} is used but never declared as an int"
                )


def test_generated_text_has_a_provenance_header(example):
    text = stan_of(example).text
    assert text.startswith("// Stan program generated from Hamiltonian Lang module")
    assert "Not compiled or validated by stanc" in text
