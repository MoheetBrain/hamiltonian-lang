"""Decoders: one per arm, each reconstructing the world from that arm's rendered text.

**This module is what makes the arena a controlled experiment rather than an assertion.**
"Information-matched" is easy to claim and easy to get wrong -- an arm that quietly omits
a fact, or states a type the others leave implicit, would produce a result that looks
like a representation effect and is really a content difference. So parity is not
asserted here, it is *proved*, per world, by round trip:

    canonical_world(decode_X(render_X(w))) == canonical_world(w)     for every arm X

If any arm drops, adds, reorders into a different tree, or subtly re-associates anything,
the canonical strings diverge and `tests/arena/test_parity.py` fails.

Two consequences worth stating plainly:

- **The English decoder is also an ambiguity proof.** Structured English is only a fair
  baseline if it has exactly one reading. Writing a decoder for it forces that question:
  a phrase form that cannot be parsed deterministically cannot be decoded, and the round
  trip fails. The bracketing forms `both ... and ...`, `either ... or ...`,
  `if ..., then ...` are prefix-marked, which is what makes recursive descent
  deterministic -- the marker announces the structure before the operands arrive.
- **The HML decoder uses HML's own parser.** It does not re-implement HML syntax. A
  private second parser could disagree with the compiler and would then certify a
  rendering the compiler reads differently -- exactly the "authoritative-looking output
  that is wrong" failure CLAUDE.md warns about. This decoder therefore also proves the
  HML arm *means* what the IR means, not merely that it compiles.
"""

from __future__ import annotations

import json
import re
from fractions import Fraction

from .ir import Atom, BinOp, BVar, Cmp, Conn, Elem, Not, Num, Prop, Quant, Rel, Term, Var
from .worlds import ARENA_VERSION, Decl, Fact, Query, Relation, World

__all__ = ["decode_english", "decode_ast", "decode_hml", "DecodeError"]


class DecodeError(RuntimeError):
    """A rendering could not be read back. Always a bug in a renderer or a decoder."""


# ---------------------------------------------------------------------------
# Shared tokenizer
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"\d+/\d+|\d+|[A-Za-z_][A-Za-z0-9_]*|<=|>=|!=|[(),.*+\-/=<>{}|:]")


def _tok(s: str) -> list[str]:
    return _TOKEN.findall(s)


class _Cursor:
    def __init__(self, toks: list[str]) -> None:
        self.t = toks
        self.i = 0

    @property
    def cur(self) -> str:
        return self.t[self.i] if self.i < len(self.t) else ""

    def peek(self, n: int = 1) -> str:
        j = self.i + n
        return self.t[j] if j < len(self.t) else ""

    def next(self) -> str:
        v = self.cur
        self.i += 1
        return v

    def eat(self, *words: str) -> bool:
        """Consume a multi-word phrase if it is next."""
        if self.t[self.i : self.i + len(words)] == list(words):
            self.i += len(words)
            return True
        return False

    def expect(self, word: str) -> None:
        if self.next() != word:
            raise DecodeError(f"expected {word!r} at token {self.i} of {self.t}")

    def at_end(self) -> bool:
        return self.i >= len(self.t)


# ---------------------------------------------------------------------------
# Shared infix-term parsing (English and, via the compiler, HML both use it)
# ---------------------------------------------------------------------------


def _parse_term(c: _Cursor) -> Term:
    return _parse_additive(c)


def _parse_additive(c: _Cursor) -> Term:
    left = _parse_multiplicative(c)
    while c.cur in ("+", "-"):
        op = c.next()
        left = BinOp(op, left, _parse_multiplicative(c))
    return left


def _parse_multiplicative(c: _Cursor) -> Term:
    left = _parse_atom_term(c)
    while c.cur == "*":
        c.next()
        left = BinOp("*", left, _parse_atom_term(c))
    return left


def _parse_atom_term(c: _Cursor) -> Term:
    if c.cur == "(":
        c.next()
        t = _parse_additive(c)
        c.expect(")")
        return t
    tk = c.next()
    if re.fullmatch(r"\d+/\d+|\d+", tk):
        return Num(Fraction(tk))
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tk):
        return Var(tk)
    raise DecodeError(f"not a term atom: {tk!r}")


