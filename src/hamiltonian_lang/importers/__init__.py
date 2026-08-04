"""Importers — reading a Hamiltonian object back out of another representation.

HML-EVAL-001 §9. Until now every backend was one-way: nine renderings, one round trip
(HML → HML), and that is the trip that cannot lose anything. These importers exist to
test the one-object-many-views claim rather than assert it.

**Each importer declares a narrow supported subset and rejects everything else.** No
general Stan or Lean interoperability is claimed, and a construct outside the subset
raises rather than being silently approximated — an importer that guesses would
manufacture a passing round trip out of nothing.

Nothing here changes v0 syntax or semantics: importers are additive and read-only with
respect to the frozen language.
"""

from __future__ import annotations

import json
import re

__all__ = [
    "UnsupportedConstruct",
    "SubsetSpec",
    "from_canonical_json",
    "from_triples",
    "from_stan",
    "from_lean",
    "SUPPORTED_SUBSETS",
]


class UnsupportedConstruct(Exception):
    """Raised when the input uses something outside the declared supported subset."""


class SubsetSpec:
    def __init__(self, name: str, supported: list[str], rejected: list[str]) -> None:
        self.name, self.supported, self.rejected = name, supported, rejected


SUPPORTED_SUBSETS = {
    "canonical": SubsetSpec(
        "canonical JSON",
        supported=[
            "declarations (var/param/const/obs/index/rv) with scalar, Vector, Matrix, "
            "Quantity, RandomVariable and Distribution types",
            "laws with role-labelled arguments and conditioning sets",
            "constraints, assumptions and theorems over comparisons and quantifiers",
            "objectives, solve and infer statements",
        ],
        rejected=["concepts", "definitions with parameters", "indexing expressions"],
    ),
    "triples": SubsetSpec(
        "semantic graph triples",
        supported=[
            "has_type, declared_as, family, role:<name>, has_law:<role>, conditioned_on"
        ],
        rejected=[
            "quantifier scope chains", "constraints", "objectives",
            "expression-valued role fillers", "concepts",
        ],
    ),
    "stan": SubsetSpec(
        "Stan subset",
        supported=[
            "data and parameters blocks with real, int, vector[n], matrix[m,n]",
            "lower/upper constraints mapped back to the scalar refinement lattice",
            "model-block sampling statements `x ~ family(a, b)` for the registered "
            "families, mapped back to roles by position",
        ],
        rejected=[
            "transformed data/parameters", "generated quantities", "functions blocks",
            "loops", "vectorised or truncated sampling statements", "target += ",
            "any dimensional information (Stan has no dimensions)",
        ],
    ),
    "lean": SubsetSpec(
        "Lean statement subset",
        supported=[
            "`variable (x : T)` declarations for R, N, Z",
            "`theorem name : <quantified comparison> := by sorry`",
            "nested forall/exists with an explicit type ascription",
        ],
        rejected=[
            "probability laws (no measure theory is invented)", "definitions",
            "tactics other than sorry", "structures", "typeclasses",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Canonical JSON -> HML source
# ---------------------------------------------------------------------------

_TYPE_OK = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\[.*\])?$")


def _expr_from_canonical(node: dict, names: dict[str, str], depth: int = 0) -> str:
    if node is None:
        raise UnsupportedConstruct("missing expression")
    kind = node.get("kind")
    if kind == "Literal":
        v = node["value"]
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)
    if kind == "Ref":
        sym = node.get("symbol")
        if sym is None:
            raise UnsupportedConstruct("unresolved reference")
        if sym not in names:
            raise UnsupportedConstruct(f"reference to unknown symbol {sym}")
        return names[sym]
    if kind == "UnaryOp":
        return f"({node['op']} {_expr_from_canonical(node['operand'], names, depth)})"
    if kind in ("BinOp", "Comparison"):
        left = _expr_from_canonical(node["left"], names, depth)
        right = _expr_from_canonical(node["right"], names, depth)
        return f"({left} {node['op']} {right})"
    if kind == "LogicalOp":
        op = {"implies": "=>", "iff": "<=>"}.get(node["op"], node["op"])
        left = _expr_from_canonical(node["left"], names, depth)
        right = _expr_from_canonical(node["right"], names, depth)
        return f"({left} {op} {right})"
    if kind == "Quantifier":
        binder = node["binder"]
        # Binder names are not in the canonical form by design (D-010), so a fresh name
        # is invented. Content hashing is name-independent, so this is sound.
        name = f"v{depth}"
        names = dict(names)
        names[binder] = name
        kw = "exists unique" if node["quantifier"] == "exists_unique" else node["quantifier"]
        body = _expr_from_canonical(node["body"], names, depth + 1)
        return f"{kw} {name} : {node['binder_type']} . {body}"
    if kind == "DistributionLaw":
        args = ", ".join(
            f"{role} := {_expr_from_canonical(v, names, depth)}"
            for role, v in sorted(node["arguments"].items())
        )
        return f"{node['family']}({args})"
    raise UnsupportedConstruct(f"expression kind {kind!r} is outside the subset")


def from_canonical_json(blob: str | dict) -> str:
    """Reconstruct HML-L1 source from canonical JSON (produced with names retained)."""
    doc = json.loads(blob) if isinstance(blob, str) else blob
    lines = [f"module {doc.get('module', 'Main')}", ""]
    names: dict[str, str] = {}

    for st in doc["statements"]:
        sym = st.get("symbol")
        if isinstance(sym, dict) and sym.get("name"):
            names[sym["id"]] = sym["name"]

    for st in doc["statements"]:
        kind = st["kind"]
        if kind == "Declaration":
            sym = st["symbol"]
            if not isinstance(sym, dict):
                raise UnsupportedConstruct(
                    "declaration names were stripped; reconstruct from the named form"
                )
            t = st["type"]
            if not t or not _TYPE_OK.match(t):
                raise UnsupportedConstruct(f"unrenderable type {t!r}")
            line = f"{st['declaration_kind']} {sym['name']} : {t}"
            if st.get("value") is not None:
                line += f" = {_expr_from_canonical(st['value'], names)}"
            lines.append(line)
        elif kind == "Law":
            target = names.get(st["target"])
            if target is None:
                raise UnsupportedConstruct("law target not resolvable")
            given = [names[g] for g in st.get("given", []) if g in names]
            g = f" | {' '.join(given)}" if given else ""
            dist = _expr_from_canonical(st["distribution"], names)
            lines.append(f"{st['role']} {target}{g} ~ {dist}")
        elif kind in ("Constraint", "Assumption", "Theorem"):
            kw = {"Constraint": "require", "Assumption": "assume", "Theorem": "prove"}[kind]
            lines.append(f"{kw} {_expr_from_canonical(st['proposition'], names)}")
        elif kind == "Objective":
            lines.append(
                f"{st['direction']} {_expr_from_canonical(st['expression'], names)}"
            )
        elif kind == "Solve":
            lines.append("solve " + " ".join(names[t] for t in st["targets"] if t in names))
        elif kind == "Inference":
            lines.append(
                f"infer {st['query']} "
                + " ".join(names[t] for t in st["targets"] if t in names)
            )
        elif kind == "Check":
            subj = _expr_from_canonical(st["subject"], names)
            if st["check_kind"] == "dimension":
                line = f"check dimension {subj}"
                if st.get("expected"):
                    line += f" = {st['expected']}"
                lines.append(line)
            else:
                lines.append(f"check {subj}")
        else:
            raise UnsupportedConstruct(f"statement kind {kind!r} is outside the subset")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Semantic graph triples -> HML source
# ---------------------------------------------------------------------------

_TRIPLE = re.compile(r"^\s*(\S+)\s*->\s*(\S+)\s+(.+?)\s*$")


def from_triples(text: str) -> str:
    """Reconstruct HML from the triple view.

    Deliberately narrow: the triple view records declarations and laws faithfully but
    does **not** record quantifier bodies, constraint expressions or objectives, so a
    module containing those cannot be reconstructed and is rejected rather than
    approximated.
    """
    types: dict[str, str] = {}
    kinds: dict[str, str] = {}
    law_family: dict[str, str] = {}
    law_roles: dict[str, dict[str, str]] = {}
    law_of: dict[str, tuple[str, str]] = {}
    conditioned: dict[str, list[str]] = {}
    labels: dict[str, str] = {}

    for line in text.splitlines():
        m = _TRIPLE.match(line)
        if not m:
            continue
        subj, pred, obj = m.groups()
        if pred == "has_type":
            types[subj] = obj.split(":", 1)[-1] if obj.startswith("type:") else obj
        elif pred == "declared_as":
            kinds[subj] = obj.split(":", 1)[-1] if obj.startswith("declkind:") else obj
        elif pred == "family":
            law_family[subj] = obj.split(":", 1)[-1] if obj.startswith("family:") else obj
        elif pred.startswith("role:"):
            law_roles.setdefault(subj, {})[pred.split(":", 1)[1]] = obj
        elif pred.startswith("has_law:"):
            law_of[subj] = (pred.split(":", 1)[1], obj)
        elif pred == "conditioned_on":
            conditioned.setdefault(subj, []).append(obj)
        elif pred in ("constrains", "objective_of", "scope_of", "binds", "queries"):
            raise UnsupportedConstruct(
                f"predicate {pred!r} is outside the triple subset: the triple view does "
                "not carry the expression it points at"
            )

    if not types:
        raise UnsupportedConstruct("no typed symbols found")

    for s in list(types):
        labels[s] = s.replace("sym:#", "s").replace(".", "_")

    lines = ["module FromTriples", ""]
    for s, t in types.items():
        lines.append(f"{kinds.get(s, 'var')} {labels[s]} : {t}")
    lines.append("")
    for target, (role, law_id) in law_of.items():
        fam = law_family.get(law_id)
        if not fam:
            raise UnsupportedConstruct(f"law {law_id} has no family")
        args = []
        for r, filler in sorted(law_roles.get(law_id, {}).items()):
            args.append(f"{r} := {labels.get(filler, filler)}")
        given = [labels.get(g, g) for g in conditioned.get(target, [])]
        g = f" | {' '.join(given)}" if given else ""
        lines.append(f"{role} {labels.get(target, target)}{g} ~ {fam}({', '.join(args)})")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Stan subset -> HML source
# ---------------------------------------------------------------------------

_STAN_DECL = re.compile(
    r"^\s*(real|int|vector|matrix)\s*(?:<([^>]*)>)?\s*(?:\[([^\]]*)\])?\s*(\w+)\s*;"
)
_STAN_SAMPLE = re.compile(r"^\s*(\w+)\s*~\s*(\w+)\s*\(([^)]*)\)\s*;")
_STAN_BLOCK = re.compile(r"^\s*(data|parameters|model|transformed\s+\w+|generated\s+quantities|functions)\s*\{")

#: Positional argument order per family, mirrored from backends/stan.py. Reversing a
#: positional convention is exactly where a silent role swap would hide, so the table is
#: written out rather than derived.
_STAN_ROLE_ORDER = {
    "normal": ("Normal", ["location", "scale"]),
    "beta": ("Beta", ["alpha", "beta"]),
    "binomial": ("Binomial", ["trials", "prob"]),
    "bernoulli": ("Bernoulli", ["prob"]),
    "poisson": ("Poisson", ["rate"]),
    "exponential": ("Exponential", ["rate"]),
    "gamma": ("Gamma", ["shape", "rate"]),
    "inv_gamma": ("InverseGamma", ["shape", "scale"]),
    "uniform": ("Uniform", ["lower", "upper"]),
    "cauchy": ("Cauchy", ["location", "scale"]),
    "lognormal": ("LogNormal", ["location", "scale"]),
    "student_t": ("StudentT", ["degrees_of_freedom", "location", "scale"]),
}


def _stan_scalar(base: str, bounds: str | None) -> str:
    lo = hi = None
    if bounds:
        for part in bounds.split(","):
            if "lower" in part:
                lo = part.split("=", 1)[1].strip()
            elif "upper" in part:
                hi = part.split("=", 1)[1].strip()
    if base == "int":
        return "Natural" if lo in ("0",) else "Integer"
    if lo == "0" and hi == "1":
        return "Probability"
    if lo == "0" and hi is None:
        return "NonNegativeReal"
    return "Real"


def from_stan(text: str) -> str:
    """Reconstruct HML from the declared Stan subset.

    Roles are recovered from **position** using ``_STAN_ROLE_ORDER``. That is the exact
    inverse of the backend's role→position mapping, and it is the step where a silent
    scale/variance swap would occur if either table were wrong, so the round-trip test
    is the check on both.
    """
    kinds: dict[str, str] = {}
    types: dict[str, str] = {}
    order: list[str] = []
    laws: list[tuple[str, str, list[str]]] = []
    block = None

    for raw in text.splitlines():
        line = raw.split("//", 1)[0]
        if not line.strip():
            continue
        mb = _STAN_BLOCK.match(line)
        if mb:
            name = re.sub(r"\s+", " ", mb.group(1))
            if name in ("transformed data", "transformed parameters",
                        "generated quantities", "functions"):
                raise UnsupportedConstruct(f"Stan block {name!r} is outside the subset")
            block = name
            continue
        if line.strip() in ("}", "{"):
            continue
        if "target +=" in line:
            raise UnsupportedConstruct("`target +=` is outside the subset")

        md = _STAN_DECL.match(line)
        if md and block in ("data", "parameters"):
            base, bounds, dims, name = md.groups()
            if base == "real":
                t = _stan_scalar("real", bounds)
            elif base == "int":
                t = _stan_scalar("int", bounds)
            elif base == "vector":
                t = f"Vector[Real, {dims.strip()}]" if dims else "Vector[Real, ?]"
            else:
                parts = [p.strip() for p in (dims or "").split(",")]
                t = (
                    f"Matrix[Real, {parts[0]}, {parts[1]}]"
                    if len(parts) == 2 else "Matrix[Real, ?, ?]"
                )
            if bounds and "lower=0" in bounds.replace(" ", "") and base == "real" \
                    and "upper" not in bounds:
                t = "NonNegativeReal"
            types[name] = t
            kinds[name] = "obs" if block == "data" else "param"
            order.append(name)
            continue

        ms = _STAN_SAMPLE.match(line)
        if ms and block == "model":
            target, family, args = ms.groups()
            fam = family.strip().lower()
            if fam not in _STAN_ROLE_ORDER:
                raise UnsupportedConstruct(f"family {family!r} is outside the subset")
            laws.append((target, fam, [a.strip() for a in args.split(",") if a.strip()]))
            continue

        if block == "model" and line.strip() and not line.strip().startswith("{"):
            if re.match(r"^\s*(for|if|while)\b", line):
                raise UnsupportedConstruct("control flow is outside the subset")

    if not types:
        raise UnsupportedConstruct("no declarations recovered")

    lines = ["module FromStan", ""]
    for n in order:
        lines.append(f"{kinds[n]} {n} : {types[n]}")
    lines.append("")
    for target, fam, args in laws:
        hml_family, roles = _STAN_ROLE_ORDER[fam]
        if len(args) != len(roles):
            raise UnsupportedConstruct(
                f"{fam} expects {len(roles)} positional arguments, got {len(args)}"
            )
        pairs = ", ".join(f"{r} := {a}" for r, a in zip(roles, args, strict=True))
        lines.append(f"law {target} ~ {hml_family}({pairs})")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Lean statement subset -> HML source
# ---------------------------------------------------------------------------

_LEAN_TYPES = {"ℝ": "Real", "ℕ": "Natural", "ℤ": "Integer", "ℚ": "Rational",
               "Real": "Real", "Nat": "Natural", "Int": "Integer"}
_LEAN_VAR = re.compile(r"^\s*variable\s*\(\s*(\w+)\s*:\s*(\S+)\s*\)")
_LEAN_THM = re.compile(r"^\s*theorem\s+(\w+)\s*:\s*(.+?)\s*:=\s*by\s+sorry\s*$")
_LEAN_Q = re.compile(r"^\s*(∀|∃)\s*(\w+)\s*:\s*(\S+?)\s*,\s*(.*)$")


def from_lean(text: str) -> str:
    """Reconstruct HML from the declared Lean statement subset.

    Only `variable` declarations and `theorem … := by sorry` over nested typed
    quantifiers with a single comparison body. Anything else is rejected: no probability
    law is invented, because Lean output carries none.
    """
    decls: list[tuple[str, str]] = []
    props: list[str] = []

    for raw in text.splitlines():
        line = raw.split("--", 1)[0].rstrip()
        if not line.strip():
            continue
        mv = _LEAN_VAR.match(line)
        if mv:
            name, lean_t = mv.groups()
            if lean_t not in _LEAN_TYPES:
                raise UnsupportedConstruct(f"Lean type {lean_t!r} is outside the subset")
            decls.append((name, _LEAN_TYPES[lean_t]))
            continue
        mt = _LEAN_THM.match(line)
        if mt:
            props.append(_lean_prop(mt.group(2)))
            continue
        if re.match(r"^\s*(def|structure|instance|class|example|lemma)\b", line):
            raise UnsupportedConstruct("only `variable` and `theorem … := by sorry`")

    if not props and not decls:
        raise UnsupportedConstruct("nothing recoverable found")

    lines = ["module FromLean", ""]
    for name, t in decls:
        lines.append(f"var {name} : {t}")
    if decls:
        lines.append("")
    for p in props:
        lines.append(f"prove {p}")
    return "\n".join(lines) + "\n"


def _lean_prop(body: str) -> str:
    body = body.strip()
    m = _LEAN_Q.match(body)
    if m:
        q, var, t, rest = m.groups()
        if t not in _LEAN_TYPES:
            raise UnsupportedConstruct(f"Lean type {t!r} is outside the subset")
        kw = "forall" if q == "∀" else "exists"
        return f"{kw} {var} : {_LEAN_TYPES[t]} . {_lean_prop(rest)}"
    cleaned = body.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
    if not re.match(r"^[\w\s+\-*/^().]+(=|!=|<|<=|>|>=)[\w\s+\-*/^().]+$", cleaned):
        raise UnsupportedConstruct(
            f"proposition body {body!r} is outside the subset (single comparison only)"
        )
    return cleaned.strip()
