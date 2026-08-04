"""Lexer for HML-L1.

Line-oriented, ASCII-canonical. Emits a NEWLINE token at the end of every logical line
so the parser can be a simple statement-per-line recursive-descent parser without
whitespace-sensitive semantics.

Unicode handling (D-002): source is expected to be ASCII. Unicode mathematical
characters in the *identifier* position are folded to their ASCII spelling via
``UNICODE_FOLD`` and reported as a warning, so that a model that emits `μ` still
parses but the canonical form stays ASCII. Any other non-ASCII character is a lexical
error, not a silent pass.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from ..ast.nodes import Span
from ..diagnostics import DiagnosticBag

__all__ = ["TokenKind", "Token", "Lexer", "tokenize", "KEYWORDS", "UNICODE_FOLD"]


class TokenKind(StrEnum):
    IDENT = "ident"
    KEYWORD = "keyword"
    NUMBER = "number"
    OP = "op"
    NEWLINE = "newline"
    EOF = "eof"


KEYWORDS = frozenset(
    {
        # structure
        "module", "concept", "extends", "end",
        # declarations
        "var", "param", "const", "obs", "index", "rv", "def", "fn",
        # probabilistic
        "law", "prior", "likelihood", "infer", "posterior", "expectation",
        "variance", "mle", "map",
        # logical / constraint
        "assume", "require", "prove", "check", "dimension", "solve",
        "minimise", "maximise", "minimize", "maximize",
        # quantifiers and connectives
        "forall", "exists", "unique", "and", "or", "not", "implies", "iff",
        # concept members
        "parameter", "transform", "invariant", "property", "example",
        "counterexample",
        # literals
        "true", "false",
    }
)

# Multi-character operators, longest first so that maximal munch is correct.
_OPERATORS = [
    "<=>", ":=", "->", "=>", "<=", ">=", "!=", "::", "**",
    ":", "~", "|", "@", "^", "+", "-", "*", "/", "=", "<", ">",
    "(", ")", "[", "]", ",", ".",
]

# Greek and mathematical characters that models routinely emit. Folding keeps the
# canonical form ASCII (D-002) instead of admitting confusables into identity.
UNICODE_FOLD = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta",
    "ε": "epsilon", "ζ": "zeta", "η": "eta", "θ": "theta",
    "λ": "lambda", "μ": "mu", "µ": "mu",  # U+00B5 MICRO SIGN
    "ν": "nu", "ξ": "xi", "π": "pi", "ρ": "rho",
    "σ": "sigma", "τ": "tau", "φ": "phi", "χ": "chi",
    "ψ": "psi", "ω": "omega",
    "Γ": "Gamma", "Δ": "Delta", "Θ": "Theta", "Λ": "Lambda",
    "Σ": "Sigma", "Φ": "Phi", "Ω": "Omega",
}

# Unicode operators accepted on input and normalised to their ASCII reserved token.
_UNICODE_OPS = {
    "→": "->", "⇒": "=>", "↔": "<=>", "≤": "<=",
    "≥": ">=", "≠": "!=", "×": "*", "÷": "/",
    "∀": "forall", "∃": "exists", "∼": "~",
}


@dataclass
class Token:
    kind: TokenKind
    value: str
    span: Span

    def is_kw(self, *names: str) -> bool:
        return self.kind is TokenKind.KEYWORD and self.value in names

    def is_op(self, *ops: str) -> bool:
        return self.kind is TokenKind.OP and self.value in ops

    def __repr__(self) -> str:  # pragma: no cover
        return f"Token({self.kind.value}, {self.value!r}, {self.span.line}:{self.span.col})"


class Lexer:
    def __init__(self, source: str, diags: DiagnosticBag, file: str = "<input>") -> None:
        self.src = source
        self.diags = diags
        self.file = file
        self.i = 0
        self.line = 1
        self.col = 0
        self.tokens: list[Token] = []

    # -- helpers ----------------------------------------------------------
    def _here(self, length: int = 1) -> Span:
        return Span(self.line, self.col, self.line, self.col + length, self.file)

    def _peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.src[j] if j < len(self.src) else ""

    def _advance(self, n: int = 1) -> str:
        out = self.src[self.i : self.i + n]
        for ch in out:
            if ch == "\n":
                self.line += 1
                self.col = 0
            else:
                self.col += 1
        self.i += n
        return out

    def _emit(self, kind: TokenKind, value: str, span: Span) -> None:
        self.tokens.append(Token(kind, value, span))

    # -- main -------------------------------------------------------------
    def run(self) -> list[Token]:
        while self.i < len(self.src):
            ch = self._peek()

            if ch == "\n":
                span = self._here()
                self._advance()
                # collapse runs of blank lines into a single NEWLINE
                if self.tokens and self.tokens[-1].kind is not TokenKind.NEWLINE:
                    self._emit(TokenKind.NEWLINE, "\\n", span)
                continue

            if ch in " \t\r":
                self._advance()
                continue

            if ch == "#":
                while self.i < len(self.src) and self._peek() != "\n":
                    self._advance()
                continue

            if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
                self._number()
                continue

            # `str.isalpha()` is true for every Unicode letter, including characters
            # with no ASCII spelling such as U+211D DOUBLE-STRUCK CAPITAL R. Dispatching
            # those into _identifier() used to consume zero characters and loop forever
            # (D-019). The ASCII test must come first.
            if ch.isascii() and (ch.isalpha() or ch == "_"):
                self._identifier()
                continue

            if ch in UNICODE_FOLD:
                self._identifier()
                continue

            if ch in _UNICODE_OPS:
                span = self._here()
                self._advance()
                repl = _UNICODE_OPS[ch]
                self.diags.warn(
                    "HML-L103",
                    f"non-ASCII operator {ch!r} normalised to ASCII {repl!r}",
                    span,
                    notes=["ASCII is the canonical serialization; Unicode is a display layer only"],
                )
                if repl in KEYWORDS:
                    self._emit(TokenKind.KEYWORD, repl, span)
                else:
                    self._emit(TokenKind.OP, repl, span)
                continue

            matched = False
            for op in _OPERATORS:
                if self.src.startswith(op, self.i):
                    span = Span(self.line, self.col, self.line, self.col + len(op), self.file)
                    self._advance(len(op))
                    self._emit(TokenKind.OP, op, span)
                    matched = True
                    break
            if matched:
                continue

            span = self._here()
            bad = self._advance()
            name = unicodedata.name(bad, "unnamed")
            self.diags.error(
                "HML-L101",
                f"unexpected character {bad!r} (U+{ord(bad):04X} {name})",
                span,
                correction="Hamiltonian Lang source is 7-bit ASCII; see docs/design/V0_DESIGN_FREEZE.md section 1",
            )

        if self.tokens and self.tokens[-1].kind is not TokenKind.NEWLINE:
            self._emit(TokenKind.NEWLINE, "\\n", self._here(0))
        self._emit(TokenKind.EOF, "", self._here(0))
        return self.tokens

    def _number(self) -> None:
        start_line, start_col, start_i = self.line, self.col, self.i
        seen_dot = False
        seen_exp = False
        while self.i < len(self.src):
            c = self._peek()
            if c.isdigit():
                self._advance()
            elif c == "." and not seen_dot and not seen_exp:
                seen_dot = True
                self._advance()
            elif c in "eE" and not seen_exp and self._peek(1) and (
                self._peek(1).isdigit() or (self._peek(1) in "+-" and self._peek(2).isdigit())
            ):
                seen_exp = True
                self._advance()
                if self._peek() in "+-":
                    self._advance()
            else:
                break
        raw = self.src[start_i : self.i]
        self._emit(
            TokenKind.NUMBER, raw, Span(start_line, start_col, self.line, self.col, self.file)
        )

    def _identifier(self) -> None:
        start_line, start_col = self.line, self.col
        out: list[str] = []
        folded: list[str] = []
        while self.i < len(self.src):
            c = self._peek()
            if c.isalnum() and c.isascii() or c == "_":
                out.append(self._advance())
            elif c in UNICODE_FOLD:
                self._advance()
                out.append(UNICODE_FOLD[c])
                folded.append(c)
            else:
                break
        span = Span(start_line, start_col, self.line, self.col, self.file)
        name = "".join(out)

        # Belt and braces for D-019: a lexer routine must never consume zero input.
        # If it did, the caller's loop would re-dispatch on the same character forever.
        # The guard is cheap and the failure mode it prevents is unbounded, not merely
        # wrong.
        if not name:
            bad = self._advance()
            if bad:
                self.diags.error(
                    "HML-L101",
                    f"unexpected character {bad!r} "
                    f"(U+{ord(bad):04X} {unicodedata.name(bad, 'unnamed')})",
                    span,
                    correction=(
                        "Hamiltonian Lang source is 7-bit ASCII; see "
                        "docs/design/V0_DESIGN_FREEZE.md section 1"
                    ),
                )
            return

        if folded:
            self.diags.warn(
                "HML-L102",
                f"non-ASCII identifier character(s) {''.join(folded)!r} folded to {name!r}",
                span,
                notes=[
                    "U+00B5 MICRO SIGN and U+03BC GREEK SMALL LETTER MU are visually "
                    "identical and both fold to 'mu'; ASCII spelling is canonical"
                ],
            )
        kind = TokenKind.KEYWORD if name in KEYWORDS else TokenKind.IDENT
        self._emit(kind, name, span)


def tokenize(source: str, diags: DiagnosticBag | None = None, file: str = "<input>"):
    bag = diags if diags is not None else DiagnosticBag(source, file)
    return Lexer(source, bag, file).run(), bag