# ---------------------------------------------------------------------------
# Arm SE
# ---------------------------------------------------------------------------

_CMP = ("=", "<", "<=", ">", ">=")


def _en_prop(c: _Cursor) -> Prop:
    """Recursive descent over the structured-English phrase grammar.

    Deterministic because every branching form is *prefix*-marked. The one infix form,
    `if and only if`, is parsed right-associatively over non-`iff` operands, and the
    renderer never nests an `iff` inside an `iff` without brackets.
    """
    left = _en_prop_nonc(c)
    if c.eat("if", "and", "only", "if"):
        return Conn("iff", left, _en_prop(c))
    return left


def _en_prop_nonc(c: _Cursor) -> Prop:
    if c.eat("both"):
        a = _en_prop_nonc(c)
        c.expect("and")
        return Conn("and", a, _en_prop_nonc(c))
    if c.eat("either"):
        a = _en_prop_nonc(c)
        c.expect("or")
        return Conn("or", a, _en_prop_nonc(c))
    if c.eat("if"):
        a = _en_prop_nonc(c)
        if c.cur == ",":
            c.next()
        c.expect("then")
        return Conn("implies", a, _en_prop_nonc(c))
    if c.eat("it", "is", "not", "the", "case", "that"):
        return Not(_en_prop_nonc(c))
    if c.eat("for", "every"):
        var = c.next()
        c.expect("in")
        dom = c.next()
        if c.cur == ",":
            c.next()
        return Quant("forall", var, dom, _en_prop_nonc(c))
    if c.eat("there", "exists"):
        var = c.next()
        c.expect("in")
        dom = c.next()
        c.eat("such", "that")
        return Quant("exists", var, dom, _en_prop_nonc(c))
    if c.cur == "(":
        c.next()
        p = _en_prop(c)
        c.expect(")")
        return p
    return _en_leaf(c)


