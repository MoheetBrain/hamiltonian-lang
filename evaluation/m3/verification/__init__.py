"""M3 verification evaluation: the H3 endpoint, its task subset, and its controls.

Three things live here, and the boundary between them is load-bearing:

:mod:`.task_subset`
    Which problems H3 may be run on at all. A task is admitted only when its expected
    solution is *mechanically* checkable by the implemented subset **and** both arms
    receive it. Narrowing a task set silently is how an experiment stops being able to
    fail; the exclusions are therefore enumerated, counted and reported.

:mod:`.process_metrics`
    Secondary measurements over a reasoning trace — verified-prefix length, first
    failing step, locally discharged fraction, and what a repair did. These describe
    *how* a trajectory failed. They are not the endpoint and cannot substitute for it,
    which is enforced: every metrics record carries the binary verdict alongside.

:mod:`.leakage`
    The four-condition control (A/B/C/D) that separates "the diagnostic helped the model
    reason" from "the diagnostic contained the answer". Without it a positive H3 result
    is unreadable, because the same number is produced by a genuinely useful verifier
    and by one that leaks the target.

Everything here runs **offline**. No module in this package makes a model call; the
arms are supplied as callables, and the fixtures supply scripted responses so the
harness itself can be tested without a server.
"""

from __future__ import annotations

import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

__all__ = ["FIXTURES", "task_subset", "process_metrics", "leakage"]
