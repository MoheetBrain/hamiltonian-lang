#!/usr/bin/env python3
"""Alphabet / tokenisation / edit-robustness benchmark for Hamiltonian Lang.

Measures, for every candidate-syntax encoding in
``examples/candidate_syntaxes/`` plus the English and LaTeX baselines:

  1. character count, line count, non-blank non-comment line count
  2. token count under every tokenizer actually importable on this machine
  3. fragmentation ratio (tokens / characters)
  4. per-operator token cost for the reserved token set
  5. Unicode fragmentation, NFC/NFKC behaviour and confusable pairs
  6. edit robustness: are corruptions LOCALLY detectable, non-locally
     detectable, or silent?
  7. the token cost of decision D-003 (mandatory role-labelled distribution
     arguments), both on a controlled micro-corpus and whole-file

HONESTY RULES OBSERVED BY THIS SCRIPT
-------------------------------------
* A tokenizer that cannot be imported or downloaded is recorded in
  ``results/tokenizer_availability.json`` with the exact exception, and NO
  numbers are produced for it. Nothing is estimated in its place.
* ``regex_approx`` is a deliberately crude, dependency-free fallback
  tokenizer. It is ALWAYS reported and ALWAYS labelled APPROXIMATE. It exists
  so the benchmark still returns a defensible ordering on a machine with no
  network. It is not a model tokenizer and must never be quoted as one.

Usage
-----
    python3 experiments/alphabet/tokenisation_benchmark.py [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples" / "candidate_syntaxes"
DEFAULT_OUT = REPO / "experiments" / "alphabet" / "results"

CANDIDATES = {
    "A": "a_labelled_linear",
    "B": "b_symbolic_ascii",
    "C": "c_sexpr",
    "D": "d_indent_block",
    "E": "e_graph_triple",
}
BASELINES = {
    "ENG": "baseline_english",
    "TEX": "baseline_latex",
}

PROBLEMS = [
    "1_normal_distribution",
    "2_bayesian_coin",
    "3_linear_regression",
    "4_kinetic_energy",
    "5_constrained_optimisation",
    "6_quantifier_scope",
    "7_concept_definition",
]


# ===========================================================================
# 1. Tokenizers
# ===========================================================================


@dataclass
class Tok:
    name: str
    encode: Callable[[str], list]
    approximate: bool = False
    note: str = ""


_APPROX_RE = re.compile(
    r"""
      \s+                      # runs of whitespace
    | [A-Za-z]+                # word chunks
    | \d+                      # digit chunks
    | .                        # every other character on its own
    """,
    re.VERBOSE,
)


def regex_approx_encode(s: str) -> list:
    """APPROXIMATE fallback tokenizer.

    Documented model: whitespace runs, maximal alphabetic runs, maximal digit
    runs, and every other character individually. Long alphabetic runs are
    then split every 6 characters, crudely imitating BPE's tendency to break
    rare long identifiers. This over-counts punctuation-dense text relative to
    a real BPE tokenizer and under-counts natural-language text. It is a
    RANKING aid only.
    """
    out: list[str] = []
    for m in _APPROX_RE.finditer(s):
        t = m.group(0)
        if t.isalpha() and len(t) > 6:
            out.extend(t[i : i + 6] for i in range(0, len(t), 6))
        else:
            out.append(t)
    return out


def build_tokenizers() -> tuple[list[Tok], dict]:
    toks: list[Tok] = []
    avail: dict[str, dict] = {}

    # --- tiktoken -------------------------------------------------------
    tiktoken_names = ["cl100k_base", "o200k_base", "p50k_base", "r50k_base"]
    try:
        import tiktoken  # type: ignore

        avail["tiktoken"] = {"importable": True, "version": tiktoken.__version__}
        for n in tiktoken_names:
            try:
                enc = tiktoken.get_encoding(n)
                enc.encode("probe")
                toks.append(Tok(f"tiktoken:{n}", enc.encode))
                avail[f"tiktoken:{n}"] = {"available": True}
            except Exception as e:  # pragma: no cover
                avail[f"tiktoken:{n}"] = {
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                }
    except Exception as e:
        avail["tiktoken"] = {
            "importable": False,
            "error": f"{type(e).__name__}: {e}",
            "consequence": "NO tiktoken numbers reported. Not estimated.",
        }

    # --- huggingface transformers --------------------------------------
    hf_names = [
        ("gpt2", "gpt2"),
        ("llama2", "NousResearch/Llama-2-7b-hf"),
        ("llama3", "meta-llama/Meta-Llama-3-8B"),
        ("gpt-neox-20b", "EleutherAI/gpt-neox-20b"),
        ("starcoder2", "bigcode/starcoder2-3b"),
    ]
    try:
        import transformers  # type: ignore
        from transformers import AutoTokenizer  # type: ignore

        avail["transformers"] = {
            "importable": True,
            "version": transformers.__version__,
        }
        for short, repo in hf_names:
            try:
                t = AutoTokenizer.from_pretrained(repo)
                t.encode("probe", add_special_tokens=False)
                toks.append(
                    Tok(
                        f"hf:{short}",
                        lambda s, _t=t: _t.encode(s, add_special_tokens=False),
                    )
                )
                avail[f"hf:{short}"] = {"available": True, "repo": repo}
            except Exception as e:
                avail[f"hf:{short}"] = {
                    "available": False,
                    "repo": repo,
                    "error": f"{type(e).__name__}: {str(e)[:200]}",
                }
    except Exception as e:
        avail["transformers"] = {
            "importable": False,
            "error": f"{type(e).__name__}: {e}",
            "consequence": "NO GPT-2 / Llama numbers reported. Not estimated.",
        }

    # --- always-present documented fallback ------------------------------
    toks.append(
        Tok(
            "regex_approx_APPROXIMATE",
            regex_approx_encode,
            approximate=True,
            note="Not a model tokenizer. See regex_approx_encode docstring.",
        )
    )
    avail["regex_approx_APPROXIMATE"] = {
        "available": True,
        "approximate": True,
        "note": "documented fallback; never quote as a model tokenizer",
    }
    return toks, avail


# ===========================================================================
# 2. Corpus
# ===========================================================================


@dataclass
class Doc:
    arm: str  # A..E, ENG, TEX
    problem: str
    path: Path
    text: str

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def bytes_utf8(self) -> int:
        return len(self.text.encode("utf-8"))

    @property
    def lines(self) -> int:
        return len(self.text.rstrip("\n").split("\n"))

    def content_lines(self, comment_prefixes: tuple[str, ...]) -> int:
        n = 0
        for ln in self.text.split("\n"):
            s = ln.strip()
            if not s:
                continue
            if any(s.startswith(p) for p in comment_prefixes):
                continue
            n += 1
        return n


COMMENT_PREFIX = {
    "A": ("#",),
    "B": (";",),
    "C": (";",),
    "D": ("#",),
    "E": ("#",),
    "ENG": (),
    "TEX": ("%",),
}

EXT = {"ENG": ".txt", "TEX": ".tex"}


def load_corpus() -> list[Doc]:
    docs: list[Doc] = []
    for arm, folder in list(CANDIDATES.items()) + list(BASELINES.items()):
        ext = EXT.get(arm, ".hml")
        for prob in PROBLEMS:
            p = EXAMPLES / folder / f"{prob}{ext}"
            if not p.exists():
                raise SystemExit(f"MISSING corpus file: {p}")
            docs.append(Doc(arm, prob, p, p.read_text(encoding="utf-8")))
    return docs


# ===========================================================================
# 3. Well-formedness checkers  (one per candidate)
#    Each returns a list of (line_number_1based, message).
# ===========================================================================

A_STMT_KEYWORDS = {
    "module", "var", "param", "const", "obs", "index", "rv", "def",
    "law", "prior", "likelihood", "assume", "require", "minimise",
    "maximise", "solve", "infer", "check", "prove", "concept", "end",
}
A_MEMBER_KEYWORDS = {
    "parameter", "property", "transform", "invariant", "example",
    "counterexample",
}
A_TYPES = {
    "Bool", "Natural", "Integer", "Rational", "Real", "NonNegativeReal",
    "PositiveReal", "Probability", "Proposition", "Vector", "Matrix",
    "Tensor", "Set", "Function", "Predicate", "RandomVariable",
    "Distribution", "Quantity",
}
DIM_BASES = {"Mass", "Length", "Time", "Temperature", "Current", "Amount",
             "Luminosity", "Dimensionless"}
FAMILIES = {"Normal", "Beta", "Binomial", "NormalVector", "Uniform", "Gamma",
            "Poisson", "Exponential"}
ROLES = {"location", "scale", "alpha", "beta", "trials", "prob", "variance",
         "rate", "lower", "upper"}
A_OTHER_WORDS = {"forall", "exists", "exists_unique", "not", "and", "or",
                 "posterior", "expectation", "variance", "mle", "map",
                 "dimension", "extends", "true", "false", "given"}

OPEN = {"(": ")", "[": "]", "{": "}"}
CLOSE = {")": "(", "]": "[", "}": "{"}

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _ascii_errors(text: str) -> list[tuple[int, str]]:
    errs = []
    for i, ln in enumerate(text.split("\n"), 1):
        for ch in ln:
            if ord(ch) > 127:
                errs.append((i, f"non-ASCII character U+{ord(ch):04X}"))
                break
    return errs


def _line_bracket_errors(text: str, comment: str) -> list[tuple[int, str]]:
    errs = []
    for i, ln in enumerate(text.split("\n"), 1):
        code = ln.split(comment)[0] if comment else ln
        depth: list[str] = []
        for ch in code:
            if ch in OPEN:
                depth.append(ch)
            elif ch in CLOSE:
                if not depth or depth[-1] != CLOSE[ch]:
                    errs.append((i, f"unmatched '{ch}'"))
                    depth = []
                    break
                depth.pop()
        if depth:
            errs.append((i, f"unclosed '{depth[-1]}' at end of line"))
    return errs


QUANT_BINDER_A = re.compile(r"\b(?:forall|exists|exists_unique)\s+([A-Za-z_]\w*)\s*:")
QUANT_BINDER_B = re.compile(r"[!?]\s*\[\s*([A-Za-z_]\w*)\s*:")


def check_A(text: str) -> list[tuple[int, str]]:
    errs = _ascii_errors(text) + _line_bracket_errors(text, "#")
    in_concept = False
    declared: set[str] = set(QUANT_BINDER_A.findall(text))
    used: list[tuple[int, str]] = []
    depth_ok = True
    for i, raw in enumerate(text.split("\n"), 1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        head = line.split()[0] if line.split() else ""
        if in_concept:
            allowed = A_MEMBER_KEYWORDS | {"end"}
            if head not in allowed:
                errs.append((i, f"'{head}' is not a concept member keyword"))
                continue
        else:
            if head not in A_STMT_KEYWORDS:
                errs.append((i, f"'{head}' is not a statement keyword"))
                continue
        if head in ("concept", "module"):
            if head == "concept":
                if in_concept:
                    errs.append((i, "nested concept"))
                in_concept = True
            m = IDENT_RE.findall(line)
            if len(m) > 1:
                declared.add(m[1])
            else:
                errs.append((i, f"'{head}' has no name"))
            continue
        if head == "end":
            if not in_concept:
                errs.append((i, "'end' without 'concept'"))
                depth_ok = False
            in_concept = False
            continue
        # binding forms
        rest = line[len(head):].strip()
        if head in {"var", "param", "const", "obs", "index", "rv",
                    "parameter", "property"}:
            if ":" not in rest:
                errs.append((i, f"'{head}' declaration lacks ':' type ascription"))
            else:
                nm = IDENT_RE.match(rest)
                if not nm:
                    errs.append((i, "declaration lacks an identifier"))
                else:
                    declared.add(nm.group(0))
                    used.extend((i, t) for t in IDENT_RE.findall(rest[nm.end():]))
        elif head in {"def", "transform", "example", "counterexample"}:
            if ":=" not in rest:
                errs.append((i, f"'{head}' lacks ':='"))
            else:
                nm = IDENT_RE.match(rest)
                if nm:
                    declared.add(nm.group(0))
                lhs, rhs = rest.split(":=", 1)
                declared.update(
                    IDENT_RE.findall(lhs[lhs.find("(") :]) if "(" in lhs else []
                )
                used.extend((i, t) for t in IDENT_RE.findall(rhs))
        elif head in {"law", "prior", "likelihood"}:
            if "~" not in rest:
                errs.append((i, f"'{head}' statement lacks '~'"))
                continue
            tgt, dist = rest.split("~", 1)
            used.extend((i, t) for t in IDENT_RE.findall(tgt))
            dm = re.match(r"\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", dist)
            if not dm:
                errs.append((i, "distribution is not Family(...)"))
                continue
            fam, argtext = dm.group(1), dm.group(2)
            if fam not in FAMILIES:
                errs.append((i, f"unknown distribution family '{fam}'"))
            for a in _split_top(argtext, ","):
                if ":=" not in a:
                    errs.append((i, f"positional distribution argument '{a.strip()}'"
                                    " (D-003 requires a role label)"))
                else:
                    r, v = a.split(":=", 1)
                    if r.strip() not in ROLES:
                        errs.append((i, f"unknown role '{r.strip()}'"))
                    used.extend((i, t) for t in IDENT_RE.findall(v))
        else:
            used.extend((i, t) for t in IDENT_RE.findall(rest))
    if in_concept and depth_ok:
        errs.append((len(text.rstrip("\n").split("\n")), "concept never closed by 'end'"))
    known = (declared | A_TYPES | DIM_BASES | FAMILIES | ROLES
             | A_OTHER_WORDS | A_STMT_KEYWORDS | A_MEMBER_KEYWORDS)
    for i, t in used:
        if t not in known:
            errs.append((i, f"undeclared identifier '{t}'"))
    return sorted(set(errs))


def _split_top(s: str, sep: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


B_OPCODES = set("%$&*@#'=~+\\/><:|^.")
B_ROLES = {"m", "s", "v", "a", "b", "n", "p", "r", "lo", "hi"}
B_TYPES = {"R", "R+", "R0", "P", "Z", "N", "Q", "B", "O"}
B_FAMILIES = {"N", "B", "Bi", "NV", "U", "G", "Po", "E"}


def check_B(text: str) -> list[tuple[int, str]]:
    errs = _ascii_errors(text) + _line_bracket_errors(text, ";")
    concept_open = False
    declared: set[str] = set(QUANT_BINDER_B.findall(text))
    used: list[tuple[int, str]] = []
    for i, raw in enumerate(text.split("\n"), 1):
        line = raw.split(";")[0].rstrip()
        if not line.strip():
            continue
        c0 = line[0]
        if c0 == "%":
            m = IDENT_RE.findall(line)
            if not m:
                errs.append((i, "module has no name"))
            else:
                declared.add(m[0])
            continue
        if line.startswith("^^"):
            if not concept_open:
                errs.append((i, "'^^' without an open concept"))
            concept_open = False
            continue
        if c0 == "^":
            concept_open = True
            m = IDENT_RE.findall(line)
            if not m:
                errs.append((i, "concept has no name"))
            else:
                declared.add(m[0])
            continue
        if c0 == ".":
            if not concept_open:
                errs.append((i, "member line '.' outside a concept"))
            tag = line[:2]
            if tag not in {".p", ".y", ".t", ".i", ".e", ".x"}:
                errs.append((i, f"unknown concept member tag '{tag}'"))
            else:
                nm = IDENT_RE.search(line[2:])
                if tag in {".p", ".y", ".t", ".e", ".x"} and nm:
                    declared.add(nm.group(0))
                    rest2 = line[2 + nm.end():]
                    if tag == ".t":
                        fm = re.match(r"\s*\(([^)]*)\)", rest2)
                        if fm:
                            for f_ in fm.group(1).split(","):
                                fn = IDENT_RE.match(f_.strip())
                                if fn:
                                    declared.add(fn.group(0))
                    used.extend((i, t) for t in IDENT_RE.findall(rest2))
                else:
                    used.extend((i, t) for t in IDENT_RE.findall(line[2:]))
            continue
        if c0 in B_OPCODES:
            if c0 in "$&*@#'":
                if ":" not in line:
                    errs.append((i, f"declaration '{c0}' lacks ':' type"))
                nm = IDENT_RE.match(line[1:])
                if not nm:
                    errs.append((i, "declaration lacks an identifier"))
                else:
                    declared.add(nm.group(0))
                    used.extend((i, t) for t in IDENT_RE.findall(line[1 + nm.end():]))
            elif c0 == "=":
                nm = IDENT_RE.match(line[1:])
                if not nm:
                    errs.append((i, "def lacks an identifier"))
                else:
                    declared.add(nm.group(0))
                    body = line[1 + nm.end():]
                    if "=" not in body:
                        errs.append((i, "def lacks '=' body"))
                    used.extend((i, t) for t in IDENT_RE.findall(body))
            else:
                used.extend((i, t) for t in IDENT_RE.findall(line[1:]))
            continue
        # bare identifier start => must be a law
        op = None
        for cand in ("::", ":<", ":>"):
            if cand in line:
                op = cand
                break
        if op is None:
            errs.append((i, f"line starts with '{c0}': not an opcode and not a law"))
            continue
        tgt, dist = line.split(op, 1)
        used.extend((i, t) for t in IDENT_RE.findall(tgt))
        dm = re.match(r"\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", dist)
        if not dm:
            errs.append((i, "distribution is not Family(...)"))
            continue
        fam, argtext = dm.group(1), dm.group(2)
        if fam not in B_FAMILIES:
            errs.append((i, f"unknown family code '{fam}'"))
        for a in _split_top(argtext, ","):
            if ":" not in a:
                errs.append((i, f"positional distribution argument '{a.strip()}'"))
            else:
                r, v = a.split(":", 1)
                if r.strip() not in B_ROLES:
                    errs.append((i, f"unknown role code '{r.strip()}'"))
                used.extend((i, t) for t in IDENT_RE.findall(v))
    if concept_open:
        errs.append((len(text.rstrip("\n").split("\n")), "concept never closed by '^^'"))
    known = declared | B_TYPES | B_FAMILIES | B_ROLES | {
        "Ma", "Le", "Ti", "Te", "Cu", "Am", "Lu", "V", "M", "T", "S", "F",
        "K", "X", "D", "U", "R", "p", "e", "v", "m", "a", "d",
    }
    for i, t in used:
        if t not in known:
            errs.append((i, f"undeclared identifier '{t}'"))
    return sorted(set(errs))


C_HEADS = (
    {"module", "var", "param", "const", "obs", "index", "rv", "def", "law",
     "prior", "likelihood", "assume", "require", "minimise", "maximise",
     "solve", "infer", "check", "prove", "concept", "extends", "given",
     "parameter", "property", "transform", "invariant", "example",
     "counterexample", "dim", "call", "forall", "exists", "exists_unique",
     "and", "or", "not", "implies", "iff"}
    | {"+", "-", "*", "/", "@", "^", "=", "!=", "<", "<=", ">", ">="}
    | A_TYPES | DIM_BASES | FAMILIES | ROLES
)


def _c_tokens(text: str) -> list[tuple[str, int]]:
    """(token, line) pairs; ';' comments stripped."""
    out = []
    for i, raw in enumerate(text.split("\n"), 1):
        line = raw.split(";")[0]
        for m in re.finditer(r"\(|\)|[^\s()]+", line):
            out.append((m.group(0), i))
    return out


C_BINDER_HEADS = {"module", "param", "var", "const", "obs", "index", "rv",
                  "def", "concept", "parameter", "property", "transform",
                  "example", "counterexample"}
C_FORMAL_PARENTS = {"def", "transform"}


def check_C(text: str) -> list[tuple[int, str]]:
    errs = _ascii_errors(text)
    toks = _c_tokens(text)
    depth = 0
    last_line = len(text.rstrip("\n").split("\n"))
    declared: set[str] = set()
    used: list[tuple[int, str]] = []
    heads: list[str] = []          # head symbol of each open form ("#list" if anonymous)
    for idx, (t, ln) in enumerate(toks):
        if t == "(":
            depth += 1
            nxt = toks[idx + 1][0] if idx + 1 < len(toks) else None
            if nxt is None:
                errs.append((ln, "'(' at end of input"))
                heads.append("#eof")
            elif nxt == "(" or nxt == ")":
                # anonymous list: legal ONLY as a formal-parameter list of
                # def / transform, i.e. directly inside such a form.
                if not (heads and heads[-1] in C_FORMAL_PARENTS):
                    errs.append((ln, "'(' must be followed by a head symbol"))
                heads.append("#list")
            else:
                heads.append(nxt)
        elif t == ")":
            depth -= 1
            if depth < 0:
                errs.append((ln, "unmatched ')'"))
                depth = 0
            if heads:
                heads.pop()
        else:
            prev = toks[idx - 1][0] if idx else None
            if prev == "(":
                # this is a form head
                parent = heads[-2] if len(heads) >= 2 else None
                if parent == "#list" and len(heads) >= 3 and heads[-3] in C_FORMAL_PARENTS:
                    declared.add(t)          # formal parameter of def / transform
                elif not (t in C_HEADS or re.fullmatch(r"[A-Za-z_]\w*", t)):
                    errs.append((ln, f"'{t}' is not a legal form head"))
            else:
                if re.fullmatch(r"[A-Za-z_]\w*", t):
                    used.append((ln, t))
        # collect binders
        if t in C_BINDER_HEADS and idx + 1 < len(toks):
            nm = toks[idx + 1][0]
            if re.fullmatch(r"[A-Za-z_]\w*", nm):
                declared.add(nm)
        if t in ("forall", "exists", "exists_unique"):
            # (forall (x Real) body)
            if idx + 2 < len(toks) and toks[idx + 1][0] == "(":
                declared.add(toks[idx + 2][0])
    if depth != 0:
        errs.append((last_line, f"{depth} unclosed '(' at end of file"))
    known = declared | C_HEADS | {"true", "false", "posterior", "expectation",
                                  "variance", "mle", "map", "dimension"}
    for ln, t in used:
        if re.fullmatch(r"-?\d+(\.\d+)?", t):
            continue
        if t not in known:
            errs.append((ln, f"undeclared identifier '{t}'"))
    return sorted(set(errs))


D_TOP_KEYS = {"module", "declarations", "definitions", "laws", "assumptions",
              "constraints", "objective", "solve", "infer", "checks",
              "proofs", "concepts"}
D_DECL_KEYS = {"kind", "name", "type", "value"}
D_LAW_KEYS = {"role", "target", "given", "family", "args"}


def check_D(text: str) -> list[tuple[int, str]]:
    errs = _ascii_errors(text)
    for i, ln in enumerate(text.split("\n"), 1):
        stripped = ln.lstrip(" ")
        if ln[: len(ln) - len(stripped)].count("\t"):
            errs.append((i, "tab in indentation (forbidden)"))
    try:
        import yaml  # type: ignore
    except Exception:
        return errs + [(0, "PyYAML unavailable: D cannot be structurally checked")]
    try:
        node = yaml.compose(text)
    except yaml.YAMLError as e:  # type: ignore[attr-defined]
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        line = (mark.line + 1) if mark is not None else 0
        return errs + [(line, f"YAML parse error: {getattr(e, 'problem', e)}")]
    if node is None:
        return errs + [(1, "empty document")]

    import yaml as _y

    def is_map(n):
        return isinstance(n, _y.MappingNode)

    def is_seq(n):
        return isinstance(n, _y.SequenceNode)

    def keys(n):
        return {k.value: (k, v) for k, v in n.value}

    if not is_map(node):
        return errs + [(1, "top level is not a mapping")]
    top = keys(node)
    for k, (kn, _v) in top.items():
        if k not in D_TOP_KEYS:
            errs.append((kn.start_mark.line + 1, f"unknown top-level key '{k}'"))
    if "module" not in top:
        errs.append((1, "missing required 'module' key"))

    # quantifier binders live inside embedded expression strings
    declared: set[str] = set(QUANT_BINDER_A.findall(text))
    used: list[tuple[int, str]] = []

    def scan_expr(s: str, line: int) -> None:
        for t in IDENT_RE.findall(str(s)):
            used.append((line, t))

    if "declarations" in top:
        seq = top["declarations"][1]
        if not is_seq(seq):
            errs.append((top["declarations"][0].start_mark.line + 1,
                         "'declarations' must be a sequence"))
        else:
            for item in seq.value:
                ln = item.start_mark.line + 1
                if not is_map(item):
                    errs.append((ln, "declaration item is not a mapping"))
                    continue
                ik = keys(item)
                for missing in ("kind", "name", "type"):
                    if missing not in ik:
                        errs.append((ln, f"declaration missing '{missing}'"))
                for k, (kn, _v) in ik.items():
                    if k not in D_DECL_KEYS:
                        errs.append((kn.start_mark.line + 1,
                                     f"unknown declaration key '{k}'"))
                if "name" in ik:
                    declared.add(str(ik["name"][1].value))
                if "type" in ik:
                    scan_expr(ik["type"][1].value, ik["type"][1].start_mark.line + 1)

    if "definitions" in top and is_seq(top["definitions"][1]):
        for item in top["definitions"][1].value:
            ln = item.start_mark.line + 1
            if not is_map(item):
                errs.append((ln, "definition item is not a mapping"))
                continue
            ik = keys(item)
            if "name" not in ik:
                errs.append((ln, "definition missing 'name'"))
            else:
                declared.add(str(ik["name"][1].value))
            if "body" not in ik:
                errs.append((ln, "definition missing 'body'"))
            else:
                scan_expr(ik["body"][1].value, ik["body"][1].start_mark.line + 1)
            if "params" in ik and is_seq(ik["params"][1]):
                for p in ik["params"][1].value:
                    declared.add(str(getattr(p, "value", p)))

    if "laws" in top and is_seq(top["laws"][1]):
        for item in top["laws"][1].value:
            ln = item.start_mark.line + 1
            if not is_map(item):
                errs.append((ln, "law item is not a mapping"))
                continue
            ik = keys(item)
            for missing in ("role", "target", "family", "args"):
                if missing not in ik:
                    errs.append((ln, f"law missing '{missing}'"))
            for k, (kn, _v) in ik.items():
                if k not in D_LAW_KEYS:
                    errs.append((kn.start_mark.line + 1, f"unknown law key '{k}'"))
            if "family" in ik and str(ik["family"][1].value) not in FAMILIES:
                errs.append((ik["family"][1].start_mark.line + 1,
                             f"unknown family '{ik['family'][1].value}'"))
            if "args" in ik and is_map(ik["args"][1]):
                for kn, vn in ik["args"][1].value:
                    if kn.value not in ROLES:
                        errs.append((kn.start_mark.line + 1,
                                     f"unknown role '{kn.value}'"))
                    scan_expr(vn.value, vn.start_mark.line + 1)
            if "target" in ik:
                used.append((ik["target"][1].start_mark.line + 1,
                             str(ik["target"][1].value)))

    for sect in ("constraints", "assumptions", "proofs"):
        if sect in top and is_seq(top[sect][1]):
            for item in top[sect][1].value:
                if is_map(item):
                    ik = keys(item)
                    if "holds" in ik:
                        scan_expr(ik["holds"][1].value,
                                  ik["holds"][1].start_mark.line + 1)
                else:
                    scan_expr(item.value, item.start_mark.line + 1)

    if "objective" in top and is_map(top["objective"][1]):
        ik = keys(top["objective"][1])
        for missing in ("direction", "expression"):
            if missing not in ik:
                errs.append((top["objective"][0].start_mark.line + 1,
                             f"objective missing '{missing}'"))
        if "direction" in ik and str(ik["direction"][1].value) not in {
            "minimise", "maximise"
        }:
            errs.append((ik["direction"][1].start_mark.line + 1,
                         "objective direction must be minimise|maximise"))
        if "expression" in ik:
            scan_expr(ik["expression"][1].value,
                      ik["expression"][1].start_mark.line + 1)

    if "solve" in top and is_seq(top["solve"][1]):
        for item in top["solve"][1].value:
            used.append((item.start_mark.line + 1, str(item.value)))

    if "infer" in top and is_map(top["infer"][1]):
        ik = keys(top["infer"][1])
        if "query" not in ik:
            errs.append((top["infer"][0].start_mark.line + 1, "infer missing 'query'"))
        elif str(ik["query"][1].value) not in {"posterior", "expectation",
                                               "variance", "mle", "map"}:
            errs.append((ik["query"][1].start_mark.line + 1, "unknown infer query"))
        if "targets" in ik and is_seq(ik["targets"][1]):
            for item in ik["targets"][1].value:
                used.append((item.start_mark.line + 1, str(item.value)))

    if "checks" in top and is_seq(top["checks"][1]):
        for item in top["checks"][1].value:
            if is_map(item):
                ik = keys(item)
                if "kind" not in ik:
                    errs.append((item.start_mark.line + 1, "check missing 'kind'"))
                if "subject" in ik:
                    scan_expr(ik["subject"][1].value,
                              ik["subject"][1].start_mark.line + 1)

    if "concepts" in top and is_seq(top["concepts"][1]):
        for item in top["concepts"][1].value:
            if not is_map(item):
                continue
            ik = keys(item)
            if "name" in ik:
                declared.add(str(ik["name"][1].value))
            if "parameters" in ik and is_map(ik["parameters"][1]):
                for kn, _vn in ik["parameters"][1].value:
                    declared.add(kn.value)
            if "invariants" not in ik:
                errs.append((item.start_mark.line + 1,
                             "concept declares no invariant"))
            if "examples" not in ik:
                errs.append((item.start_mark.line + 1,
                             "concept declares no example"))
            for sub in ("transforms", "invariants", "examples"):
                if sub in ik and is_seq(ik[sub][1]):
                    for si in ik[sub][1].value:
                        if is_map(si):
                            sk = keys(si)
                            if "name" in sk:
                                declared.add(str(sk["name"][1].value))
                            if "params" in sk and is_seq(sk["params"][1]):
                                for p in sk["params"][1].value:
                                    declared.add(str(p.value))

    # second pass over concept bodies now that names are known
    if "concepts" in top and is_seq(top["concepts"][1]):
        for item in top["concepts"][1].value:
            if not is_map(item):
                continue
            ik = keys(item)
            for sub in ("transforms", "invariants", "examples"):
                if sub in ik and is_seq(ik[sub][1]):
                    for si in ik[sub][1].value:
                        if is_map(si):
                            sk = keys(si)
                            for bk in ("body", "value"):
                                if bk in sk:
                                    scan_expr(sk[bk][1].value,
                                              sk[bk][1].start_mark.line + 1)
                        else:
                            scan_expr(si.value, si.start_mark.line + 1)

    known = (declared | A_TYPES | DIM_BASES | FAMILIES | ROLES | A_OTHER_WORDS
             | {"True", "False", "None"})
    for ln, t in used:
        if re.fullmatch(r"-?\d+(\.\d+)?", str(t)):
            continue
        if t not in known:
            errs.append((ln, f"undeclared identifier '{t}'"))
    return sorted(set(errs))


E_PREDICATES = {
    "is", "inModule", "order", "declKind", "name", "hasType", "hasValue",
    "typeCtor", "typeElement", "typeRows", "typeCols", "typeLength",
    "typeSupport", "dimExponent", "dimBase", "dimPower",
    "lawRole", "lawTarget", "lawGiven", "lawDist", "distFamily", "distArg",
    "argRole", "argValue",
    "op", "lhs", "rhs", "operand", "litValue", "refTo", "callee", "callArg",
    "argIndex", "indexBase", "indexAt",
    "quantKind", "quantVar", "quantBody",
    "asserts", "objDirection", "objExpr", "solveFor", "inferQuery",
    "inferTarget", "checkKind", "checkExpected",
    "extends", "hasMember", "memberKind", "memberParam", "memberBody",
}
E_NODE_VALUED = {
    "inModule", "hasType", "hasValue", "typeElement", "typeSupport",
    "dimExponent", "lawTarget", "lawGiven", "lawDist", "distArg", "argValue",
    "lhs", "rhs", "operand", "refTo", "callArg", "indexBase", "indexAt",
    "quantVar", "quantBody", "asserts", "objExpr", "solveFor", "inferTarget",
    "checkExpected", "extends", "hasMember", "memberParam", "memberBody",
}
E_CLASSES = {
    "Module", "Declaration", "Definition", "Law", "Assumption", "Constraint",
    "Objective", "Solve", "Infer", "Check", "Proof", "Concept",
    "ConceptMember", "Argument", "Literal", "Ref", "BinOp", "UnaryOp",
    "Comparison", "LogicalOp", "Quantifier", "Call", "Index", "DistExpr",
    "Type",
}
NAME_RE = re.compile(r"(?:_:)?[A-Za-z_][A-Za-z0-9_]*$")


def check_E(text: str) -> list[tuple[int, str]]:
    errs = _ascii_errors(text)
    subjects: set[str] = set()
    refs: list[tuple[int, str]] = []
    for i, raw in enumerate(text.split("\n"), 1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 3:
            errs.append((i, f"expected exactly 3 fields, got {len(parts)}"))
            continue
        s, p, o = parts
        if not NAME_RE.fullmatch(s):
            errs.append((i, f"illegal subject '{s}'"))
        if p not in E_PREDICATES:
            errs.append((i, f"unknown predicate '{p}'"))
        subjects.add(s)
        if p == "is" and o not in E_CLASSES:
            errs.append((i, f"unknown node class '{o}'"))
        if p in E_NODE_VALUED:
            if not NAME_RE.fullmatch(o):
                errs.append((i, f"'{p}' requires a node reference, got '{o}'"))
            else:
                refs.append((i, o))
    for i, o in refs:
        if o not in subjects:
            errs.append((i, f"dangling reference to undefined node '{o}'"))
    return sorted(set(errs))


CHECKERS: dict[str, Callable[[str], list[tuple[int, str]]]] = {
    "A": check_A, "B": check_B, "C": check_C, "D": check_D, "E": check_E,
}


# ===========================================================================
# 4. Semantic digests (used to tell "silent but harmless" from
#    "silent and meaning-changing")
# ===========================================================================


def _find_matching(text: str, i: int) -> int:
    """Index of the ')' matching the '(' at index i, or -1."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _canon_dist_args(text: str, arm: str) -> str:
    """Sort role-labelled distribution arguments into role order.

    This is the whole point of D-003: with mandatory role labels the argument
    ORDER carries no meaning, so two spellings that differ only in argument
    order must produce the same digest. Without this normalisation the digest
    would report a meaning change where none exists, and the benchmark would
    credit D-003 for catching an error it did not catch.
    """
    sep = ":=" if arm == "A" else ":"
    out = text
    for m in reversed(list(re.finditer(r"[A-Za-z_]\w*\(", out))):
        op = m.end() - 1
        cl = _find_matching(out, op)
        if cl < 0:
            continue
        inner = out[op + 1 : cl]
        parts = _split_top(inner, ",")
        if len(parts) < 2:
            continue
        roles = []
        for p in parts:
            if sep not in p:
                roles = []
                break
            r = p.split(sep, 1)[0].strip()
            if not re.fullmatch(r"[A-Za-z_]\w*", r):
                roles = []
                break
            roles.append((r, p.strip()))
        if not roles:
            continue
        out = out[: op + 1] + ",".join(p for _r, p in sorted(roles)) + out[cl:]
    return out


