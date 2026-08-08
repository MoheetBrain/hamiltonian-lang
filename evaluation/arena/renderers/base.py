"""Shared rendering machinery and the arm registry.

Everything here exists to stop an arm from winning or losing for a reason that is not
about representation:

- **One numeral format.** HML accepts an integer literal where a `Real` is expected
  (verified against the compiler, not assumed), so every arm writes `4`, not `4.0` in
  one and `4` in another. A notation tax that is really a literal-syntax quirk would
  otherwise show up as a token-count difference.
- **One arithmetic notation.** English and HML both use ordinary infix with standard
  precedence and *minimal* parentheses, computed the same way for both. Rendering one
  arm fully parenthesised and the other not would compare bracket policy.
- **Parenthesise on precedence, never defensively.** The printer inserts a bracket only
  where dropping it would change the parse. It is shared, so neither arm can be quietly
  handicapped.
"""

from __future__ import annotations

from fractions import Fraction

from ..ir import BinOp, Conn, Not, Num, Prop, Term, Var

__all__ = ["fmt_num", "infix_term", "TERM_PREC", "PROP_PREC", "ARMS", "arm"]

#: Higher binds tighter.
TERM_PREC = {"+": 1, "-": 1, "*": 2}
#: Logical precedence, shared by the English and HML printers.
PROP_PREC = {"iff": 1, "implies": 1, "or": 2, "and": 3, "not": 4}


def fmt_num(v: Fraction) -> str:
    """Exact, and identical in every arm."""
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def _term_prec(t: Term) -> int:
    return TERM_PREC[t.op] if isinstance(t, BinOp) else 99


def infix_term(t: Term) -> str:
    """Ordinary infix arithmetic with minimal parentheses.

    ``-`` is left-associative and not commutative, so a right operand of equal
    precedence must be bracketed: ``a - (b - c)`` is not ``a - b - c``.
    """
    match t:
        case Num(value):
            return fmt_num(value)
        case Var(name):
            return name
        case BinOp(op, left, right):
            lp, rp = _term_prec(left), _term_prec(right)
            ls = infix_term(left)
            rs = infix_term(right)
            if lp < TERM_PREC[op]:
                ls = f"({ls})"
            if rp < TERM_PREC[op] or (rp == TERM_PREC[op] and op == "-"):
                rs = f"({rs})"
            return f"{ls} {op} {rs}"
        case _:  # pragma: no cover
            raise TypeError(f"not a term: {t!r}")


def prop_prec(p: Prop) -> int:
    match p:
        case Conn(op, _, _):
            return PROP_PREC[op]
        case Not(_):
            return PROP_PREC["not"]
        case _:
            return 99


def needs_paren(child: Prop, parent_prec: int, *, right_of_same: bool = False) -> bool:
    """Bracket a child only where dropping the bracket would change the parse."""
    cp = prop_prec(child)
    if cp < parent_prec:
        return True
    # `and`/`or` are left-associative in HML, so an equal-precedence right operand
    # needs a bracket to keep the same tree. `implies`/`iff` are right-associative.
    if cp == parent_prec and right_of_same:
        return isinstance(child, Conn) and child.op in ("and", "or")
    return False


#: Registry of arms, populated by the renderer modules at import time.
ARMS: dict[str, object] = {}


def arm(name: str):
    def register(cls):
        ARMS[name] = cls
        cls.ARM = name
        return cls

    return register