def _en_leaf(c: _Cursor) -> Prop:
    start = c.i
    # A relation application: NAME ( args ) holds | does not hold
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", c.cur) and c.peek() == "(":
        name = c.next()
        c.next()
        args: list = []
        while c.cur != ")":
            tk = c.next()
            args.append(Elem(int(tk)) if tk.isdigit() else BVar(tk))
            if c.cur == ",":
                c.next()
        c.expect(")")
        node: Prop = Rel(name, tuple(args))
        if c.eat("does", "not", "hold"):
            return Not(node)
        c.expect("holds")
        return node
    # A bare propositional atom.
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", c.cur) and c.peek() in ("holds", "does"):
        name = c.next()
        if c.eat("does", "not", "hold"):
            return Not(Atom(name))
        c.expect("holds")
        return Atom(name)
    # Otherwise: a comparison between two terms.
    c.i = start
    left = _parse_term(c)
    op = c.next()
    if op not in _CMP:
        raise DecodeError(f"not a comparison operator: {op!r}")
    return Cmp(op, left, _parse_term(c))


def decode_english(state: str, question: str, family: str) -> World:
    lines = [ln.rstrip() for ln in state.splitlines()]
    decls: list[Decl] = []
    facts: list[Fact] = []
    domain: tuple[int, ...] = ()
    relation: Relation | None = None
    rel_name = ""

    section = ""
    pending_pairs = False
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s in ("DECLARATIONS", "FACTS"):
            section = s
            continue
        if section == "DECLARATIONS":
            if m := re.fullmatch(r"(.+) are exact rational numbers\.", s):
                decls = [Decl(n.strip(), "Real") for n in m.group(1).split(",")]
            elif m := re.fullmatch(r"(.+) are propositions\. Each is either true or false\.", s):
                decls = [Decl(n.strip(), "Proposition") for n in m.group(1).split(",")]
            elif m := re.fullmatch(r"D is the set \{(.+)\}\.", s):
                domain = tuple(int(x) for x in m.group(1).split(","))
            elif m := re.fullmatch(r"(\w+) is a binary relation on D\.", s):
                rel_name = m.group(1)
                decls = [Decl(rel_name, "Relation", arity=2)]
            else:
                raise DecodeError(f"unreadable declaration line: {s!r}")
        elif section == "FACTS":
            if s == "All of the following are true.":
                continue
            if pending_pairs:
                pairs = () if s == "(none)" else tuple(
                    tuple(int(x) for x in p.split(","))
                    for p in re.findall(r"\(([^)]*)\)", s)
                )
                relation = Relation(rel_name, 2, domain, pairs)
                pending_pairs = False
                continue
            if "holds for exactly the following" in s:
                pending_pairs = True
                continue
            m = re.fullmatch(r"(f\d+)\. (.+)\.", s)
            if not m:
                raise DecodeError(f"unreadable fact line: {s!r}")
            c = _Cursor(_tok(m.group(2)))
            p = _en_prop(c)
            if not c.at_end():
                raise DecodeError(f"trailing tokens in {s!r}: {c.t[c.i:]}")
            facts.append(Fact(m.group(1), p))

    query = _decode_question_en(question, facts, relation)
    return _assemble(family, decls, facts, domain, relation, query)


def _decode_question_en(question: str, facts, relation) -> Query:
    if m := re.search(r"Determine the exact value of (\w+)\.", question):
        return Query("VALUE", "", ("an exact integer or fraction",), target=m.group(1))
    if m := re.search(r"Is (\w+) necessarily true", question):
        return Query("ENTAILMENT", "", ("TRUE", "FALSE", "UNDETERMINED"), target=m.group(1))
    body = question.split("\n\n", 1)[1].strip()
    c = _Cursor(_tok(body))
    claim = _en_prop(c)
    return Query("TRUTH", "", ("TRUE", "FALSE"), claim=claim)


# ---------------------------------------------------------------------------
# Arm AST
# ---------------------------------------------------------------------------


def _ast_term(node) -> Term:
    if isinstance(node, int):
        return Num(Fraction(node))
    if isinstance(node, str):
        return Var(node)
    if isinstance(node, dict) and "lit" in node:
        return Num(Fraction(node["lit"]))
    if isinstance(node, dict) and "op" in node:
        a, b = node["args"]
        return BinOp(node["op"], _ast_term(a), _ast_term(b))
    raise DecodeError(f"not an AST term: {node!r}")


def _ast_prop(node) -> Prop:
    if isinstance(node, str):
        return Atom(node)
    if isinstance(node, dict) and "bind" in node:
        return Quant(node["bind"], node["var"], node["domain"], _ast_prop(node["body"]))
    if isinstance(node, dict) and "op" in node:
        op, args = node["op"], node["args"]
        if op == "not":
            return Not(_ast_prop(args[0]))
        if op in ("and", "or", "implies", "iff"):
            return Conn(op, _ast_prop(args[0]), _ast_prop(args[1]))
        if op in _CMP:
            return Cmp(op, _ast_term(args[0]), _ast_term(args[1]))
        # Anything else applied to arguments is a relation.
        return Rel(
            op,
            tuple(Elem(a) if isinstance(a, int) else BVar(a) for a in args),
        )
    raise DecodeError(f"not an AST proposition: {node!r}")


def decode_ast(state: str, question: str, family: str) -> World:
    doc = json.loads(state)
    decls: list[Decl] = []
    facts: list[Fact] = []
    domain: tuple[int, ...] = ()
    relation: Relation | None = None
    rel_name = ""

    for d in doc["decls"]:
        if d["sort"] == "set":
            domain = tuple(d["elements"])
        elif d["sort"] == "relation":
            rel_name = d["decl"]
            decls.append(Decl(rel_name, "Relation", arity=d["arity"]))
        else:
            decls.append(Decl(d["decl"], d["sort"]))

    for f in doc["facts"]:
        if "extension_of" in f:
            relation = Relation(
                f["extension_of"], 2, domain,
                tuple(tuple(t) for t in f["holds_exactly_for"]),
            )
        else:
            facts.append(Fact(f["fact"], _ast_prop(f["body"])))

    payload = json.loads(question.split("\n\n", 1)[1].strip())
    if payload["query"] == "value_of":
        query = Query("VALUE", "", ("an exact integer or fraction",), target=payload["target"])
    elif payload["query"] == "entailment":
        query = Query("ENTAILMENT", "", ("TRUE", "FALSE", "UNDETERMINED"), target=payload["target"])
    else:
        query = Query("TRUTH", "", ("TRUE", "FALSE"), claim=_ast_prop(payload["claim"]))
    return _assemble(family, decls, facts, domain, relation, query)


# ---------------------------------------------------------------------------
# Arm HML -- via the compiler's own parser
# ---------------------------------------------------------------------------


def _hml_term(e) -> Term:
    from hamiltonian_lang.ast import nodes as n

    if isinstance(e, n.Literal):
        return Num(Fraction(str(e.raw)))
    if isinstance(e, n.Ref):
        return Var(e.name)
    if isinstance(e, n.BinOp):
        return BinOp(e.op, _hml_term(e.left), _hml_term(e.right))
    raise DecodeError(f"not an HML term: {type(e).__name__}")


def _hml_arg(e):
    from hamiltonian_lang.ast import nodes as n

    if isinstance(e, n.Literal):
        return Elem(int(str(e.raw)))
    if isinstance(e, n.Ref):
        return BVar(e.name)
    raise DecodeError(f"not a relation argument: {type(e).__name__}")


def _hml_prop(e) -> Prop:
    """Map an HML expression back to arena IR, undoing relativised quantification."""
    from hamiltonian_lang.ast import nodes as n

    if isinstance(e, n.Quantifier):
        body = e.body
        # `forall v : Real . v in D implies BODY`  /  `exists v : Real . v in D and BODY`
        guard_op = "implies" if e.kind == "forall" else "and"
        if (
            isinstance(body, n.LogicalOp)
            and body.op == guard_op
            and isinstance(body.left, n.MembershipExpr)
            and isinstance(body.left.element, n.Ref)
            and body.left.element.name == e.var
            and isinstance(body.left.collection, n.Ref)
        ):
            return Quant(e.kind, e.var, body.left.collection.name, _hml_prop(body.right))
        raise DecodeError(
            f"quantifier over {e.var!r} is not in relativised form; the HML renderer "
            f"and this decoder have diverged"
        )
    if isinstance(e, n.LogicalOp):
        return Conn(e.op, _hml_prop(e.left), _hml_prop(e.right))
    if isinstance(e, n.UnaryOp) and e.op == "not":
        return Not(_hml_prop(e.operand))
    if isinstance(e, n.Comparison):
        return Cmp(e.op, _hml_term(e.left), _hml_term(e.right))
    if isinstance(e, n.Call):
        name = e.callee if isinstance(e.callee, str) else getattr(e.callee, "name", None)
        if name is None:
            raise DecodeError("relation application with an unnamed callee")
        return Rel(name, tuple(_hml_arg(a) for a in e.args))
    if isinstance(e, n.Ref):
        return Atom(e.name)
    raise DecodeError(f"not an HML proposition: {type(e).__name__}")


def _hml_extension(body) -> tuple[tuple[int, ...], ...]:
    """Read `(x = 1 and y = 2) or (x = 3 and y = 4)` back into a set of tuples."""
    from hamiltonian_lang.ast import nodes as n

    if isinstance(body, n.Literal) and str(body.raw) == "false":
        return ()
    out: list[tuple[int, ...]] = []

    def disjuncts(e):
        if isinstance(e, n.LogicalOp) and e.op == "or":
            yield from disjuncts(e.left)
            yield from disjuncts(e.right)
        else:
            yield e

    for d in disjuncts(body):
        if not (isinstance(d, n.LogicalOp) and d.op == "and"):
            raise DecodeError("a disjunct of a relation extension is not a conjunction")
        vals = []
        for side in (d.left, d.right):
            if not (isinstance(side, n.Comparison) and side.op == "="):
                raise DecodeError("a conjunct of a relation extension is not an equality")
            vals.append(int(str(side.right.raw)))
        out.append(tuple(vals))
    return tuple(out)


def _hml_domain(pred) -> tuple[int, ...]:
    """Read `{x : Real | x = 1 or x = 2}` back into the element list."""
    from hamiltonian_lang.ast import nodes as n

    def disjuncts(e):
        if isinstance(e, n.LogicalOp) and e.op == "or":
            yield from disjuncts(e.left)
            yield from disjuncts(e.right)
        else:
            yield e

    return tuple(int(str(d.right.raw)) for d in disjuncts(pred))


def decode_hml(state: str, question: str, family: str) -> World:
    from hamiltonian_lang.ast import nodes as n
    from hamiltonian_lang.parser import parse

    # The model-visible state carries no `module` header -- it leaked the contrast operation
    # through `world_id`, so it now lives only in `compilable()`. The compiler still needs
    # one to parse, and this decoder is offline machinery, so a content-free header is
    # supplied here. It is deliberately constant: anything derived from the world would
    # reintroduce exactly the identifier that was removed.
    module, bag = parse(f"module Arena\n\n{state}\n", "<arena>")
    if not bag.ok:
        raise DecodeError(f"HML arm did not parse: {[d.code for d in bag.errors][:3]}")

    decls: list[Decl] = []
    facts: list[Fact] = []
    domain: tuple[int, ...] = ()
    relation: Relation | None = None

    for st in module.statements:
        if isinstance(st, n.Declaration):
            sort = getattr(st.declared_type, "name", None) or type(st.declared_type).__name__
            sort = "Real" if "Real" in str(st.declared_type) else "Proposition"
            decls.append(Decl(st.name, sort))
        elif isinstance(st, n.DefineStmt):
            if st.name == "D":
                domain = _hml_domain(st.body.predicate)
            else:
                relation = Relation(st.name, len(st.params), domain, _hml_extension(st.body))
                decls.append(Decl(st.name, "Relation", arity=len(st.params)))
        elif isinstance(st, n.AssumeStmt):
            facts.append(Fact(st.label, _hml_prop(st.proposition)))

    if relation is not None:
        relation = Relation(relation.name, relation.arity, domain, relation.true_tuples)

    query = _decode_question_hml(question)
    return _assemble(family, decls, facts, domain, relation, query)


def _decode_question_hml(question: str) -> Query:
    from hamiltonian_lang.parser import parse

    if m := re.search(r"Determine the exact value of (\w+)\.", question):
        return Query("VALUE", "", ("an exact integer or fraction",), target=m.group(1))
    if m := re.search(r"Is (\w+) necessarily true", question):
        return Query("ENTAILMENT", "", ("TRUE", "FALSE", "UNDETERMINED"), target=m.group(1))
    goal_line = question.split("\n\n", 1)[1].strip()
    module, bag = parse(f"module Q\n\n{goal_line}\n", "<arena-q>")
    if not bag.ok:
        raise DecodeError(f"HML question did not parse: {[d.code for d in bag.errors][:3]}")
    from hamiltonian_lang.ast import nodes as n

    for st in module.statements:
        if isinstance(st, n.GoalStmt):
            return Query("TRUTH", "", ("TRUE", "FALSE"), claim=_hml_prop(st.proposition))
    raise DecodeError("no goal statement in the HML question")


# ---------------------------------------------------------------------------


def _assemble(family, decls, facts, domain, relation, query) -> World:
    """Rebuild a World for canonical comparison.

    Fields that are bookkeeping rather than content -- seed, level, metrics, the stored
    answer -- are blanked, because they are not part of what a rendering carries and
    comparing them would make parity fail for reasons that have nothing to do with the
    arms.
    """
    return World(
        world_id="",
        family=family,
        version=ARENA_VERSION,
        seed=0,
        level="",
        decls=tuple(decls),
        facts=tuple(facts),
        query=query,
        domain=tuple(domain),
        relation=relation,
        metrics={},
    )