def _canon_c_dist_args(text: str) -> str:
    """Sort the (role expr) subforms of every known distribution family in C."""
    out = text
    for m in reversed(list(re.finditer(r"\(\s*(" + "|".join(FAMILIES) + r")\s", out))):
        op = m.start()
        cl = _find_matching(out, op)
        if cl < 0:
            continue
        head_end = m.end()
        body = out[head_end:cl]
        subs, i = [], 0
        ok = True
        while i < len(body):
            if body[i].isspace():
                i += 1
                continue
            if body[i] != "(":
                ok = False
                break
            j = _find_matching(body, i)
            if j < 0:
                ok = False
                break
            subs.append(body[i : j + 1])
            i = j + 1
        if not ok or len(subs) < 2:
            continue
        out = out[:head_end] + " ".join(sorted(subs)) + out[cl:]
    return out


def digest(arm: str, text: str) -> str:
    if arm in {"A", "B", "C"}:
        comment = "#" if arm == "A" else ";"
        code_lines = [ln.split(comment)[0] for ln in text.split("\n")]
        body = "\n".join(code_lines)
        try:
            body = (_canon_c_dist_args(body) if arm == "C"
                    else _canon_dist_args(body, arm))
        except Exception:
            pass
        toks = re.findall(r"[A-Za-z_]\w*|\d+\.\d+|\d+|\S", body)
        return "|".join(toks)
    if arm == "D":
        try:
            import yaml

            return json.dumps(yaml.safe_load(text), sort_keys=True, default=str)
        except Exception:
            return "UNPARSEABLE"
    if arm == "E":
        trs = []
        for ln in text.split("\n"):
            code = ln.split("#")[0].strip()
            if code:
                trs.append(" ".join(code.split()))
        return "\n".join(sorted(trs))
    return text


