#!/usr/bin/env python3
"""Regenerate ONTOLOGY_DEPENDENCIES.json deterministically from the ontology JSON.

The dependency relation used for the graph is ``depends_on`` only.
``composes_with`` is a separate, symmetric-in-intent *interaction* relation and is
reported separately: it is deliberately NOT treated as a dependency, because two
atoms that compose with each other would otherwise create spurious cycles.

Computed products
-----------------
adjacency              : atom -> sorted list of atoms it depends on
reverse_adjacency      : atom -> sorted list of atoms that depend on it
roots                  : atoms with no dependencies (graph sources)
leaves                 : atoms nothing depends on (graph sinks)
strongly_connected     : all SCCs of size > 1 (Tarjan); a non-empty list means the
                         ontology contains a definitional cycle and is a defect
topological_layers     : layer 0 = roots; layer k = atoms whose every dependency
                         lies in a strictly lower layer (longest-path layering)
closure_sizes          : |transitive dependency closure| per atom, excluding self
composition_graph      : undirected view of ``composes_with`` with degree counts

Determinism: every list is sorted; the output depends only on the input file.

Usage:
    python3 tools/build_ontology_deps.py
    python3 tools/build_ontology_deps.py --check   # fail if the file is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ONTOLOGY = ROOT / "ontology" / "MATHEMATICAL_REASONING_ONTOLOGY_V1.json"
OUTPUT = ROOT / "ontology" / "ONTOLOGY_DEPENDENCIES.json"


def tarjan_scc(adj: dict[str, list[str]]) -> list[list[str]]:
    """Iterative Tarjan. Returns SCCs, each sorted, list sorted by first member."""
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    result: list[list[str]] = []
    counter = 0

    for root in sorted(adj):
        if root in index_of:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index_of[node] = counter
                low[node] = counter
                counter += 1
                stack.append(node)
                on_stack[node] = True
            recursed = False
            succs = adj[node]
            for i in range(pi, len(succs)):
                succ = succs[i]
                if succ not in index_of:
                    work[-1] = (node, i + 1)
                    work.append((succ, 0))
                    recursed = True
                    break
                if on_stack.get(succ):
                    low[node] = min(low[node], index_of[succ])
            if recursed:
                continue
            if low[node] == index_of[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.append(w)
                    if w == node:
                        break
                result.append(sorted(comp))
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    result.sort(key=lambda c: c[0])
    return result


def longest_path_layers(adj: dict[str, list[str]]) -> dict[str, int]:
    """layer(a) = 0 if a has no deps, else 1 + max(layer(d) for d in deps).

    Requires acyclicity; nodes inside a cycle are assigned -1.
    """
    layer: dict[str, int] = {}
    state: dict[str, int] = {}  # 0 unvisited, 1 in progress, 2 done
    for start in sorted(adj):
        if state.get(start, 0) == 2:
            continue
        stack = [(start, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                deps = adj[node]
                if any(layer.get(d, -1) < 0 for d in deps):
                    layer[node] = -1
                else:
                    layer[node] = 0 if not deps else 1 + max(layer[d] for d in deps)
                state[node] = 2
                continue
            if state.get(node, 0) == 1:
                layer[node] = -1  # cycle member
                state[node] = 2
                continue
            if state.get(node, 0) == 2:
                continue
            state[node] = 1
            stack.append((node, True))
            for dep in adj[node]:
                if state.get(dep, 0) != 2:
                    stack.append((dep, False))
    return layer


def transitive_closure_sizes(adj: dict[str, list[str]]) -> dict[str, int]:
    cache: dict[str, frozenset[str]] = {}

    def closure(node: str, seen: frozenset[str]) -> frozenset[str]:
        if node in cache:
            return cache[node]
        if node in seen:  # cycle guard
            return frozenset()
        acc: set[str] = set()
        for dep in adj[node]:
            acc.add(dep)
            acc |= closure(dep, seen | {node})
        res = frozenset(acc)
        if node not in seen:
            cache[node] = res
        return res

    sys.setrecursionlimit(10000)
    return {n: len(closure(n, frozenset())) for n in sorted(adj)}


def build(doc: dict) -> dict:
    atoms = doc["atoms"]
    ids = sorted(a["id"] for a in atoms)
    domain_of = {a["id"]: a["domain"] for a in atoms}
    crit_of = {a["id"]: a["criticality"] for a in atoms}

    adj = {a["id"]: sorted(a["depends_on"]) for a in atoms}
    radj: dict[str, list[str]] = {i: [] for i in ids}
    for src, deps in adj.items():
        for dep in deps:
            radj[dep].append(src)
    radj = {k: sorted(v) for k, v in sorted(radj.items())}

    sccs = [c for c in tarjan_scc(adj) if len(c) > 1]
    layers = longest_path_layers(adj)
    closures = transitive_closure_sizes(adj)

    roots = sorted(i for i in ids if not adj[i])
    leaves = sorted(i for i in ids if not radj[i])

    layer_index: dict[str, list[str]] = {}
    for atom_id in ids:
        layer_index.setdefault(str(layers[atom_id]), []).append(atom_id)
    layer_index = {k: sorted(v) for k, v in sorted(layer_index.items(), key=lambda kv: int(kv[0]))}

    comp: dict[str, set[str]] = {i: set() for i in ids}
    for a in atoms:
        for other in a["composes_with"]:
            comp[a["id"]].add(other)
            comp[other].add(a["id"])
    comp_sorted = {k: sorted(v) for k, v in sorted(comp.items())}

    cross_domain_edges = sorted(
        {
            f"{domain_of[src]}->{domain_of[dep]}"
            for src, deps in adj.items()
            for dep in deps
            if domain_of[src] != domain_of[dep]
        }
    )

    # Foundational atoms: highest in-degree under the transitive reverse closure.
    dependents_count = {i: 0 for i in ids}
    for i in ids:
        for dep_closure_member in _closure_members(adj, i):
            dependents_count[dep_closure_member] += 1
    most_depended_on = sorted(
        ids, key=lambda i: (-dependents_count[i], i)
    )[:25]

    return {
        "generated_from": ONTOLOGY.name,
        "ontology_version": doc["version"],
        "relation_used_for_graph": "depends_on",
        "notes": [
            "composes_with is reported separately as an undirected interaction "
            "graph; it is not a dependency and is not used for layering.",
            "A non-empty strongly_connected_components list is a defect: the "
            "dependency relation is intended to be a strict partial order.",
            "topological_layers uses longest-path layering, so layer(a) is the "
            "length of the longest dependency chain below a.",
        ],
        "counts": {
            "atoms": len(ids),
            "dependency_edges": sum(len(v) for v in adj.values()),
            "composition_edges_undirected": sum(len(v) for v in comp_sorted.values()) // 2,
            "roots": len(roots),
            "leaves": len(leaves),
            "max_layer": max(layers.values()),
            "cyclic_atoms": sum(1 for v in layers.values() if v < 0),
        },
        "roots": roots,
        "leaves": leaves,
        "strongly_connected_components": sccs,
        "topological_layers": layer_index,
        "layer_of": {i: layers[i] for i in ids},
        "transitive_dependency_closure_size": {i: closures[i] for i in ids},
        "transitive_dependent_count": {i: dependents_count[i] for i in ids},
        "most_depended_on": [
            {
                "id": i,
                "domain": domain_of[i],
                "criticality": crit_of[i],
                "transitive_dependents": dependents_count[i],
            }
            for i in most_depended_on
        ],
        "cross_domain_dependency_edges": cross_domain_edges,
        "adjacency": {i: adj[i] for i in ids},
        "reverse_adjacency": radj,
        "composition_graph": comp_sorted,
    }


_CLOSURE_CACHE: dict[str, frozenset[str]] = {}


def _closure_members(adj: dict[str, list[str]], node: str) -> frozenset[str]:
    if node in _CLOSURE_CACHE:
        return _CLOSURE_CACHE[node]
    acc: set[str] = set()
    stack = list(adj[node])
    seen = set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        acc.add(cur)
        stack.extend(adj.get(cur, []))
    res = frozenset(acc)
    _CLOSURE_CACHE[node] = res
    return res


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    with ONTOLOGY.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    out = build(doc)
    text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            print("ONTOLOGY_DEPENDENCIES.json is stale", file=sys.stderr)
            return 1
        print("OK: dependency file is current")
        return 0

    OUTPUT.write_text(text, encoding="utf-8")
    c = out["counts"]
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(f"  atoms={c['atoms']} dep_edges={c['dependency_edges']} "
          f"comp_edges={c['composition_edges_undirected']}")
    print(f"  roots={c['roots']} leaves={c['leaves']} max_layer={c['max_layer']} "
          f"cyclic_atoms={c['cyclic_atoms']}")
    print(f"  SCCs(size>1)={len(out['strongly_connected_components'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
