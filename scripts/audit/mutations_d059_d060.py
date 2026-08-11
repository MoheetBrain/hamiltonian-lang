"""Mutations for the checks added by D-059 and D-060, plus a disambiguated M049.

New production code with no mutation coverage is the same unverified surface the census
exists to measure. Each entry below removes exactly one of the guards added this session;
if a test suite does not go red, the guard is decorative.

M049 is re-expressed as two entries. The original targeted
``if str(settled.status) != "DISCHARGED":`` when that line occurred once. D-059 added the
goal-side equivalent, so the pattern now matches twice and the harness refuses to apply it
(``BAD_MUTATION``) rather than silently mutating the wrong site. Both sites are given
disambiguating context here so neither loses coverage.

Format: (id, file, old, new, invariant).
"""

MUTATIONS = [
    # -- M049, disambiguated -------------------------------------------------
    (
        "D049a", "verify.py",
        '        if str(settled.status) != "DISCHARGED":\n'
        "            out.append(\n"
        "                Finding(\n"
        '                    "OBLIGATIONS",\n',
        "        if False:\n"
        "            out.append(\n"
        "                Finding(\n"
        '                    "OBLIGATIONS",\n',
        "M049 (obligation site): an obligation claimed discharged may remain OPEN",
    ),
    (
        "D049b", "verify.py",
        '            if str(settled.status) != "DISCHARGED":\n'
        "                out.append(\n"
        "                    Finding(\n"
        '                        "GOAL_DISCHARGE",\n',
        "            if False:\n"
        "                out.append(\n"
        "                    Finding(\n"
        '                        "GOAL_DISCHARGE",\n',
        "D-059a: a declared goal discharge need not leave the goal DISCHARGED",
    ),
    # -- D-059a: the effect must materialise ---------------------------------
    (
        "D059a2", "verify.py",
        "        settled = t.state_after.goals.get(gid) if gid else None\n",
        "        settled = t.state_before.goals.get(gid) if gid else None\n",
        "D-059a: materialisation is checked against the PRIOR state, so it always holds",
    ),
    (
        "D059a3", "verify.py",
        "        elif goal is not None and settled is None:\n",
        "        elif False:\n",
        "D-059a: a declared discharge may delete the goal instead of discharging it",
    ),
    # -- D-059b: the goal status enum ----------------------------------------
    (
        "D059b1", "neutral.py",
        '            status=_enum(raw.get("status", "OPEN"), GoalStatus, f"goal {gid!r} status"),\n',
        '            status=raw.get("status", "OPEN"),\n',
        "D-059b: goal status bypasses the enum validator at the import boundary again",
    ),
    (
        "D059b2", "view.py",
        "                status=_status(f, GoalStatus, GoalStatus.OPEN),\n",
        '                status=_txt(f, "status", "OPEN"),\n',
        "D-059b: the view parser reads a goal status back as unvalidated free text",
    ),
    # -- D-059c: UNKNOWN relevance for goals and obligations -----------------
    (
        "D059c1", "verify.py",
        "        for key, goal in state.goals.items():\n"
        "            if key in want_goals and str(goal.status) == UNKNOWN:\n",
        "        for key, goal in state.goals.items():\n"
        "            if False and key in want_goals and str(goal.status) == UNKNOWN:\n",
        "D-059c: an UNKNOWN goal the action cites no longer makes the transition UNRESOLVED",
    ),
    (
        "D059c2", "verify.py",
        "        for key, obligation in state.obligations.items():\n"
        "            if key in want_obligations and str(obligation.status) == UNKNOWN:\n",
        "        for key, obligation in state.obligations.items():\n"
        "            if False and key in want_obligations and str(obligation.status) == UNKNOWN:\n",
        "D-059c: an UNKNOWN obligation the action discharges is answered INVALID again",
    ),
    (
        "D059c3", "verify.py",
        "    goals = {action.goal_effect.get(\"goal_id\")} - {None}\n",
        "    goals = set()\n",
        "D-059c: goals are dropped from the relevance set, so their UNKNOWNs are ignored",
    ),
    # -- D-060: the obligation discharge evidence seam -----------------------
    (
        "D060a", "verify.py",
        "        record = _evidence(t, eid)\n"
        "        if record is None:\n"
        "            out.append(\n"
        "                Finding(\n"
        '                    "OBLIGATIONS",\n',
        "        record = _evidence(t, eid)\n"
        "        if False:\n"
        "            out.append(\n"
        "                Finding(\n"
        '                    "OBLIGATIONS",\n',
        "D-060: an obligation may be discharged citing evidence that does not exist",
    ),
    (
        "D060b", "verify.py",
        "        ok, why = _accepted(\n"
        "            t, record, cited_as=eid, claim=settled.proposition,\n"
        "            premises=t.action.dependencies,\n"
        "        )\n"
        "        if not ok:\n",
        "        ok, why = _accepted(\n"
        "            t, record, cited_as=eid, claim=settled.proposition,\n"
        "            premises=t.action.dependencies,\n"
        "        )\n"
        "        if False:\n",
        "D-060: discharge evidence need not be accepted at the authority seam (runtime hole)",
    ),
    (
        "D060c", "verify.py",
        "        eid = (entry.get(\"evidence_id\") if isinstance(entry, dict) else None) or (\n"
        "            settled.discharge_evidence_id\n"
        "        )\n",
        "        eid = None\n",
        "D-060: no discharge citation is ever resolved, so the seam is unreachable",
    ),
    (
        "D060d", "verify.py",
        "        eid = (entry.get(\"evidence_id\") if isinstance(entry, dict) else None) or (\n"
        "            settled.discharge_evidence_id\n"
        "        )\n",
        "        eid = entry.get(\"evidence_id\") if isinstance(entry, dict) else None\n",
        "D-060: the obligation record's own discharge_evidence_id is no longer honoured",
    ),
]