# ===========================================================================
# 5. Corruptions
# ===========================================================================


def corrupt_delete_char(text: str, rng: random.Random):
    idx = [i for i, c in enumerate(text) if c != "\n"]
    if not idx:
        return None
    i = rng.choice(idx)
    line = text.count("\n", 0, i) + 1
    return text[:i] + text[i + 1:], line


def corrupt_swap_chars(text: str, rng: random.Random):
    idx = [i for i in range(len(text) - 1)
           if text[i] != "\n" and text[i + 1] != "\n" and text[i] != text[i + 1]]
    if not idx:
        return None
    i = rng.choice(idx)
    line = text.count("\n", 0, i) + 1
    return text[:i] + text[i + 1] + text[i] + text[i + 2:], line


def corrupt_dedent_line(text: str, rng: random.Random):
    lines = text.split("\n")
    cands = [i for i, l in enumerate(lines) if l[:1] in (" ", "\t") and l.strip()]
    if not cands:
        return None
    i = rng.choice(cands)
    lines[i] = lines[i].lstrip(" \t")
    return "\n".join(lines), i + 1


def corrupt_delete_closing_bracket(text: str, rng: random.Random):
    idx = [i for i, c in enumerate(text) if c in ")]}"]
    if not idx:
        return None
    i = rng.choice(idx)
    line = text.count("\n", 0, i) + 1
    return text[:i] + text[i + 1:], line


