"""Verification services layered *over* the compiler, never inside it.

Nothing in this package modifies ``ast/nodes.py``, ``types.py``, the parser, the
resolver or the type checker. Every checker here reads the output of
:func:`hamiltonian_lang.compile_source` and adds one thing the compiler deliberately
does not do: it **discharges** proof obligations, within an explicitly bounded subset,
and refuses to pretend about the rest.

See :mod:`hamiltonian_lang.verification.obligations` and
``docs/architecture/HML_PROCESS_VERIFICATION.md``.
"""

from __future__ import annotations

# The submodule is imported, not merely named. `__all__ = ["obligations"]` alone was a
# stale re-export: `hasattr(verification, "obligations")` was False, `verification.
# obligations` raised AttributeError unless some other module had already imported it,
# and `from ... import *` silently bound nothing. Found by Pyright
# (reportUnsupportedDunderAll) and confirmed at runtime.
from . import obligations

__all__ = ["obligations"]
