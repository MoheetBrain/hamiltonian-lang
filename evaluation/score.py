"""Deterministic scoring harness for the Hamiltonian Lang benchmark.

**No model calls anywhere in this file.** Every function here returns the same verdict
on every run given the same inputs. That is the point: `docs/research/BENCHMARK_PROTOCOL.md`
§9.4 forbids scoring by model judgement wherever a mechanical check is possible.

What this module implements
---------------------------
* ``parse_success`` — does the artefact compile clean
* ``count_tokens`` — token counts (``tiktoken`` if available, otherwise APPROXIMATE)
* the assertion language of protocol §11, covering binding accuracy, quantifier scope,
  dimensional correctness, conditioning sets, obligation counts, dependency retrieval and
  content-hash equality / inequality
* ``diagnostic_line_accuracy`` — does the compiler point at the line that was broken

What this module deliberately does NOT implement
------------------------------------------------
Anything requiring judgement. In particular there is no scorer for "did the prose arm
notice the error and explain it correctly"; that metric is marked NON-DETERMINISTIC in the
protocol and must be reported separately, never folded into a headline number.

A warning about ``content_hash``
--------------------------------
``hash_equals`` is **not** a semantic-equivalence oracle. It is equality of a canonical
syntax tree modulo bound-variable spelling and distribution-argument order. Measured
counterexamples: ``a > 0`` and ``0 < a`` hash differently; ``a + b`` and ``b + a`` hash
differently; reordering two independent ``require`` statements changes the hash; and
renaming a module-level declaration changes the hash. Use ``hash_differs`` freely (it is
sound), and use ``hash_equals`` only against a fixed reference form.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from hamiltonian_lang import CompileResult, compile_source  # noqa: E402
from hamiltonian_lang.ast.nodes import (  # noqa: E402
    AssumeStmt,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    Declaration,
    DefineStmt,
    DistExpr,
    Expr,
    Index,
    LawStmt,
    LogicalOp,
    ProveStmt,
    Quantifier,
    RequireStmt,
    UnaryOp,
)
from hamiltonian_lang.types import dimension_of  # noqa: E402

DATASETS = REPO / "benchmarks" / "datasets"
REPRESENTATIONS = REPO / "benchmarks" / "representations"
EXPECTED = REPO / "benchmarks" / "expected"

ARM_EXTENSIONS = {
    "english": ".txt",
    "latex": ".tex",
    "python": ".py",
    "stan_or_lean": (".stan", ".lean"),
    "hamiltonian": ".hml",
}

__all__ = [
    "TOKENIZER_NAME",
    "TOKENIZER_IS_APPROXIMATE",
    "count_tokens",
    "load_problems",
    "arm_path",
    "compile_problem",
    "check_assertion",
    "score_problem",
    "diagnostic_line_accuracy",
    "AssertionResult",
    "ProblemScore",
]


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

try:  # pragma: no cover - depends on the environment
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
    TOKENIZER_NAME = "tiktoken/cl100k_base"
    TOKENIZER_IS_APPROXIMATE = False
except Exception:  # pragma: no cover
    _ENCODING = None
    TOKENIZER_NAME = "fallback/regex-word-punct"
    TOKENIZER_IS_APPROXIMATE = True

#: Fallback tokenizer. Splits on runs of word characters, runs of whitespace-free
#: punctuation, and individual symbols. Calibrated against nothing. It is adequate for
#: comparing arms *within one run* and inadequate for any absolute claim. Every number
#: derived from it must carry the label APPROXIMATE.
_FALLBACK_RE = re.compile(r"[A-Za-z_]+|\d+\.\d+|\d+|\s+|[^\sA-Za-z0-9_]")


def count_tokens(text: str) -> int:
    """Token count. Exact with ``tiktoken``; otherwise APPROXIMATE (see module docstring)."""
    if _ENCODING is not None:  # pragma: no cover
        return len(_ENCODING.encode(text))
    return sum(1 for m in _FALLBACK_RE.finditer(text) if not m.group(0).isspace())


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_problems(directory: Path = DATASETS) -> list[dict]:
    """Every dataset item, sorted by id. Raises if the directory is empty."""
    items = [json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))]
    if not items:
        raise FileNotFoundError(f"no dataset items in {directory}")
    return items


def arm_path(problem_id: str, arm: str) -> Path | None:
    ext = ARM_EXTENSIONS[arm]
    candidates = (ext,) if isinstance(ext, str) else ext
    for e in candidates:
        p = REPRESENTATIONS / arm / f"{problem_id}{e}"
        if p.exists():
            return p
    return None


_COMPILE_CACHE: dict[str, CompileResult] = {}


def compile_problem(problem_id: str) -> CompileResult:
    """Compile the hamiltonian arm of a problem. Cached, because assertions such as
    ``hash_equals`` compile a second problem."""
    if problem_id not in _COMPILE_CACHE:
        p = arm_path(problem_id, "hamiltonian")
        if p is None:
            raise FileNotFoundError(f"no hamiltonian arm for {problem_id}")
        _COMPILE_CACHE[problem_id] = compile_source(p.read_text(), str(p))
    return _COMPILE_CACHE[problem_id]


# ---------------------------------------------------------------------------
# Structural extraction from a compiled module
# ---------------------------------------------------------------------------


def _symbols_by_name(result: CompileResult) -> dict[str, Any]:
    if result.symbols is None:
        return {}
    return {s.name: s for s in result.symbols.all.values()}


def _laws_by_target(result: CompileResult) -> dict[str, LawStmt]:
    return {st.target: st for st in result.module.statements if isinstance(st, LawStmt)}


def _definitions_by_name(result: CompileResult) -> dict[str, DefineStmt]:
    return {st.name: st for st in result.module.statements if isinstance(st, DefineStmt)}


def _declarations_by_name(result: CompileResult) -> dict[str, Declaration]:
    return {st.name: st for st in result.module.statements if isinstance(st, Declaration)}


def _expr_children(e: Expr) -> Iterable[Expr]:
    if isinstance(e, (BinOp, Comparison, LogicalOp)):
        return (e.left, e.right)
    if isinstance(e, UnaryOp):
        return (e.operand,)
    if isinstance(e, Call):
        return tuple(e.args)
    if isinstance(e, Index):
        return (e.base, *e.indices)
    if isinstance(e, DistExpr):
        return tuple(a.value for a in e.args)
    if isinstance(e, Quantifier):
        return (e.body,)
    return ()


def _quantifier_prefix(e: Expr | None) -> list[str]:
    """The ordered quantifier prefix of an expression, outermost first.

    Descends through non-quantifier nodes (so ``not forall x . P`` still reports
    ``["forall:x"]``) and follows the *body* of each quantifier it meets, which is what
    makes nesting order recoverable. Deterministic: no judgement, no model.
    """
    out: list[str] = []
    if e is None:
        return out
    if isinstance(e, Quantifier):
        out.append(f"{e.kind}:{e.var}")
        out.extend(_quantifier_prefix(e.body))
        return out
    for child in _expr_children(e):
        out.extend(_quantifier_prefix(child))
    return out


def _module_quantifier_prefix(result: CompileResult) -> list[str]:
    """Concatenated prefixes of every proposition-bearing statement, in source order."""
    out: list[str] = []
    for st in result.module.statements:
        if isinstance(st, (RequireStmt, AssumeStmt, ProveStmt)):
            out.extend(_quantifier_prefix(st.proposition))
        elif isinstance(st, CheckStmt) and st.subject is not None:
            out.extend(_quantifier_prefix(st.subject))
    return out


def _rendered_argument(expr: Expr) -> str:
    from hamiltonian_lang.backends.hml import render_expr

    return render_expr(expr)


# ---------------------------------------------------------------------------
# The assertion language (protocol §11)
# ---------------------------------------------------------------------------


@dataclass
class AssertionResult:
    assertion: dict
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {"assert": self.assertion.get("assert"), "passed": self.passed,
                "detail": self.detail, "spec": self.assertion}


class UnknownAssertion(Exception):
    """Raised when a dataset uses an assertion the harness does not implement.

    Raised rather than skipped on purpose: a silently skipped assertion inflates the
    pass rate, which is the cheapest way to fake a positive result.
    """


def _a_compiles(r: CompileResult, a: dict) -> tuple[bool, str]:
    if r.ok():
        substantive = [s for s in r.module.statements
                       if type(s).__name__ != "ModuleDecl"]
        if not substantive:
            return False, "compiles but contains no statement other than the module header"
        return True, f"{len(substantive)} statements"
    return False, "; ".join(f"{d.code} {d.message}" for d in r.diagnostics.errors)


def _a_rejects_with(r: CompileResult, a: dict) -> tuple[bool, str]:
    codes = [d.code for d in r.diagnostics.errors]
    if r.ok():
        return False, "compiled clean; expected rejection"
    return a["code"] in codes, f"codes={codes}"


def _a_symbol_type(r: CompileResult, a: dict) -> tuple[bool, str]:
    sym = _symbols_by_name(r).get(a["symbol"])
    if sym is None:
        return False, f"{a['symbol']!r} is not in the symbol table"
    got = sym.declared_type.render() if sym.declared_type else None
    return got == a["type"], f"declared_type={got!r}"


def _a_symbol_kind(r: CompileResult, a: dict) -> tuple[bool, str]:
    sym = _symbols_by_name(r).get(a["symbol"])
    if sym is None:
        return False, f"{a['symbol']!r} is not in the symbol table"
    return sym.kind == a["kind"], f"kind={sym.kind!r}"


def _a_stochastic(r: CompileResult, a: dict) -> tuple[bool, str]:
    sym = _symbols_by_name(r).get(a["symbol"])
    if sym is None:
        return False, f"{a['symbol']!r} is not in the symbol table"
    return bool(sym.stochastic) is bool(a["value"]), f"stochastic={sym.stochastic}"


def _a_law_family(r: CompileResult, a: dict) -> tuple[bool, str]:
    law = _laws_by_target(r).get(a["symbol"])
    if law is None or law.distribution is None:
        return False, f"{a['symbol']!r} carries no law"
    return law.distribution.family == a["family"], f"family={law.distribution.family!r}"


def _a_law_role(r: CompileResult, a: dict) -> tuple[bool, str]:
    law = _laws_by_target(r).get(a["symbol"])
    if law is None or law.distribution is None:
        return False, f"{a['symbol']!r} carries no law"
    value = law.distribution.arg(a["role"])
    if value is None:
        roles = [x.role for x in law.distribution.args]
        return False, f"role {a['role']!r} absent; roles={roles}"
    got = _rendered_argument(value)
    return got == a["argument"], f"{a['role']} := {got}"


def _a_conditioned_on(r: CompileResult, a: dict) -> tuple[bool, str]:
    law = _laws_by_target(r).get(a["symbol"])
    if law is None:
        return False, f"{a['symbol']!r} carries no law"
    got = sorted(g.name for g in law.given)
    return got == sorted(a["given"]), f"given={got}"


def _a_quantifier_prefix(r: CompileResult, a: dict) -> tuple[bool, str]:
    got = _module_quantifier_prefix(r)
    return got == list(a["prefix"]), f"prefix={got}"


def _a_dimension_of(r: CompileResult, a: dict) -> tuple[bool, str]:
    name = a["symbol"]
    node = _definitions_by_name(r).get(name) or _declarations_by_name(r).get(name)
    if node is None:
        return False, f"{name!r} is neither a definition nor a declaration"
    t = getattr(node, "type_", None) or getattr(node, "declared_type", None)
    if t is None:
        return False, f"{name!r} has no inferred type"
    dim = dimension_of(t)
    if dim is None:
        return False, f"{t.render()} carries no dimension"
    return dim.render() == a["dimension"], f"dimension={dim.render()!r}"


def _a_obligation_count(r: CompileResult, a: dict) -> tuple[bool, str]:
    n = len(r.obligations)
    return n == a["count"], f"obligations={n}"


def _a_depends_on(r: CompileResult, a: dict) -> tuple[bool, str]:
    try:
        got = sorted(r.graph().dependencies_of(a["symbol"]))
    except ValueError as exc:
        return False, str(exc)
    return got == sorted(a["set"]), f"dependencies={got}"


def _a_hash_equals(r: CompileResult, a: dict) -> tuple[bool, str]:
    other = compile_problem(a["problem"])
    if not (r.ok() and other.ok()):
        return False, "one side failed to compile"
    return r.hash() == other.hash(), f"{r.hash()[:12]} vs {other.hash()[:12]}"


def _a_hash_differs(r: CompileResult, a: dict) -> tuple[bool, str]:
    other = compile_problem(a["problem"])
    if not (r.ok() and other.ok()):
        return False, "one side failed to compile"
    return r.hash() != other.hash(), f"{r.hash()[:12]} vs {other.hash()[:12]}"


_ASSERTIONS: dict[str, Callable[[CompileResult, dict], tuple[bool, str]]] = {
    "compiles": _a_compiles,
    "rejects_with": _a_rejects_with,
    "symbol_type": _a_symbol_type,
    "symbol_kind": _a_symbol_kind,
    "stochastic": _a_stochastic,
    "law_family": _a_law_family,
    "law_role": _a_law_role,
    "conditioned_on": _a_conditioned_on,
    "quantifier_prefix": _a_quantifier_prefix,
    "dimension_of": _a_dimension_of,
    "obligation_count": _a_obligation_count,
    "depends_on": _a_depends_on,
    "hash_equals": _a_hash_equals,
    "hash_differs": _a_hash_differs,
}

#: Which protocol metric each assertion feeds. Used to aggregate per-metric rates.
ASSERTION_METRIC = {
    "compiles": "parse_success",
    "rejects_with": "error_visibility",
    "symbol_type": "type_correctness",
    "symbol_kind": "binding_accuracy",
    "stochastic": "type_correctness",
    "law_family": "binding_accuracy",
    "law_role": "role_accuracy",
    "conditioned_on": "binding_accuracy",
    "quantifier_prefix": "scope_accuracy",
    "dimension_of": "dimension_correct",
    "obligation_count": "obligation_accounting",
    "depends_on": "retrieval_accuracy",
    "hash_equals": "semantic_equivalence",
    "hash_differs": "semantic_discrimination",
}


def check_assertion(result: CompileResult, assertion: dict) -> AssertionResult:
    kind = assertion.get("assert")
    fn = _ASSERTIONS.get(kind)
    if fn is None:
        raise UnknownAssertion(
            f"assertion {kind!r} is not implemented. Implement it or remove the dataset "
            f"item; skipping it would inflate the pass rate."
        )
    passed, detail = fn(result, assertion)
    return AssertionResult(assertion, passed, detail)


# ---------------------------------------------------------------------------
# Per-problem scoring
# ---------------------------------------------------------------------------


@dataclass
class ProblemScore:
    problem_id: str
    category: str
    expects_rejection: bool
    compiled: bool
    diagnostic_codes: list[str] = field(default_factory=list)
    content_hash: str | None = None
    obligations: int = 0
    assertions: list[AssertionResult] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=dict)

    @property
    def assertions_passed(self) -> int:
        return sum(1 for a in self.assertions if a.passed)

    @property
    def all_assertions_passed(self) -> bool:
        return all(a.passed for a in self.assertions)

    def to_dict(self) -> dict:
        return {
            "problem_id": self.problem_id,
            "category": self.category,
            "expects_rejection": self.expects_rejection,
            "compiled": self.compiled,
            "diagnostic_codes": self.diagnostic_codes,
            "content_hash": self.content_hash,
            "obligations": self.obligations,
            "assertions_total": len(self.assertions),
            "assertions_passed": self.assertions_passed,
            "all_assertions_passed": self.all_assertions_passed,
            "assertions": [a.to_dict() for a in self.assertions],
            "tokens_by_arm": self.tokens,
        }


def score_problem(item: dict) -> ProblemScore:
    pid = item["id"]
    result = compile_problem(pid)
    score = ProblemScore(
        problem_id=pid,
        category=item["category"],
        expects_rejection=bool(item.get("expects_rejection")),
        compiled=result.ok(),
        diagnostic_codes=[d.code for d in result.diagnostics.errors],
        obligations=len(result.obligations),
    )
    if result.ok():
        score.content_hash = result.hash()
    for a in item["deterministic_check"]["assertions"]:
        score.assertions.append(check_assertion(result, a))
    for arm in ARM_EXTENSIONS:
        p = arm_path(pid, arm)
        if p is not None:
            score.tokens[arm] = count_tokens(p.read_text())
    return score


# ---------------------------------------------------------------------------
# Diagnostic quality
# ---------------------------------------------------------------------------

#: Each injection is a (name, mutator) pair. The mutator takes the source lines and
#: returns ``(mutated_source, expected_1_based_line)`` or ``None`` when the injection does
#: not apply to that file. Every mutation touches exactly one line, so "the compiler
#: pointed at the right line" is well defined.


def _inject_unbound_reference(lines: list[str]) -> tuple[str, int] | None:
    out = list(lines) + ["require zzz_not_declared_anywhere > 0.0"]
    return "\n".join(out) + "\n", len(out)


def _inject_bad_role(lines: list[str]) -> tuple[str, int] | None:
    for i, ln in enumerate(lines):
        if "location :=" in ln:
            out = list(lines)
            out[i] = ln.replace("location :=", "centre :=", 1)
            return "\n".join(out) + "\n", i + 1
    return None


def _inject_unknown_family(lines: list[str]) -> tuple[str, int] | None:
    for i, ln in enumerate(lines):
        m = re.search(r"~\s*([A-Z][A-Za-z0-9_]*)\s*\(", ln)
        if m:
            out = list(lines)
            out[i] = ln[: m.start(1)] + "Zzzznotafamily" + ln[m.end(1):]
            return "\n".join(out) + "\n", i + 1
    return None


def _inject_positional_arguments(lines: list[str]) -> tuple[str, int] | None:
    for i, ln in enumerate(lines):
        m = re.search(r"~\s*[A-Z][A-Za-z0-9_]*\s*\(", ln)
        if m and ":=" in ln:
            head = ln[: m.end()]
            out = list(lines)
            out[i] = head + "1.0, 2.0)"
            return "\n".join(out) + "\n", i + 1
    return None


def _inject_undeclared_quantifier_type(lines: list[str]) -> tuple[str, int] | None:
    for i, ln in enumerate(lines):
        m = re.search(r"(forall|exists)\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", ln)
        if m:
            out = list(lines)
            out[i] = ln[: m.end(2)] + ln[m.end():]  # drop the ':' and keep the rest
            return "\n".join(out) + "\n", i + 1
    return None


INJECTIONS: list[tuple[str, Callable[[list[str]], tuple[str, int] | None]]] = [
    ("unbound_reference", _inject_unbound_reference),
    ("bad_distribution_role", _inject_bad_role),
    ("unknown_distribution_family", _inject_unknown_family),
    ("positional_distribution_arguments", _inject_positional_arguments),
    ("quantifier_without_type", _inject_undeclared_quantifier_type),
]


def diagnostic_line_accuracy(problem_ids: Iterable[str]) -> dict:
    """For each single-line injected error: does the FIRST reported diagnostic point at it?

    Deterministic. Reports per-injection rates as well as the aggregate, because a single
    aggregate hides the case where one injection kind is perfect and another is useless.
    """
    trials: list[dict] = []
    for pid in problem_ids:
        path = arm_path(pid, "hamiltonian")
        if path is None:
            continue
        base = compile_source(path.read_text(), str(path))
        if not base.ok():
            continue  # only inject into files that were clean to begin with
        lines = path.read_text().rstrip("\n").split("\n")
        for name, mutate in INJECTIONS:
            made = mutate(lines)
            if made is None:
                continue
            mutated, expected_line = made
            r = compile_source(mutated, str(path))
            errs = r.diagnostics.errors
            trials.append({
                "problem_id": pid,
                "injection": name,
                "expected_line": expected_line,
                "detected": bool(errs),
                "reported_line": errs[0].line if errs else None,
                "reported_code": errs[0].code if errs else None,
                "line_correct": bool(errs) and errs[0].line == expected_line,
            })

    by_injection: dict[str, dict] = {}
    for t in trials:
        b = by_injection.setdefault(t["injection"], {"n": 0, "detected": 0, "line_correct": 0})
        b["n"] += 1
        b["detected"] += int(t["detected"])
        b["line_correct"] += int(t["line_correct"])
    for b in by_injection.values():
        b["detection_rate"] = b["detected"] / b["n"] if b["n"] else None
        b["line_accuracy"] = b["line_correct"] / b["n"] if b["n"] else None

    n = len(trials)
    return {
        "trials": n,
        "detection_rate": (sum(t["detected"] for t in trials) / n) if n else None,
        "line_accuracy": (sum(t["line_correct"] for t in trials) / n) if n else None,
        "by_injection": by_injection,
        "detail": trials,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate(scores: list[ProblemScore]) -> dict:
    per_metric: dict[str, dict[str, int]] = {}
    for s in scores:
        for a in s.assertions:
            metric = ASSERTION_METRIC.get(a.assertion.get("assert"), "unclassified")
            m = per_metric.setdefault(metric, {"passed": 0, "total": 0})
            m["total"] += 1
            m["passed"] += int(a.passed)
    for m in per_metric.values():
        m["rate"] = m["passed"] / m["total"] if m["total"] else None

    valid = [s for s in scores if not s.expects_rejection]
    negative = [s for s in scores if s.expects_rejection]
    by_category: dict[str, dict] = {}
    for s in scores:
        c = by_category.setdefault(s.category, {"problems": 0, "assertions_total": 0,
                                                "assertions_passed": 0})
        c["problems"] += 1
        c["assertions_total"] += len(s.assertions)
        c["assertions_passed"] += s.assertions_passed
    for c in by_category.values():
        c["assertion_rate"] = (c["assertions_passed"] / c["assertions_total"]
                               if c["assertions_total"] else None)

    # Problems that share a content hash. Some sharing is *intended* (an item whose
    # assertions include hash_equals against the other member). Unintended sharing means
    # two problems the corpus treats as distinct are indistinguishable to the compiler,
    # which would invalidate every hash_differs result in the run.
    hashes: dict[str, list[str]] = {}
    for s in scores:
        if s.content_hash:
            hashes.setdefault(s.content_hash, []).append(s.problem_id)
    intended: set[frozenset[str]] = set()
    for s in scores:
        for a in s.assertions:
            if a.assertion.get("assert") == "hash_equals":
                intended.add(frozenset({s.problem_id, a.assertion["problem"]}))
    collisions = {}
    for h, ids in hashes.items():
        if len(ids) < 2:
            continue
        is_intended = all(
            frozenset({x, y}) in intended
            for i, x in enumerate(ids) for y in ids[i + 1:]
        )
        collisions[h] = {"problems": ids, "intended": is_intended}
    unintended = {h: v for h, v in collisions.items() if not v["intended"]}

    return {
        "problems_scored": len(scores),
        "problems_expected_valid": len(valid),
        "problems_expected_rejected": len(negative),
        "valid_parse_success_rate": (sum(s.compiled for s in valid) / len(valid)
                                     if valid else None),
        "negative_rejection_rate": (sum(not s.compiled for s in negative) / len(negative)
                                    if negative else None),
        "assertions_total": sum(len(s.assertions) for s in scores),
        "assertions_passed": sum(s.assertions_passed for s in scores),
        "problems_all_assertions_passed": sum(s.all_assertions_passed for s in scores),
        "per_metric": per_metric,
        "by_category": by_category,
        "content_hash_shared": collisions,
        "content_hash_collisions_UNINTENDED": unintended,
    }


def token_summary(scores: list[ProblemScore]) -> dict:
    arms = sorted({a for s in scores for a in s.tokens})
    out: dict[str, Any] = {
        "tokenizer": TOKENIZER_NAME,
        "APPROXIMATE": TOKENIZER_IS_APPROXIMATE,
        "by_arm": {},
    }
    for arm in arms:
        vals = [s.tokens[arm] for s in scores if arm in s.tokens]
        out["by_arm"][arm] = {
            "problems": len(vals),
            "total_tokens": sum(vals),
            "mean_tokens": sum(vals) / len(vals) if vals else None,
            "min_tokens": min(vals) if vals else None,
            "max_tokens": max(vals) if vals else None,
        }
    base = out["by_arm"].get("english", {}).get("total_tokens")
    if base:
        for v in out["by_arm"].values():
            v["ratio_to_english"] = round(v["total_tokens"] / base, 4)
    out["CAVEAT"] = (
        "These counts are NOT a like-for-like comparison and must not be quoted as one. "
        "The english / latex / python / stan_or_lean files state the PROBLEM (prose, the "
        "question asked, and commentary on what the notation does and does not capture). "
        "The hamiltonian files contain only the ANSWER: the finished encoding, with no "
        "problem statement. A shorter hamiltonian total therefore reflects the corpus "
        "layout, not token efficiency. The protocol's H5 metric is tokens-to-verified-"
        "correct in a model-in-the-loop run, which is not measured here and cannot be "
        "estimated from these numbers."
    )
    return out


if __name__ == "__main__":  # pragma: no cover
    items = load_problems()
    scores = [score_problem(i) for i in items]
    print(json.dumps({"aggregate": aggregate(scores),
                      "tokens": token_summary(scores)}, indent=2))