CORRUPTIONS = {
    "delete_char": corrupt_delete_char,
    "swap_adjacent_chars": corrupt_swap_chars,
    "drop_leading_whitespace": corrupt_dedent_line,
    "delete_closing_bracket": corrupt_delete_closing_bracket,
}

TRIALS = 80


def run_edit_robustness(docs: list[Doc]) -> list[dict]:
    rows = []
    for doc in docs:
        if doc.arm not in CHECKERS:
            continue
        check = CHECKERS[doc.arm]
        base_errs = check(doc.text)
        base_digest = digest(doc.arm, doc.text)
        for cname, fn in CORRUPTIONS.items():
            rng = random.Random(hash((doc.arm, doc.problem, cname)) & 0xFFFFFFFF)
            counts = {"LOCAL": 0, "NONLOCAL": 0, "SILENT_MEANING_CHANGE": 0,
                      "SILENT_BENIGN": 0, "NA": 0}
            attempted = 0
            for _ in range(TRIALS):
                res = fn(doc.text, rng)
                if res is None:
                    counts["NA"] = TRIALS
                    break
                new, line = res
                if new == doc.text:
                    continue
                attempted += 1
                errs = [e for e in check(new) if e not in base_errs]
                if errs:
                    if any(e[0] == line for e in errs):
                        counts["LOCAL"] += 1
                    else:
                        counts["NONLOCAL"] += 1
                else:
                    if digest(doc.arm, new) != base_digest:
                        counts["SILENT_MEANING_CHANGE"] += 1
                    else:
                        counts["SILENT_BENIGN"] += 1
            rows.append({
                "arm": doc.arm,
                "problem": doc.problem,
                "corruption": cname,
                "trials": attempted if counts["NA"] == 0 else 0,
                "applicable": counts["NA"] == 0,
                **{k: v for k, v in counts.items() if k != "NA"},
            })
    return rows


