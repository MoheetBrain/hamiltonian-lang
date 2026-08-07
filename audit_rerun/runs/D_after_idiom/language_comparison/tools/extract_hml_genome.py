#!/usr/bin/env python3
"""Deterministic extraction of the Hamiltonian Lang (HML) language genome.

SOURCE OF TRUTH: the local repository only. Nothing here consults any external
project. There is an unrelated public "Hamiltonian Lang" mechanics DSL; it is NOT
this project and contributes nothing to this extraction.

Method
------
Two independent channels, deliberately combined:

* **Static** -- ``ast.parse`` over every ``.py`` under ``src/hamiltonian_lang``.
  Used for anything whose *definition site* is the fact: class declarations,
  diagnostic-code string literals, which module mentions which AST node.
* **Runtime** -- the package is imported and its registries are read directly
  (``KEYWORDS``, ``DISTRIBUTIONS``, ``SCALARS``, ``EDGE_KINDS``, the backend
  ``REGISTRY``). A dict is a better witness of itself than a re-parse of the
  literal that built it.

Both channels are order-independent: every collection is sorted before it is
emitted, so two runs on the same tree produce byte-identical JSON.

Counting rules are emitted *inside* the JSON next to every count, under
``counting_rule``. A count with no stated rule is not a measurement.

Status vocabulary (exactly one per capability)
----------------------------------------------
IMPLEMENTED             surface form parses AND some checker imposes a rule on it
PARTIALLY_IMPLEMENTED   rule exists but is narrower than the construct it governs
DECLARED_BUT_UNENFORCED parses / is declared, but no checker reads it
TEST_ONLY               exists only to satisfy a test; no production caller
PLANNED                 named in docs or spec with no implementation
ABSENT                  claimed somewhere, not present

Usage::

    PYTHONPATH=<repo>/src python audit/language_comparison/tools/extract_hml_genome.py

Writes ``audit/language_comparison/genomes/HML_LANGUAGE_GENOME.json``.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Repository layout
# --------------------------------------------------------------------------

TOOLS_DIR = Path(__file__).resolve().parent
REPO = TOOLS_DIR.parents[2]
SRC = REPO / "src" / "hamiltonian_lang"
TESTS = REPO / "tests"
EXAMPLES = REPO / "examples"
OUT = TOOLS_DIR.parent / "genomes" / "HML_LANGUAGE_GENOME.json"

if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

import hamiltonian_lang  # noqa: E402

# Refuse to measure the wrong tree. The live experiment repo has the same package
# name; importing it here would silently produce a genome of a different checkout.
_pkg = Path(hamiltonian_lang.__file__).resolve()
if not str(_pkg).startswith(str(SRC)):
    raise SystemExit(
        f"FATAL: imported hamiltonian_lang from {_pkg}, expected a path under {SRC}.\n"
        f"Set PYTHONPATH={REPO / 'src'} and re-run."
    )

from hamiltonian_lang import ast as hml_ast  # noqa: E402
from hamiltonian_lang import types as hml_types  # noqa: E402
from hamiltonian_lang.backends import REGISTRY as BACKEND_REGISTRY  # noqa: E402
from hamiltonian_lang.backends.canonical import CANONICAL_VERSION  # noqa: E402
from hamiltonian_lang.graph import EDGE_KINDS  # noqa: E402
from hamiltonian_lang.lexer import KEYWORDS, UNICODE_FOLD, TokenKind  # noqa: E402
from hamiltonian_lang.parser import (  # noqa: E402
    _COMPARISONS,
    _CONCEPT_MEMBER_KEYWORDS,
    _DECL_KEYWORDS,
    _INFER_QUERIES,
)
from hamiltonian_lang.semantics import _BUILTIN_FUNCTIONS  # noqa: E402
from hamiltonian_lang.type_system import _BUILTIN_SIGNATURES  # noqa: E402
from hamiltonian_lang.type_system.distributions import (  # noqa: E402
    DISTRIBUTIONS,
    MISPARAMETERISATIONS,
)

# Private module-level tables read from the lexer/parser source text, because they
# are module-private and importing them by name would be brittle if renamed.
_LEXER_SRC = (SRC / "lexer" / "__init__.py").read_text()
_PARSER_SRC = (SRC / "parser" / "__init__.py").read_text()


# --------------------------------------------------------------------------
# Capability record
# --------------------------------------------------------------------------

STATUSES = {
    "IMPLEMENTED",
    "PARTIALLY_IMPLEMENTED",
    "DECLARED_BUT_UNENFORCED",
    "TEST_ONLY",
    "PLANNED",
    "ABSENT",
}


@dataclass
class Capability:
    """One claimed capability, with the evidence that decides its status."""

    name: str
    status: str
    source_path: str
    symbol: str
    confidence: str  # high | medium | low
    layer: str = "CORE"  # CORE (the .hml language) | LIBRARY (Python-API only)
    test_file: str | None = None
    evidence: str = ""
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        assert self.status in STATUSES, f"bad status {self.status!r} for {self.name!r}"
        assert self.confidence in {"high", "medium", "low"}, self.name
        assert self.layer in {"CORE", "LIBRARY"}, self.name


CAPS: list[Capability] = []


def cap(**kw: Any) -> Capability:
    c = Capability(**kw)
    CAPS.append(c)
    return c


def rel(p: Path | str) -> str:
    return str(Path(p).resolve().relative_to(REPO))


# --------------------------------------------------------------------------
# Static pass: parse every source file once
# --------------------------------------------------------------------------


@dataclass
class ParsedFile:
    path: Path
    tree: ast.Module
    text: str


def python_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*.py") if "__pycache__" not in p.parts
    )


PARSED: dict[str, ParsedFile] = {}
for _p in python_files(SRC):
    _t = _p.read_text()
    PARSED[rel(_p)] = ParsedFile(_p, ast.parse(_t), _t)


def classes_in(pf: ParsedFile) -> list[ast.ClassDef]:
    return [n for n in ast.walk(pf.tree) if isinstance(n, ast.ClassDef)]


def base_names(c: ast.ClassDef) -> list[str]:
    out = []
    for b in c.bases:
        if isinstance(b, ast.Name):
            out.append(b.id)
        elif isinstance(b, ast.Attribute):
            out.append(b.attr)
        elif isinstance(b, ast.Subscript):  # e.g. dict[str, str]
            out.append(ast.unparse(b))
    return out


# --------------------------------------------------------------------------
# 1. Lexical layer
# --------------------------------------------------------------------------


def extract_lexical() -> dict:
    # _OPERATORS is a module-private list literal in the lexer; read it statically so
    # the extraction records the *maximal-munch order* as written, not a set.
    lex = PARSED[rel(SRC / "lexer" / "__init__.py")]
    operators: list[str] = []
    unicode_ops: dict[str, str] = {}
    for node in ast.walk(lex.tree):
        if isinstance(node, ast.Assign) and node.targets:
            tgt = node.targets[0]
            name = tgt.id if isinstance(tgt, ast.Name) else None
            if name == "_OPERATORS" and isinstance(node.value, ast.List):
                operators = [
                    e.value for e in node.value.elts if isinstance(e, ast.Constant)
                ]
            if name == "_UNICODE_OPS" and isinstance(node.value, ast.Dict):
                unicode_ops = {
                    k.value: v.value
                    for k, v in zip(node.value.keys, node.value.values, strict=True)
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
                }

    # Delimiters vs true operators: a token that only ever groups or separates is a
    # delimiter. This split is a judgement about ROLE, applied uniformly.
    delimiters = ["(", ")", "[", "]", ",", "."]
    binding = [":", "::", ":=", "|", "~", "->"]
    true_ops = [o for o in operators if o not in delimiters and o not in binding]

    # Which keywords does the parser actually dispatch on? Any keyword string that
    # appears as an argument to is_kw()/accept_kw() or as a key of a parser table.
    reachable: set[str] = set()
    par = PARSED[rel(SRC / "parser" / "__init__.py")]
    for node in ast.walk(par.tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"is_kw", "accept_kw"}:
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        reachable.add(a.value)
    reachable |= set(_DECL_KEYWORDS)
    reachable |= set(_INFER_QUERIES)
    reachable |= set(_CONCEPT_MEMBER_KEYWORDS)

    unreachable = sorted(set(KEYWORDS) - reachable)

    # Keyword grouping mirrors the comment blocks in lexer/__init__.py::KEYWORDS.
    groups = {
        "structure": ["module", "concept", "extends", "end"],
        "declaration": ["var", "param", "const", "obs", "index", "rv", "def", "fn"],
        "probabilistic": [
            "law", "prior", "likelihood", "infer", "posterior", "expectation",
            "variance", "mle", "map",
        ],
        "logical_constraint": [
            "assume", "require", "prove", "check", "dimension", "solve",
            "minimise", "maximise", "minimize", "maximize",
        ],
        "quantifier_connective": [
            "forall", "exists", "unique", "and", "or", "not", "implies", "iff",
        ],
        "concept_member": [
            "parameter", "transform", "invariant", "property", "example",
            "counterexample",
        ],
        "literal": ["true", "false"],
    }
    grouped = sorted(x for g in groups.values() for x in g)
    assert grouped == sorted(KEYWORDS), (
        "keyword grouping drifted from lexer.KEYWORDS; "
        f"missing={sorted(set(KEYWORDS) - set(grouped))} "
        f"extra={sorted(set(grouped) - set(KEYWORDS))}"
    )

    # Spelling variants: pairs the parser folds to one meaning.
    aliases = {
        "minimize": "minimise",
        "maximize": "maximise",
        "fn": "def",
    }

    cap(
        name="reserved keyword set (closed, no contextual keywords)",
        status="IMPLEMENTED",
        source_path=rel(SRC / "lexer" / "__init__.py"),
        symbol="KEYWORDS",
        confidence="high",
        test_file="tests/parser/test_parser.py",
        evidence=(
            "frozenset of 47 strings; the lexer classifies by set membership at "
            "TokenKind assignment time, so every keyword is reserved everywhere "
            "and none is contextual"
        ),
    )
    cap(
        name="'fn' as a distinct declaration form",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="Parser.parse_define",
        confidence="high",
        test_file=None,
        evidence=(
            "parse_statement dispatches t.is_kw('def','fn') to the same "
            "parse_define; the resulting DefineStmt records no discriminator, so "
            "'fn' is a pure spelling variant with no semantics of its own"
        ),
    )
    cap(
        name="Unicode input folding to ASCII canonical form",
        status="IMPLEMENTED",
        source_path=rel(SRC / "lexer" / "__init__.py"),
        symbol="UNICODE_FOLD / _UNICODE_OPS",
        confidence="high",
        test_file="tests/fuzz/test_frontend_robustness.py",
        evidence=(
            f"{len(UNICODE_FOLD)} identifier characters and {len(unicode_ops)} "
            "operators fold, each emitting HML-L102/HML-L103; any other non-ASCII "
            "character is HML-L101 error"
        ),
    )
    cap(
        name="string literals",
        status="ABSENT",
        source_path=rel(SRC / "lexer" / "__init__.py"),
        symbol="Lexer.run",
        confidence="high",
        evidence=(
            "no quote character is in _OPERATORS and no _string() routine exists; "
            "a double quote reaches the fallthrough and is reported HML-L101. "
            "HML has no string type and no string literal"
        ),
    )
    cap(
        name="comments",
        status="IMPLEMENTED",
        source_path=rel(SRC / "lexer" / "__init__.py"),
        symbol="Lexer.run ('#' branch)",
        confidence="high",
        evidence="line comments only, '#' to end of line; no block comment form",
    )

    return {
        "token_kinds": {
            "count": len(list(TokenKind)),
            "counting_rule": "members of lexer.TokenKind (a StrEnum)",
            "values": sorted(t.value for t in TokenKind),
        },
        "reserved_keywords": {
            "count": len(KEYWORDS),
            "counting_rule": (
                "distinct strings in lexer.KEYWORDS; every one is reserved in all "
                "positions (the lexer tags by set membership before the parser sees "
                "it), therefore CONTEXTUAL KEYWORDS = 0"
            ),
            "values": sorted(KEYWORDS),
            "by_group": {k: sorted(v) for k, v in sorted(groups.items())},
            "spelling_aliases_folded_to_one_meaning": aliases,
            "distinct_meanings_after_alias_folding": len(KEYWORDS) - len(aliases),
            "unreachable_from_parser": unreachable,
        },
        "contextual_keywords": {
            "count": 0,
            "counting_rule": (
                "a keyword usable as an identifier in some position. The lexer "
                "assigns TokenKind.KEYWORD unconditionally and Parser.expect_ident "
                "rejects any keyword with HML-P202, so the count is structurally zero"
            ),
            "values": [],
        },
        "operators": {
            "count": len(true_ops),
            "counting_rule": (
                "entries of lexer._OPERATORS that compute or relate, excluding pure "
                "delimiters and binding/annotation punctuation, which are counted "
                "separately"
            ),
            "values": sorted(true_ops),
            "arithmetic": ["*", "**", "+", "-", "/", "^", "@"],
            "relational": sorted(_COMPARISONS),
            "logical_symbolic": ["<=>", "=>"],
            "logical_worded": ["and", "iff", "implies", "not", "or"],
            "note": (
                "'**' and '^' are folded to a single BinOp op='^' by "
                "Parser.parse_power, so they are one operator with two spellings"
            ),
        },
        "binding_and_annotation_punctuation": {
            "count": len(binding),
            "counting_rule": "tokens that bind, annotate or condition rather than compute",
            "values": sorted(binding),
            "meanings": {
                ":": "type annotation",
                "::": "type annotation, non-canonical synonym (warns HML-P206)",
                ":=": "definition / role-label binding",
                "|": "conditioning bar in a law",
                "~": "distributed-as",
                "->": "function arrow inside Function[...]",
            },
        },
        "delimiters": {
            "count": len(delimiters),
            "counting_rule": "grouping and separation tokens with no denotation",
            "values": sorted(delimiters),
        },
        "literal_forms": {
            "count": 2,
            "counting_rule": (
                "syntactic categories Parser.parse_primary can turn into an "
                "ast.Literal node"
            ),
            "values": ["boolean (true/false)", "numeric (integer, decimal, exponent)"],
            "absent": ["string", "character", "complex", "array/list", "record/struct"],
        },
        "unicode_operator_normalisations": dict(sorted(unicode_ops.items())),
        "maximal_munch_operator_order": operators,
    }


# --------------------------------------------------------------------------
# 2. AST node inventory
# --------------------------------------------------------------------------


def extract_ast_nodes() -> dict:
    pf = PARSED[rel(SRC / "ast" / "nodes.py")]
    classes = {c.name: c for c in classes_in(pf)}

    def descends_from(name: str, root: str) -> bool:
        seen, cur = set(), name
        while cur in classes and cur not in seen:
            seen.add(cur)
            bases = base_names(classes[cur])
            if root in bases:
                return True
            cur = bases[0] if bases else ""
        return False

    exprs = sorted(n for n in classes if descends_from(n, "Expr") and n != "Expr")
    stmts = sorted(n for n in classes if descends_from(n, "Statement") and n != "Statement")
    support = sorted(
        n for n in classes if n not in exprs and n not in stmts
    )

    # Which modules mention each node class by name? A node no consumer names is
    # structurally dead. This is the DECLARED_BUT_UNENFORCED detector for the AST.
    mentions: dict[str, list[str]] = defaultdict(list)
    for path, p in PARSED.items():
        if path.endswith("ast/nodes.py"):
            continue
        names = {n.id for n in ast.walk(p.tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(p.tree) if isinstance(n, ast.Attribute)}
        for cls in classes:
            if cls in names:
                mentions[cls].append(path)

    consumers = {
        "parser": rel(SRC / "parser" / "__init__.py"),
        "resolver": rel(SRC / "semantics" / "__init__.py"),
        "type_checker": rel(SRC / "type_system" / "__init__.py"),
        "canonical": rel(SRC / "backends" / "canonical.py"),
        "graph": rel(SRC / "graph" / "__init__.py"),
        "hml_renderer": rel(SRC / "backends" / "hml.py"),
    }
    coverage: dict[str, dict[str, bool]] = {}
    for cls in sorted(exprs + stmts):
        coverage[cls] = {
            role: path in mentions.get(cls, []) for role, path in consumers.items()
        }

    unvisited = sorted(
        c for c, cov in coverage.items() if not cov["type_checker"]
    )

    cap(
        name="typed AST / frozen IR contract",
        status="IMPLEMENTED",
        source_path=rel(SRC / "ast" / "nodes.py"),
        symbol="Module / Statement / Expr hierarchy",
        confidence="high",
        test_file="tests/roundtrip/test_roundtrip.py",
        evidence=(
            f"{len(exprs)} expression classes and {len(stmts)} statement classes, "
            "every one reached by the parser and serialised by "
            "backends/canonical.py::_statement/_expr"
        ),
    )
    if unvisited:
        cap(
            name="AST node kinds the type checker never dispatches on",
            status="DECLARED_BUT_UNENFORCED",
            source_path=rel(SRC / "type_system" / "__init__.py"),
            symbol="TypeChecker.check_statement / _expr_type",
            confidence="high",
            evidence=f"no isinstance branch for: {', '.join(unvisited)}",
        )

    cap(
        name="Arg (role-labelled argument) as a first-class AST form",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "ast" / "nodes.py"),
        symbol="Arg",
        confidence="high",
        test_file="tests/parser/test_parser.py",
        evidence=(
            "Arg is not an Expr and is only legal inside DistExpr. "
            "Parser.parse_call builds a DistExpr from ANY labelled call, so a "
            "labelled call to a user function is silently reinterpreted as a "
            "distribution law. VERIFIED: with 'def f(x : Real) : Real := x + 1', "
            "the call 'f(x := 1.0)' is reported HML-T412 \"unknown distribution "
            "family 'f'\" and the correction suggests Beta/Bernoulli/Binomial. The "
            "diagnostic names the wrong category entirely, which is the failure "
            "mode the repair loop is least able to act on"
        ),
    )

    return {
        "expression_node_classes": {
            "count": len(exprs),
            "counting_rule": "classes in ast/nodes.py transitively deriving from Expr",
            "values": exprs,
        },
        "statement_node_classes": {
            "count": len(stmts),
            "counting_rule": "classes in ast/nodes.py transitively deriving from Statement",
            "values": stmts,
        },
        "support_classes": {
            "count": len(support),
            "counting_rule": "classes in ast/nodes.py deriving from neither Expr nor Statement",
            "values": support,
        },
        "total_node_kinds": {
            "count": len(exprs) + len(stmts),
            "counting_rule": (
                "expression classes + statement classes. Support classes (Span, "
                "SymbolId, Node, Arg, ConceptMember, Module, DeclKind) are excluded "
                "because they are not themselves nodes of the statement/expression "
                "grammar"
            ),
        },
        "consumer_coverage": coverage,
        "not_dispatched_by_type_checker": unvisited,
        "discriminated_subkinds": {
            "counting_rule": (
                "string-valued discriminator fields on a node class. These multiply "
                "the surface forms without adding node classes, which is why a node "
                "count understates the grammar"
            ),
            "Declaration.kind": sorted(_DECL_KEYWORDS.values()),
            "LawStmt.role": ["law", "likelihood", "prior"],
            "InferStmt.query": sorted(_INFER_QUERIES),
            "ObjectiveStmt.direction": ["maximise", "minimise"],
            "CheckStmt.check_kind": ["dimension", "proposition", "type"],
            "Quantifier.kind": ["exists", "exists_unique", "forall"],
            "ConceptMember.kind": sorted(_CONCEPT_MEMBER_KEYWORDS),
        },
    }


# --------------------------------------------------------------------------
# 3. Grammar: declaration / statement / expression forms
# --------------------------------------------------------------------------


def extract_grammar() -> dict:
    # Productions are counted as parse_* methods on Parser, which is the grammar as
    # implemented rather than the grammar as documented.
    par = PARSED[rel(SRC / "parser" / "__init__.py")]
    parser_cls = next(c for c in classes_in(par) if c.name == "Parser")
    productions = sorted(
        n.name
        for n in parser_cls.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith(("parse_", "_dim"))
    )

    statement_forms = [
        {"form": "module <Ident>", "node": "ModuleDecl", "keyword": "module"},
        {"form": "<declkind> <Ident> [: T] [= expr | := expr]", "node": "Declaration",
         "keyword": "var|param|const|obs|index|rv", "variants": 6},
        {"form": "def|fn <Ident> [(params)] [: T] := expr", "node": "DefineStmt",
         "keyword": "def|fn"},
        {"form": "law|prior|likelihood <Ident> [| refs] ~ Dist(...)", "node": "LawStmt",
         "keyword": "law|prior|likelihood", "variants": 3},
        {"form": "assume <prop>", "node": "AssumeStmt", "keyword": "assume"},
        {"form": "require <prop>", "node": "RequireStmt", "keyword": "require"},
        {"form": "prove <prop>", "node": "ProveStmt", "keyword": "prove"},
        {"form": "minimise|maximise <expr>", "node": "ObjectiveStmt",
         "keyword": "minimise|maximise", "variants": 2},
        {"form": "solve <refs>", "node": "SolveStmt", "keyword": "solve"},
        {"form": "infer <query> <refs>", "node": "InferStmt", "keyword": "infer",
         "variants": 5},
        {"form": "check [dimension] <expr> [= <dim>]", "node": "CheckStmt",
         "keyword": "check", "variants": 2},
        {"form": "concept <Ident> [extends ...] <members> end", "node": "ConceptDecl",
         "keyword": "concept"},
    ]

    expression_forms = [
        {"form": "numeric / boolean literal", "node": "Literal"},
        {"form": "name reference", "node": "Ref"},
        {"form": "a OP b  (+ - * / ^ @)", "node": "BinOp", "operators": 6},
        {"form": "-a | not a", "node": "UnaryOp", "operators": 2},
        {"form": "a REL b  (= != < <= > >=)", "node": "Comparison", "operators": 6},
        {"form": "a CONN b (and or implies iff)", "node": "LogicalOp", "operators": 4},
        {"form": "f(a, b)", "node": "Call"},
        {"form": "x[i] / m[i, j]", "node": "Index"},
        {"form": "Family(role := e, ...)", "node": "DistExpr"},
        {"form": "forall|exists [unique] x : T . body", "node": "Quantifier",
         "variants": 3},
        {"form": "( e )", "node": "-- grouping, no node; span is rewritten in place"},
    ]

    concept_member_forms = sorted(_CONCEPT_MEMBER_KEYWORDS)

    cap(
        name="one statement per line, no block structure except 'concept ... end'",
        status="IMPLEMENTED",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="Parser.end_line / parse_concept",
        confidence="high",
        test_file="tests/parser/test_parser.py",
        evidence=(
            "end_line() emits HML-P204 for any token after a statement; the only "
            "multi-line construct is concept...end. There is no block, no "
            "indentation sensitivity, no nesting of statements, and no line "
            "continuation character"
        ),
    )
    cap(
        name="chained comparison rejection",
        status="IMPLEMENTED",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="Parser.parse_comparison",
        confidence="high",
        test_file="tests/adversarial/test_rejections.py",
        evidence="HML-P230 on a second relational operator; 'a < b < c' is a parse error",
    )
    cap(
        name="bounded expression nesting",
        status="IMPLEMENTED",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="MAX_EXPR_DEPTH = 50",
        confidence="high",
        test_file="tests/fuzz/test_frontend_robustness.py",
        evidence="HML-P240 above depth 50, HML-P241 as a RecursionError backstop",
    )
    cap(
        name="concept 'extends' (inheritance)",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "semantics" / "__init__.py"),
        symbol="ConceptDecl.extends / Resolver.visit_concept",
        confidence="high",
        test_file="tests/semantics/test_scope.py",
        evidence=(
            "'extends' is checked for existence (HML-N305) and for cycles "
            "(HML-S602) and is preserved in the canonical form -- and does nothing "
            "else. Resolver.visit_concept pushes a scope containing only THIS "
            "concept's own members; a base's members are never looked up or "
            "copied. VERIFIED: 'concept A' declaring 'parameter scale' followed by "
            "'concept B extends A' whose invariant mentions 'scale' fails "
            "HML-N301 'scale is not bound'. Nor does extends create subtyping: "
            "types.is_subtype has no ConceptType branch at all, so B is not a "
            "subtype of A anywhere. The keyword names inheritance and implements "
            "neither half of it"
        ),
    )
    cap(
        name="concept members are referenceable / a concept is instantiable",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "semantics" / "__init__.py"),
        symbol="ConceptDecl / ConceptType",
        confidence="high",
        evidence=(
            "concept members live in a scope that is pushed and popped inside "
            "visit_concept, so nothing outside the concept can name them "
            "(VERIFIED: HML-N301). There is no member-access syntax -- '.' is the "
            "quantifier-body separator. 'param a : A' is accepted and gives 'a' the "
            "type ConceptType('A'), but no expression can construct a concept "
            "value, no invariant of A is ever checked against 'a', and ConceptType "
            "has no is_subtype rule. A concept is a namespace for obligations, not "
            "a type in the ordinary sense"
        ),
    )
    cap(
        name="module system (imports, namespaces, visibility)",
        status="ABSENT",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="ModuleDecl",
        confidence="high",
        evidence=(
            "'module X' sets Module.name and nothing else. There is no import "
            "keyword, no qualified name syntax ('.' is a quantifier-body separator "
            "only), no export list and no cross-file resolution: "
            "semantics.Resolver.run walks a single Module's statements. A program "
            "is exactly one file"
        ),
    )
    cap(
        name="user-defined functions",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="CallableSignature / TypeChecker._check_user_call",
        confidence="high",
        test_file="tests/type_system/test_call_signatures.py",
        evidence=(
            "def f(x : T, ...) : R := body gives a first-order, non-recursive, "
            "single-expression function. Arity and each argument are checked "
            "(HML-T471/T472). No closures, no higher-order values (a FunctionType "
            "cannot be constructed by any expression), no recursion (HML-S606 "
            "rejects it as a definition cycle), no local bindings, no branching"
        ),
    )
    cap(
        name="conditional / branching expression (if-then-else, case, piecewise)",
        status="ABSENT",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="Parser.parse_primary",
        confidence="high",
        evidence=(
            "no 'if', 'then', 'else', 'case', 'match' or 'where' keyword exists "
            "and parse_primary has no branch form. A piecewise-defined function "
            "is not expressible; the nearest encoding is 'implies' between "
            "propositions, which is not a value-level selection"
        ),
    )
    cap(
        name="let / local binding",
        status="ABSENT",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="Parser.parse_primary",
        confidence="high",
        evidence="no let form; every binder is a top-level statement, a def parameter, or a quantifier",
    )
    cap(
        name="sum / product over an index set (big-sigma notation)",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="TypeChecker._aggregate_type",
        confidence="high",
        test_file="tests/type_system/test_types.py",
        evidence=(
            "sum(v)/prod(v) reduce a WHOLE Vector/Matrix/Tensor. There is no "
            "binding form for an index range, so sum_{i=1}^{n} f(i) has no "
            "encoding: 'index' declares a symbol but no iteration construct "
            "consumes it"
        ),
    )
    cap(
        name="'index' declaration kind",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "ast" / "nodes.py"),
        symbol="DeclKind.INDEX",
        confidence="high",
        evidence=(
            "parsed into Declaration(kind='index') and stored on the Symbol, but no "
            "rule anywhere reads kind == 'index'. The checker and resolver special-"
            "case 'obs' and 'const' (HML-S607) and 'def', and never 'index'. "
            "VERIFIED: 'index i : Natural' and 'var i : Natural' are accepted "
            "identically and neither constrains i to an indexing position. The kind "
            "IS preserved in the canonical form, so the two hash differently -- the "
            "word changes the object's IDENTITY while imposing no rule on it, which "
            "is the worse of the two failures: a distinction that is recorded but "
            "never checked"
        ),
    )
    cap(
        name="'rv' declaration kind",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "ast" / "nodes.py"),
        symbol="DeclKind.RANDOM",
        confidence="high",
        evidence=(
            "no checker reads kind == 'rv'. Stochasticity is tracked by "
            "Symbol.stochastic, which is set by a LawStmt, not by the declaration "
            "kind. VERIFIED: 'rv x : Real' with no law is accepted exactly as "
            "'var x : Real' is -- declaring something a random variable and never "
            "giving it a law is not an error -- and conversely 'var x : Real' with "
            "a law becomes fully stochastic. The keyword that names the central "
            "object of a probabilistic language constrains nothing"
        ),
    )

    return {
        "parser_productions": {
            "count": len(productions),
            "counting_rule": (
                "methods named parse_* or _dim* on parser.Parser -- the grammar as "
                "implemented. There is no separate .ebnf/.lark file consumed at "
                "runtime; spec/grammars/ is documentation"
            ),
            "values": productions,
        },
        "declaration_forms": {
            "count": 6,
            "counting_rule": (
                "keys of parser._DECL_KEYWORDS -- keywords that introduce a "
                "Declaration node. 'def'/'fn' produce DefineStmt and 'concept' "
                "produces ConceptDecl, so they are counted as statement forms, not "
                "declaration forms"
            ),
            "values": sorted(_DECL_KEYWORDS),
            "wider_reading": {
                "count": 8,
                "counting_rule": "any statement that introduces a new name binding",
                "values": sorted([*_DECL_KEYWORDS, "def", "concept"]),
            },
        },
        "statement_forms": {
            "count": len(statement_forms),
            "counting_rule": (
                "distinct leading keywords accepted by Parser.parse_statement, "
                "collapsing spelling aliases and discriminator variants"
            ),
            "values": statement_forms,
            "expanded_by_discriminator": {
                "count": sum(f.get("variants", 1) for f in statement_forms),
                "counting_rule": (
                    "each discriminator value counted separately (var/param/const/"
                    "obs/index/rv as 6, law/prior/likelihood as 3, the 5 infer "
                    "queries, 2 objective directions, 2 check kinds)"
                ),
            },
        },
        "expression_forms": {
            "count": len(expression_forms),
            "counting_rule": (
                "distinct syntactic productions Parser can build in expression "
                "position, including parenthesised grouping which produces no node"
            ),
            "values": expression_forms,
            "by_ast_node": {
                "count": len(expression_forms) - 1,
                "counting_rule": "expression forms that produce a distinct AST class",
            },
        },
        "concept_member_forms": {
            "count": len(concept_member_forms),
            "counting_rule": "keys of parser._CONCEPT_MEMBER_KEYWORDS",
            "values": concept_member_forms,
        },
        "precedence_levels": {
            "count": 9,
            "counting_rule": (
                "chained parse_* expression methods from parse_implication down to "
                "parse_primary"
            ),
            "values": [
                "implication (=> <=> implies iff, right-assoc)",
                "disjunction (or, left-assoc)",
                "conjunction (and, left-assoc)",
                "negation (not, prefix)",
                "comparison (= != < <= > >=, non-associative -- chaining is HML-P230)",
                "additive (+ -, left-assoc)",
                "multiplicative (* / @, left-assoc)",
                "unary minus (prefix)",
                "power (^ **, right-assoc) then postfix index then primary",
            ],
        },
    }


# --------------------------------------------------------------------------
# 4. Type system
# --------------------------------------------------------------------------


def extract_types() -> dict:
    pf = PARSED[rel(SRC / "types.py")]
    ctors = sorted(
        c.name
        for c in classes_in(pf)
        if "Type" in base_names(c) and c.name != "Type"
    )

    parents: dict[str, tuple[str, ...]] = hml_types._SCALAR_PARENTS
    edges = sorted(
        ({"sub": k, "sup": p} for k, ps in parents.items() for p in ps),
        key=lambda d: (d["sub"], d["sup"]),
    )

    # Transitive closure, so incomparability is a computed fact rather than a claim.
    def ancestors(n: str) -> set[str]:
        return hml_types._scalar_ancestors(n)

    scalars = sorted(hml_types.SCALARS)
    incomparable = sorted(
        [a, b]
        for i, a in enumerate(scalars)
        for b in scalars[i + 1 :]
        if b not in ancestors(a) and a not in ancestors(b)
    )

    # Which constructors does the type checker actually have a rule for?
    tc = PARSED[rel(SRC / "type_system" / "__init__.py")]
    tc_names = {n.id for n in ast.walk(tc.tree) if isinstance(n, ast.Name)}
    unruled = sorted(c for c in ctors if c not in tc_names)

    cap(
        name="scalar refinement partial order (not a chain)",
        status="IMPLEMENTED",
        source_path=rel(SRC / "types.py"),
        symbol="_SCALAR_PARENTS / is_subtype / join / meet",
        confidence="high",
        test_file="tests/type_system/test_types.py",
        evidence=(
            f"{len(scalars)} scalars, {len(edges)} immediate-parent edges, "
            f"{len(incomparable)} incomparable unordered pairs computed by "
            "transitive closure"
        ),
    )
    cap(
        name="prohibited conflation: Distribution[T] vs RandomVariable[T] vs T",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "types.py"),
        symbol="DistributionType / RandomVariableType",
        confidence="high",
        test_file="tests/type_system/test_types.py",
        evidence=(
            "is_subtype has no cross-constructor branch between the three, so no "
            "subtyping PATH exists. The Distribution-vs-value half is actively "
            "enforced: HML-T410 (law on a Distribution), HML-T428 (comparing a "
            "law), HML-T430 (arithmetic on a law). The RandomVariable-vs-value half "
            "is NOT: check_law unwraps a RandomVariableType but accepts a bare "
            "value type unchanged, so nothing ever obliges a program to write "
            "RandomVariable[T], and a symbol carrying a law behaves as an ordinary "
            "value in every expression. See the separate '~ requires "
            "RandomVariable[T] on the left' entry"
        ),
    )
    cap(
        name="prohibited conflation: Probability / PValue / PosteriorProbability",
        status="IMPLEMENTED",
        source_path=rel(SRC / "types.py"),
        symbol="UNIT_INTERVAL_KINDS / _UNIT_INTERVAL_CONFLATIONS",
        confidence="high",
        test_file="tests/type_system/test_pvalue.py",
        evidence=(
            "all three have NonNegativeReal as sole parent, so all three pairs are "
            "pairwise incomparable; all 6 ordered pairs carry a named explanation "
            "surfaced through type_system._conflation_note, and "
            "TypeChecker._repair_hint suppresses the generic 'declare x : T' hint "
            "for exactly these pairs so a repair loop is not advised to commit the "
            "prosecutor's fallacy"
        ),
    )
    cap(
        name="'~' requires RandomVariable[T] on the left",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="TypeChecker.check_law",
        confidence="high",
        test_file="tests/type_system/test_types.py",
        evidence=(
            "docs/design/V0_DESIGN_FREEZE.md section 4 states: '~ requires "
            "Distribution[T] on the right and RandomVariable[T] on the left'. The "
            "right-hand requirement is real. The left-hand one is not: check_law "
            "computes 'codomain = target_type.codomain if isinstance(target_type, "
            "RandomVariableType) else target_type', i.e. a bare value type is "
            "accepted unwrapped. VERIFIED: 'var y : Real' then 'law y ~ "
            "Normal(...)' compiles clean, and afterwards 'y + c' with c : Real is "
            "also clean -- so a quantity that has a probability law is still an "
            "ordinary number for every other purpose. Only 1 of the 8 compiled "
            "examples writes RandomVariable[...] at all. The T-vs-RandomVariable[T] "
            "half of the prohibited conflation is documented, not enforced; the "
            "Distribution[T] half IS enforced (HML-T410/T428/T430)"
        ),
    )
    cap(
        name="prohibited conflation: '=' vs '~' vs ':='",
        status="IMPLEMENTED",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="Parser.parse_law / parse_define",
        confidence="high",
        test_file="tests/adversarial/test_rejections.py",
        evidence=(
            "syntactically separated: '~' is legal only in a law (HML-P208 "
            "otherwise), ':=' is required for a definition (HML-P207), '=' builds "
            "a Comparison whose type is Proposition. The separation is at the "
            "grammar, so no conflating program is representable"
        ),
    )
    cap(
        name="prohibited conflation: '=>' is not correlation/causation",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="TypeChecker._expr_type (LogicalOp branch)",
        confidence="high",
        test_file="tests/adversarial/test_rejections.py",
        evidence=(
            "HML-T421 forces both operands of '=>' to be truth-valued, which stops "
            "'x => y' on numbers. But HML has no correlation and no causation "
            "construct at all, so there is nothing for implication to be confused "
            "WITH inside the language -- the conflation is prevented by absence, "
            "not by discrimination"
        ),
    )
    cap(
        name="SetType",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "types.py"),
        symbol="SetType",
        confidence="high",
        evidence=(
            "Set[T] parses (parser.parse_type) and has a covariant is_subtype rule, "
            "but no expression can construct, index, test membership in, or "
            "otherwise consume a Set. TypeChecker._expr_type has no SetType branch. "
            "VERIFIED: 's + 1' on a Set[Real] is rejected as HML-T431 \"'+' is not "
            "defined for these operand types\" -- the generic fallthrough, not a "
            "set-aware rule. There is no set literal, no 'in' operator, no "
            "cardinality, no comprehension, and quantifiers range over a TYPE, not "
            "over a set. A declared Set is inert"
        ),
    )
    cap(
        name="PredicateType",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "types.py"),
        symbol="PredicateType",
        confidence="high",
        evidence=(
            "Predicate[T, ...] parses and _validate_type recurses into its domain, "
            "but is_subtype has NO PredicateType branch (so it is comparable only "
            "by dataclass equality) and _call_type never consults it. VERIFIED: "
            "'param p : Predicate[Real]' then 'require p(1.0)' is rejected "
            "HML-T470 \"'p' is not callable\" -- the one thing a predicate is for "
            "is the one thing the checker refuses"
        ),
    )
    cap(
        name="TensorType",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "types.py"),
        symbol="TensorType",
        confidence="high",
        evidence=(
            "is_subtype has no TensorType branch (identity only, so Tensor[Real,3] "
            "is not a subtype of Tensor[Real,?]); Index returns the element with "
            "NO rank check, unlike Vector (HML-T424) and Matrix; '@' rejects it; "
            "arithmetic _elementwise handles only Vector and Matrix"
        ),
    )
    cap(
        name="FunctionType as a value type",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "types.py"),
        symbol="FunctionType",
        confidence="high",
        evidence=(
            "has a correct variance rule in is_subtype (contravariant domain, "
            "covariant codomain) and can be written as an annotation, but no "
            "expression produces a FunctionType value -- there is no lambda and a "
            "bare 'f' reference to a def yields its codomain, not an arrow. The "
            "variance rule is unreachable from any .hml program"
        ),
    )
    cap(
        name="dimensional analysis with exact rational exponents",
        status="IMPLEMENTED",
        source_path=rel(SRC / "types.py"),
        symbol="Dimension",
        confidence="high",
        test_file="tests/type_system/test_dimension_grammar.py",
        evidence=(
            f"{len(hml_types.BASE_DIMENSIONS)} SI base dimensions, Fraction "
            "exponents, canonical mapping with zeros elided so structural equality "
            "is dimensional equality; enforced at + - (HML-D502), comparison "
            "(HML-D502), ^ (HML-D505) and 'check dimension' (HML-D503/D504)"
        ),
    )
    cap(
        name="dimension variables / dimensional polymorphism",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "types.py"),
        symbol="Dimension.unify",
        confidence="high",
        test_file="tests/type_system/test_dimension_grammar.py",
        evidence=(
            "a single capital letter is a dimension variable; Dimension.unify "
            "solves ONLY the single-free-variable case and returns None otherwise, "
            "stated in its own docstring. Two unknown dimensions in one expression "
            "cannot be related"
        ),
    )
    cap(
        name="units (as opposed to dimensions)",
        status="ABSENT",
        source_path=rel(SRC / "types.py"),
        symbol="Dimension / QuantityType",
        confidence="high",
        evidence=(
            "the machinery is purely DIMENSIONAL. There is no unit, no metre vs "
            "foot, no prefix, and no conversion factor anywhere in types.py or the "
            "checker. Quantity[Length] cannot distinguish metres from miles, so "
            "the Mars Climate Orbiter class of error -- the canonical motivating "
            "example for unit systems -- is NOT caught"
        ),
    )
    cap(
        name="generic / parametric polymorphism over ordinary types",
        status="ABSENT",
        source_path=rel(SRC / "types.py"),
        symbol="-- no TypeVar equivalent",
        confidence="high",
        evidence=(
            "no type variable exists outside the single-capital DIMENSION "
            "variable. def cannot be polymorphic in its element type; "
            "shape-polymorphism exists only for the 6 hard-coded builtins in "
            "_aggregate_type"
        ),
    )
    cap(
        name="type inference beyond literals and operators",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="TypeChecker.synthesise / check",
        confidence="high",
        test_file="tests/type_system/test_contextual_positions.py",
        evidence=(
            "the checker's own docstring table (asserted mechanically by "
            "tests/type_system/test_contextual_positions.py) records 5 of 12 "
            "expression-bearing positions as contextually checked; the other 7 "
            "impose a predicate, not a type expectation. Declaration without an "
            "annotation is HML-T401, so there is no let-polymorphic inference"
        ),
    )

    return {
        "type_constructors": {
            "count": len(ctors),
            "counting_rule": (
                "classes in types.py declaring Type as a base. ScalarType counts as "
                f"ONE constructor; its {len(scalars)} inhabitants are enumerated "
                "separately as scalar type names, because they are values of a "
                "name field, not distinct classes"
            ),
            "values": ctors,
            "no_rule_in_type_checker": unruled,
        },
        "scalar_types": {
            "count": len(scalars),
            "counting_rule": "keys of types._SCALAR_PARENTS",
            "values": scalars,
            "roots": sorted(k for k, v in parents.items() if not v),
        },
        "subtyping_edges": {
            "count": len(edges),
            "counting_rule": (
                "immediate-parent edges declared in _SCALAR_PARENTS. Structural "
                "constructor rules in is_subtype (Vector, Matrix, Set, "
                "RandomVariable, Distribution, Function, Quantity<->Scalar) are "
                "counted separately as constructor rules, not as lattice edges"
            ),
            "values": edges,
            "constructor_subtyping_rules": {
                "count": 8,
                "counting_rule": "isinstance-guarded branches inside types.is_subtype",
                "values": [
                    "ScalarType <= ScalarType (refinement ancestors)",
                    "QuantityType <= QuantityType (equal dimension + base subtype)",
                    "QuantityType <-> ScalarType (only when dimensionless)",
                    "VectorType (covariant element, compatible extent)",
                    "MatrixType (covariant element, compatible extents)",
                    "SetType (covariant element)",
                    "RandomVariableType (covariant codomain)",
                    "DistributionType (covariant support)",
                    "FunctionType (contravariant domain, covariant codomain)",
                ],
                "constructors_with_NO_rule": ["PredicateType", "TensorType", "ConceptType"],
            },
        },
        "incomparable_scalar_pairs": {
            "count": len(incomparable),
            "counting_rule": (
                "unordered pairs {a,b} of scalar names where neither is in the "
                "other's transitive ancestor set -- computed, not asserted"
            ),
            "values": incomparable,
        },
        "unit_interval_kinds": sorted(hml_types.UNIT_INTERVAL_KINDS),
        "base_dimensions": {
            "count": len(hml_types.BASE_DIMENSIONS),
            "counting_rule": "entries of types.BASE_DIMENSIONS",
            "values": list(hml_types.BASE_DIMENSIONS),
        },
        "prohibited_conflations": {
            "count": 5,
            "counting_rule": (
                "the conflations CLAUDE.md names as enforced by the type system. "
                "Each is scored separately as a capability above"
            ),
            "values": [
                "Distribution[T] is not a value of T",
                "RandomVariable[T] is neither Distribution[T] nor T",
                "'=' is not '~' and is not approximation",
                "'=>' is not correlation and is not causation",
                "Probability is not PositiveReal (they meet at NonNegativeReal)",
            ],
            "additionally_enforced_not_in_CLAUDE_md": [
                "PValue / PosteriorProbability / Probability are pairwise incomparable (D-022)",
            ],
        },
    }


# --------------------------------------------------------------------------
# 5. Diagnostics
# --------------------------------------------------------------------------

CODE_RE = re.compile(r'"(HML-[A-Z]+\d+)"')

FAMILY_MEANING = {
    "L": ("lexical", "documented in diagnostics/__init__.py"),
    "P": ("parse", "documented in diagnostics/__init__.py"),
    "N": ("name resolution / scope", "documented in diagnostics/__init__.py"),
    "T": ("type", "documented in diagnostics/__init__.py"),
    "D": ("dimensional", "documented in diagnostics/__init__.py"),
    "S": ("semantic / structural", "documented in diagnostics/__init__.py"),
    "B": ("backend", "documented in diagnostics/__init__.py"),
    "X": ("v1 transformation edge", "NOT documented in diagnostics/__init__.py"),
    "E": ("v1 epistemic status", "NOT documented in diagnostics/__init__.py"),
    "G": ("v1 discourse state", "NOT documented in diagnostics/__init__.py"),
}

# Which files does compile_source() actually reach? Anything outside this set emits
# codes that `hml check` can never produce.
COMPILER_PIPELINE = {
    "src/hamiltonian_lang/__init__.py",
    "src/hamiltonian_lang/lexer/__init__.py",
    "src/hamiltonian_lang/parser/__init__.py",
    "src/hamiltonian_lang/semantics/__init__.py",
    "src/hamiltonian_lang/type_system/__init__.py",
    "src/hamiltonian_lang/type_system/distributions.py",
    "src/hamiltonian_lang/diagnostics/__init__.py",
    "src/hamiltonian_lang/types.py",
    "src/hamiltonian_lang/ast/nodes.py",
    "src/hamiltonian_lang/backends/hml.py",
}


def extract_diagnostics() -> dict:
    # Emitters do not share one call shape: the compiler uses
    # ``diags.error("HML-T401", ...)``, the bidirectional checker threads the code
    # through a KEYWORD argument ``code="HML-T402"``, and v1 wraps it in a
    # dataclass (``EpistemicViolation("HML-E701", ...)``) or a local ``fail(...)``.
    # Whitelisting method names missed two of the three shapes, so the rule is
    # instead: every string literal under src/ that matches the code pattern.
    sites: dict[str, set[str]] = defaultdict(set)
    severity: dict[str, set[str]] = defaultdict(set)
    code_pat = re.compile(r"^HML-[A-Z]+\d+$")

    for path, pf in PARSED.items():
        for node in ast.walk(pf.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if code_pat.match(node.value):
                    sites[node.value].add(path)
        # Severity is only knowable where the emitter names it.
        for node in ast.walk(pf.tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            attr = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if attr not in {"error", "warn"}:
                continue
            for a in [*node.args, *(k.value for k in node.keywords)]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    if code_pat.match(a.value):
                        severity[a.value].add("warning" if attr == "warn" else "error")

    sites = {k: sorted(v) for k, v in sites.items()}
    declared_never_emitted: list[str] = []

    by_family: dict[str, list[str]] = defaultdict(list)
    for code in sites:
        by_family[re.match(r"HML-([A-Z]+)", code).group(1)].append(code)

    reachable, unreachable = [], []
    for code, paths in sites.items():
        (reachable if any(p in COMPILER_PIPELINE for p in paths) else unreachable).append(code)

    families = {
        fam: {
            "count": len(codes),
            "meaning": FAMILY_MEANING.get(fam, ("unknown", "undocumented"))[0],
            "documentation": FAMILY_MEANING.get(fam, ("unknown", "undocumented"))[1],
            "reachable_from_compile_source": sorted(c for c in codes if c in reachable),
            "not_reachable_from_compile_source": sorted(
                c for c in codes if c in unreachable
            ),
            "codes": {
                c: {
                    "severity": sorted(severity[c]) or ["unstated at the literal site"],
                    "emitted_from": sorted(sites[c]),
                }
                for c in sorted(codes)
            },
        }
        for fam, codes in sorted(by_family.items())
    }

    cap(
        name="structured diagnostics (code, expected, found, correction, notes)",
        status="IMPLEMENTED",
        source_path=rel(SRC / "diagnostics" / "__init__.py"),
        symbol="Diagnostic / DiagnosticBag",
        confidence="high",
        test_file="tests/evaluation/test_diagnostics_budget.py",
        evidence=(
            f"{len(sites)} distinct codes emitted from src/; every Diagnostic "
            "carries optional expected/found/correction/notes and renders a "
            "source-line caret"
        ),
    )
    cap(
        name="diagnostic families X / E / G reachable from `hml check`",
        status="ABSENT",
        source_path=rel(SRC / "v1"),
        symbol="HML-X6xx / HML-E7xx / HML-G8xx",
        layer="LIBRARY",
        confidence="high",
        evidence=(
            "these are raised only by v1/transformation.py, v1/epistemic_checks.py, "
            "v1/discourse.py and context_broker/index.py. "
            "hamiltonian_lang.compile_source calls parse -> resolve -> check and "
            "nothing else, so no .hml source can ever produce one. They are also "
            "absent from the code-range table in diagnostics/__init__.py"
        ),
    )
    if declared_never_emitted:
        cap(
            name="diagnostic codes named in source but never emitted",
            status="DECLARED_BUT_UNENFORCED",
            source_path="src/hamiltonian_lang/",
            symbol=", ".join(declared_never_emitted),
            confidence="medium",
            evidence="string literal present but no .error()/.warn() call site",
        )

    return {
        "total_distinct_codes_emitted": {
            "count": len(sites),
            "counting_rule": (
                "distinct string literals under src/hamiltonian_lang matching "
                "^HML-[A-Z]+[0-9]+$, found by AST constant-walk. Literal position "
                "rather than call shape is the rule because the three emitters in "
                "this codebase use three different shapes (positional argument, "
                "code= keyword, dataclass constructor). Codes appearing only in "
                "tests/ or in prose are NOT counted"
            ),
        },
        "families": {
            "count": len(families),
            "counting_rule": "distinct alphabetic prefixes of emitted codes",
            "documented_in_diagnostics_module": 7,
            "undocumented": sorted(
                f for f in families if "NOT documented" in FAMILY_MEANING.get(f, ("", ""))[1]
            ),
        },
        "reachable_from_compile_source": {
            "count": len(reachable),
            "counting_rule": (
                "codes with at least one emission site inside the lex->parse->"
                "resolve->check pipeline that hamiltonian_lang.compile_source "
                "actually calls"
            ),
        },
        "not_reachable_from_compile_source": {
            "count": len(unreachable),
            "values": sorted(unreachable),
        },
        "declared_but_never_emitted": declared_never_emitted,
        "by_family": families,
    }


# --------------------------------------------------------------------------
# 6. Probability
# --------------------------------------------------------------------------


def extract_probability() -> dict:
    fams = {
        name: {
            "roles": {r: t.render() for r, t in sorted(spec.roles.items())},
            "optional_roles": sorted(spec.optional_roles),
            "support": spec.support.render(),
            "support_depends_on_args": spec.support_from_args is not None,
            "cross_constraints": [list(c) for c in spec.cross_constraints],
            "note": spec.note,
        }
        for name, spec in sorted(DISTRIBUTIONS.items())
    }
    with_cross = sorted(n for n, s in DISTRIBUTIONS.items() if s.cross_constraints)

    cap(
        name="mandatory role-labelled distribution parameters",
        status="IMPLEMENTED",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="Parser.parse_dist_expr",
        confidence="high",
        test_file="tests/parser/test_parser.py",
        evidence=(
            "HML-P234 rejects any positional argument in a law; HML-P235 rejects a "
            "duplicated role; HML-T414 reports missing required roles; HML-T415/416 "
            "report unknown roles. Argument ORDER is erased in the canonical form "
            "(backends/canonical.py sorts DistExpr args by role), so role, not "
            "position, carries identity"
        ),
    )
    cap(
        name="named misparameterisation diagnostics (scale vs variance etc.)",
        status="IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "distributions.py"),
        symbol="MISPARAMETERISATIONS",
        confidence="high",
        test_file="tests/adversarial/test_rejections.py",
        evidence=(
            f"{len(MISPARAMETERISATIONS)} wrong-but-common role names mapped to an "
            "explanation and a canonical role, surfaced as HML-T415. The module "
            "docstring explicitly withdraws any claim that this helps: whether it "
            "does is unmeasured hypothesis H5/H3"
        ),
    )
    cap(
        name="cross-role constraint checking",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="TypeChecker._check_cross_role_constraints",
        confidence="high",
        evidence=(
            f"only {len(with_cross)} of {len(DISTRIBUTIONS)} families declares any "
            f"cross-role constraint ({', '.join(with_cross)}). Decided only when "
            "BOTH sides are literals; otherwise deferred to a proof obligation. "
            "Beta(alpha:=a, beta:=b) has no declared relation, Binomial has no "
            "trials>=0 relation beyond the Natural type"
        ),
    )
    cap(
        name="conditioning / conditional probability",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "semantics" / "__init__.py"),
        symbol="LawStmt.given",
        confidence="high",
        test_file="tests/semantics/test_scope.py",
        evidence=(
            "'law y | x ~ D' records the conditioning set and resolves each name, "
            "and the graph emits a conditioned_on edge. But nothing checks the "
            "conditioning is well founded: there is no P(x) > 0 obligation, no "
            "check that the conditioner is stochastic, no d-separation, no check "
            "that the distribution arguments mention the conditioners. VERIFIED: "
            "'const z : Real = 3.0' then 'law y | z ~ Normal(location := 0.0, "
            "scale := 1.0)' -- conditioning on a non-random constant that the law "
            "does not mention -- compiles clean. Conditioning is recorded, never "
            "validated"
        ),
    )
    cap(
        name="one law per symbol",
        status="IMPLEMENTED",
        source_path=rel(SRC / "semantics" / "__init__.py"),
        symbol="Resolver.visit_statement (LawStmt branch)",
        confidence="high",
        test_file="tests/adversarial/test_rejections.py",
        evidence="HML-S601 on a second law for the same target",
    )
    cap(
        name="inference-query well-posedness",
        status="IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="TypeChecker._query_is_well_posed",
        confidence="high",
        test_file="tests/adversarial/test_rejections.py",
        evidence=(
            "HML-S604; posterior/map require a law on the target, expectation/"
            "variance require a law, mle requires the target to appear in some "
            "likelihood's conditioning set (D-020)"
        ),
    )
    cap(
        name="prior on observed data / on a constant is rejected",
        status="IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="TypeChecker.check_law",
        confidence="high",
        test_file="tests/adversarial/test_rejections.py",
        evidence="HML-S607 for role=='prior' on kind in {obs, const} and likelihood on const",
    )
    cap(
        name="independence / exchangeability / i.i.d. declaration",
        status="ABSENT",
        source_path=rel(SRC / "ast" / "nodes.py"),
        symbol="-- no node",
        confidence="high",
        evidence=(
            "no keyword, node or type expresses independence. NormalVector's note "
            "says 'an i.i.d. vector of normals' in PROSE only; nothing in the type "
            "system represents the i.i.d. assumption or lets a model state one"
        ),
    )
    cap(
        name="user-defined distribution family",
        status="ABSENT",
        source_path=rel(SRC / "type_system" / "distributions.py"),
        symbol="DISTRIBUTIONS",
        confidence="high",
        evidence=(
            "DISTRIBUTIONS is a module-level dict literal with no registration "
            "hook, no plugin entry point and no .hml syntax. Adding a family "
            "requires editing the compiler. A user cannot even mix two: there is "
            "no mixture, truncation, transformation or censoring combinator"
        ),
    )
    cap(
        name="distribution family / value namespace collision check",
        status="IMPLEMENTED",
        source_path=rel(SRC / "semantics" / "__init__.py"),
        symbol="Resolver._check_family_collision",
        confidence="high",
        evidence="HML-N307; a symbol may not be spelled like a distribution family",
    )

    return {
        "distribution_families": {
            "count": len(DISTRIBUTIONS),
            "counting_rule": "keys of type_system.distributions.DISTRIBUTIONS",
            "values": sorted(DISTRIBUTIONS),
            "detail": fams,
            "families_with_cross_role_constraints": with_cross,
            "extensibility": "compiler edit required; no registration API, no .hml syntax",
        },
        "misparameterisation_table": {
            "count": len(MISPARAMETERISATIONS),
            "counting_rule": "keys of distributions.MISPARAMETERISATIONS",
            "values": {
                k: {"family": v[0], "canonical_role": v[2], "explanation": v[1]}
                for k, v in sorted(MISPARAMETERISATIONS.items())
            },
        },
        "distinct_roles": {
            "count": len({r for s in DISTRIBUTIONS.values() for r in s.roles}),
            "counting_rule": "union of role names over all families",
            "values": sorted({r for s in DISTRIBUTIONS.values() for r in s.roles}),
        },
        "law_roles": {
            "count": 3,
            "counting_rule": "accepted values of LawStmt.role",
            "values": ["law", "likelihood", "prior"],
        },
        "inference_queries": {
            "count": len(_INFER_QUERIES),
            "counting_rule": "parser._INFER_QUERIES",
            "values": sorted(_INFER_QUERIES),
            "note": (
                "these are DECLARATIONS of intent. No inference is performed by the "
                "compiler; InferStmt only type-checks its targets and asserts well-"
                "posedness. Actual sampling requires the Stan backend and an "
                "external Stan install"
            ),
        },
    }


# --------------------------------------------------------------------------
# 7. Definedness / partiality
# --------------------------------------------------------------------------


def extract_partiality() -> dict:
    ops = {
        "log": {
            "handled": True,
            "mechanism": "_BUILTIN_SIGNATURES['log'] domain is PositiveReal",
            "diagnostic": "HML-T427",
            "status": "IMPLEMENTED",
            "gap": (
                "guards the TYPE only. log(x) where x : PositiveReal is accepted "
                "with no obligation; log(x - y) with both PositiveReal has type "
                "Real (subtraction widens) and is then rejected -- correct here, "
                "but by accident of the widening table rather than by a "
                "definedness rule"
            ),
        },
        "sqrt": {
            "handled": True,
            "mechanism": "_BUILTIN_SIGNATURES['sqrt'] domain is NonNegativeReal",
            "diagnostic": "HML-T427",
            "status": "IMPLEMENTED",
            "gap": "same type-only guarantee as log",
        },
        "division": {
            "handled": False,
            "mechanism": (
                "TypeChecker._binop_type '/' branch does dimensional algebra and "
                "joins the bases. It never inspects the denominator"
            ),
            "diagnostic": None,
            "status": "ABSENT",
            "gap": (
                "VERIFIED: 'def q := a / 0' type-checks clean with zero "
                "diagnostics, and no proof obligation is emitted. The checker "
                "emits obligations for PositiveReal/Probability/NonNegativeReal "
                "bindings and for require/assume/prove, but there is no "
                "division-definedness obligation anywhere in _obligate's call sites"
            ),
        },
        "matrix_inverse": {
            "handled": False,
            "mechanism": "no inverse operator or builtin exists",
            "diagnostic": None,
            "status": "ABSENT",
            "gap": (
                "_BUILTIN_FUNCTIONS has transpose but no inv/det/solve. "
                "Invertibility cannot arise because inversion cannot be written"
            ),
        },
        "conditional_probability": {
            "handled": False,
            "mechanism": "LawStmt.given is resolved but never constrained",
            "diagnostic": None,
            "status": "ABSENT",
            "gap": "no P(condition) > 0 obligation is generated for any law",
        },
        "vector_matrix_indexing": {
            "handled": "partially",
            "mechanism": "index must be Integer (HML-T423); index COUNT is checked",
            "diagnostic": "HML-T423 / HML-T424",
            "status": "PARTIALLY_IMPLEMENTED",
            "gap": (
                "index BOUNDS are never checked and no bounds obligation is "
                "emitted, even when both the extent and the index are literals. "
                "VERIFIED: 'param v : Vector[Real, 3]' then 'v[99]' type-checks "
                "clean. VERIFIED: 'param t : Tensor[Real, 2, 2, 2]' then 't[0]' -- "
                "one index for a rank-3 tensor -- also type-checks clean, because "
                "the TensorType branch returns the element with no rank check at "
                "all, unlike Vector and Matrix which do get HML-T424"
            ),
        },
        "power_with_symbolic_exponent": {
            "handled": True,
            "mechanism": "_power_type refuses a non-literal exponent on a dimensional base",
            "diagnostic": "HML-D505",
            "status": "IMPLEMENTED",
            "gap": "dimensionless bases are unrestricted, so 0 ^ -1 is accepted",
        },
        "tan_at_pi_over_2": {
            "handled": False,
            "mechanism": "tan : Real -> Real, total by declaration",
            "diagnostic": None,
            "status": "ABSENT",
            "gap": "tan is declared total; its poles are not represented",
        },
    }

    cap(
        name="partial-operation definedness handling",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="_BUILTIN_SIGNATURES / _binop_type",
        confidence="high",
        test_file="tests/evaluation/test_partiality_scanner.py",
        evidence=(
            "3 of 8 surveyed partial operations are guarded (log, sqrt, dimensional "
            "power) and all 3 are guarded by a TYPE DOMAIN rather than by a "
            "definedness obligation. Division by zero, index bounds, matrix "
            "invertibility and conditioning on a null event are all unguarded and "
            "generate no obligation"
        ),
    )

    return {
        "surveyed_operations": {
            "count": len(ops),
            "counting_rule": (
                "partial mathematical operations reachable in HML expression "
                "position, surveyed by hand against the checker source and each "
                "verified by locating (or failing to locate) a guard"
            ),
            "guarded": sorted(k for k, v in ops.items() if v["status"] == "IMPLEMENTED"),
            "unguarded": sorted(k for k, v in ops.items() if v["status"] == "ABSENT"),
            "detail": ops,
        },
        "obligation_kinds_emitted_by_the_checker": {
            "count": 5,
            "counting_rule": "distinct first arguments to TypeChecker._obligate",
            "values": [
                "assumption", "constraint", "dimension", "parameter_positivity",
                "theorem",
            ],
            "note": (
                "'dimension' is the only kind the checker itself ever marks "
                "discharged_by; every other obligation leaves the checker "
                "undischarged"
            ),
        },
    }


# --------------------------------------------------------------------------
# 8. Compiler phases, canonicalisation, identity
# --------------------------------------------------------------------------


def extract_pipeline() -> dict:
    cap(
        name="content-addressed semantic identity (alpha-invariant hash)",
        status="IMPLEMENTED",
        source_path=rel(SRC / "backends" / "canonical.py"),
        symbol="content_hash / SymbolId.canonical",
        confidence="high",
        test_file="tests/adversarial/test_alpha_equivalence.py",
        evidence=(
            "SHA-256 over the nameless canonical JSON: binder names replaced by "
            "'sym:#depth.ordinal', keys sorted, spans dropped, DistExpr args sorted "
            "by role, def parameter names erased. Quantifier nesting order IS "
            "preserved, so forall-exists and exists-forall hash differently"
        ),
    )
    cap(
        name="thread-safe canonicalisation",
        status="IMPLEMENTED",
        source_path=rel(SRC / "backends" / "canonical.py"),
        symbol="_INCLUDE_NAMES (ContextVar)",
        confidence="high",
        test_file="tests/concurrency/test_canonical_thread_safety.py",
        evidence="a module global was replaced by a ContextVar after a measured 1-in-N corruption (D-024)",
    )
    cap(
        name="order-independent module scope with cycle detection",
        status="IMPLEMENTED",
        source_path=rel(SRC / "semantics" / "__init__.py"),
        symbol="Resolver.run / _find_cycle",
        confidence="high",
        test_file="tests/semantics/test_scope.py",
        evidence=(
            "two-pass binder collection (D-008), then explicit iterative-DFS cycle "
            "detection for definitions (HML-S606) and for concept 'extends' "
            "(HML-S602)"
        ),
    )
    cap(
        name="shadowing rejected as an error",
        status="IMPLEMENTED",
        source_path=rel(SRC / "semantics" / "__init__.py"),
        symbol="Resolver.declare",
        confidence="high",
        test_file="tests/semantics/test_scope.py",
        evidence="HML-N302 (shadowing) and HML-N303 (redeclaration) are errors, not warnings (D-006)",
    )
    cap(
        name="no UnknownType survives a clean check",
        status="IMPLEMENTED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="TypeChecker._check_no_unknown_types_survive",
        confidence="high",
        test_file="tests/type_system/test_unknown_types.py",
        evidence=(
            "HML-T450 walks every Expr after checking. Guarded by 'if not "
            "self.diags.ok(): return', so it is suppressed whenever any earlier "
            "error fired -- the invariant holds only for otherwise-clean programs"
        ),
    )

    return {
        "phases": {
            "count": 4,
            "counting_rule": (
                "stages hamiltonian_lang.compile_source actually invokes, in order. "
                "Each is gated: a failing stage short-circuits the rest"
            ),
            "values": [
                {"phase": "lex", "entry": "lexer.tokenize", "codes": "HML-L1xx"},
                {"phase": "parse", "entry": "parser.parse", "codes": "HML-P2xx, HML-D501"},
                {"phase": "resolve", "entry": "semantics.resolve",
                 "codes": "HML-N3xx, HML-S601/S602/S603/S606"},
                {"phase": "type check", "entry": "type_system.check",
                 "codes": "HML-T4xx, HML-D50x, HML-S604/S605/S607"},
            ],
            "NOT_invoked_by_compile_source": [
                "verification.obligations.discharge (separate entry point verify_source)",
                "every v1/ checker (X/E/G codes)",
                "equivalence/, repair/, improvement/, context_broker/ (harness, not compiler)",
            ],
        },
        "canonicalisation": {
            "version": CANONICAL_VERSION,
            "erased_for_identity": [
                "binder spellings (declaration, def parameter, quantifier variable)",
                "source spans",
                "comments and blank lines",
                "distribution argument order",
                "'extends' list order",
                "law 'given' order",
            ],
            "preserved_for_identity": [
                "statement order",
                "quantifier nesting order",
                "declaration kind",
                "law role (prior vs likelihood vs law)",
                "operator spelling after '**'->'^' folding",
                "distribution family name (a plain string, not a symbol)",
            ],
        },
        "graph_view": {
            "edge_kinds": {
                "count": len(EDGE_KINDS),
                "counting_rule": "members of graph.EDGE_KINDS (a closed frozenset, asserted at add time)",
                "values": sorted(EDGE_KINDS),
            },
        },
    }


# --------------------------------------------------------------------------
# 9. Backends and importers
# --------------------------------------------------------------------------


def extract_backends() -> dict:
    loss: dict[str, dict[str, Any]] = {}
    for f in sorted((SRC / "backends").glob("*.py")):
        if f.name in {"__init__.py", "base.py"}:
            continue
        pf = PARSED[rel(f)]
        counts = {"drop": 0, "approximate": 0, "weaken": 0}
        constructs: dict[str, list[str]] = {"drop": [], "approximate": [], "weaken": []}
        for node in ast.walk(pf.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                m = node.func.attr
                if m in counts and isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                    counts[m] += 1
                    if node.args and isinstance(node.args[0], ast.Constant):
                        constructs[m].append(str(node.args[0].value))
        lim = re.search(r"limitations\s*=\s*\(", pf.text)
        loss[f.stem] = {
            "loss_call_counts": counts,
            "total_loss_sites": sum(counts.values()),
            "declares_limitations_tuple": bool(lim),
            "constructs_named": {k: sorted(set(v)) for k, v in constructs.items()},
        }

    silent = sorted(
        k for k, v in loss.items()
        if v["total_loss_sites"] == 0 and k not in {"hml", "canonical"}
    )

    cap(
        name="mandatory translation-loss reporting",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "backends" / "base.py"),
        symbol="Backend.drop / approximate / weaken",
        confidence="high",
        test_file="tests/golden/test_golden.py",
        evidence=(
            "the contract is real and stan/sympy/lean/latex use it heavily. But the "
            f"english backend has ZERO loss sites ({silent}), so "
            "BackendResult.faithful is True for it and `hml render -t english` "
            "prints 'no loss reported'. Natural-language prose is the least "
            "faithful target in the registry and it is the one target that "
            "declares no loss. It does define a `limitations` tuple, which reaches "
            "BackendResult.notes but does NOT affect .faithful. "
            "tests/golden/test_golden.py::test_lossy_backends_declare_their_loss "
            "asserts loss only for the latex backend, so nothing tests this"
        ),
        notes=[
            "CLAUDE.md: 'A backend that silently omits a construct produces "
            "authoritative-looking output that is wrong; that is the worst failure "
            "mode in this codebase.'"
        ],
    )
    cap(
        name="round-trip importers (foreign notation -> HML)",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "importers" / "__init__.py"),
        symbol="from_canonical_json / from_triples / from_stan / from_lean",
        confidence="high",
        test_file="tests/roundtrip/test_importers.py",
        evidence=(
            "4 importers, each over an explicitly declared SubsetSpec, raising "
            "UnsupportedConstruct outside it. No SymPy importer despite a SymPy "
            "backend, and no LaTeX or English importer, so 3 of 5 lossy backends "
            "are one-way"
        ),
    )

    return {
        "backends": {
            "count": len(BACKEND_REGISTRY),
            "counting_rule": (
                "keys of backends.REGISTRY after _bootstrap(). stan/sympy/lean are "
                "registered only if their optional import succeeds, so this count "
                "is environment-dependent; it is recorded as measured in THIS "
                "environment"
            ),
            "values": sorted(BACKEND_REGISTRY),
            "core_always_present": ["english", "graph", "hml", "json", "latex", "triples"],
            "optional_third_party": ["lean", "stan", "sympy"],
            "loss_reporting": loss,
            "backends_reporting_no_loss_at_all": silent,
        },
        "importers": {
            "count": 4,
            "counting_rule": "from_* public functions in importers/__init__.py",
            "values": ["from_canonical_json", "from_lean", "from_stan", "from_triples"],
            "no_importer_for": ["english", "latex", "sympy"],
        },
    }


# --------------------------------------------------------------------------
# 10. Extensibility
# --------------------------------------------------------------------------


def extract_extensibility() -> dict:
    mechanisms = [
        {
            "extension": "new named type",
            "in_language": "PARTIAL -- 'concept X ... end' mints a ConceptType",
            "mechanism": "ConceptDecl",
            "source": rel(SRC / "parser" / "__init__.py"),
            "limits": (
                "a ConceptType has NO is_subtype rule, so a concept is comparable "
                "only by name identity; 'extends' is checked for cycles and "
                "existence but establishes no subtyping and no member inheritance "
                "-- Resolver.visit_concept never copies or looks up a base's "
                "members. Concept members cannot be referenced from outside the "
                "concept, and no expression can construct a concept INSTANCE"
            ),
            "status": "PARTIALLY_IMPLEMENTED",
        },
        {
            "extension": "new scalar refinement type",
            "in_language": "NO",
            "mechanism": "edit types._SCALAR_PARENTS",
            "source": rel(SRC / "types.py"),
            "limits": "compiler edit; ScalarType.__post_init__ raises for any unlisted name",
            "status": "ABSENT",
        },
        {
            "extension": "new distribution family",
            "in_language": "NO",
            "mechanism": "edit type_system.distributions.DISTRIBUTIONS",
            "source": rel(SRC / "type_system" / "distributions.py"),
            "limits": "module-level dict literal, no registration hook, no entry point",
            "status": "ABSENT",
        },
        {
            "extension": "new operator",
            "in_language": "NO",
            "mechanism": "edit lexer._OPERATORS and the parser precedence chain",
            "source": rel(SRC / "lexer" / "__init__.py"),
            "limits": "no user-defined operator, no fixity declaration, no overloading",
            "status": "ABSENT",
        },
        {
            "extension": "new inference rule / proof tactic",
            "in_language": "NO",
            "mechanism": "subclass verification.obligations.checkers.Checker",
            "source": rel(SRC / "verification" / "obligations" / "checkers.py"),
            "limits": (
                "a real Python extension point (DEFAULT_CHECKERS is a list), but it "
                "is a Python API outside the compiler. There is no .hml syntax for "
                "a rule, a tactic, an axiom or a lemma. 'prove' states a goal and "
                "discharges nothing"
            ),
            "status": "PARTIALLY_IMPLEMENTED",
        },
        {
            "extension": "new backend",
            "in_language": "NO",
            "mechanism": "backends.register(name, fn) / subclass Backend",
            "source": rel(SRC / "backends" / "__init__.py"),
            "limits": "genuine public API, but Python-level and unversioned",
            "status": "IMPLEMENTED",
        },
        {
            "extension": "new builtin function",
            "in_language": "NO",
            "mechanism": "edit _BUILTIN_FUNCTIONS and _BUILTIN_SIGNATURES",
            "source": rel(SRC / "type_system" / "__init__.py"),
            "limits": (
                "TWO tables in TWO modules must agree by hand; semantics."
                "_BUILTIN_FUNCTIONS has 13 names, type_system._BUILTIN_SIGNATURES "
                "has 7, and _aggregate_type covers 6 more -- the resolver's list "
                "and the checker's coverage are maintained separately"
            ),
            "status": "ABSENT",
        },
        {
            "extension": "new concept in the V1 registry",
            "in_language": "NO",
            "mechanism": "v1.registry / v1.minting (JSON-schema-validated Python API)",
            "source": rel(SRC / "v1" / "registry.py"),
            "limits": (
                "a full minting protocol with lifecycle states -- and entirely "
                "disjoint from the .hml 'concept' keyword. Two unrelated things "
                "share the word 'concept'"
            ),
            "status": "PARTIALLY_IMPLEMENTED",
        },
    ]

    resolver_builtins = sorted(_BUILTIN_FUNCTIONS)
    checker_signed = sorted(_BUILTIN_SIGNATURES)
    aggregates = ["sum", "prod", "mean", "variance", "expectation", "transpose"]
    unsigned = sorted(set(resolver_builtins) - set(checker_signed) - set(aggregates))

    # A builtin whose spelling is a reserved keyword can never be CALLED: the lexer
    # tags it TokenKind.KEYWORD, and Parser.parse_primary only builds a Call from
    # TokenKind.IDENT. Computed, not asserted.
    shadowed = sorted(set(resolver_builtins) & set(KEYWORDS))
    if shadowed:
        cap(
            name="builtin functions unreachable because a keyword shadows them",
            status="DECLARED_BUT_UNENFORCED",
            source_path=rel(SRC / "lexer" / "__init__.py"),
            symbol=f"KEYWORDS & _BUILTIN_FUNCTIONS = {shadowed}",
            confidence="high",
            evidence=(
                f"{', '.join(shadowed)} appear in semantics._BUILTIN_FUNCTIONS AND "
                "have full implementations in TypeChecker._aggregate_type, but both "
                "spellings are reserved keywords (they are 'infer' query kinds). "
                "The lexer tags them TokenKind.KEYWORD and parse_primary builds a "
                "Call only from TokenKind.IDENT. VERIFIED: 'def q := variance(v)' "
                "fails at HML-P231 'expected an expression'. Consequence: the "
                "HML-T428 branch 'expectation applies to a random variable, not to "
                "a law' -- a diagnostic written specifically to prevent one of the "
                "prohibited conflations -- is unreachable from that path, and HML "
                "has NO way to write the expectation of a random variable in an "
                "expression"
            ),
        )

    cap(
        name="user-extensible language surface (new type / operator / distribution)",
        status="ABSENT",
        source_path=rel(SRC),
        symbol="-- no extension syntax",
        confidence="high",
        evidence=(
            "of 8 extension axes, exactly one ('concept') has any in-language "
            "syntax and it neither participates in subtyping nor inherits members. "
            "Every other extension requires editing the compiler"
        ),
    )
    if unsigned:
        cap(
            name="builtin functions the resolver admits but the checker cannot type",
            status="DECLARED_BUT_UNENFORCED",
            source_path=rel(SRC / "semantics" / "__init__.py"),
            symbol=f"_BUILTIN_FUNCTIONS - _BUILTIN_SIGNATURES = {unsigned}",
            confidence="high",
            evidence=(
                "these names pass name resolution but reach neither "
                "_BUILTIN_SIGNATURES nor _aggregate_type in _call_type, so they "
                "fall through to UnknownType. HML-T450 then catches it only when "
                "no earlier error fired"
            ),
        )

    return {
        "extension_mechanisms": {
            "count": len(mechanisms),
            "counting_rule": (
                "axes along which a user might extend the language, each scored by "
                "whether .hml SYNTAX exists for it (in_language) as distinct from "
                "whether a Python API exists"
            ),
            "in_language_count": 1,
            "python_api_count": 3,
            "compiler_edit_required_count": 4,
            "values": mechanisms,
        },
        "builtin_functions": {
            "admitted_by_resolver": {
                "count": len(resolver_builtins),
                "counting_rule": "semantics._BUILTIN_FUNCTIONS",
                "values": resolver_builtins,
            },
            "with_a_fixed_signature": {
                "count": len(checker_signed),
                "counting_rule": "keys of type_system._BUILTIN_SIGNATURES",
                "values": checker_signed,
            },
            "shape_polymorphic": {
                "count": len(aggregates),
                "counting_rule": "names handled by TypeChecker._aggregate_type",
                "values": sorted(aggregates),
            },
            "admitted_but_untypeable": unsigned,
            "unreachable_because_a_keyword_shadows_them": shadowed,
            "actually_callable": {
                "count": len(set(resolver_builtins) - set(shadowed)),
                "counting_rule": (
                    "_BUILTIN_FUNCTIONS minus names the lexer classifies as "
                    "keywords, which parse_primary can never turn into a Call"
                ),
                "values": sorted(set(resolver_builtins) - set(shadowed)),
            },
        },
    }


# --------------------------------------------------------------------------
# 11. V1 library layer (Python API, not the language)
# --------------------------------------------------------------------------


def _enum_members(path: Path, cls_name: str) -> list[str]:
    pf = PARSED[rel(path)]
    for c in classes_in(pf):
        if c.name == cls_name:
            return sorted(
                t.targets[0].id
                for t in c.body
                if isinstance(t, ast.Assign)
                and t.targets
                and isinstance(t.targets[0], ast.Name)
            )
    return []


def extract_v1() -> dict:
    from hamiltonian_lang.v1 import epistemic, morphology, transformation
    from hamiltonian_lang.v1 import discourse, registry

    cap(
        name="epistemic status types",
        status="IMPLEMENTED",
        source_path=rel(SRC / "v1" / "epistemic.py"),
        symbol="EpistemicStatus / Justification",
        layer="LIBRARY",
        confidence="high",
        test_file="tests/v1/test_epistemic_checks.py",
        evidence=(
            f"{len(list(epistemic.EpistemicStatus))} statuses, "
            f"{len(list(epistemic.Justification))} justification kinds, "
            f"{len(epistemic.PROHIBITED_COERCIONS)} prohibited coercions with "
            "reasons. Python only: NO .hml keyword attaches an epistemic status to "
            "a statement, and compile_source never touches this module"
        ),
    )
    cap(
        name="transformation / inference edges",
        status="IMPLEMENTED",
        source_path=rel(SRC / "v1" / "transformation.py"),
        symbol="TransformationEdge / OPERATIONS",
        layer="LIBRARY",
        confidence="high",
        test_file="tests/v1/test_transformation.py",
        evidence=(
            f"{len(list(transformation.EdgeKind))} edge kinds, "
            f"{len(transformation.OPERATIONS)} operation specs each with side "
            "conditions, warrant kinds and a converse table. Python only: no .hml "
            "statement builds a TransformationEdge"
        ),
    )
    cap(
        name="discourse state",
        status="IMPLEMENTED",
        source_path=rel(SRC / "v1" / "discourse.py"),
        symbol="DiscourseState / DiscourseConstruct",
        layer="LIBRARY",
        confidence="high",
        test_file="tests/v1/test_discourse.py",
        evidence=(
            f"{len(list(discourse.DiscourseConstruct))} constructs, "
            f"{len(discourse.KERNEL_PHRASES)} kernel phrases and "
            f"{len(discourse.RHETORICAL_PHRASES)} rhetorical phrases classified. "
            "Operates on ENGLISH STRINGS, not on the AST"
        ),
    )
    cap(
        name="semantic morphology (role vocabulary)",
        status="IMPLEMENTED",
        source_path=rel(SRC / "v1" / "morphology.py"),
        symbol="Morphology / Role / EstimationRole",
        layer="LIBRARY",
        confidence="high",
        test_file="tests/v1/test_morphology.py",
        evidence=(
            f"{len(list(morphology.Role))} concept-family roles with prerequisite "
            f"edges, {len(list(morphology.EstimationRole))} estimation roles with a "
            "property-carrier table. Python only"
        ),
    )
    cap(
        name="concept registry with lifecycle and provenance",
        status="IMPLEMENTED",
        source_path=rel(SRC / "v1" / "registry.py"),
        symbol="Lifecycle / ClaimStatus / Provenance",
        layer="LIBRARY",
        confidence="high",
        test_file="tests/v1/test_registry.py",
        evidence=(
            f"{len(list(registry.Lifecycle))} lifecycle states with an explicit "
            "transition table, JSON-schema validated against "
            "spec/concept_registry.schema.json. Disjoint from the .hml 'concept' "
            "keyword"
        ),
    )
    cap(
        name="provenance tracking for .hml source",
        status="ABSENT",
        source_path=rel(SRC / "ast" / "nodes.py"),
        symbol="-- no field",
        layer="CORE",
        confidence="high",
        evidence=(
            "an AST Node carries only span and type_. There is no author, no "
            "derivation, no citation, no confidence and no epistemic status on any "
            "statement. Provenance exists in v1/registry.py::Provenance for "
            "registry concepts, which .hml cannot reference"
        ),
    )
    cap(
        name="epistemic status attachable to an .hml statement",
        status="ABSENT",
        source_path=rel(SRC / "parser" / "__init__.py"),
        symbol="-- no syntax",
        layer="CORE",
        confidence="high",
        evidence=(
            "the closest in-language distinctions are the 3 law roles "
            "(law/prior/likelihood) and the 3 proposition statements "
            "(assume/require/prove). 'assume' vs 'prove' is the ONLY epistemic "
            "contrast the language encodes, and both produce an obligation the "
            "compiler discharges identically (i.e. not at all)"
        ),
    )

    return {
        "layer": "LIBRARY -- Python API, unreachable from .hml source",
        "epistemic_states": {
            "count": len(list(epistemic.EpistemicStatus)),
            "counting_rule": "members of v1.epistemic.EpistemicStatus",
            "values": sorted(m.value for m in epistemic.EpistemicStatus),
            "justification_kinds": sorted(m.value for m in epistemic.Justification),
            "prohibited_coercions": len(epistemic.PROHIBITED_COERCIONS),
            "probability_kinds": sorted(m.value for m in epistemic.ProbabilityKind),
            "prohibited_probability_coercions": len(
                epistemic.PROHIBITED_PROBABILITY_COERCIONS
            ),
            "in_language_equivalent": {
                "count": 2,
                "counting_rule": (
                    "distinct epistemic postures expressible in .hml. Only "
                    "'assume' (taken as given) vs 'prove'/'require' (to be "
                    "established) is encoded"
                ),
                "values": ["assumed", "to-be-established"],
            },
        },
        "transformation_forms": {
            "count": len(list(transformation.EdgeKind)),
            "counting_rule": "members of v1.transformation.EdgeKind",
            "values": sorted(m.value for m in transformation.EdgeKind),
            "operations": {
                "count": len(transformation.OPERATIONS),
                "counting_rule": "keys of v1.transformation.OPERATIONS",
                "values": sorted(o.value for o in transformation.OPERATIONS),
            },
            "warrant_kinds": sorted(m.value for m in transformation.WarrantKind),
            "obligation_kinds": sorted(m.value for m in transformation.ObligationKind),
            "prohibited_edge_coercions": len(transformation.PROHIBITED_EDGE_COERCIONS),
            "inference_rules": {
                "count": len(transformation.INFERENCE_RULES),
                "values": sorted(transformation.INFERENCE_RULES),
            },
            "in_language_equivalent": {
                "count": 0,
                "counting_rule": (
                    "the .hml grammar has no statement that relates one expression "
                    "to another by a justified step. A model cannot write a "
                    "derivation in HML: there is no 'therefore', no 'by', no "
                    "proof step and no rewriting form"
                ),
            },
        },
        "discourse_constructs": {
            "count": len(list(discourse.DiscourseConstruct)),
            "counting_rule": "members of v1.discourse.DiscourseConstruct",
            "values": sorted(m.value for m in discourse.DiscourseConstruct),
        },
        "morphology_roles": {
            "count": len(list(morphology.Role)),
            "values": sorted(m.value for m in morphology.Role),
            "estimation_roles": sorted(m.value for m in morphology.EstimationRole),
        },
        "registry_lifecycle": {
            "count": len(list(registry.Lifecycle)),
            "values": sorted(m.value for m in registry.Lifecycle),
            "claim_statuses": sorted(m.value for m in registry.ClaimStatus),
            "relation_kinds": sorted(m.value for m in registry.RelationKind),
        },
    }


# --------------------------------------------------------------------------
# 12. Verification layer
# --------------------------------------------------------------------------


def extract_verification() -> dict:
    from hamiltonian_lang.verification import obligations as ob

    # DEFAULT_CHECKERS holds instances, not classes.
    checkers = [type(c).__name__ for c in ob.DEFAULT_CHECKERS]

    cap(
        name="deterministic proof-obligation discharge over a bounded subset",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(SRC / "verification" / "obligations" / "checkers.py"),
        symbol="DEFAULT_CHECKERS",
        layer="LIBRARY",
        confidence="high",
        test_file="tests/verification/test_checkers.py",
        evidence=(
            f"{len(checkers)} checker classes over "
            f"{len(ob.SUPPORTED_CLASSES)} obligation classes. NOT part of "
            "compile_source: reached only via verify_source/verify_result. "
            "Everything outside the subset returns UNSUPPORTED, and UNSUPPORTED "
            "blocks VERIFIED as firmly as a failure -- which is the honest design, "
            "and also means most real obligations are never decided"
        ),
    )
    cap(
        name="'prove' discharges a theorem",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="ProveStmt",
        confidence="high",
        evidence=(
            "the compiler records a ProofObligation(kind='theorem') and stops. "
            "VERIFIED: 'prove 1 = 2' -- a closed, decidable, FALSE proposition -- "
            "compiles with zero diagnostics and ok()==True. Only the separate "
            "verify_source entry point attempts discharge, and only within the "
            "bounded subset"
        ),
    )
    cap(
        name="'assume' semantics",
        status="DECLARED_BUT_UNENFORCED",
        source_path=rel(SRC / "type_system" / "__init__.py"),
        symbol="AssumeStmt",
        confidence="high",
        evidence=(
            "an AssumeStmt produces ProofObligation(kind='assumption') and nothing "
            "else in the compiler. VERIFIED: 'assume x > 5' followed by "
            "'assume x < 1' compiles clean, as does 'assume x > 5' followed by "
            "'require x < 1'. The assumption is not added to any context a later "
            "require or prove is checked against, and it does not refine x's type. "
            "The obligations engine does use assumptions "
            "(LogicalConsistencyChecker), but that is outside compile_source"
        ),
    )

    return {
        "layer": "LIBRARY -- separate entry point verify_source(), not compile_source()",
        "obligation_checkers": {
            "count": len(checkers),
            "counting_rule": "entries of verification.obligations.DEFAULT_CHECKERS",
            "values": sorted(checkers),
        },
        "obligation_classes": {
            "count": len(ob.SUPPORTED_CLASSES),
            "counting_rule": "verification.obligations.records.SUPPORTED_CLASSES",
            "values": sorted(
                c.value if hasattr(c, "value") else str(c) for c in ob.SUPPORTED_CLASSES
            ),
        },
        "verdicts": sorted(m.value for m in ob.GlobalVerdict),
        "obligation_statuses": sorted(m.value for m in ob.ObligationStatus),
        "explicitly_refused": [
            "quantification over an infinite domain",
            "distributional claims",
            "integrals and limits",
            "anything involving RandomVariable or Distribution",
            "dimensioned quantities in numeric comparisons",
            "indexing",
            "the matrix product",
        ],
    }


# --------------------------------------------------------------------------
# 13. Test inventory and examples
# --------------------------------------------------------------------------


def extract_tests() -> dict:
    counts: dict[str, int] = {}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=900,
            env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        )
        for line in proc.stdout.splitlines():
            m = re.match(r"^(tests/\S+\.py): (\d+)$", line.strip())
            if m:
                counts[m.group(1)] = int(m.group(2))
    except Exception as exc:  # pragma: no cover
        counts = {}
        print(f"warning: pytest collection failed ({exc}); test counts omitted", file=sys.stderr)

    by_dir: dict[str, int] = defaultdict(int)
    for path, n in counts.items():
        by_dir[path.split("/")[1]] += n

    LANGUAGE_CORE = {
        "parser", "semantics", "type_system", "golden", "roundtrip", "adversarial",
        "fuzz", "constitutional", "concurrency",
    }
    core_total = sum(n for d, n in by_dir.items() if d in LANGUAGE_CORE)
    total = sum(by_dir.values())

    all_examples = sorted(
        rel(p) for p in EXAMPLES.rglob("*.hml")
    )
    compiled = [e for e in all_examples if "candidate_syntaxes" not in e]

    cap(
        name="every example under examples/ compiles",
        status="PARTIALLY_IMPLEMENTED",
        source_path="tests/conftest.py",
        symbol="example_files()",
        confidence="high",
        test_file="tests/golden/test_golden.py",
        evidence=(
            f"CLAUDE.md rule 10 says 'tests/golden compiles every .hml under "
            f"examples/'. tests/conftest.py::example_files filters "
            f"'candidate_syntaxes' out, so {len(compiled)} of {len(all_examples)} "
            f".hml files are compiled and {len(all_examples) - len(compiled)} are "
            "not. The excluded files are alternative candidate surfaces for the "
            "syntax tournament and mostly are NOT HML-L1, so excluding them is "
            "right -- but the rule as written is false"
        ),
    )

    return {
        "total_collected_tests": {
            "count": total,
            "counting_rule": "sum of pytest --collect-only -q per-file counts",
        },
        "language_core_tests": {
            "count": core_total,
            "counting_rule": (
                "tests under parser, semantics, type_system, golden, roundtrip, "
                "adversarial, fuzz, constitutional, concurrency -- the directories "
                "that exercise the .hml language itself rather than the evaluation "
                "harness or the v1 Python API"
            ),
            "share_of_suite": round(core_total / total, 4) if total else None,
        },
        "by_directory": dict(sorted(by_dir.items(), key=lambda kv: -kv[1])),
        "examples": {
            "total_hml_files": len(all_examples),
            "compiled_by_golden_tests": len(compiled),
            "excluded_from_compilation": sorted(
                set(all_examples) - set(compiled)
            ),
            "compiled_values": compiled,
        },
    }


# --------------------------------------------------------------------------
# 14. ACQ0 evidence
# --------------------------------------------------------------------------


def extract_acq0() -> dict:
    summary_path = REPO / "evaluation/results/acq0/v2_tranche_a/tranche_a_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    invalid = REPO / "evaluation/results/acq0/v2_tranche_a/MEASUREMENT_INVALID.md"

    cap(
        name="measured evidence that a model can WRITE HML",
        status="PARTIALLY_IMPLEMENTED",
        source_path=rel(summary_path) if summary_path.exists() else "evaluation/results/acq0/",
        symbol="tranche_a_summary.json",
        layer="LIBRARY",
        confidence="high",
        test_file="tests/evaluation/test_acq0_protocols.py",
        evidence=(
            "the only completed writability tranche is ACQ0 v2 Tranche A: n=8 tasks "
            "per surface, 4 surfaces, 32 conditions, one model. Surface A "
            "(v0 labelled linear, i.e. HML as it exists) scored 7/8 repaired-parse "
            "and 7/8 exact-semantic. The run is closed MEASUREMENT_INVALID: 3 of 32 "
            "conditions hit a 6144-token completion cap and the truncation is "
            "outcome-determining, so no viability verdict may be read from it"
        ),
    )

    return {
        "what_was_measured": (
            "ACQ0 measures ENCODING only -- format adherence, parse, resolve, type, "
            "and exact semantic preservation. The prompts disclose the target "
            "proposition under a scoped oracle exemption, so "
            "oracle.ACQ0_ANSWER_FACET_VOID records that ACQ0's answer_correct facet "
            "is uninformative by construction and must never be cited as evidence "
            "about the representation"
        ),
        "tranche_a": {
            "status": "MEASUREMENT_INVALID",
            "n_per_surface": 8,
            "n_surfaces": 4,
            "n_conditions": 32,
            "models": 1,
            "summary": summary,
            "invalidation_reason": (
                "3 of 32 conditions hit finish_reason=length at COMPLETION_ALLOWANCE"
                "=6144; the truncation decides the verdict for surfaces A and C"
            ),
            "record": rel(invalid) if invalid.exists() else None,
        },
        "prior_calibrations": {
            "v1_protocol_calibration": (
                "closed PROTOCOL_UNSTABLE -- 56 of 76 generations hit "
                "finish_reason=length at 2048 tokens"
            ),
            "protocol_calibration_v2": (
                "16-condition developmental calibration; "
                "docs/evaluation/ACQ0_PROTOCOL_CALIBRATION.md states it is 'not a "
                "powered test' and 'nothing here licenses a claim of statistical "
                "significance'"
            ),
        },
        "claimed_vs_measured": {
            "MEASURED": [
                "one model can produce parseable, type-correct, semantically exact "
                "HML for 7 of 8 encoding tasks under a disclosed-target prompt",
                "a JSON-graph surface (D) scored 0/8 -- the only clearly separated "
                "surface, and it separated downward",
            ],
            "NOT_MEASURED": [
                "that HML improves reasoning (V1_GATE_DECISION passed on catchability only)",
                "any comparison against Lean, Stan, SymPy, Python or natural language",
                "that role labels help (distributions.py withdraws this claim in its own docstring)",
                "writability by any model other than the single one used",
                "writability of concept, quantifier, dimension or objective constructs at scale",
            ],
        },
    }


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------


def summary_counts(sections: dict) -> dict:
    lex = sections["lexical"]
    gram = sections["grammar"]
    nodes = sections["ast_nodes"]
    ty = sections["type_system"]
    diag = sections["diagnostics"]
    v1 = sections["v1_library_layer"]
    be = sections["backends_and_importers"]
    ext = sections["extensibility"]

    return {
        "N_keywords": {
            "CORE": lex["reserved_keywords"]["count"],
            "LIBRARY": 0,
            "counting_definition": lex["reserved_keywords"]["counting_rule"],
            "note": (
                f"{lex['reserved_keywords']['distinct_meanings_after_alias_folding']} "
                "distinct meanings after folding minimize/maximize/fn onto "
                "minimise/maximise/def"
            ),
        },
        "N_operators": {
            "CORE": lex["operators"]["count"],
            "LIBRARY": 0,
            "counting_definition": lex["operators"]["counting_rule"],
            "note": (
                f"plus {lex['binding_and_annotation_punctuation']['count']} binding/"
                f"annotation tokens and {lex['delimiters']['count']} delimiters, "
                "counted separately"
            ),
        },
        "N_statement_forms": {
            "CORE": gram["statement_forms"]["count"],
            "LIBRARY": 0,
            "counting_definition": gram["statement_forms"]["counting_rule"],
            "note": (
                f"{gram['statement_forms']['expanded_by_discriminator']['count']} "
                "when each discriminator value is counted separately"
            ),
        },
        "N_expression_forms": {
            "CORE": gram["expression_forms"]["count"],
            "LIBRARY": 0,
            "counting_definition": gram["expression_forms"]["counting_rule"],
        },
        "N_declaration_forms": {
            "CORE": gram["declaration_forms"]["count"],
            "LIBRARY": 0,
            "counting_definition": gram["declaration_forms"]["counting_rule"],
            "note": (
                f"{gram['declaration_forms']['wider_reading']['count']} under the "
                "wider reading that counts any name-binding statement"
            ),
        },
        "N_AST_node_kinds": {
            "CORE": nodes["total_node_kinds"]["count"],
            "LIBRARY": 0,
            "counting_definition": nodes["total_node_kinds"]["counting_rule"],
            "note": (
                f"{nodes['expression_node_classes']['count']} expression + "
                f"{nodes['statement_node_classes']['count']} statement; "
                f"{nodes['support_classes']['count']} support classes excluded"
            ),
        },
        "N_type_constructors": {
            "CORE": ty["type_constructors"]["count"],
            "LIBRARY": 0,
            "counting_definition": ty["type_constructors"]["counting_rule"],
            "note": (
                f"ScalarType has {ty['scalar_types']['count']} inhabitants; counting "
                f"those individually gives "
                f"{ty['type_constructors']['count'] - 1 + ty['scalar_types']['count']} "
                "nameable types"
            ),
        },
        "N_semantic_primitives": {
            "CORE": 18,
            "LIBRARY": 0,
            "counting_definition": (
                "irreducible semantic relations the .hml language can assert: 6 "
                "declaration kinds, definition, 3 law roles, assumption, "
                "constraint, theorem, objective, solve, inference query, "
                "dimensional assertion, concept, quantified proposition"
            ),
        },
        "N_epistemic_states": {
            "CORE": v1["epistemic_states"]["in_language_equivalent"]["count"],
            "LIBRARY": v1["epistemic_states"]["count"],
            "counting_definition": (
                "CORE = distinct epistemic postures a .hml statement can carry "
                "(assume vs require/prove). LIBRARY = members of "
                "v1.epistemic.EpistemicStatus, which no .hml program can reference"
            ),
        },
        "N_transformation_forms": {
            "CORE": 0,
            "LIBRARY": v1["transformation_forms"]["count"],
            "counting_definition": (
                "CORE = .hml statements relating one expression to another by a "
                "justified step: there are none. LIBRARY = members of "
                "v1.transformation.EdgeKind, plus "
                f"{v1['transformation_forms']['operations']['count']} operation specs"
            ),
        },
        "N_diagnostics_categories": {
            "CORE": 7,
            "LIBRARY": 3,
            "counting_definition": (
                "distinct alphabetic code-family prefixes. CORE = L,P,N,T,D,S,B "
                "(the 7 documented in diagnostics/__init__.py, all reachable from "
                "compile_source). LIBRARY = X,E,G, which are emitted only by v1/ "
                "and context_broker/ and are unreachable from any .hml source"
            ),
            "total_distinct_codes": diag["total_distinct_codes_emitted"]["count"],
            "codes_reachable_from_compile_source": diag["reachable_from_compile_source"]["count"],
        },
        "N_extension_mechanisms": {
            "CORE": ext["extension_mechanisms"]["in_language_count"],
            "LIBRARY": ext["extension_mechanisms"]["python_api_count"],
            "counting_definition": (
                "CORE = extension axes with .hml syntax (only 'concept', and it "
                "neither subtypes nor inherits). LIBRARY = axes with a real Python "
                "extension point (backends.register, Checker subclassing, v1 "
                "registry minting). The remaining "
                f"{ext['extension_mechanisms']['compiler_edit_required_count']} "
                "require editing the compiler"
            ),
        },
        "N_backends": {
            "CORE": len(be["backends"]["core_always_present"]),
            "LIBRARY": len(be["backends"]["optional_third_party"]),
            "counting_definition": (
                "CORE = targets registered unconditionally by backends._bootstrap. "
                "LIBRARY = targets registered only if an optional third-party "
                "import succeeds (stan, sympy, lean)"
            ),
            "total_in_this_environment": be["backends"]["count"],
        },
    }


def build() -> dict:
    sections: dict[str, Any] = {}
    sections["lexical"] = extract_lexical()
    sections["ast_nodes"] = extract_ast_nodes()
    sections["grammar"] = extract_grammar()
    sections["type_system"] = extract_types()
    sections["diagnostics"] = extract_diagnostics()
    sections["probability"] = extract_probability()
    sections["partiality_and_definedness"] = extract_partiality()
    sections["pipeline_and_identity"] = extract_pipeline()
    sections["backends_and_importers"] = extract_backends()
    sections["extensibility"] = extract_extensibility()
    sections["v1_library_layer"] = extract_v1()
    sections["verification_layer"] = extract_verification()
    sections["tests_and_examples"] = extract_tests()
    sections["acq0_evidence"] = extract_acq0()

    caps = sorted(
        (asdict(c) for c in CAPS), key=lambda d: (d["layer"], d["status"], d["name"])
    )
    tally: dict[str, int] = defaultdict(int)
    for c in caps:
        tally[c["status"]] += 1

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO, capture_output=True, text=True,
        ).stdout.strip()
    except Exception:  # pragma: no cover
        head, branch = "", ""

    src_digest = hashlib.sha256(
        b"".join(
            (path + "\0" + hashlib.sha256(pf.text.encode()).hexdigest()).encode()
            for path, pf in sorted(PARSED.items())
        )
    ).hexdigest()

    return {
        "genome_schema": "hml-language-genome-1.0",
        "subject": {
            "language": "Hamiltonian Lang (HML-L1)",
            "package_version": hamiltonian_lang.__version__,
            "repository": str(REPO),
            "git_head": head,
            "git_branch": branch,
            "source_tree_digest": src_digest,
            "disclaimer": (
                "Extracted exclusively from this local repository. The unrelated "
                "public 'Hamiltonian Lang' Python/JAX mechanics DSL is NOT this "
                "project and contributed nothing to this document."
            ),
        },
        "method": {
            "static": "ast.parse over every .py under src/hamiltonian_lang",
            "runtime": "direct import of the package's registries",
            "python_files_parsed": len(PARSED),
            "determinism": "all collections sorted before emission; re-runs are byte-identical",
        },
        "summary_counts": summary_counts(sections),
        "capability_status_tally": dict(sorted(tally.items())),
        "capabilities": caps,
        "sections": sections,
    }


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=False, ensure_ascii=False) + "\n")
    print(f"wrote {rel(OUT)}")
    print(f"  capabilities: {len(doc['capabilities'])}")
    for k, v in doc["capability_status_tally"].items():
        print(f"    {k:<24} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
