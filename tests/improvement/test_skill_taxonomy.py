"""Phase 11 — the taxonomy file, attribution, and the arithmetic over observations.

Two groups of assertions matter most:

* the taxonomy describes *this* compiler — every code it names is emitted somewhere in
  ``src/hamiltonian_lang``, and no code is claimed by two skills;
* nothing invents a rate. Learning gain per token is unavailable from one round and
  cannot be coerced into a number.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hamiltonian_lang.improvement.skills import (
    BetaPosterior,
    NoForgetting,
    SkillLedger,
    SkillObservation,
    SkillStatus,
    TaxonomyError,
    TokenAccount,
    TokenSource,
    aggregate_observations,
    default_taxonomy,
    load_taxonomy,
)
from hamiltonian_lang.improvement.state import Hypothesis, Unavailable

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "hamiltonian_lang"
H3 = Hypothesis.H3_VERIFIER_GUIDED_REPAIR

#: The taxonomy the directive specifies, in full. A skill quietly dropped or renamed
#: fails here rather than showing up as a gap in a report six months later.
EXPECTED_SKILLS = {
    "syntax.declaration",
    "syntax.binding",
    "syntax.role_label",
    "syntax.delimiter",
    "typing.scalar",
    "typing.function_arity",
    "typing.function_argument",
    "typing.distribution",
    "typing.epistemic",
    "binding.quantifier_scope",
    "binding.variable_capture",
    "binding.index_tracking",
    "dimension.base",
    "dimension.rational_exponent",
    "dimension.variable",
    "reasoning.implication",
    "reasoning.equivalence",
    "reasoning.assumption",
    "reasoning.obligation",
    "statistics.likelihood",
    "statistics.posterior",
    "statistics.pvalue",
    "statistics.estimator_estimand",
}


def observation(idx: int, success: bool, **kw) -> SkillObservation:
    defaults = {
        "observation_id": f"o-{idx}",
        "skill_id": "syntax.role_label",
        "hypothesis": H3,
        "episode_id": f"ep-{idx}",
        "round_id": "r1",
        "success": success,
    }
    defaults.update(kw)
    return SkillObservation(**defaults)


# ---------------------------------------------------------------------------
# The file
# ---------------------------------------------------------------------------


def test_the_taxonomy_loads_and_is_versioned():
    t = default_taxonomy()
    assert t.version == "hml-skill-taxonomy-1.0.0"
    assert t.schema == "skill-taxonomy/1"
    assert t.source_path.exists()


def test_every_specified_skill_is_present_and_no_others():
    assert set(default_taxonomy().ids()) == EXPECTED_SKILLS


def test_every_diagnostic_code_named_is_one_the_compiler_emits():
    """A taxonomy naming codes the compiler never emits describes another compiler."""
    sources = "\n".join(
        p.read_text(encoding="utf-8") for p in SRC.rglob("*.py") if "improvement" not in p.parts
    )
    missing = [
        code
        for skill in default_taxonomy().skills.values()
        for code in skill.diagnostics
        if f'"{code}"' not in sources
    ]
    assert not missing, f"codes named in the taxonomy but never emitted: {missing}"


def test_attribution_is_a_function_because_the_code_sets_are_disjoint():
    seen: dict[str, str] = {}
    for skill in default_taxonomy().skills.values():
        for code in skill.diagnostics:
            assert code not in seen, f"{code} claimed by {seen[code]} and {skill.skill_id}"
            seen[code] = skill.skill_id
    assert default_taxonomy().attribute("HML-T471") == "typing.function_arity"
    assert default_taxonomy().attribute("HML-Z999") is None


def test_a_skill_with_no_code_says_so_rather_than_borrowing_one():
    for skill in default_taxonomy().skills.values():
        empty = not skill.diagnostics
        assert empty == (skill.status is SkillStatus.NO_DEDICATED_DIAGNOSTIC), skill.skill_id
        if skill.status is not SkillStatus.ENFORCED:
            assert skill.limitation.strip(), skill.skill_id


def test_the_known_failures_from_the_lead_audit_are_recorded_as_limitations():
    t = default_taxonomy()
    assert "PValue" in t.skill("statistics.pvalue").limitation
    assert t.skill("statistics.pvalue").status is SkillStatus.NO_DEDICATED_DIAGNOSTIC
    assert "defect A" in t.skill("typing.function_arity").limitation
    assert "defect B" in t.skill("typing.scalar").limitation


def test_unknown_skill_ids_are_rejected():
    with pytest.raises(TaxonomyError, match="unknown skill"):
        default_taxonomy().skill("syntax.does_not_exist")
    with pytest.raises(TaxonomyError, match="unknown skill id"):
        default_taxonomy().require_known(["syntax.declaration", "nope"])


def test_a_missing_taxonomy_file_raises_rather_than_defaulting(tmp_path):
    with pytest.raises(TaxonomyError, match="not found"):
        load_taxonomy(tmp_path / "absent.yaml")


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("version: \"v\"\n\tfamilies:\n", "tabs"),
        ("families:\n  - one\n", "sequences"),
        ("families\n", "expected"),
        ("a: 1\na: 2\n", "duplicate key"),
        ("a:\n      b: 1\n", "indentation"),
        ('a: "unterminated\n', "unterminated"),
    ],
)
def test_the_reader_rejects_everything_outside_its_subset(tmp_path, text, match):
    p = tmp_path / "t.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(TaxonomyError, match=match):
        load_taxonomy(p)


def test_a_structurally_valid_but_incomplete_taxonomy_is_rejected(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text(
        'version: "v"\nschema: "s"\nstatus: "proposed"\nbasis: "none"\n'
        "families:\n  syntax:\n    skills:\n      declaration:\n"
        '        description: "d"\n',
        encoding="utf-8",
    )
    with pytest.raises(TaxonomyError, match="missing"):
        load_taxonomy(p)


# ---------------------------------------------------------------------------
# Beta posterior
# ---------------------------------------------------------------------------


def test_the_posterior_matches_closed_form_values():
    uniform = BetaPosterior(1.0, 1.0)
    assert uniform.mean == pytest.approx(0.5)
    lo, hi = uniform.credible_interval(0.95)
    assert (lo, hi) == pytest.approx((0.025, 0.975), abs=1e-9)  # CDF of Beta(1,1) is x
    assert BetaPosterior(2.0, 2.0).quantile(0.5) == pytest.approx(0.5, abs=1e-9)
    assert BetaPosterior(7.0, 3.0).cdf(0.5) == pytest.approx(23 / 256, abs=1e-12)


def test_the_count_shows_up_as_uncertainty_where_a_ratio_would_hide_it():
    few = aggregate_observations([observation(i, True) for i in range(6)])
    many = aggregate_observations([observation(i, True) for i in range(60)])
    assert few.successes == 6 and many.successes == 60
    assert few.mastery < many.mastery  # both "100%", different posteriors
    assert few.uncertainty > many.uncertainty


def test_the_prior_is_recorded_rather_than_assumed():
    agg = aggregate_observations([observation(0, True)])
    assert agg.posterior.to_dict()["prior"] == {"alpha": 1.0, "beta": 1.0}


def test_forgetting_is_declared_unavailable_rather_than_silently_assumed():
    agg = aggregate_observations([observation(0, True)], forgetting=NoForgetting())
    assert agg.forgetting_model == "none"
    assert agg.forgetting_available is False


# ---------------------------------------------------------------------------
# Tokens and learning gain
# ---------------------------------------------------------------------------


def test_token_counts_may_not_be_reported_and_present_at_once():
    with pytest.raises(ValueError, match="not reported"):
        TokenAccount(TokenSource.NOT_REPORTED, prompt_tokens=0, completion_tokens=0)
    with pytest.raises(ValueError, match="missing"):
        TokenAccount(TokenSource.REPORTED, prompt_tokens=5)


def test_an_unreported_token_count_is_unavailable_and_never_zero():
    assert isinstance(TokenAccount().total, Unavailable)
    agg = aggregate_observations([observation(0, True)])
    assert isinstance(agg.total_tokens, Unavailable)
    with pytest.raises(TypeError):
        float(agg.total_tokens)


def test_learning_gain_per_token_cannot_be_computed_from_one_round():
    agg = aggregate_observations(
        [
            observation(i, True, tokens=TokenAccount(TokenSource.REPORTED, 10, 10))
            for i in range(4)
        ]
    )
    assert len(agg.rounds) == 1
    gain = agg.learning_gain_per_token()
    assert isinstance(gain, Unavailable)
    assert not isinstance(gain, float)
    assert "two comparable rounds" in gain.reason
    with pytest.raises(TypeError):
        float(gain)
    assert agg.to_dict()["learning_gain_per_token"]["UNAVAILABLE"] is True


def test_learning_gain_needs_token_counts_in_every_later_round():
    agg = aggregate_observations(
        [
            observation(0, False, round_id="r1", tokens=TokenAccount(TokenSource.REPORTED, 5, 5)),
            observation(1, True, round_id="r2"),
        ]
    )
    gain = agg.learning_gain_per_token()
    assert isinstance(gain, Unavailable)
    assert "no token counts" in gain.reason


def test_learning_gain_is_a_number_once_two_measured_rounds_exist():
    agg = aggregate_observations(
        [
            observation(0, False, round_id="r1", tokens=TokenAccount(TokenSource.REPORTED, 5, 5)),
            observation(1, True, round_id="r2", tokens=TokenAccount(TokenSource.REPORTED, 10, 10)),
        ]
    )
    gain = agg.learning_gain_per_token()
    assert isinstance(gain, float)
    assert gain == pytest.approx((1.0 - 0.0) / 20)


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


def test_the_ledger_validates_skill_ids_against_the_taxonomy():
    ledger = SkillLedger(taxonomy=default_taxonomy())
    with pytest.raises(TaxonomyError):
        ledger.add(observation(0, True, skill_id="syntax.invented"))


def test_an_aggregate_over_nothing_is_refused():
    ledger = SkillLedger()
    with pytest.raises(ValueError, match="no observations"):
        ledger.aggregate("syntax.role_label", H3)


def test_an_observation_must_name_its_round():
    with pytest.raises(ValueError, match="round"):
        observation(0, True, round_id="  ")


def test_aggregate_observations_refuses_more_than_one_skill():
    with pytest.raises(ValueError, match="one skill"):
        aggregate_observations(
            [observation(0, True), observation(1, True, skill_id="syntax.delimiter")]
        )


def test_the_report_prints_what_the_hypothesis_does_not_support():
    ledger = SkillLedger(taxonomy=default_taxonomy())
    ledger.add(observation(0, True))
    report = ledger.report(H3)
    assert report["hypothesis"] == "H3"
    assert "does NOT support any claim about the representation" in report["hypothesis_excluded_claim"]