# ===========================================================================
# 5b. Deterministic adversarial cases
#
# Random corruption measures resilience to NOISE. It does not measure
# resilience to the specific mistakes a human or a model actually makes.
# These cases are hand-authored, each with a declared expectation, and the
# script reports ACTUAL vs EXPECTED so a wrong expectation is visible.
# ===========================================================================

# (case_id, arm, problem, old_substring, new_substring, intent, expected)
#   expected in {LOCAL, NONLOCAL, SILENT_MEANING_CHANGE, SILENT_BENIGN}
ADVERSARIAL: list[tuple[str, str, str, str, str, str, str]] = [
    # --- D-003: does labelling actually make the argument-order error loud? ---
    ("A-transpose-labelled", "A", "1_normal_distribution",
     "Normal(location := mu, scale := sigma)",
     "Normal(scale := sigma, location := mu)",
     "transpose the two distribution arguments, keeping their role labels",
     "SILENT_BENIGN"),
    ("A-transpose-positional", "A", "1_normal_distribution",
     "Normal(location := mu, scale := sigma)",
     "Normal(sigma, mu)",
     "the same transposition in the POSITIONAL form D-003 forbids",
     "LOCAL"),
    ("A-positional-correct-order", "A", "1_normal_distribution",
     "Normal(location := mu, scale := sigma)",
     "Normal(mu, sigma)",
     "correct positional form; D-003 must still reject it",
     "LOCAL"),
    ("A-sd-vs-variance", "A", "1_normal_distribution",
     "scale := sigma", "variance := sigma",
     "the classic Normal(mu, sigma) vs Normal(mu, sigma^2) confusion, "
     "written explicitly",
     "SILENT_MEANING_CHANGE"),
    ("B-role-code-typo", "B", "1_normal_distribution",
     "N(m:mu,s:sigma)", "N(m:mu,v:sigma)",
     "one-character role-code slip: scale -> variance",
     "SILENT_MEANING_CHANGE"),
    ("B-transpose-positional", "B", "1_normal_distribution",
     "N(m:mu,s:sigma)", "N(sigma,mu)",
     "positional transposition in B",
     "LOCAL"),
    ("C-transpose-labelled", "C", "1_normal_distribution",
     "(Normal (location mu) (scale sigma))",
     "(Normal (scale sigma) (location mu))",
     "transpose role-labelled forms in C",
     "SILENT_BENIGN"),

    # --- whitespace: the canonical candidate-D hazard ---
    ("D-dedent-scale-out-of-args", "D", "1_normal_distribution",
     "    args:\n      location: mu\n      scale: sigma",
     "    args:\n      location: mu\n    scale: sigma",
     "remove 2 spaces so `scale` leaves the args mapping; still valid YAML",
     "LOCAL"),
    ("D-dedent-into-toplevel", "D", "2_bayesian_coin",
     "  targets:\n    - theta", "  targets:\n- theta",
     "dedent a sequence item out of the infer block",
     "LOCAL"),
    ("D-indent-law-into-args", "D", "1_normal_distribution",
     "    family: Normal\n    args:", "    family: Normal\n      args:",
     "over-indent `args` so it is no longer a sibling of `family`",
     "LOCAL"),
    ("A-dedent-concept-member", "A", "7_concept_definition",
     "  invariant scale > 0", "invariant scale > 0",
     "same class of whitespace damage in A: must be a total no-op",
     "SILENT_BENIGN"),
    ("C-dedent", "C", "1_normal_distribution",
     "  (param mu Real)", "(param mu Real)",
     "same class of whitespace damage in C: must be a total no-op",
     "SILENT_BENIGN"),

    # --- bracket damage ---
    ("C-drop-inner-paren", "C", "3_linear_regression",
     "(scale sigma)))", "(scale sigma))",
     "drop one closing paren deep inside a form, two lines before EOF",
     "NONLOCAL"),
    ("A-drop-paren", "A", "1_normal_distribution",
     "scale := sigma)", "scale := sigma",
     "drop the closing paren of a distribution",
     "LOCAL"),
    ("D-drop-type-bracket", "D", "3_linear_regression",
     "type: Matrix[Real, N, P]", "type: Matrix[Real, N, P",
     "drop a bracket inside a D type STRING: invisible to the YAML layer",
     "SILENT_MEANING_CHANGE"),

    # --- quantifier scope ---
    ("A-quantifier-swap", "A", "6_quantifier_scope",
     "forall x : Real . exists y : Real . y > x",
     "exists y : Real . forall x : Real . y > x",
     "silently reverse quantifier order in A",
     "SILENT_MEANING_CHANGE"),
    ("C-quantifier-swap", "C", "6_quantifier_scope",
     "(forall (x Real) (exists (y Real) (> y x)))",
     "(exists (y Real) (forall (x Real) (> y x)))",
     "silently reverse quantifier order in C",
     "SILENT_MEANING_CHANGE"),
    ("E-quantifier-swap", "E", "6_quantifier_scope",
     "_:q1out quantKind forall", "_:q1out quantKind exists",
     "a ONE-LINE edit in E reverses a quantifier; nothing else changes",
     "SILENT_MEANING_CHANGE"),
    ("E-drop-edge", "E", "1_normal_distribution",
     "_:d distArg _:a2\n", "",
     "delete one edge in E: the scale argument simply vanishes",
     "SILENT_MEANING_CHANGE"),
    ("E-dangling-ref", "E", "1_normal_distribution",
     "_:a2 argValue _:v2", "_:a2 argValue _:v9",
     "retarget an edge at an undefined node",
     "LOCAL"),

    # --- name damage ---
    ("A-typo-in-reference", "A", "1_normal_distribution",
     "scale := sigma", "scale := sigmaa",
     "one-character typo in a variable reference",
     "LOCAL"),
    ("B-typo-in-reference", "B", "1_normal_distribution",
     "s:sigma)", "s:sigmaa)",
     "one-character typo in a variable reference",
     "LOCAL"),
    ("D-typo-in-expr-string", "D", "3_linear_regression",
     'location: "x @ beta"', 'location: "x @ betaa"',
     "typo inside a D expression string",
     "LOCAL"),
]


