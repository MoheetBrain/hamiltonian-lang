"""`__all__` must name things that exist. Found by Pyright, confirmed at runtime.

`hamiltonian_lang.verification` declared `__all__ = ["obligations"]` without importing
the submodule, so `hasattr(verification, "obligations")` was False, attribute access
raised unless another module had already imported it, and `from ... import *` bound
nothing while appearing to succeed. A stale re-export fails at a consumer, not here,
which is why it survived.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest


@pytest.mark.parametrize(
    "module_name",
    [m.name for m in pkgutil.walk_packages(
        importlib.import_module("hamiltonian_lang").__path__,
        prefix="hamiltonian_lang.")
     if m.ispkg],
)
def test_every_package_exports_what_it_declares(module_name: str):
    module = importlib.import_module(module_name)
    for name in getattr(module, "__all__", ()):
        assert hasattr(module, name), (
            f"{module_name}.__all__ names {name!r}, which does not exist on the module. "
            f"A star-import binds nothing and attribute access raises at the consumer.")


def test_the_verification_obligations_export_is_reachable():
    """The specific defect, pinned directly."""
    from hamiltonian_lang import verification

    assert verification.obligations is not None
    assert "obligations" in verification.__all__