def run_adversarial(docs: list[Doc]) -> list[dict]:
    index = {(d.arm, d.problem): d for d in docs}
    rows = []
    for cid, arm, prob, old, new, intent, expected in ADVERSARIAL:
        d = index[(arm, prob)]
        if old not in d.text:
            rows.append({"case": cid, "arm": arm, "problem": prob,
                         "intent": intent, "expected": expected,
                         "actual": "PATCH_DID_NOT_APPLY", "agrees": False,
                         "first_error": ""})
            continue
        mutated = d.text.replace(old, new, 1)
        check = CHECKERS[arm]
        base = check(d.text)
        errs = [e for e in check(mutated) if e not in base]
        target_line = d.text[: d.text.index(old)].count("\n") + 1
        span = old.count("\n")
        # LOCAL iff an error is reported inside the edited region itself.
        # (Same tight rule as the random-corruption harness, which requires
        # exact line equality. A +-1 window let C's EOF paren error count as
        # local on a 12-line file, which would have flattered C.)
        if errs:
            if any(target_line <= e[0] <= target_line + span for e in errs):
                actual = "LOCAL"
            else:
                actual = "NONLOCAL"
        else:
            actual = ("SILENT_MEANING_CHANGE"
                      if digest(arm, mutated) != digest(arm, d.text)
                      else "SILENT_BENIGN")
        rows.append({
            "case": cid, "arm": arm, "problem": prob, "intent": intent,
            "expected": expected, "actual": actual,
            "agrees": actual == expected,
            "edited_line": target_line,
            "first_error": (f"L{errs[0][0]}: {errs[0][1]}" if errs else ""),
        })
    return rows


# ===========================================================================
# 6. Operator cost
# ===========================================================================

OPERATORS = ["::", ":=", "~", "|", "->", "=>", "<=>", "@", "^",
             ":", ".", ":<", ":>", "(", ")", "[", "]", ",", "#", ";"]


def operator_costs(toks: list[Tok]) -> list[dict]:
    rows = []
    for op in OPERATORS:
        for t in toks:
            standalone = len(t.encode(op))
            spaced = len(t.encode(f"a {op} b")) - len(t.encode("a b"))
            glued = len(t.encode(f"a{op}b")) - len(t.encode("ab"))
            after_ident = len(t.encode(f"sigma{op}")) - len(t.encode("sigma"))
            rows.append({
                "operator": op,
                "tokenizer": t.name,
                "approximate": t.approximate,
                "standalone_tokens": standalone,
                "marginal_tokens_spaced": spaced,
                "marginal_tokens_glued": glued,
                "marginal_after_identifier": after_ident,
            })
    return rows


# ===========================================================================
# 7. Unicode analysis
# ===========================================================================

UNICODE_SYMBOLS = [
    ("FOR ALL", "∀"), ("THERE EXISTS", "∃"), ("ELEMENT OF", "∈"),
    ("RIGHTWARDS ARROW", "→"), ("RIGHTWARDS DOUBLE ARROW", "⇒"),
    ("LEFT RIGHT DOUBLE ARROW", "⇔"),
    ("GREEK SMALL LAMDA", "λ"), ("GREEK SMALL MU", "μ"),
    ("GREEK SMALL SIGMA", "σ"), ("GREEK SMALL THETA", "θ"),
    ("N-ARY SUMMATION", "∑"), ("N-ARY PRODUCT", "∏"),
    ("INTEGRAL", "∫"), ("PARTIAL DIFFERENTIAL", "∂"),
    ("ALMOST EQUAL TO", "≈"),
]

CONFUSABLE_PAIRS = [
    ("μ", "µ", "GREEK SMALL MU vs MICRO SIGN"),
    ("Ω", "Ω", "GREEK CAPITAL OMEGA vs OHM SIGN"),
    ("Å", "Å", "LATIN A WITH RING vs ANGSTROM SIGN"),
    ("Σ", "∑", "GREEK CAPITAL SIGMA vs N-ARY SUMMATION"),
    ("Π", "∏", "GREEK CAPITAL PI vs N-ARY PRODUCT"),
    ("σ", "ς", "GREEK SIGMA vs FINAL SIGMA"),
    ("θ", "ϑ", "GREEK THETA vs THETA SYMBOL"),
    ("ϵ", "∈", "GREEK LUNATE EPSILON vs ELEMENT OF"),
    ("−", "-", "MINUS SIGN vs HYPHEN-MINUS"),
    ("×", "x", "MULTIPLICATION SIGN vs LATIN x"),
    ("∅", "Ø", "EMPTY SET vs LATIN O WITH STROKE"),
    ("Α", "A", "GREEK CAPITAL ALPHA vs LATIN A"),
    ("А", "A", "CYRILLIC A vs LATIN A"),
    ("∂", "д", "PARTIAL DIFFERENTIAL vs CYRILLIC DE"),
    ("′", "'", "PRIME vs APOSTROPHE"),
    ("⁄", "/", "FRACTION SLASH vs SOLIDUS"),
    ("ᴇ", "e", "LATIN LETTER SMALL CAPITAL E vs LATIN e"),
]


def unicode_rows(toks: list[Tok]) -> tuple[list[dict], list[dict]]:
    frag = []
    for label, ch in UNICODE_SYMBOLS:
        base = {
            "symbol": ch,
            "codepoint": f"U+{ord(ch):04X}",
            "name": unicodedata.name(ch, label),
            "utf8_bytes": len(ch.encode("utf-8")),
            "nfc_changes": unicodedata.normalize("NFC", ch) != ch,
            "nfkc_changes": unicodedata.normalize("NFKC", ch) != ch,
            "nfkc_result": "U+" + " U+".join(
                f"{ord(c):04X}" for c in unicodedata.normalize("NFKC", ch)
            ),
        }
        for t in toks:
            base[f"tok:{t.name}"] = len(t.encode(ch))
            base[f"tok_in_ident:{t.name}"] = len(t.encode(f"x{ch}y"))
        frag.append(base)

    conf = []
    for a, b, why in CONFUSABLE_PAIRS:
        na, nb = unicodedata.normalize("NFKC", a), unicodedata.normalize("NFKC", b)
        ca, cb = unicodedata.normalize("NFC", a), unicodedata.normalize("NFC", b)
        row = {
            "a": a, "a_cp": f"U+{ord(a):04X}",
            "a_name": unicodedata.name(a, "?"),
            "b": b, "b_cp": f"U+{ord(b):04X}",
            "b_name": unicodedata.name(b, "?"),
            "why": why,
            "equal_raw": a == b,
            "equal_after_NFC": ca == cb,
            "equal_after_NFKC": na == nb,
            "nfkc_collision": (a != b) and (na == nb),
        }
        for t in toks:
            row[f"tok_a:{t.name}"] = len(t.encode(a))
            row[f"tok_b:{t.name}"] = len(t.encode(b))
            row[f"same_tokens:{t.name}"] = t.encode(a) == t.encode(b)
        conf.append(row)
    return frag, conf


# ===========================================================================
# 8. D-003 cost: role-labelled vs positional distribution arguments
# ===========================================================================

D003_MICRO = [
    ("A", "law X ~ Normal(location := mu, scale := sigma)",
          "law X ~ Normal(mu, sigma)"),
    ("A", "prior theta ~ Beta(alpha := 1, beta := 1)",
          "prior theta ~ Beta(1, 1)"),
    ("A", "likelihood successes | theta ~ Binomial(trials := trials, prob := theta)",
          "likelihood successes | theta ~ Binomial(trials, theta)"),
    ("A", "likelihood y | x, beta, sigma ~ NormalVector(location := x @ beta, scale := sigma)",
          "likelihood y | x, beta, sigma ~ NormalVector(x @ beta, sigma)"),
    ("B", "X::N(m:mu,s:sigma)", "X::N(mu,sigma)"),
    ("B", "theta:<B(a:1,b:1)", "theta:<B(1,1)"),
    ("B", "successes|theta:>Bi(n:trials,p:theta)", "successes|theta:>Bi(trials,theta)"),
    ("B", "y|x,beta,sigma:>NV(m:x@beta,s:sigma)", "y|x,beta,sigma:>NV(x@beta,sigma)"),
    ("C", "(law X (Normal (location mu) (scale sigma)))",
          "(law X (Normal mu sigma))"),
    ("C", "(prior theta (Beta (alpha 1) (beta 1)))", "(prior theta (Beta 1 1))"),
    ("C", "(likelihood successes (given theta) (Binomial (trials trials) (prob theta)))",
          "(likelihood successes (given theta) (Binomial trials theta))"),
    ("C", "(likelihood y (given x beta sigma) (NormalVector (location (@ x beta)) (scale sigma)))",
          "(likelihood y (given x beta sigma) (NormalVector (@ x beta) sigma))"),
    ("D", "    args:\n      location: mu\n      scale: sigma\n",
          "    args: [mu, sigma]\n"),
    ("D", "    args:\n      alpha: \"1\"\n      beta: \"1\"\n",
          "    args: [\"1\", \"1\"]\n"),
    ("E", "_:d distArg _:a1\n_:a1 is Argument\n_:a1 argRole location\n_:a1 argValue _:v1\n",
          "_:d distArg _:a1\n_:a1 is Argument\n_:a1 argIndex 0\n_:a1 argValue _:v1\n"),
    ("E", "_:d distArg _:a2\n_:a2 is Argument\n_:a2 argRole scale\n_:a2 argValue _:v2\n",
          "_:d distArg _:a2\n_:a2 is Argument\n_:a2 argIndex 1\n_:a2 argValue _:v2\n"),
]

# Whole-file strippers. Each returns a text with role labels removed and
# documents its transform.
def strip_roles_A(text: str) -> str:
    def f(m):
        inner = re.sub(r"\b[A-Za-z_]\w*\s*:=\s*", "", m.group(2))
        return f"{m.group(1)}({inner})"
    out = []
    for ln in text.split("\n"):
        s = ln.strip()
        if (s.startswith(("law ", "prior ", "likelihood ")) or " := Normal(" in s
                or re.search(r"~\s*[A-Za-z_]\w*\(", s)):
            ln = re.sub(r"([A-Za-z_]\w*)\(([^()]*)\)", f, ln)
        elif s.startswith("example "):
            ln = re.sub(r"([A-Za-z_]\w*)\(([^()]*)\)", f, ln)
        out.append(ln)
    return "\n".join(out)


def strip_roles_B(text: str) -> str:
    out = []
    for ln in text.split("\n"):
        if re.search(r"(::|:<|:>)", ln) or ln.startswith(".e"):
            def f(m):
                inner = re.sub(r"\b(?:m|s|v|a|b|n|p|r|lo|hi):", "", m.group(2))
                return f"{m.group(1)}({inner})"
            ln = re.sub(r"([A-Za-z_]\w*)\(([^()]*)\)", f, ln)
        out.append(ln)
    return "\n".join(out)


def strip_roles_C(text: str) -> str:
    role_alt = "|".join(sorted(ROLES, key=len, reverse=True))
    prev = None
    while prev != text:
        prev = text
        text = re.sub(rf"\(\s*({role_alt})\s+([^()]*?)\s*\)", r"\2", text)
        text = re.sub(rf"\(\s*({role_alt})\s+(\([^()]*\))\s*\)", r"\2", text)
    return text


def strip_roles_D(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(\s*)args:\s*$", ln)
        if m:
            indent = m.group(1)
            j = i + 1
            vals = []
            while j < len(lines) and lines[j].startswith(indent + "  ") and ":" in lines[j]:
                vals.append(lines[j].split(":", 1)[1].strip())
                j += 1
            out.append(f"{indent}args: [{', '.join(vals)}]")
            i = j
            continue
        out.append(ln)
        i += 1
    return "\n".join(out)


def strip_roles_E(text: str) -> str:
    out, n = [], {}
    for ln in text.split("\n"):
        m = re.match(r"^(\S+) argRole (\S+)\s*$", ln)
        if m:
            subj = m.group(1)
            k = n.get(subj[:4], 0)
            n[subj[:4]] = k + 1
            out.append(f"{subj} argIndex {k}")
        else:
            out.append(ln)
    return "\n".join(out)


STRIPPERS = {"A": strip_roles_A, "B": strip_roles_B, "C": strip_roles_C,
             "D": strip_roles_D, "E": strip_roles_E}
STRIPPER_DOC = {
    "A": "delete '<role> := ' inside every distribution argument list",
    "B": "delete '<rolecode>:' inside every distribution argument list",
    "C": "splice out the (role expr) wrapper form, leaving expr",
    "D": "replace the args: block mapping with a flow sequence of values",
    "E": "replace 'argRole <name>' triples with 'argIndex <n>' triples",
}


# ===========================================================================
# 9. Main
# ===========================================================================


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    toks, avail = build_tokenizers()
    real = [t for t in toks if not t.approximate]
    print(f"tokenizers available: {[t.name for t in toks]}")
    print(f"  real (non-approximate): {len(real)}")
    (out / "tokenizer_availability.json").write_text(
        json.dumps(avail, indent=2), encoding="utf-8"
    )

    docs = load_corpus()
    print(f"corpus: {len(docs)} documents")

    # --- 1..3 corpus metrics -------------------------------------------
    corpus_rows = []
    for d in docs:
        row = {
            "arm": d.arm,
            "problem": d.problem,
            "file": str(d.path.relative_to(REPO)),
            "chars": d.chars,
            "utf8_bytes": d.bytes_utf8,
            "lines": d.lines,
            "content_lines": d.content_lines(COMMENT_PREFIX[d.arm]),
        }
        for t in toks:
            n = len(t.encode(d.text))
            row[f"tokens:{t.name}"] = n
            row[f"frag:{t.name}"] = round(n / d.chars, 5)
        corpus_rows.append(row)
    write_csv(out / "corpus_metrics.csv", corpus_rows)

    # --- 4 operator cost ------------------------------------------------
    op_rows = operator_costs(toks)
    write_csv(out / "operator_cost.csv", op_rows)

    # --- 5 unicode ------------------------------------------------------
    frag_rows, conf_rows = unicode_rows(toks)
    write_csv(out / "unicode_fragmentation.csv", frag_rows)
    write_csv(out / "unicode_confusables.csv", conf_rows)

    # --- 6 edit robustness ---------------------------------------------
    rob_rows = run_edit_robustness(docs)
    write_csv(out / "edit_robustness.csv", rob_rows)

    adv_rows = run_adversarial(docs)
    write_csv(out / "adversarial_cases.csv", adv_rows)

    # --- 7 D-003 --------------------------------------------------------
    d003_micro = []
    for arm, labelled, positional in D003_MICRO:
        for t in toks:
            nl, np_ = len(t.encode(labelled)), len(t.encode(positional))
            d003_micro.append({
                "arm": arm,
                "tokenizer": t.name,
                "approximate": t.approximate,
                "labelled_text": labelled.replace("\n", "\\n"),
                "labelled_tokens": nl,
                "positional_tokens": np_,
                "delta_tokens": nl - np_,
                "pct_overhead": round(100.0 * (nl - np_) / np_, 2) if np_ else None,
            })
    write_csv(out / "d003_micro_cost.csv", d003_micro)

    d003_file = []
    for d in docs:
        if d.arm not in STRIPPERS:
            continue
        stripped = STRIPPERS[d.arm](d.text)
        if stripped == d.text:
            continue
        for t in toks:
            nl, np_ = len(t.encode(d.text)), len(t.encode(stripped))
            d003_file.append({
                "arm": d.arm,
                "problem": d.problem,
                "tokenizer": t.name,
                "approximate": t.approximate,
                "transform": STRIPPER_DOC[d.arm],
                "labelled_tokens": nl,
                "positional_tokens": np_,
                "delta_tokens": nl - np_,
                "pct_overhead": round(100.0 * (nl - np_) / np_, 2) if np_ else None,
                "labelled_chars": len(d.text),
                "positional_chars": len(stripped),
            })
    write_csv(out / "d003_file_cost.csv", d003_file)

    # --- baseline well-formedness of the pristine corpus ----------------
    wf_rows = []
    for d in docs:
        if d.arm not in CHECKERS:
            continue
        e = CHECKERS[d.arm](d.text)
        wf_rows.append({
            "arm": d.arm, "problem": d.problem,
            "errors": len(e),
            "detail": "; ".join(f"L{l}:{m}" for l, m in e[:6]),
        })
    write_csv(out / "baseline_wellformedness.csv", wf_rows)

    # --- summary --------------------------------------------------------
    def agg(arm: str, key: str) -> int:
        return sum(r[key] for r in corpus_rows if r["arm"] == arm)

    summary: dict = {
        "generated_by": "experiments/alphabet/tokenisation_benchmark.py",
        "python": sys.version.split()[0],
        "tokenizers": {
            "real": [t.name for t in real],
            "approximate": [t.name for t in toks if t.approximate],
            "availability": avail,
        },
        "problems": PROBLEMS,
        "per_arm": {},
        "d003": {},
        "edit_robustness": {},
        "unicode": {},
        "baseline_wellformedness_errors": {
            r["arm"]: sum(x["errors"] for x in wf_rows if x["arm"] == r["arm"])
            for r in wf_rows
        },
    }

    for arm in list(CANDIDATES) + list(BASELINES):
        entry = {
            "total_chars": agg(arm, "chars"),
            "total_lines": agg(arm, "lines"),
            "total_content_lines": agg(arm, "content_lines"),
            "tokens": {},
            "fragmentation_tokens_per_char": {},
        }
        for t in toks:
            tot = agg(arm, f"tokens:{t.name}")
            entry["tokens"][t.name] = tot
            entry["fragmentation_tokens_per_char"][t.name] = round(
                tot / entry["total_chars"], 5
            )
        if real:
            entry["mean_tokens_real_tokenizers"] = round(
                sum(entry["tokens"][t.name] for t in real) / len(real), 1
            )
        summary["per_arm"][arm] = entry

    # relative-to-English token cost
    if real:
        eng = summary["per_arm"]["ENG"]["mean_tokens_real_tokenizers"]
        for arm in summary["per_arm"]:
            summary["per_arm"][arm]["tokens_relative_to_english"] = round(
                summary["per_arm"][arm]["mean_tokens_real_tokenizers"] / eng, 3
            )

    for arm in CANDIDATES:
        rows = [r for r in d003_file if r["arm"] == arm and not r["approximate"]]
        if rows:
            summary["d003"][arm] = {
                "whole_file_delta_tokens_total": sum(r["delta_tokens"] for r in rows),
                "whole_file_labelled_tokens_total": sum(r["labelled_tokens"] for r in rows),
                "whole_file_pct_overhead": round(
                    100.0 * sum(r["delta_tokens"] for r in rows)
                    / sum(r["positional_tokens"] for r in rows), 2),
                "transform": STRIPPER_DOC[arm],
                "tokenizers_counted": sorted({r["tokenizer"] for r in rows}),
            }
        micro = [r for r in d003_micro if r["arm"] == arm and not r["approximate"]]
        if micro:
            summary["d003"].setdefault(arm, {})["micro_mean_pct_overhead"] = round(
                sum(r["pct_overhead"] for r in micro) / len(micro), 2
            )
            summary["d003"][arm]["micro_mean_delta_tokens"] = round(
                sum(r["delta_tokens"] for r in micro) / len(micro), 2
            )

    for arm in CANDIDATES:
        rows = [r for r in rob_rows if r["arm"] == arm and r["applicable"]]
        tot = sum(r["trials"] for r in rows)
        if not tot:
            continue
        summary["edit_robustness"][arm] = {
            "total_applicable_trials": tot,
            "local_pct": round(100 * sum(r["LOCAL"] for r in rows) / tot, 2),
            "nonlocal_pct": round(100 * sum(r["NONLOCAL"] for r in rows) / tot, 2),
            "silent_meaning_change_pct": round(
                100 * sum(r["SILENT_MEANING_CHANGE"] for r in rows) / tot, 2),
            "silent_benign_pct": round(
                100 * sum(r["SILENT_BENIGN"] for r in rows) / tot, 2),
            "by_corruption": {
                c: {
                    "trials": sum(r["trials"] for r in rows if r["corruption"] == c),
                    "local_pct": (
                        round(100 * sum(r["LOCAL"] for r in rows if r["corruption"] == c)
                              / max(1, sum(r["trials"] for r in rows
                                           if r["corruption"] == c)), 2)),
                    "silent_meaning_change_pct": (
                        round(100 * sum(r["SILENT_MEANING_CHANGE"] for r in rows
                                        if r["corruption"] == c)
                              / max(1, sum(r["trials"] for r in rows
                                           if r["corruption"] == c)), 2)),
                }
                for c in CORRUPTIONS
                if any(r["corruption"] == c for r in rows)
            },
        }

    summary["adversarial_cases"] = {
        "total": len(adv_rows),
        "expectation_met": sum(1 for r in adv_rows if r["agrees"]),
        "expectation_missed": [
            {"case": r["case"], "expected": r["expected"], "actual": r["actual"],
             "first_error": r.get("first_error", "")}
            for r in adv_rows if not r["agrees"]
        ],
        "by_case": {r["case"]: r["actual"] for r in adv_rows},
    }

    summary["unicode"] = {
        "nfkc_collisions": [
            f"{r['a_cp']} ({r['a_name']}) == {r['b_cp']} ({r['b_name']}) after NFKC"
            for r in conf_rows if r["nfkc_collision"]
        ],
        "identical_token_ids_despite_different_codepoints": {
            t.name: [
                f"{r['a_cp']}/{r['b_cp']}" for r in conf_rows
                if r.get(f"same_tokens:{t.name}") and not r["equal_raw"]
            ]
            for t in toks
        },
        "worst_fragmenting_symbols": {
            t.name: sorted(
                ((r["codepoint"], r[f"tok:{t.name}"]) for r in frag_rows),
                key=lambda kv: -kv[1],
            )[:5]
            for t in toks
        },
        "mean_tokens_per_symbol": {
            t.name: round(sum(r[f"tok:{t.name}"] for r in frag_rows)
                          / len(frag_rows), 2)
            for t in toks
        },
    }

    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # --- console report -------------------------------------------------
    print("\n=== TOKEN TOTALS ACROSS ALL 7 PROBLEMS ===")
    hdr = ["arm", "chars", "lines"] + [t.name for t in toks]
    print(" | ".join(f"{h:>26}" if h.startswith(("tik", "hf", "reg")) else f"{h:>8}"
                     for h in hdr))
    for arm in list(CANDIDATES) + list(BASELINES):
        e = summary["per_arm"][arm]
        cells = [f"{arm:>8}", f"{e['total_chars']:>8}", f"{e['total_lines']:>8}"]
        for t in toks:
            cells.append(f"{e['tokens'][t.name]:>26}")
        print(" | ".join(cells))

    print("\n=== EDIT ROBUSTNESS (all corruptions pooled) ===")
    for arm, e in summary["edit_robustness"].items():
        print(f"  {arm}: trials={e['total_applicable_trials']:>5} "
              f"LOCAL={e['local_pct']:>6}%  NONLOCAL={e['nonlocal_pct']:>6}%  "
              f"SILENT-MEANING-CHANGE={e['silent_meaning_change_pct']:>6}%  "
              f"SILENT-BENIGN={e['silent_benign_pct']:>6}%")

    print("\n=== D-003 ROLE-LABEL OVERHEAD (real tokenizers only) ===")
    for arm, e in summary["d003"].items():
        print(f"  {arm}: whole-file +{e.get('whole_file_delta_tokens_total', 0)} tokens "
              f"({e.get('whole_file_pct_overhead')}%)   "
              f"micro mean +{e.get('micro_mean_delta_tokens')} tok "
              f"({e.get('micro_mean_pct_overhead')}%)")

    print("\n=== DETERMINISTIC ADVERSARIAL CASES ===")
    print(f"  {'case':<30} {'expected':<24} {'actual':<24} ok")
    for r in adv_rows:
        print(f"  {r['case']:<30} {r['expected']:<24} {r['actual']:<24} "
              f"{'OK' if r['agrees'] else 'MISMATCH'}"
              + (f"   [{r['first_error']}]" if r.get("first_error") else ""))
    print(f"  --> {summary['adversarial_cases']['expectation_met']}"
          f"/{len(adv_rows)} matched the stated expectation")

    print("\n=== BASELINE WELL-FORMEDNESS OF THE PRISTINE CORPUS ===")
    for r in wf_rows:
        if r["errors"]:
            print(f"  {r['arm']} {r['problem']}: {r['errors']} -> {r['detail']}")
    if all(r["errors"] == 0 for r in wf_rows):
        print("  all candidate files pass their own checker with 0 errors")

    print(f"\nwrote results to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
